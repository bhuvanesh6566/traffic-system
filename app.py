"""
app.py  —  Main entry point.
Run: python app.py
Open: http://localhost:5000
"""
import os, json, threading
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from werkzeug.utils import secure_filename
from detector import process_video, stream_video

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXT   = {"mp4", "avi", "mov", "mkv", "wmv"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"]        = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"]   = 500 * 1024 * 1024

JUNCTIONS = ["A", "B", "C", "D"]

# ── State ─────────────────────────────────────────────────────────────────────
junction_data = {}   # jid → full result dict
live_counts   = {}   # jid → live per-frame counts during streaming
stop_flags    = {}   # jid → [bool]
lock          = threading.Lock()

# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def compute_signals(data):
    scores = {
        jid: (d["vehicles"] * 0.6) + (d.get("waiting_time", 0) * 0.3)
        for jid, d in data.items()
    }
    total = sum(scores.values()) or 1
    top   = max(scores, key=scores.get)
    return {
        jid: {
            "green_time": max(10, round(90 * scores[jid] / total)),
            "is_green":   jid == top,
            "score":      round(scores[jid], 2),
        }
        for jid in scores
    }

def refresh_signals():
    with lock:
        ready = {jid: d for jid, d in junction_data.items() if d["status"] == "done"}
    if not ready:
        return
    sigs = compute_signals(ready)
    with lock:
        for jid, sig in sigs.items():
            junction_data[jid].update(sig)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload/<junction>", methods=["POST"])
def upload(junction):
    if junction not in JUNCTIONS:
        return jsonify({"error": "Invalid junction"}), 400
    if "video" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["video"]
    if not f.filename or not allowed(f.filename):
        return jsonify({"error": "Invalid file type"}), 400

    filename  = secure_filename(f.filename)
    save_path = os.path.join(UPLOAD_FOLDER, f"junction_{junction}_{filename}")
    f.save(save_path)

    with lock:
        # Stop any previous stream for this junction
        if junction in stop_flags:
            stop_flags[junction][0] = True
        stop_flags[junction] = [False]
        live_counts[junction] = {"Car":0,"Motorcycle":0,"Bus":0,"Truck":0,"Ambulance":0,"total":0}
        junction_data[junction] = {
            "status": "processing", "vehicles": 0, "waiting_time": 0,
            "green_time": 0, "is_green": False, "score": 0,
            "counts": {}, "filename": filename, "video_path": save_path,
        }

    threading.Thread(target=bg_process, args=(junction, save_path), daemon=True).start()
    return jsonify({"message": f"Junction {junction} uploaded, processing..."})

def bg_process(junction, video_path):
    try:
        counts = process_video(video_path)
        total  = counts["total"]
        with lock:
            junction_data[junction].update({
                "status": "done", "vehicles": total,
                "waiting_time": total * 2, "counts": counts,
            })
        refresh_signals()
    except Exception as e:
        with lock:
            junction_data[junction]["status"] = f"error: {e}"

# ── MJPEG live stream ─────────────────────────────────────────────────────────

@app.route("/stream/<junction>")
def stream(junction):
    with lock:
        d = junction_data.get(junction)
    if not d:
        return "No video uploaded", 404

    video_path = d.get("video_path")
    if not video_path or not os.path.exists(video_path):
        return "Video file missing", 404

    # Reset stop flag for a fresh stream
    with lock:
        stop_flags[junction] = [False]
        live_counts[junction] = {"Car":0,"Motorcycle":0,"Bus":0,"Truck":0,"Ambulance":0,"total":0}

    def generate():
        sf = stop_flags[junction]
        lc = live_counts[junction]
        for jpeg, counts, _ in stream_video(video_path, lc, sf):
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")

    return Response(stream_with_context(generate()),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/stop/<junction>", methods=["POST"])
def stop_stream(junction):
    with lock:
        if junction in stop_flags:
            stop_flags[junction][0] = True
    return jsonify({"message": "Stopped"})

# ── SSE: live counts while streaming ─────────────────────────────────────────

@app.route("/events/<junction>")
def events(junction):
    def generate():
        import time
        while True:
            with lock:
                data = dict(live_counts.get(junction, {}))
                jd   = dict(junction_data.get(junction, {}))
            data["green_time"] = jd.get("green_time", 0)
            data["is_green"]   = jd.get("is_green", False)
            data["score"]      = jd.get("score", 0)
            data["status"]     = jd.get("status", "idle")
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.5)
    return Response(stream_with_context(generate()), mimetype="text/event-stream")

# ── Global state / reset ──────────────────────────────────────────────────────

@app.route("/api/state")
def api_state():
    with lock:
        return jsonify(dict(junction_data))

@app.route("/api/reset", methods=["POST"])
def reset():
    with lock:
        for sf in stop_flags.values():
            sf[0] = True
        junction_data.clear()
        live_counts.clear()
        stop_flags.clear()
    return jsonify({"message": "Reset OK"})

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
