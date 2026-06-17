"""
simulate.py — Test without cameras.
Simulates 4 agents sending fake vehicle counts to the broker.
Run AFTER starting broker.py
"""
import socket, json, time, random, threading
from config import BROKER_HOST, BROKER_PORT

JUNCTIONS = ["A", "B", "C", "D"]

def simulate_junction(jid):
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((BROKER_HOST, BROKER_PORT))
            waiting = 0
            last = 0
            while True:
                vehicles = random.randint(5, 60)
                waiting = waiting + 5 if vehicles >= last else max(0, waiting - 5)
                last = vehicles
                msg = {"junction": jid, "vehicles": vehicles, "waiting_time": waiting, "emergency": False}
                s.sendall(json.dumps(msg).encode())
                print(f"[SIM-{jid}] sent: {msg}")
                time.sleep(5)
        except Exception as e:
            print(f"[SIM-{jid}] error: {e}, retrying...")
            time.sleep(3)

if __name__ == "__main__":
    for jid in JUNCTIONS:
        threading.Thread(target=simulate_junction, args=(jid,), daemon=True).start()
    print("Simulation running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
