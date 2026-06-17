"""
Dashboard - Run on Laptop 1 alongside broker.
Visit http://localhost:5000
"""
from flask import Flask, jsonify, render_template_string
import json, socket, threading, time
from config import BROKER_PORT

app = Flask(__name__)
traffic_state = {}
state_lock = threading.Lock()

HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Traffic Dashboard</title>
  <meta http-equiv="refresh" content="3">
  <style>
    body { font-family: Arial, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
    h1 { color: #e94560; }
    table { border-collapse: collapse; width: 100%; max-width: 700px; }
    th, td { padding: 12px 20px; border: 1px solid #444; text-align: center; }
    th { background: #16213e; color: #e94560; }
    tr:nth-child(even) { background: #0f3460; }
    .green { color: #00ff88; font-weight: bold; }
    .red   { color: #ff4444; font-weight: bold; }
  </style>
</head>
<body>
  <h1>🚦 Smart Traffic Control</h1>
  <table>
    <tr><th>Junction</th><th>Vehicles</th><th>Waiting (s)</th><th>Green Time (s)</th><th>Signal</th></tr>
    {% for j, d in data.items() | sort %}
    <tr>
      <td>{{ j }}</td>
      <td>{{ d.vehicles }}</td>
      <td>{{ d.waiting_time }}</td>
      <td>{{ d.green_time }}</td>
      <td class="{{ 'green' if d.is_green else 'red' }}">{{ '🟢 GREEN' if d.is_green else '🔴 RED' }}</td>
    </tr>
    {% endfor %}
  </table>
  <p style="color:#888; font-size:12px">Auto-refreshes every 3 seconds</p>
</body>
</html>
"""

def compute_signals(state):
    if not state:
        return {}
    scores = {
        jid: (d["vehicles"] * 0.6) + (d.get("waiting_time", 0) * 0.3) + (10 if d.get("emergency") else 0)
        for jid, d in state.items()
    }
    total = sum(scores.values()) or 1
    green_times = {jid: max(10, round(90 * scores[jid] / total)) for jid in scores}
    top = max(scores, key=scores.get)
    return {jid: {"green_time": green_times[jid], "is_green": jid == top} for jid in scores}

@app.route("/")
def index():
    with state_lock:
        snapshot = dict(traffic_state)
    signals = compute_signals(snapshot)
    data = {
        jid: {**snapshot[jid], **signals.get(jid, {"green_time": 15, "is_green": False})}
        for jid in snapshot
    }
    return render_template_string(HTML, data=data)

@app.route("/api/state")
def api_state():
    with state_lock:
        snapshot = dict(traffic_state)
    signals = compute_signals(snapshot)
    return jsonify({jid: {**snapshot[jid], **signals.get(jid, {})} for jid in snapshot})

# Listen on broker port to sniff traffic (passive observer)
def sniff_broker():
    """Acts as a regular client that connects to the broker to receive updates."""
    time.sleep(2)
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", BROKER_PORT))
            # Register as dashboard observer
            s.sendall(json.dumps({"junction": "DASHBOARD", "vehicles": 0, "waiting_time": 0}).encode())
            buf = ""
            while True:
                chunk = s.recv(4096).decode()
                if not chunk:
                    break
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            if msg.get("junction") not in (None, "DASHBOARD"):
                                with state_lock:
                                    traffic_state[msg["junction"]] = msg
                        except Exception:
                            pass
        except Exception:
            time.sleep(3)

if __name__ == "__main__":
    threading.Thread(target=sniff_broker, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
