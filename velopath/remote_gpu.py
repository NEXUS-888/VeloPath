"""
Run the ball model on a friend's GPU (worker/velopath_worker.py) instead of this CPU.
RemoteYolo answers the same predict() calls the tracker makes on a local YOLO; if the worker
stops answering, it uses the local model and retries the worker 30s later.
Config: gpu_worker.json in the project root, {"url": "http://100.x.y.z:8765", "key": "..."}.
"""
import http.client
import json
import os
import time
from typing import Optional
from urllib.parse import urlencode, urlparse

import cv2
import numpy as np

RETRY_AFTER_S = 30.0


class _Boxes:
    def __init__(self, rows):
        rows = np.asarray(rows, dtype=float).reshape(-1, 6)
        self.xyxy, self.conf, self.cls = rows[:, :4], rows[:, 4], rows[:, 5]


class _Result:
    def __init__(self, rows):
        self.boxes = _Boxes(rows)


class RemoteYolo:
    def __init__(self, url: str, key: str, fallback=None, timeout: float = 5.0):
        self.url, self.key, self.fallback, self.timeout = url.rstrip("/"), key, fallback, timeout
        self._conn, self._down_until = None, 0.0
        health = self._request("GET", "/health")  # raises if unreachable or the key is wrong
        self.gpu_name = health.get("gpu", "")
        self.names = {int(k): v for k, v in health["names"].items()}

    @property
    def using_fallback(self) -> bool:
        return time.monotonic() < self._down_until

    def _request(self, method: str, path: str, body: Optional[bytes] = None) -> dict:
        u = urlparse(self.url)
        if self._conn is None or (self._conn.host, self._conn.port) != (u.hostname, u.port or 80):
            self._conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=self.timeout)
        try:
            self._conn.request(method, path, body=body, headers={"X-VeloPath-Key": self.key})
            resp = self._conn.getresponse()
            data = json.loads(resp.read() or b"{}")
        except Exception:
            self._conn.close()
            self._conn = None
            raise
        if resp.status == 401:
            raise PermissionError("GPU worker rejected the key (check gpu_worker.json and the worker's key.txt)")
        if resp.status != 200:
            raise RuntimeError(f"GPU worker error {resp.status}: {data}")
        return data

    def predict(self, img, imgsz: int = 640, conf: float = 0.25, classes=None, **kw):
        if not self.using_fallback:
            try:
                # YOLO shrinks the image to imgsz anyway: shrink before the trip so less goes over the network
                scale = min(1.0, imgsz / float(max(img.shape[:2])))
                small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else img
                jpg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes()
                q = {"imgsz": imgsz, "conf": conf}
                if classes is not None:
                    q["classes"] = ",".join(str(int(c)) for c in classes)
                rows = np.asarray(self._request("POST", "/predict?" + urlencode(q), jpg)["boxes"], dtype=float).reshape(-1, 6)
                rows[:, :4] /= scale
                return [_Result(rows)]
            except PermissionError:
                raise
            except Exception as e:
                if self.fallback is None:
                    raise
                print(f"[RemoteGPU] Worker unreachable ({e}); using this computer for {RETRY_AFTER_S:.0f}s.")
                self._down_until = time.monotonic() + RETRY_AFTER_S
        return self.fallback.predict(img, imgsz=imgsz, conf=conf, classes=classes, **kw)


def connect_remote(config_path: str, fallback=None) -> Optional[RemoteYolo]:
    """RemoteYolo if config_path exists and its worker answers; None (stay local) otherwise."""
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        remote = RemoteYolo(cfg["url"], cfg["key"], fallback=fallback, timeout=float(cfg.get("timeout", 5)))
        print(f"[RemoteGPU] Using GPU worker at {cfg['url']} ({remote.gpu_name})")
        return remote
    except Exception as e:
        print(f"[RemoteGPU] GPU worker not used ({e}); running on this computer.")
        return None
