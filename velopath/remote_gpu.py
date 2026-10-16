"""
Run the ball model or full tracking on a friend's GPU (worker/velopath_worker.py) instead of this CPU.
RemoteTracker uploads the video once and tracks remotely; if the worker stops answering, is busy,
or runs mismatched code, it falls back to the local PitchTracker and retries after 30s.
Config: gpu_worker.json in the project root, {"url": "http://100.x.y.z:8765", "key": "..."}.
"""
import hashlib
import http.client
import json
import os
import time
from typing import Optional, Tuple
from urllib.parse import urlencode, urlparse

RETRY_AFTER_S = 30.0


def _get_local_tracker_hash() -> str:
    """Computes SHA256 of velopath/tracker.py for version verification."""
    try:
        import velopath.tracker
        if hasattr(velopath.tracker, "__file__") and velopath.tracker.__file__:
            with open(velopath.tracker.__file__, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        pass
    p = os.path.join(os.path.dirname(__file__), "tracker.py")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    return ""


class _RemoteModelAdapter:
    """Adapter exposing model attributes expected by the pipeline UI."""
    def __init__(self, tracker: "RemoteTracker"):
        self._tracker = tracker

    @property
    def gpu_name(self) -> str:
        return self._tracker.gpu_name

    @property
    def using_fallback(self) -> bool:
        return self._tracker.using_fallback


class RemoteTracker:
    """Runs PitchTracker.track_video on the remote GPU worker via HTTP."""
    def __init__(self, url: str, key: str, fallback=None, timeout: float = 5.0):
        self.url = url.rstrip("/")
        self.key = key
        self.fallback = fallback
        self.timeout = timeout
        self.gpu_name = ""
        self._down_until = 0.0
        self.last_plate = None
        self.last_resolved_perspective = "auto"
        self.model = _RemoteModelAdapter(self)
        self.poll_interval = 1.0  # seconds between poll requests

    @property
    def using_fallback(self) -> bool:
        return time.monotonic() < self._down_until

    def _run_fallback(self, error, *args, **kwargs):
        if self.fallback is None:
            raise error
        if not self.using_fallback:
            print(f"[RemoteGPU] GPU worker error ({error}); using this computer for {RETRY_AFTER_S:.0f}s.")
            self._down_until = time.monotonic() + RETRY_AFTER_S
        res = self.fallback.track_video(*args, **kwargs)
        self.last_plate = getattr(self.fallback, "last_plate", None)
        self.last_resolved_perspective = getattr(
            self.fallback, "last_resolved_perspective", kwargs.get("perspective", "auto")
        )
        return res

    def track_video(
        self,
        path: str,
        conf_thresh: float = 0.15,
        ball_type: str = "auto",
        perspective: str = "auto",
        mode: str = "baseball",
        progress_callback=None,
        time_window: Optional[Tuple[float, float]] = None,
    ):
        if self.using_fallback:
            return self._run_fallback(
                RuntimeError("worker temporarily offline"),
                path,
                conf_thresh=conf_thresh,
                ball_type=ball_type,
                perspective=perspective,
                mode=mode,
                progress_callback=progress_callback,
                time_window=time_window,
            )

        u = urlparse(self.url)
        host, port = u.hostname, u.port or 80

        try:
            # 1. Health check & code hash check (timeout: 5s)
            h_conn = http.client.HTTPConnection(host, port, timeout=self.timeout)
            try:
                h_conn.request("GET", "/health", headers={"X-VeloPath-Key": self.key})
                h_resp = h_conn.getresponse()
                if h_resp.status == 401:
                    raise PermissionError("GPU worker rejected the key (check gpu_worker.json and the worker's key.txt)")
                if h_resp.status != 200:
                    raise RuntimeError(f"worker /health returned status {h_resp.status}")
                health = json.loads(h_resp.read().decode("utf-8") or "{}")
            finally:
                h_conn.close()

            self.gpu_name = health.get("gpu", "")
            local_hash = _get_local_tracker_hash()
            remote_hash = health.get("code", "")
            if local_hash and remote_hash and local_hash != remote_hash:
                print("[RemoteGPU] worker runs different tracker code, using this computer")
                raise RuntimeError("worker runs different tracker code, using this computer")

            if health.get("busy"):
                raise RuntimeError("worker is busy")

            # 2. Upload video file by streaming (timeout: 10 min = 600s)
            q = {"conf": conf_thresh, "ball": ball_type, "persp": perspective, "mode": mode}
            if time_window:
                q["start"], q["end"] = time_window[0], time_window[1]

            file_size = os.path.getsize(path)
            up_conn = http.client.HTTPConnection(host, port, timeout=600)
            try:
                headers = {
                    "X-VeloPath-Key": self.key,
                    "Content-Length": str(file_size),
                }
                with open(path, "rb") as f:
                    up_conn.request("POST", "/track?" + urlencode(q), body=f, headers=headers)
                up_resp = up_conn.getresponse()
                if up_resp.status == 401:
                    raise PermissionError("GPU worker rejected the key")
                if up_resp.status == 409:
                    raise RuntimeError("worker is busy")
                if up_resp.status == 413:
                    raise RuntimeError("video exceeds maximum upload size")
                if up_resp.status != 202:
                    raise RuntimeError(f"upload failed with status {up_resp.status}")
                job_data = json.loads(up_resp.read().decode("utf-8") or "{}")
                job_id = job_data.get("job")
                if not job_id:
                    raise RuntimeError("no job id returned from worker")
            finally:
                up_conn.close()

            if progress_callback:
                progress_callback(0.1)

            # 3. Poll /job/<id> (timeout: 15 min = 900s)
            deadline = time.monotonic() + 900.0
            poll_conn = http.client.HTTPConnection(host, port, timeout=10.0)
            try:
                while True:
                    if time.monotonic() > deadline:
                        raise TimeoutError("worker job timed out after 15 minutes")
                    time.sleep(self.poll_interval)
                    poll_conn.request("GET", f"/job/{job_id}", headers={"X-VeloPath-Key": self.key})
                    p_resp = poll_conn.getresponse()
                    if p_resp.status == 401:
                        raise PermissionError("GPU worker rejected the key")
                    if p_resp.status != 200:
                        raise RuntimeError(f"polling job returned status {p_resp.status}")
                    p_data = json.loads(p_resp.read().decode("utf-8") or "{}")
                    state = p_data.get("state")
                    if state == "running":
                        frac = float(p_data.get("progress", 0.0))
                        if progress_callback:
                            progress_callback(0.1 + 0.9 * frac)
                    elif state == "done":
                        res = p_data["result"]
                        from velopath.tracker import TrajectoryPoint
                        points = [
                            TrajectoryPoint(int(pt[0]), float(pt[1]), float(pt[2]), float(pt[3]), float(pt[4]))
                            for pt in res["points"]
                        ]
                        fps = float(res["fps"])
                        size = tuple(res["size"])
                        self.last_plate = tuple(float(v) for v in res["plate"]) if res.get("plate") is not None else None
                        self.last_resolved_perspective = res.get("perspective", perspective)
                        if progress_callback:
                            progress_callback(1.0)
                        return points, fps, size
                    elif state == "error":
                        raise RuntimeError(p_data.get("error", "remote tracking error"))
                    else:
                        raise RuntimeError(f"unknown worker state: {state}")
            finally:
                poll_conn.close()

        except PermissionError:
            raise
        except Exception as e:
            return self._run_fallback(
                e,
                path,
                conf_thresh=conf_thresh,
                ball_type=ball_type,
                perspective=perspective,
                mode=mode,
                progress_callback=progress_callback,
                time_window=time_window,
            )


def connect_remote(config_path: str, fallback=None) -> Optional[RemoteTracker]:
    """RemoteTracker if config_path exists and its worker answers; None (stay local) otherwise."""
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        remote = RemoteTracker(cfg["url"], cfg["key"], fallback=fallback, timeout=float(cfg.get("timeout", 5)))
        u = urlparse(remote.url)
        conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=remote.timeout)
        try:
            conn.request("GET", "/health", headers={"X-VeloPath-Key": remote.key})
            resp = conn.getresponse()
            if resp.status == 200:
                health = json.loads(resp.read().decode("utf-8") or "{}")
                remote.gpu_name = health.get("gpu", "")
                print(f"[RemoteGPU] Using GPU worker at {cfg['url']} ({remote.gpu_name})")
                return remote
            elif resp.status == 401:
                print("[RemoteGPU] GPU worker rejected the key; running on this computer.")
                return None
            else:
                print(f"[RemoteGPU] GPU worker returned status {resp.status}; running on this computer.")
                return None
        finally:
            conn.close()
    except Exception as e:
        print(f"[RemoteGPU] GPU worker not used ({e}); running on this computer.")
        return None
