"""Remote GPU worker: runs ball tracking remotely on the worker and falls back cleanly."""
import importlib.util
import json
import os
import threading

import pytest

from velopath.remote_gpu import RemoteTracker, connect_remote
from velopath.tracker import TrajectoryPoint

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("velopath_worker", os.path.join(ROOT, "worker", "velopath_worker.py"))
worker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(worker)

KEY = "test-key-123"


class FakeLocalFallback:
    def __init__(self):
        self.last_plate = (1.0, 2.0, 3.0, 4.0)
        self.last_resolved_perspective = "behind_pitcher"
        self.called = False

    def track_video(self, *args, **kwargs):
        self.called = True
        return [TrajectoryPoint(0, 50.0, 50.0, 0.8, 4.0)], 25.0, (1280, 720)


class FakeWorkerTracker:
    def __init__(self, sleep_s=0.05):
        self.sleep_s = sleep_s
        self.last_plate = (10.0, 20.0, 30.0, 40.0)
        self.last_resolved_perspective = "behind_catcher"
        self.points = [
            TrajectoryPoint(1, 100.0, 100.0, 0.9, 5.0),
            TrajectoryPoint(2, 110.0, 110.0, 0.95, 5.1),
        ]

    def track_video(self, path, progress_callback=None, **kw):
        import time
        if progress_callback:
            progress_callback(0.5)
        if self.sleep_s:
            time.sleep(self.sleep_s)
        return self.points, 30.0, (1920, 1080)


@pytest.fixture
def server():
    srv = worker.make_server(FakeWorkerTracker(), KEY, "127.0.0.1", 0, gpu_name="Fake GPU")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_connect_remote_uses_config_file_when_worker_is_up(server, tmp_path):
    cfg = tmp_path / "gpu_worker.json"
    assert connect_remote(str(cfg), fallback=None) is None  # no config: stay local
    cfg.write_text(json.dumps({"url": server, "key": KEY}))
    remote = connect_remote(str(cfg), fallback=None)
    assert remote is not None and remote.gpu_name == "Fake GPU"
    cfg.write_text(json.dumps({"url": "http://127.0.0.1:9", "key": KEY}))
    assert connect_remote(str(cfg), fallback=None) is None  # configured but offline: stay local


def test_remote_tracker_happy_path(tmp_path):
    wt = FakeWorkerTracker(sleep_s=0.02)
    code_hash = worker.compute_tracker_code_hash()
    srv = worker.make_server(wt, KEY, "127.0.0.1", 0, gpu_name="RTX 4090", code_hash=code_hash)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        video_file = tmp_path / "pitch.mp4"
        video_file.write_bytes(b"dummy video data")

        fallback = FakeLocalFallback()
        remote = RemoteTracker(url, KEY, fallback=fallback)
        remote.poll_interval = 0.02
        progresses = []
        points, fps, size = remote.track_video(
            str(video_file),
            progress_callback=lambda p: progresses.append(p)
        )

        assert len(points) == 2
        assert points[0].frame_idx == 1 and points[0].x == 100.0
        assert fps == 30.0
        assert size == (1920, 1080)
        assert remote.last_plate == (10.0, 20.0, 30.0, 40.0)
        assert remote.last_resolved_perspective == "behind_catcher"
        assert not remote.using_fallback
        assert remote.model.gpu_name == "RTX 4090"
        assert not fallback.called
        assert len(progresses) > 0 and progresses[-1] == 1.0
    finally:
        srv.shutdown()


def test_remote_tracker_busy_gives_fallback(tmp_path):
    slow_worker = FakeWorkerTracker(sleep_s=0.5)
    code_hash = worker.compute_tracker_code_hash()
    srv = worker.make_server(slow_worker, KEY, "127.0.0.1", 0, gpu_name="RTX 4090", code_hash=code_hash)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        video_file = tmp_path / "pitch.mp4"
        video_file.write_bytes(b"dummy video data")

        # Start a background request to make worker busy
        import http.client
        from urllib.parse import urlparse
        u = urlparse(url)
        conn = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
        conn.request("POST", "/track", body=b"video1", headers={"X-VeloPath-Key": KEY, "Content-Length": "6"})
        resp = conn.getresponse()
        assert resp.status == 202

        fallback = FakeLocalFallback()
        remote = RemoteTracker(url, KEY, fallback=fallback)
        remote.poll_interval = 0.02
        points, fps, size = remote.track_video(str(video_file))

        assert fallback.called
        assert remote.using_fallback
        assert points[0].frame_idx == 0
        assert remote.last_plate == (1.0, 2.0, 3.0, 4.0)
    finally:
        srv.shutdown()


def test_remote_tracker_worker_killed_mid_job_gives_fallback(tmp_path):
    slow_worker = FakeWorkerTracker(sleep_s=0.5)
    code_hash = worker.compute_tracker_code_hash()
    srv = worker.make_server(slow_worker, KEY, "127.0.0.1", 0, gpu_name="RTX 4090", code_hash=code_hash)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"

    video_file = tmp_path / "pitch.mp4"
    video_file.write_bytes(b"dummy video data")

    fallback = FakeLocalFallback()
    remote = RemoteTracker(url, KEY, fallback=fallback)
    remote.poll_interval = 0.02

    # Hook progress_callback to kill worker during job
    def on_progress(p):
        srv.shutdown()

    points, fps, size = remote.track_video(str(video_file), progress_callback=on_progress)
    assert fallback.called
    assert remote.using_fallback
    assert points[0].frame_idx == 0


def test_remote_tracker_code_mismatch_gives_fallback(tmp_path):
    wt = FakeWorkerTracker()
    srv = worker.make_server(wt, KEY, "127.0.0.1", 0, gpu_name="RTX 4090", code_hash="mismatched_sha")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        video_file = tmp_path / "pitch.mp4"
        video_file.write_bytes(b"dummy video data")

        fallback = FakeLocalFallback()
        remote = RemoteTracker(url, KEY, fallback=fallback)
        remote.poll_interval = 0.02
        points, fps, size = remote.track_video(str(video_file))

        assert fallback.called
        assert remote.using_fallback
    finally:
        srv.shutdown()


def test_remote_tracker_wrong_key_raises(tmp_path):
    wt = FakeWorkerTracker()
    code_hash = worker.compute_tracker_code_hash()
    srv = worker.make_server(wt, KEY, "127.0.0.1", 0, gpu_name="RTX 4090", code_hash=code_hash)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        video_file = tmp_path / "pitch.mp4"
        video_file.write_bytes(b"dummy video data")

        fallback = FakeLocalFallback()
        remote = RemoteTracker(url, "wrong-key", fallback=fallback)
        with pytest.raises(PermissionError):
            remote.track_video(str(video_file))
        assert not fallback.called
    finally:
        srv.shutdown()


def test_pipeline_with_fake_remote_tracker_injected(tmp_path):
    from velopath.pipeline import process_pitch_video
    video_path = os.path.join(ROOT, "assets", "sample_pitch.mp4")
    out_path = str(tmp_path / "out.mp4")

    class FakeRemoteTracker:
        def __init__(self):
            self.last_plate = None
            self.last_resolved_perspective = "behind_catcher"
            self.model = type("M", (), {"gpu_name": "RTX 4090", "using_fallback": False})()
            self.track_called = False

        def track_video(self, *args, **kwargs):
            self.track_called = True
            pts = [
                TrajectoryPoint(0, 100.0, 200.0, 0.9, 5.0),
                TrajectoryPoint(1, 105.0, 205.0, 0.9, 5.0),
                TrajectoryPoint(2, 110.0, 210.0, 0.9, 5.0),
            ]
            return pts, 30.0, (1920, 1080)

    fake_remote = FakeRemoteTracker()
    res = process_pitch_video(video_path, out_path, tracker=fake_remote)
    assert fake_remote.track_called
    assert res["compute"] == "RTX 4090 (GPU worker)"
    assert res["pitch_detected"] is True
    assert "trajectory" in res
    assert "zone_calibrated" in res
    assert os.path.exists(out_path)


def test_pipeline_fallback_label(tmp_path):
    from velopath.pipeline import process_pitch_video
    video_path = os.path.join(ROOT, "assets", "sample_pitch.mp4")
    out_path = str(tmp_path / "out_fb.mp4")

    class FakeFallbackTracker:
        def __init__(self):
            self.last_plate = None
            self.last_resolved_perspective = "behind_catcher"
            self.model = type("M", (), {"gpu_name": "RTX 4090", "using_fallback": True})()

        def track_video(self, *args, **kwargs):
            pts = [
                TrajectoryPoint(0, 100.0, 200.0, 0.9, 5.0),
                TrajectoryPoint(1, 105.0, 205.0, 0.9, 5.0),
            ]
            return pts, 30.0, (1920, 1080)

    res = process_pitch_video(video_path, out_path, tracker=FakeFallbackTracker())
    assert res["compute"] == "this computer"


def test_pipeline_without_worker_configured_stays_local(tmp_path):
    from velopath.pipeline import get_active_tracker, get_tracker
    tracker = get_active_tracker(config_path=str(tmp_path / "nonexistent.json"))
    assert tracker is get_tracker()


def test_remote_tracker_cooldown_and_label_after_slow_fallback(tmp_path, monkeypatch):
    import time
    from velopath import remote_gpu
    from velopath.pipeline import process_pitch_video
    monkeypatch.setattr(remote_gpu, "RETRY_AFTER_S", 0.05)

    class SlowFallback:
        def __init__(self):
            self.last_plate = None
            self.last_resolved_perspective = "behind_catcher"
        def track_video(self, *args, **kwargs):
            time.sleep(0.1)  # Longer than RETRY_AFTER_S
            return [TrajectoryPoint(0, 100.0, 200.0, 0.9, 5.0)], 30.0, (1920, 1080)

    # Worker on port 9 (offline)
    remote = remote_gpu.RemoteTracker("http://127.0.0.1:9", KEY, fallback=SlowFallback(), timeout=0.1)
    remote.gpu_name = "NVIDIA GeForce RTX 3050"

    video_path = os.path.join(ROOT, "assets", "sample_pitch.mp4")
    out_path = str(tmp_path / "out_slow_fb.mp4")

    # Run via pipeline
    res = process_pitch_video(video_path, out_path, tracker=remote)
    assert remote.model.using_fallback is True
    assert getattr(remote, "last_run_remote", None) is False
    assert res["compute"] == "this computer"


def test_get_active_tracker_caches_and_second_clip_skips_unreachable_worker(tmp_path):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from velopath.pipeline import get_active_tracker

    connection_count = 0
    class CountingHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal connection_count
            connection_count += 1
            self.send_response(500)
            self.end_headers()
        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), CountingHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        cfg = tmp_path / "gpu_worker.json"
        cfg.write_text(json.dumps({"url": url, "key": KEY, "timeout": 0.5}))

        video_file = tmp_path / "pitch.mp4"
        video_file.write_bytes(b"dummy video")

        tracker1 = get_active_tracker(config_path=str(cfg))
        fallback = FakeLocalFallback()
        tracker1.fallback = fallback
        tracker1.track_video(str(video_file))

        assert connection_count == 1
        assert fallback.called

        # Second clip immediately: should reuse tracker and skip connection because in cooldown
        tracker2 = get_active_tracker(config_path=str(cfg))
        assert tracker2 is tracker1
        fallback2 = FakeLocalFallback()
        tracker2.fallback = fallback2
        tracker2.track_video(str(video_file))

        assert connection_count == 1  # No second connection attempted!
        assert fallback2.called
    finally:
        server.shutdown()


def test_remote_tracker_missing_code_in_health_gives_fallback_without_upload(tmp_path):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from velopath.remote_gpu import RemoteTracker

    upload_attempted = False
    class OldWorkerHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                # Old worker without code hash
                body = json.dumps({"ok": True, "gpu": "RTX 3050"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()
        def do_POST(self):
            nonlocal upload_attempted
            upload_attempted = True
            self.send_response(404)
            self.end_headers()
        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), OldWorkerHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        fallback = FakeLocalFallback()
        remote = RemoteTracker(url, KEY, fallback=fallback)
        video_file = tmp_path / "pitch.mp4"
        video_file.write_bytes(b"dummy video data")

        pts, fps, size = remote.track_video(str(video_file))
        assert fallback.called
        assert not upload_attempted  # No upload was attempted!
    finally:
        server.shutdown()



