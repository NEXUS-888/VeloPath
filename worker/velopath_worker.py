# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["ultralytics>=8.3", "torch", "torchvision", "opencv-python-headless", "numpy", "scipy"]
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
VeloPath GPU worker: runs the ball tracking on this laptop's NVIDIA GPU for a VeloPath app elsewhere.

POST /track?conf=0.15&ball=auto&persp=auto&mode=baseball&start=<s>&end=<s>
    body: raw video bytes, header: X-VeloPath-Key
    -> 202 {"job": "<32 hex>"}
GET  /job/<id>                                  header: X-VeloPath-Key
    -> {"state": "running", "progress": 0.0-1.0}
    -> {"state": "done", "result": {"points": [...], "fps": f, "size": [w, h], "plate": [...], "perspective": "..."}}
    -> {"state": "error", "error": "..."}
GET  /health                                    header: X-VeloPath-Key
    -> {"ok": true, "gpu": "...", "names": {...}, "code": "<sha256>", "busy": false}

Needs key.txt and the model weights (*.pt) next to this file. Started by start_worker.bat.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
MAX_VIDEO_BYTES = 400_000_000


def compute_tracker_code_hash() -> str:
    """Computes SHA256 of velopath/tracker.py for client-worker version verification."""
    try:
        import velopath.tracker
        if hasattr(velopath.tracker, "__file__") and velopath.tracker.__file__:
            with open(velopath.tracker.__file__, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        pass
    for rel in ("../velopath/tracker.py", "velopath/tracker.py"):
        p = os.path.join(HERE, rel)
        if os.path.exists(p):
            with open(p, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
    return ""


def make_server(
    tracker,
    key: str,
    host: str,
    port: int,
    gpu_name: str = "",
    code_hash: str = "",
    max_video_bytes: int = MAX_VIDEO_BYTES,
    half: bool = False,
) -> ThreadingHTTPServer:
    """ThreadingHTTPServer: polls and health checks answer while one background job runs."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

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
            url = urlparse(self.path)
            if url.path == "/health":
                names_dict = getattr(tracker, "names", None)
                if names_dict is None:
                    names_dict = getattr(getattr(tracker, "model", None), "names", {})
                names = {int(k): v for k, v in names_dict.items()} if names_dict else {}
                with self.server.jobs_lock:
                    busy = self.server.current_job_id is not None
                return self._reply(200, {
                    "ok": True,
                    "gpu": gpu_name,
                    "names": names,
                    "code": self.server.code_hash,
                    "busy": busy,
                })

            if url.path.startswith("/job/"):
                match = re.fullmatch(r"/job/([0-9a-f]{32})", url.path)
                if not match:
                    return self._reply(404, {"error": "not found"})
                job_id = match.group(1)
                now = time.time()
                with self.server.jobs_lock:
                    # Clean up jobs older than 10 minutes (600s)
                    stale = [jid for jid, j in self.server.jobs.items() if j.get("done_at") and now - j["done_at"] > 600]
                    for jid in stale:
                        del self.server.jobs[jid]
                    if job_id not in self.server.jobs:
                        return self._reply(404, {"error": "not found"})
                    j = self.server.jobs[job_id]
                    if j["state"] == "running":
                        payload = {"state": "running", "progress": j.get("progress", 0.0)}
                    elif j["state"] == "done":
                        payload = {"state": "done", "result": j["result"]}
                    else:
                        payload = {"state": "error", "error": j.get("error", "unknown error")}
                return self._reply(200, payload)

            return self._reply(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorized():
                return
            url = urlparse(self.path)

            if url.path == "/track":
                length_str = self.headers.get("Content-Length")
                if not length_str:
                    return self._reply(400, {"error": "Content-Length required"})
                try:
                    length = int(length_str)
                except ValueError:
                    return self._reply(400, {"error": "invalid Content-Length"})

                if length > self.server.max_video_bytes:
                    return self._reply(413, {"error": "payload too large"})

                with self.server.jobs_lock:
                    if self.server.current_job_id is not None:
                        return self._reply(409, {"error": "busy"})
                    job_id = secrets.token_hex(16)
                    self.server.current_job_id = job_id
                    self.server.jobs[job_id] = {"state": "running", "progress": 0.0}

                fd, temp_path = tempfile.mkstemp(suffix=".mp4")
                try:
                    remaining = length
                    with os.fdopen(fd, "wb") as f:
                        while remaining > 0:
                            chunk = self.rfile.read(min(remaining, 65536))
                            if not chunk:
                                break
                            f.write(chunk)
                            remaining -= len(chunk)
                    if remaining > 0:
                        raise IOError("Incomplete body read")
                except Exception as e:
                    with self.server.jobs_lock:
                        if self.server.current_job_id == job_id:
                            self.server.current_job_id = None
                        self.server.jobs.pop(job_id, None)
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except OSError:
                            pass
                    return self._reply(400, {"error": f"upload failed: {e}"})

                q = {k: v[0] for k, v in parse_qs(url.query).items()}
                t = threading.Thread(
                    target=self._run_job,
                    args=(job_id, temp_path, q),
                    daemon=True,
                )
                t.start()
                return self._reply(202, {"job": job_id})

            return self._reply(404, {"error": "not found"})

        def _run_job(self, job_id: str, temp_path: str, q: dict):
            try:
                def on_progress(frac):
                    with self.server.jobs_lock:
                        if job_id in self.server.jobs and self.server.jobs[job_id]["state"] == "running":
                            self.server.jobs[job_id]["progress"] = float(frac)

                conf = float(q.get("conf", 0.15))
                ball = q.get("ball", "auto")
                persp = q.get("persp", "auto")
                mode = q.get("mode", "baseball")
                start = float(q["start"]) if "start" in q else None
                end = float(q["end"]) if "end" in q else None
                time_window = (start, end) if (start is not None and end is not None) else None

                points, fps, (w, h) = tracker.track_video(
                    temp_path,
                    conf_thresh=conf,
                    ball_type=ball,
                    perspective=persp,
                    mode=mode,
                    progress_callback=on_progress,
                    time_window=time_window,
                )
                plate = getattr(tracker, "last_plate", None)
                persp_res = getattr(tracker, "last_resolved_perspective", persp)
                pt_rows = [
                    [p.frame_idx, p.x, p.y, p.conf, p.radius] if hasattr(p, "frame_idx") else list(p)
                    for p in points
                ]
                res = {
                    "points": pt_rows,
                    "fps": float(fps),
                    "size": [int(w), int(h)],
                    "plate": list(plate) if plate is not None else None,
                    "perspective": str(persp_res),
                }
                with self.server.jobs_lock:
                    self.server.jobs[job_id] = {"state": "done", "result": res, "done_at": time.time()}
            except Exception as e:
                with self.server.jobs_lock:
                    self.server.jobs[job_id] = {"state": "error", "error": str(e), "done_at": time.time()}
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                with self.server.jobs_lock:
                    if self.server.current_job_id == job_id:
                        self.server.current_job_id = None

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    server.jobs = {}
    server.jobs_lock = threading.Lock()
    server.current_job_id = None
    server.max_video_bytes = max_video_bytes
    server.code_hash = code_hash or compute_tracker_code_hash()
    return server


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


def find_weights(here: str) -> str:
    """The big ball model: next to this script (old layout) or in models/ (zip from worker/package.py). Never the small scan model."""
    found = [os.path.join(d, f) for d in (here, os.path.join(here, "models")) if os.path.isdir(d)
             for f in sorted(os.listdir(d)) if f.endswith(".pt") and "small" not in f]
    return found[0] if found else ""


def main():
    import torch
    from ultralytics import YOLO

    key_path = os.path.join(HERE, "key.txt")
    weights = find_weights(HERE)
    if not os.path.exists(key_path) or not weights:
        sys.exit("Missing key.txt or the model .pt file next to this script. Ask for the full worker folder.")
    key = open(key_path, encoding="utf-8").read().strip()
    if not torch.cuda.is_available():
        sys.exit("No NVIDIA GPU visible to PyTorch. Update the NVIDIA driver (nvidia.com/drivers) and retry.")

    gpu = torch.cuda.get_device_name(0)
    model = YOLO(weights)
    model.to("cuda")
    model.predict(np.zeros((640, 640, 3), np.uint8), imgsz=640, half=True, verbose=False)  # warm up CUDA
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    from velopath.tracker import PitchTracker
    tracker = PitchTracker(model_path=weights)
    code_hash = compute_tracker_code_hash()

    host = tailscale_ip()
    if not host:
        sys.exit("Tailscale is not connected. Open Tailscale, sign in, then run this again.")
    keep_awake()
    print("=" * 60)
    print(f"  VeloPath GPU worker running on {gpu}")
    print(f"  Address: http://{host}:{PORT}")
    print("  Keep this window open. Close it to stop.")
    print("=" * 60)
    make_server(tracker, key, host, PORT, gpu_name=gpu, code_hash=code_hash, half=True).serve_forever()


if __name__ == "__main__":
    main()
