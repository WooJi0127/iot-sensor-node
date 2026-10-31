#!/usr/bin/env python3
"""Standard-library sensor simulation; hardware drivers remain reference stubs."""
import csv
import io
import json
import math
import os
import queue
import random
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PORT = int(os.environ.get("SENSOR_PORT", "8000"))
PUSH_INTERVAL = float(os.environ.get("SENSOR_INTERVAL", "1.0"))
SEED = os.environ.get("SENSOR_SEED")
HISTORY_LEN = 600
SSE_QUEUE_LEN = 32
MAX_SUBSCRIBERS = 32
SSE_HEARTBEAT = 0.5
SSE_WRITE_TIMEOUT = 5.0
FIELDS = ("id", "name", "ts", "temp", "hum", "lux", "anomaly")
NODES = [
    {"id": "node-A", "name": "实验室-01", "base_temp": 24.0, "base_hum": 55.0, "base_lux": 420.0},
    {"id": "node-B", "name": "温室-02", "base_temp": 28.0, "base_hum": 70.0, "base_lux": 800.0},
    {"id": "node-C", "name": "机房-03", "base_temp": 22.0, "base_hum": 45.0, "base_lux": 300.0},
]
_LOCK = threading.Lock()
LATEST = {}
HISTORY = {}
_SUBSCRIBERS = []


def _gen_reading(node, t, rng=None):
    """t is Unix seconds; injected RNG + the same times reproduce frames."""
    rng = random if rng is None else rng
    temp = node["base_temp"] + 1.8 * math.sin(t / 40.0) + rng.gauss(0, 0.35)
    hum = node["base_hum"] + 3.0 * math.cos(t / 55.0) + rng.gauss(0, 1.4)
    lux = max(0.0, node["base_lux"] + 120.0 * math.sin(t / 25.0) + rng.gauss(0, 18.0))
    anomaly = rng.random() < 0.04
    if anomaly:
        temp += rng.uniform(6.0, 12.0)
        hum -= rng.uniform(8.0, 18.0)
    return dict(id=node["id"], name=node["name"], ts=int(t * 1000),
                temp=round(temp, 2), hum=round(max(0.0, hum), 2),
                lux=round(lux, 1), anomaly=anomaly)


def _publish(reading):
    """No network I/O or blocking queue puts in the sampling path."""
    reading = dict(reading)
    payload = f"data: {json.dumps(reading, ensure_ascii=False, allow_nan=False)}\n\n"
    with _LOCK:
        LATEST[reading["id"]] = reading
        HISTORY.setdefault(reading["id"], deque(maxlen=HISTORY_LEN)).append(reading)
        for subscriber in _SUBSCRIBERS:
            try:
                subscriber.put_nowait(payload)
            except queue.Full:
                # Drop oldest: a live dashboard prefers recent readings.
                try:
                    subscriber.get_nowait()
                except queue.Empty:
                    pass
                subscriber.put_nowait(payload)


def _subscribe():
    with _LOCK:
        if len(_SUBSCRIBERS) >= MAX_SUBSCRIBERS:
            return None
        subscriber = queue.Queue(maxsize=SSE_QUEUE_LEN)
        _SUBSCRIBERS.append(subscriber)
        return subscriber


def _history_snapshot():
    with _LOCK:
        return [dict(frame) for node_id in sorted(HISTORY) for frame in HISTORY[node_id]]


def _tick(stop, rng):
    while not stop.is_set():
        t = time.time()
        for node in NODES:
            _publish(_gen_reading(node, t, rng))
        stop.wait(PUSH_INTERVAL)


def _dashboard_html():
    path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")
    with open(path, encoding="utf-8") as source:
        return source.read()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        body = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        if ctype.startswith("text/csv"):
            self.send_header("Content-Disposition", 'attachment; filename="sensor-history.csv"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, _dashboard_html(), "text/html; charset=utf-8")
        elif path == "/stream":
            self._sse_stream()
        elif path == "/latest":
            with _LOCK:
                data = list(LATEST.values())
            self._send(200, json.dumps(data, ensure_ascii=False))
        elif path == "/nodes":
            self._send(200, json.dumps(NODES, ensure_ascii=False))
        elif path in ("/history", "/history.csv"):
            # Each request gets a detached snapshot, consistent under the lock.
            rows = _history_snapshot()
            if path == "/history":
                self._send(200, json.dumps(rows, ensure_ascii=False))
            else:
                output = io.StringIO(newline="")
                writer = csv.DictWriter(output, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(dict(row, anomaly=str(row["anomaly"]).lower()) for row in rows)
                self._send(200, output.getvalue(), "text/csv; charset=utf-8")
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def _sse_stream(self):
        subscriber = _subscribe()
        if subscriber is None:
            self._send(503, json.dumps({"error": "too many stream subscribers"}))
            return
        try:
            self.connection.settimeout(SSE_WRITE_TIMEOUT)
            self.close_connection = True
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            with _LOCK:
                snapshot = list(LATEST.values())
            if snapshot:
                self.wfile.write(f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
            while True:
                try:
                    message = subscriber.get(timeout=SSE_HEARTBEAT).encode("utf-8")
                except queue.Empty:
                    message = b": ping\n\n"
                self.wfile.write(message)
                self.wfile.flush()
        except (OSError, TimeoutError):
            pass
        finally:
            with _LOCK:
                _SUBSCRIBERS.remove(subscriber)

    def log_message(self, *args):
        pass


def main():
    if not math.isfinite(PUSH_INTERVAL) or PUSH_INTERVAL <= 0:
        raise ValueError("SENSOR_INTERVAL must be finite and > 0")
    rng = random.Random(SEED)
    t = time.time()
    for node in NODES:
        _publish(_gen_reading(node, t, rng))
    stop = threading.Event()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    worker = threading.Thread(target=_tick, args=(stop, rng), daemon=True)
    worker.start()
    print(f"[iot-sensor-node] Simulator http://localhost:{PORT}/", flush=True)
    print("  /latest | /nodes | /stream | /history | /history.csv", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stop.set()
        worker.join(2)
        server.server_close()


if __name__ == "__main__":
    main()
