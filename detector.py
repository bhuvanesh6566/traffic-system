import cv2
import json
from ultralytics import YOLO

model = YOLO("yolov8n.pt")

# cls_id → (label, BGR color)
CLS_MAP = {
    2:  ("Car",        (255, 140,  0)),
    3:  ("Motorcycle", (0,   200, 255)),
    5:  ("Bus",        (0,   255, 100)),
    7:  ("Truck",      (80,  80,  255)),
    # COCO has no ambulance — we flag bus class as potential emergency placeholder
}
EMPTY_COUNTS = {"Car": 0, "Motorcycle": 0, "Bus": 0, "Truck": 0, "Ambulance": 0}

def _draw_boxes(frame, results):
    counts = dict(EMPTY_COUNTS)
    for box in results.boxes:
        cls = int(box.cls)
        if cls not in CLS_MAP:
            continue
        label, color = CLS_MAP[cls]
        counts[label] += 1
        conf  = float(box.conf)
        x1,y1,x2,y2 = map(int, box.xyxy[0])
        cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
        txt = f"{label} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x1, y1-th-6), (x1+tw+4, y1), color, -1)
        cv2.putText(frame, txt, (x1+2, y1-4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (10,10,10), 1, cv2.LINE_AA)
    return counts


def stream_video(video_path, junction_state: dict, stop_flag: list):
    """
    Streams every frame at the original video FPS regardless of YOLO speed.

    Architecture:
      - Reader thread  : reads frames from disk into a queue at full speed
      - YOLO thread    : pulls frames from reader queue, runs inference,
                         pushes (frame, results) into detect queue
      - Main generator : reads detect queue, draws boxes, paces to src_fps,
                         yields JPEG bytes
    YOLO always runs on a resized copy (416px wide) for speed.
    Bounding box coords are scaled back to original resolution before drawing.
    """
    import time
    import threading
    import queue

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return

    src_fps  = cap.get(cv2.CAP_PROP_FPS) or 25.0
    delay    = 1.0 / src_fps
    # Resize width for YOLO inference (keeps aspect ratio, much faster on CPU)
    INFER_W  = 416

    read_q   = queue.Queue(maxsize=4)   # raw frames
    detect_q = queue.Queue(maxsize=4)   # (annotated_frame, counts, idx)

    # ── Thread 1: read frames ────────────────────────────────────────────────
    def reader():
        i = 0
        while not stop_flag[0]:
            ret, frame = cap.read()
            if not ret:
                read_q.put(None)
                return
            i += 1
            try:
                read_q.put((i, frame), timeout=1)
            except queue.Full:
                pass  # drop frame if pipeline is backed up
        read_q.put(None)

    # ── Thread 2: YOLO inference ─────────────────────────────────────────────
    def detector():
        last_boxes = []   # list of (x1,y1,x2,y2,label,conf,color) in original coords
        last_counts = dict(EMPTY_COUNTS)
        last_counts["total"] = 0

        while not stop_flag[0]:
            item = read_q.get()
            if item is None:
                detect_q.put(None)
                return

            idx, frame = item
            h, w = frame.shape[:2]

            # Resize for inference
            scale   = INFER_W / w
            infer_h = int(h * scale)
            small   = cv2.resize(frame, (INFER_W, infer_h))

            results = model(small, verbose=False)[0]

            counts = dict(EMPTY_COUNTS)
            boxes  = []
            for box in results.boxes:
                cls = int(box.cls)
                if cls not in CLS_MAP:
                    continue
                label, color = CLS_MAP[cls]
                counts[label] += 1
                conf = float(box.conf)
                # Scale coords back to original resolution
                sx1, sy1, sx2, sy2 = box.xyxy[0]
                x1 = int(sx1 / scale)
                y1 = int(sy1 / scale)
                x2 = int(sx2 / scale)
                y2 = int(sy2 / scale)
                boxes.append((x1, y1, x2, y2, label, conf, color))

            counts["total"] = sum(v for k, v in counts.items() if k != "Ambulance")
            last_boxes  = boxes
            last_counts = counts

            # Draw on original-resolution frame
            annotated = frame.copy()
            for (x1, y1, x2, y2, label, conf, color) in last_boxes:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                txt = f"{label} {conf:.2f}"
                (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
                cv2.rectangle(annotated, (x1, y1-th-6), (x1+tw+4, y1), color, -1)
                cv2.putText(annotated, txt, (x1+2, y1-4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (10, 10, 10), 1, cv2.LINE_AA)

            elapsed_sec = idx / src_fps
            overlay = f"Frame {idx}  |  {elapsed_sec:.1f}s  |  {src_fps:.0f} FPS"
            cv2.putText(annotated, overlay, (10, annotated.shape[0]-12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 100, 255), 1, cv2.LINE_AA)
            cv2.circle(annotated, (8, annotated.shape[0]-16), 5, (180, 100, 255), -1)

            try:
                detect_q.put((annotated, last_counts, idx), timeout=1)
            except queue.Full:
                pass

    threading.Thread(target=reader,   daemon=True).start()
    threading.Thread(target=detector, daemon=True).start()

    # ── Main: pace output to src_fps ─────────────────────────────────────────
    while not stop_flag[0]:
        t_start = time.time()

        item = detect_q.get(timeout=5)
        if item is None:
            break

        annotated, counts, idx = item
        junction_state.update(counts)

        ret2, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ret2:
            yield buf.tobytes(), counts, idx

        sleep_t = delay - (time.time() - t_start)
        if sleep_t > 0:
            time.sleep(sleep_t)

    cap.release()


def process_video(video_path, sample_every=30):
    """Non-streaming: return averaged counts (used for final signal computation)."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    totals = {"Car": 0, "Motorcycle": 0, "Bus": 0, "Truck": 0}
    frame_results = []
    idx = 0
    sampled = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % sample_every == 0:
            results = model(frame, verbose=False)[0]
            counts = dict(EMPTY_COUNTS)
            for box in results.boxes:
                cls = int(box.cls)
                if cls in CLS_MAP:
                    counts[CLS_MAP[cls][0]] += 1
            frame_results.append(counts)
            for k in totals:
                totals[k] += counts[k]
            sampled += 1
        idx += 1

    cap.release()

    if sampled == 0:
        return {**EMPTY_COUNTS, "total": 0, "peak": 0}

    avg = {k: round(totals[k] / sampled) for k in totals}
    avg["Ambulance"] = 0
    avg["total"] = sum(avg[k] for k in totals)
    avg["peak"]  = max(sum(f[k] for k in totals) for f in frame_results) if frame_results else 0
    return avg


def get_frame(cap):
    ret, frame = cap.read()
    return frame if ret else None

def open_camera(index=0):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {index}")
    return cap
