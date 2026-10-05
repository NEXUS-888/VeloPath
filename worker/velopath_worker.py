# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["ultralytics>=8.3", "torch", "torchvision"]
#
# [tool.uv.sources]
# torch = { index = "pytorch-cu124" }
# torchvision = { index = "pytorch-cu124" }
#
# [[tool.uv.index]]
# name = "pytorch-cu124"
# url = "https://download.pytorch.org/whl/cu124"
# explicit = true
# ///
"""
VeloPath GPU worker: runs the ball model on this laptop's NVIDIA GPU for a VeloPath app elsewhere.

POST /predict?imgsz=640&conf=0.15&classes=1,2   body: JPEG   header: X-VeloPath-Key
    -> {"boxes": [[x1, y1, x2, y2, conf, cls], ...]} in the JPEG's pixels
GET  /health                                    header: X-VeloPath-Key
    -> {"ok": true, "gpu": "...", "names": {...}}

Needs key.txt and the model weights (*.pt) next to this file. Started by start_worker.bat.
"""
import hmac
import json
import os
import socket
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765


def make_server(model, key: str, host: str, port: int, gpu_name: str = "", half: bool = False) -> HTTPServer:
    """One request at a time: the GPU model is not thread-safe and there is one client."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # keep-alive: one connection for a whole clip

        def _reply(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self):
            if hmac.compare_digest(self.headers.get("X-VeloPath-Key", ""), key):
                return True
            self._reply(401, {"error": "bad key"})
            return False

        def do_GET(self):
            if not self._authorized():
                return
            if urlparse(self.path).path != "/health":
                return self._reply(404, {"error": "not found"})
            self._reply(200, {"ok": True, "gpu": gpu_name, "names": {int(k): v for k, v in model.names.items()}})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(length) if 0 < length <= 20_000_000 else b""  # always drain the body
            if not self._authorized():
                return
            url = urlparse(self.path)
            if url.path != "/predict" or not data:
                return self._reply(404 if url.path != "/predict" else 400, {"error": "bad request"})
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return self._reply(400, {"error": "not an image"})
            classes = [int(c) for c in q["classes"].split(",")] if q.get("classes") else None
            kwargs = {"imgsz": int(q.get("imgsz", 640)), "conf": float(q.get("conf", 0.25)), "verbose": False}
            if half:
                kwargs["half"] = True
            boxes = model.predict(img, classes=classes, **kwargs)[0].boxes
            rows = [list(map(float, b)) + [float(c), float(k)]
                    for b, c, k in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist())]
            self._reply(200, {"boxes": rows})

        def log_message(self, *args):  # quiet: one line per frame would flood the window
            pass

    return HTTPServer((host, port), Handler)


def tailscale_ip() -> str:
    """This laptop's Tailscale address (100.64.0.0/10), so only the private Tailscale network can connect."""
    for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
        ip = info[4][0]
        a, b = (int(x) for x in ip.split(".")[:2])
        if a == 100 and 64 <= b <= 127:
            return ip
    return ""


def keep_awake():
    """Stop Windows sleeping while the worker runs; released automatically when it exits."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED


def main():
    import torch
    from ultralytics import YOLO

    key_path = os.path.join(HERE, "key.txt")
    weights = sorted(f for f in os.listdir(HERE) if f.endswith(".pt"))
    if not os.path.exists(key_path) or not weights:
        sys.exit("Missing key.txt or the model .pt file next to this script. Ask for the full worker folder.")
    key = open(key_path, encoding="utf-8").read().strip()
    if not torch.cuda.is_available():
        sys.exit("No NVIDIA GPU visible to PyTorch. Update the NVIDIA driver (nvidia.com/drivers) and retry.")

    gpu = torch.cuda.get_device_name(0)
    model = YOLO(os.path.join(HERE, weights[0]))
    model.to("cuda")
    model.predict(np.zeros((640, 640, 3), np.uint8), imgsz=640, half=True, verbose=False)  # warm up CUDA

    host = tailscale_ip()
    if not host:
        sys.exit("Tailscale is not connected. Open Tailscale, sign in, then run this again.")
    keep_awake()
    print("=" * 60)
    print(f"  VeloPath GPU worker running on {gpu}")
    print(f"  Address: http://{host}:{PORT}")
    print("  Keep this window open. Close it to stop.")
    print("=" * 60)
    make_server(model, key, host, PORT, gpu_name=gpu, half=True).serve_forever()


if __name__ == "__main__":
    main()
