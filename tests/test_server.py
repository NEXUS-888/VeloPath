import os
import pytest
from fastapi.testclient import TestClient
from velopath.server import app, OUTPUTS_DIR


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["app"] == "VeloPath AI"


def test_stream_video_not_found(client):
    res = client.get("/api/video/non_existent_file_12345.mp4")
    assert res.status_code == 404


def test_stream_video_ranges(client, tmp_path):
    # Create a dummy video file in outputs directory for testing range requests
    test_filename = "test_range_video.mp4"
    test_filepath = os.path.join(OUTPUTS_DIR, test_filename)
    dummy_data = b"0123456789" * 100  # 1000 bytes

    with open(test_filepath, "wb") as f:
        f.write(dummy_data)

    try:
        # 1. Full video request (no range)
        res = client.get(f"/api/video/{test_filename}")
        assert res.status_code == 200
        assert len(res.content) == 1000

        # 2. Standard byte range: bytes=0-99 (first 100 bytes)
        res = client.get(f"/api/video/{test_filename}", headers={"Range": "bytes=0-99"})
        assert res.status_code == 206
        assert res.headers["content-range"] == "bytes 0-99/1000"
        assert res.headers["content-length"] == "100"
        assert res.content == dummy_data[:100]

        # 3. Open range: bytes=500- (from 500 to end)
        res = client.get(f"/api/video/{test_filename}", headers={"Range": "bytes=500-"})
        assert res.status_code == 206
        assert res.headers["content-range"] == "bytes 500-999/1000"
        assert res.headers["content-length"] == "500"
        assert res.content == dummy_data[500:]

        # 4. Suffix range: bytes=-200 (last 200 bytes)
        res = client.get(f"/api/video/{test_filename}", headers={"Range": "bytes=-200"})
        assert res.status_code == 206
        assert res.headers["content-range"] == "bytes 800-999/1000"
        assert res.headers["content-length"] == "200"
        assert res.content == dummy_data[800:]

        # 5. Out of bounds range -> 416 Range Not Satisfiable
        res = client.get(f"/api/video/{test_filename}", headers={"Range": "bytes=2000-3000"})
        assert res.status_code == 416
        assert "bytes */1000" in res.headers.get("content-range", "")

        # 6. HEAD request
        res = client.head(f"/api/video/{test_filename}", headers={"Range": "bytes=0-49"})
        assert res.status_code == 206
        assert res.headers["content-range"] == "bytes 0-49/1000"
        assert res.headers["content-length"] == "50"
    finally:
        if os.path.exists(test_filepath):
            os.remove(test_filepath)


@pytest.mark.parametrize("name", ["README.md", "AGENTS.md", "..%5CREADME.md", "..%5C..%5CREADME.md", "%2E%2E%5CREADME.md"])
def test_stream_video_cannot_escape_outputs(client, name):
    res = client.get(f"/api/video/{name}")
    assert res.status_code == 404


def test_rerender_rejects_unsafe_video_id(client):
    traj = [{"frame": 1, "x": 1, "y": 1}, {"frame": 2, "x": 2, "y": 2}]
    res = client.post("/api/rerender", json={"video_id": "", "trajectory": traj})
    assert res.status_code == 404


def test_rerender_rejects_missing_trajectory(client):
    res = client.post("/api/rerender", json={"video_id": "sample", "trajectory": []})
    assert res.status_code == 422


def test_processing_does_not_block_other_requests(monkeypatch, tmp_path):
    """Pipeline is minutes of blocking CPU work; it must not freeze the event loop (health, streaming).
    `with TestClient` runs every request on one event loop, like the real server."""
    import threading
    import time
    import velopath.server as server

    started, release = threading.Event(), threading.Event()

    def slow_pipeline(**kw):
        started.set()
        release.wait(10)
        return {"pitch_detected": False}

    monkeypatch.setattr(server, "process_pitch_video", slow_pipeline)
    monkeypatch.setattr(server, "UPLOADS_DIR", str(tmp_path))
    with TestClient(app) as client:
        upload = threading.Thread(target=lambda: client.post("/api/process", files={"file": ("a.mp4", b"x")}))
        upload.start()
        try:
            assert started.wait(5)
            t0 = time.monotonic()
            assert client.get("/api/health").status_code == 200
            elapsed = time.monotonic() - t0
        finally:
            release.set()
            upload.join()
    assert elapsed < 2


@pytest.mark.parametrize("extra", [{"plate_corners": [[1, 2]]}, {"plate_corners": [[1, 2], [1, 2]]},
                                   {"plate_corners": [[1, 2], [3]]}, {"batter_height_in": 5}])
def test_rerender_rejects_bad_calibration(client, extra):
    res = client.post("/api/rerender", json={"video_id": "sample", "trajectory": [{"frame": 1, "x": 1, "y": 1}], **extra})
    assert res.status_code == 422


@pytest.mark.parametrize("window", [{"start_s": "2", "end_s": "1"}, {"start_s": "-1", "end_s": "1"}, {"start_s": "1"}])
def test_process_rejects_bad_pitch_window(window, tmp_path, monkeypatch):
    import velopath.server as server
    monkeypatch.setattr(server, "UPLOADS_DIR", str(tmp_path))
    res = TestClient(app).post("/api/process", files={"file": ("a.mp4", b"x")}, data=window)
    assert res.status_code == 422


def test_process_passes_pitch_window_to_pipeline(tmp_path, monkeypatch):
    import velopath.server as server
    got = {}
    monkeypatch.setattr(server, "process_pitch_video", lambda **kw: got.update(kw) or {"pitch_detected": False})
    monkeypatch.setattr(server, "UPLOADS_DIR", str(tmp_path))
    res = TestClient(app).post("/api/process", files={"file": ("a.mp4", b"x")}, data={"start_s": "1.5", "end_s": "2.75"})
    assert res.status_code == 200 and got["time_window"] == (1.5, 2.75)


def test_sample_cache_is_rebuilt_when_code_is_newer(tmp_path, monkeypatch):
    """A cached demo result must not outlive a code change (it once served a stale always-STRIKE result)."""
    import json
    import velopath.server as server
    monkeypatch.setattr(server, "OUTPUTS_DIR", str(tmp_path))
    meta, out = tmp_path / "velopath_sample_meta.json", tmp_path / "velopath_sample_result.mp4"
    meta.write_text(json.dumps({"call": "STALE"}))
    out.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(server, "process_pitch_video", lambda **kw: calls.append(1) or {"call": "FRESH"})
    monkeypatch.setattr(server.os.path, "exists", lambda p: True if str(p).endswith("sample_pitch.mp4") else os.path.isfile(p))

    os.utime(meta, (1, 1))  # cache older than the code
    assert TestClient(app).get("/api/sample").json()["call"] == "FRESH" and calls == [1]
    future = 4102444800  # cache newer than the code
    os.utime(meta, (future, future))
    assert TestClient(app).get("/api/sample").json()["call"] == "FRESH" and calls == [1]  # served from cache, no rerun
