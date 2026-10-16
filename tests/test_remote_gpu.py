"""Remote GPU worker: the friend's laptop runs worker/velopath_worker.py; RemoteYolo calls it like a local YOLO."""
import importlib.util
import json
import os
import threading

import cv2
import numpy as np
import pytest

from velopath.remote_gpu import RemoteYolo, RemoteTracker, connect_remote
from velopath.tracker import TrajectoryPoint

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("velopath_worker", os.path.join(ROOT, "worker", "velopath_worker.py"))
worker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(worker)

KEY = "test-key-123"


class _Boxes:
    def __init__(self, rows):
        rows = np.array(rows, dtype=float).reshape(-1, 6)
        self.xyxy, self.conf, self.cls = rows[:, :4], rows[:, 4], rows[:, 5]


class BlobModel:
    """Finds the bright blob in the image it is given and reports it as class 2 (baseball)."""
    names = {0: "glove", 1: "homeplate", 2: "baseball", 3: "rubber"}

    def predict(self, img, imgsz=640, conf=0.25, classes=None, **kw):
        ys, xs = np.nonzero(img[..., 0] > 200)
        rows = [] if xs.size == 0 else [(xs.min(), ys.min(), xs.max() + 1, ys.max() + 1, 0.9, 2)]
        rows = [r for r in rows if classes is None or r[5] in classes]
        return [type("R", (), {"boxes": _Boxes(rows)})()]


@pytest.fixture
def server():
    srv = worker.make_server(BlobModel(), KEY, "127.0.0.1", 0, gpu_name="Fake GPU")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def frame_with_ball(w=1920, h=1080, cx=1500, cy=300, r=12):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.circle(img, (cx, cy), r, (255, 255, 255), -1)
    return img


def boxes_of(results):
    b = results[0].boxes
    return list(zip(b.xyxy.tolist(), b.conf.tolist(), b.cls.tolist()))


def test_remote_predict_returns_boxes_in_original_pixels(server):
    model = RemoteYolo(server, KEY)
    assert model.names[2] == "baseball"
    (xyxy, conf, cls), = boxes_of(model.predict(frame_with_ball(), imgsz=640, conf=0.15, classes=[2]))
    cx, cy = (xyxy[0] + xyxy[2]) / 2, (xyxy[1] + xyxy[3]) / 2
    assert (cx, cy) == pytest.approx((1500, 300), abs=3)  # frame was shrunk to 640 for the trip
    assert cls == 2 and conf == pytest.approx(0.9)


def test_remote_predict_on_small_window_is_not_resized(server):
    model = RemoteYolo(server, KEY)
    crop = frame_with_ball(320, 320, 100, 200, 6)
    (xyxy, _, _), = boxes_of(model.predict(crop, imgsz=320, conf=0.05, classes=[2]))
    assert ((xyxy[0] + xyxy[2]) / 2, (xyxy[1] + xyxy[3]) / 2) == pytest.approx((100, 200), abs=1.5)


def test_worker_rejects_wrong_key(server):
    with pytest.raises(PermissionError):
        RemoteYolo(server, "wrong-key")


def test_remote_falls_back_to_local_model_when_worker_drops(server):
    fallback = BlobModel()
    model = RemoteYolo(server, KEY, fallback=fallback)
    model.url = "http://127.0.0.1:9"  # worker gone mid-clip (nothing listens on port 9)
    (xyxy, _, _), = boxes_of(model.predict(frame_with_ball(), imgsz=640, classes=[2]))
    assert (xyxy[0] + xyxy[2]) / 2 == pytest.approx(1500, abs=1)
    assert model.using_fallback


def test_connect_remote_uses_config_file_when_worker_is_up(server, tmp_path):
    cfg = tmp_path / "gpu_worker.json"
    assert connect_remote(str(cfg), fallback=None) is None  # no config: stay local
    cfg.write_text(json.dumps({"url": server, "key": KEY}))
    model = connect_remote(str(cfg), fallback=None)
    assert model is not None and model.gpu_name == "Fake GPU"
    cfg.write_text(json.dumps({"url": "http://127.0.0.1:9", "key": KEY}))
    assert connect_remote(str(cfg), fallback=None) is None  # configured but offline: stay local


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


