"""
Broker - Run ONLY on Laptop 1.
Receives traffic data from all junctions and broadcasts to all.
"""
import socket
import threading
import json
from config import BROKER_PORT

clients = {}
lock = threading.Lock()

def handle_client(conn, addr):
    junction_id = None
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            msg = json.loads(data.decode())
            junction_id = msg.get("junction")

            with lock:
                clients[junction_id] = conn

            # Broadcast to all other connected clients
            broadcast(msg, exclude=junction_id)
            print(f"[Broker] {junction_id}: vehicles={msg.get('vehicles')} wait={msg.get('waiting_time')}s")
    except Exception as e:
        print(f"[Broker] Client error: {e}")
    finally:
        with lock:
            if junction_id and clients.get(junction_id) is conn:
                del clients[junction_id]
        conn.close()

def broadcast(msg, exclude=None):
    dead = []
    with lock:
        targets = {k: v for k, v in clients.items() if k != exclude}
    for jid, conn in targets.items():
        try:
            conn.sendall((json.dumps(msg) + "\n").encode())
        except Exception:
            dead.append(jid)
    with lock:
        for jid in dead:
            clients.pop(jid, None)

def start():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", BROKER_PORT))
    srv.listen(10)
    print(f"[Broker] Listening on port {BROKER_PORT}")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start()
