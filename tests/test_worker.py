import http.client
import importlib.util
import json
import os
import re
import threading
import time
from urllib.parse import urlparse

import pytest
from velopath.tracker import TrajectoryPoint

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("velopath_worker", os.path.join(ROOT, "worker", "velopath_worker.py"))
worker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(worker)

KEY = "test-worker-key"


class FakeTracker:
    def __init__(self, should_fail=False, sleep_s=0.1):
        self.should_fail = should_fail
        self.sleep_s = sleep_s
        self.last_path = None
        self.last_plate = (100.0, 200.0, 300.0, 400.0)
        self.last_resolved_perspective = "behind_catcher"
        self.fixed_points = [
            TrajectoryPoint(1, 100.0, 200.0, 0.9, 5.0),
            TrajectoryPoint(2, 105.0, 205.0, 0.92, 5.1),
        ]

    def track_video(self, path, conf_thresh=0.15, ball_type="auto", perspective="auto", mode="baseball", progress_callback=None, time_window=None):
        self.last_path = path
        if progress_callback:
            progress_callback(0.2)
        if self.sleep_s:
            time.sleep(self.sleep_s)
        if progress_callback:
            progress_callback(0.8)
        if self.should_fail:
            raise RuntimeError("Fake tracker failure")
        return self.fixed_points, 30.0, (1920, 1080)


def request(url: str, method: str, path: str, body: bytes = None, key: str = KEY, headers: dict = None):
    u = urlparse(url)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    req_headers = {"X-VeloPath-Key": key} if key is not None else {}
    if headers:
        req_headers.update(headers)
    if body is not None and "Content-Length" not in req_headers:
        req_headers["Content-Length"] = str(len(body))
    conn.request(method, path, body=body, headers=req_headers)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    try:
        parsed = json.loads(data.decode("utf-8"))
    except Exception:
        parsed = None
    return resp.status, parsed


@pytest.fixture
def fake_tracker():
    return FakeTracker(sleep_s=0.05)


@pytest.fixture
def worker_server(fake_tracker):
    srv = worker.make_server(fake_tracker, KEY, "127.0.0.1", 0, gpu_name="Fake GPU", code_hash="test_code_sha")
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    yield url, fake_tracker
    srv.shutdown()


def test_health_includes_code_and_busy(worker_server):
    url, _ = worker_server
    status, data = request(url, "GET", "/health")
    assert status == 200
    assert data["ok"] is True
    assert data["gpu"] == "Fake GPU"
    assert data["code"] == "test_code_sha"
    assert data["busy"] is False


def test_401_without_key_or_bad_key(worker_server):
    url, _ = worker_server
    status, _ = request(url, "GET", "/health", key=None)
    assert status == 401
    status, _ = request(url, "GET", "/health", key="wrong-key")
    assert status == 401
    status, _ = request(url, "POST", "/track", body=b"dummy", key="wrong-key")
    assert status == 401


def test_upload_gives_202_and_polls_done_with_points_and_removes_temp(worker_server):
    url, tracker = worker_server
    video_bytes = b"fake-video-content-stream"
    status, data = request(url, "POST", "/track?conf=0.2&mode=baseball", body=video_bytes)
    assert status == 202
    job_id = data.get("job")
    assert job_id and re.fullmatch(r"[0-9a-f]{32}", job_id)

    # Poll until done
    for _ in range(50):
        status, poll_data = request(url, "GET", f"/job/{job_id}")
        assert status == 200
        state = poll_data.get("state")
        if state == "done":
            break
        assert state == "running"
        time.sleep(0.02)
    else:
        pytest.fail("Job did not finish in time")

    res = poll_data["result"]
    assert res["points"] == [[1, 100.0, 200.0, 0.9, 5.0], [2, 105.0, 205.0, 0.92, 5.1]]
    assert res["fps"] == 30.0
    assert res["size"] == [1920, 1080]
    assert res["plate"] == [100.0, 200.0, 300.0, 400.0]
    assert res["perspective"] == "behind_catcher"

    # Temp file removed
    assert tracker.last_path is not None
    assert not os.path.exists(tracker.last_path)


def test_second_upload_while_running_gives_409():
    slow_tracker = FakeTracker(sleep_s=0.5)
    srv = worker.make_server(slow_tracker, KEY, "127.0.0.1", 0, gpu_name="Fake GPU", code_hash="test_code_sha")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        status1, data1 = request(url, "POST", "/track", body=b"video-1")
        assert status1 == 202

        # Immediately send second upload
        status2, data2 = request(url, "POST", "/track", body=b"video-2")
        assert status2 == 409
        assert data2 == {"error": "busy"}
    finally:
        srv.shutdown()


def test_bad_job_id_gives_404(worker_server):
    url, _ = worker_server
    # Invalid hex string
    status, _ = request(url, "GET", "/job/invalid-id")
    assert status == 404
    # Valid hex but non-existent job
    status, _ = request(url, "GET", "/job/" + "a" * 32)
    assert status == 404


def test_413_when_too_big():
    tracker = FakeTracker(sleep_s=0.01)
    srv = worker.make_server(tracker, KEY, "127.0.0.1", 0, gpu_name="Fake GPU", max_video_bytes=50)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        status, data = request(url, "POST", "/track", body=b"x" * 100)
        assert status == 413
    finally:
        srv.shutdown()


def test_tracker_exception_gives_state_error_and_server_alive():
    failing_tracker = FakeTracker(should_fail=True, sleep_s=0.02)
    srv = worker.make_server(failing_tracker, KEY, "127.0.0.1", 0, gpu_name="Fake GPU")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        status, data = request(url, "POST", "/track", body=b"failing-video")
        assert status == 202
        job_id = data["job"]

        for _ in range(50):
            status, poll_data = request(url, "GET", f"/job/{job_id}")
            assert status == 200
            if poll_data.get("state") == "error":
                break
            time.sleep(0.02)
        else:
            pytest.fail("Job did not enter error state")

        assert "Fake tracker failure" in poll_data["error"]
        assert failing_tracker.last_path is not None
        assert not os.path.exists(failing_tracker.last_path)

        # Server is alive and not busy
        status, health = request(url, "GET", "/health")
        assert status == 200
        assert health["busy"] is False
    finally:
        srv.shutdown()
