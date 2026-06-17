"""
Agent - Run on EVERY laptop (A, B, C, D).
Set JUNCTION_ID in config.py before running.
"""
import socket
import threading
import json
import time
from detector import open_camera, get_frame, count_vehicles
from config import JUNCTION_ID, BROKER_HOST, BROKER_PORT, CAMERA_INDEX

# Shared state: latest data from all junctions including self
traffic_state = {}
state_lock = threading.Lock()

# ── Timing ───────────────────────────────────────────────────────────────────

def compute_green_time(vehicles, waiting_time=0, emergency=False):
    score = (vehicles * 0.6) + (waiting_time * 0.3) + (10 if emergency else 0)
    return round(15 + score * 0.5)

def decide_signals():
    """Returns dict of junction → green_time, sorted by priority score."""
    with state_lock:
        snapshot = dict(traffic_state)
    if not snapshot:
        return {}
    scores = {
        jid: (d["vehicles"] * 0.6) + (d.get("waiting_time", 0) * 0.3) + (10 if d.get("emergency") else 0)
        for jid, d in snapshot.items()
    }
    # Proportional green time: share 90 total seconds across junctions
    total_score = sum(scores.values()) or 1
    return {
        jid: max(10, round(90 * scores[jid] / total_score))
        for jid in scores
    }

# ── Network ───────────────────────────────────────────────────────────────────

def connect_to_broker():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((BROKER_HOST, BROKER_PORT))
            print(f"[{JUNCTION_ID}] Connected to broker")
            return s
        except Exception:
            print(f"[{JUNCTION_ID}] Broker unreachable, retrying in 3s...")
            time.sleep(3)

def listen_for_updates(sock):
    buf = ""
    while True:
        try:
            chunk = sock.recv(4096).decode()
            if not chunk:
                break
            buf += chunk
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if line.strip():
                    msg = json.loads(line)
                    with state_lock:
                        traffic_state[msg["junction"]] = msg
        except Exception as e:
            print(f"[{JUNCTION_ID}] Receive error: {e}")
            break

# ── Main loop ─────────────────────────────────────────────────────────────────

def run():
    cap = open_camera(CAMERA_INDEX)
    sock = connect_to_broker()
    threading.Thread(target=listen_for_updates, args=(sock,), daemon=True).start()

    waiting_time = 0
    last_count = 0

    while True:
        frame = get_frame(cap)
        if frame is None:
            time.sleep(1)
            continue

        vehicles = count_vehicles(frame)
        waiting_time = waiting_time + 5 if vehicles >= last_count else max(0, waiting_time - 5)
        last_count = vehicles

        payload = {
            "junction": JUNCTION_ID,
            "vehicles": vehicles,
            "waiting_time": waiting_time,
            "emergency": False,
            "timestamp": time.time()
        }

        with state_lock:
            traffic_state[JUNCTION_ID] = payload

        try:
            sock.sendall(json.dumps(payload).encode())
        except Exception:
            print(f"[{JUNCTION_ID}] Lost connection, reconnecting...")
            sock = connect_to_broker()
            threading.Thread(target=listen_for_updates, args=(sock,), daemon=True).start()

        signals = decide_signals()
        my_green = signals.get(JUNCTION_ID, 15)
        print(f"[{JUNCTION_ID}] vehicles={vehicles} wait={waiting_time}s | my green={my_green}s | network={signals}")

        time.sleep(5)

if __name__ == "__main__":
    run()
