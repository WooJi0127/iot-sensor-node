#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iot-sensor-node · 智慧环境监测终端 · 设备模拟器 + SSE 服务

零外部依赖（仅用 Python 标准库）。
- 模拟多个传感器节点（温度 / 湿度 / 光照）的实时读数
- 通过 SSE（Server-Sent Events）把数据推给浏览器看板
- 通过 /latest 提供最新快照，供 edge-anomaly-llm 项目轮询消费
- 内置「异常注入」，便于演示异常检测与告警

真实硬件对应代码见 ../firmware（STM32 + FreeRTOS + 传感器采集 + MQTT 上报）。
本模拟器用软件复现同样的「采集 → 上报」协议，无需任何硬件即可演示全链路。
"""
import json
import math
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# ----------------------------------------------------------------------------
# 配置
# ----------------------------------------------------------------------------
PORT = int(os.environ.get("SENSOR_PORT", "8000"))
PUSH_INTERVAL = float(os.environ.get("SENSOR_INTERVAL", "1.0"))  # 秒
HISTORY_LEN = 600  # 服务端保留的历史点数（每个节点每类指标）

# 节点定义：模拟分布在不同位置的传感器终端
NODES = [
    {"id": "node-A", "name": "实验室-01", "base_temp": 24.0, "base_hum": 55.0, "base_lux": 420.0},
    {"id": "node-B", "name": "温室-02",   "base_temp": 28.0, "base_hum": 70.0, "base_lux": 800.0},
    {"id": "node-C", "name": "机房-03",   "base_temp": 22.0, "base_hum": 45.0, "base_lux": 300.0},
]

# 线程安全的共享状态
_LOCK = threading.Lock()
LATEST = {}        # node_id -> 最新读数
HISTORY = {}       # node_id -> {"ts":[], "temp":[], "hum":[], "lux":[]}
_SUBSCRIBERS = []  # SSE 连接队列（每项为 queue.Queue）


# ----------------------------------------------------------------------------
# 数据模拟
# ----------------------------------------------------------------------------
def _gen_reading(node, t):
    """生成某节点在时刻 t 的一帧读数（含噪声与周期性变化）。"""
    # 周期性 + 噪声，贴近真实环境曲线
    temp = node["base_temp"] + 1.8 * math.sin(t / 40.0) + random.gauss(0, 0.35)
    hum = node["base_hum"] + 3.0 * math.cos(t / 55.0) + random.gauss(0, 1.4)
    lux = max(0.0, node["base_lux"] + 120.0 * math.sin(t / 25.0) + random.gauss(0, 18.0))

    # 异常注入：约 4% 概率出现一次「温度骤升 + 湿度骤降」的异常
    anomaly = False
    if random.random() < 0.04:
        temp += random.uniform(6.0, 12.0)
        hum -= random.uniform(8.0, 18.0)
        anomaly = True

    return {
        "id": node["id"],
        "name": node["name"],
        "ts": int(t * 1000),
        "temp": round(temp, 2),
        "hum": round(max(0.0, hum), 2),
        "lux": round(lux, 1),
        "anomaly": anomaly,
    }


def _tick():
    """定时生成读数、更新状态、广播给 SSE 订阅者。"""
    while True:
        t = time.time()
        for node in NODES:
            reading = _gen_reading(node, t)
            with _LOCK:
                LATEST[node["id"]] = reading
                hist = HISTORY.setdefault(
                    node["id"], {"ts": [], "temp": [], "hum": [], "lux": []}
                )
                for k in ("ts", "temp", "hum", "lux"):
                    hist[k].append(reading[k])
                # 截断历史
                for k in hist:
                    if len(hist[k]) > HISTORY_LEN:
                        hist[k] = hist[k][-HISTORY_LEN:]
                subscribers = list(_SUBSCRIBERS)
            payload = f"data: {json.dumps(reading, ensure_ascii=False)}\n\n"
            for q in subscribers:
                try:
                    q.put_nowait(payload)
                except Exception:
                    pass
        time.sleep(PUSH_INTERVAL)


# ----------------------------------------------------------------------------
# HTTP / SSE 服务
# ----------------------------------------------------------------------------
def _dashboard_html():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "dashboard", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(200, _dashboard_html(), "text/html; charset=utf-8")
        elif parsed.path == "/stream":
            self._sse_stream()
        elif parsed.path == "/latest":
            with _LOCK:
                data = list(LATEST.values())
            self._send(200, json.dumps(data, ensure_ascii=False))
        elif parsed.path == "/nodes":
            self._send(200, json.dumps(NODES, ensure_ascii=False))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def _sse_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Content-Length", "0")
        self.end_headers()
        import queue
        q = queue.Queue()
        with _LOCK:
            _SUBSCRIBERS.append(q)
        try:
            # 先推一帧当前快照
            with _LOCK:
                snap = list(LATEST.values())
            if snap:
                self.wfile.write(
                    f"data: {json.dumps(snap, ensure_ascii=False)}\n\n".encode("utf-8")
                )
                self.wfile.flush()
            while True:
                try:
                    msg = q.get(timeout=30)
                except Exception:
                    # 心跳，保活
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                self.wfile.write(msg.encode("utf-8"))
                self.wfile.flush()
        except Exception:
            pass
        finally:
            with _LOCK:
                if q in _SUBSCRIBERS:
                    _SUBSCRIBERS.remove(q)

    def log_message(self, *args):
        pass  # 静默


def main():
    # 预填一帧，避免看板/检测器首帧为空
    t = time.time()
    for node in NODES:
        with _LOCK:
            LATEST[node["id"]] = _gen_reading(node, t)

    threading.Thread(target=_tick, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[iot-sensor-node] 模拟器已启动")
    print(f"  看板:    http://localhost:{PORT}/")
    print(f"  数据流:  http://localhost:{PORT}/stream  (SSE)")
    print(f"  快照:    http://localhost:{PORT}/latest  (JSON, 供 edge-anomaly-llm 消费)")
    print(f"  节点:    http://localhost:{PORT}/nodes")
    print("  按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
