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


@pytest.mark.parametrize("extra", [{"rubber_corners": [[1, 2]]}, {"rubber_corners": [[5, 5], [5, 5]]}])
def test_rerender_rejects_bad_rubber_taps(client, extra):
    traj = [{"frame": 1, "x": 1, "y": 1}, {"frame": 2, "x": 2, "y": 2}]
    res = client.post("/api/rerender", json={"video_id": "sample", "trajectory": traj, **extra})
    assert res.status_code == 422


@pytest.fixture
def games_dir(tmp_path, monkeypatch):
    import velopath.server as server
    monkeypatch.setattr(server, "GAMES_DIR", str(tmp_path))
    server.GAMES.clear()
    yield tmp_path
    server.GAMES.clear()


def test_game_flow_over_the_api(client, games_dir):
    g = client.post("/api/games", json={"away": "Lions", "home": "Tigers", "innings": 7}).json()
    gid = g["id"]
    assert g["state"]["innings"] == 7 and g["state"]["balls"] == 0
    for kind in ("ball", "strike", "in_play"):
        assert client.post(f"/api/games/{gid}/pitch", json={"kind": kind}).status_code == 200
    s = client.post(f"/api/games/{gid}/play", json={"outcome": "single"}).json()
    assert s["bases"] == [True, False, False] and s["balls"] == 0
    s = client.post(f"/api/games/{gid}/adjust", json={"bases": [False, True, False], "runs": 1}).json()
    assert s["runs"] == [1, 0] and s["bases"] == [False, True, False]
    assert client.post(f"/api/games/{gid}/undo").json()["runs"] == [0, 0]
    assert client.get(f"/api/games/{gid}").json()["bases"] == [True, False, False]


def test_game_rules_errors_are_409_and_bad_input_is_422(client, games_dir):
    gid = client.post("/api/games", json={}).json()["id"]
    assert client.post(f"/api/games/{gid}/play", json={"outcome": "single"}).status_code == 409  # nothing in play
    assert client.post(f"/api/games/{gid}/pitch", json={"kind": "spitball"}).status_code == 422
    assert client.post("/api/games", json={"innings": 0}).status_code == 422
    assert client.post(f"/api/games/{gid}/adjust", json={"bases": [True]}).status_code == 422
    assert client.get("/api/games/doesnotexist").status_code == 404
    assert client.get("/api/games/..%5Cx").status_code in (404, 422)


def test_games_survive_a_server_restart(client, games_dir):
    import velopath.server as server
    gid = client.post("/api/games", json={"away": "Lions"}).json()["id"]
    client.post(f"/api/games/{gid}/pitch", json={"kind": "ball"})
    server.GAMES.clear()  # restart: memory gone, the file remains
    s = client.get(f"/api/games/{gid}").json()
    assert s["balls"] == 1 and s["away"] == "Lions"
    assert client.post(f"/api/games/{gid}/undo").json()["balls"] == 0  # and so does the undo history


def test_pitch_can_carry_the_measured_pitch_into_the_log(client, games_dir):
    gid = client.post("/api/games", json={}).json()["id"]
    s = client.post(f"/api/games/{gid}/pitch", json={"kind": "strike", "mph": 84.5, "source": "abs"}).json()
    assert s["log"][-1]["mph"] == 84.5 and s["log"][-1]["source"] == "abs"


def test_export_csv(client, games_dir):
    import csv
    import io

    g = client.post("/api/games", json={"away": "Tigers, Detroit", "home": "Lions", "innings": 9}).json()
    gid = g["id"]

    assert client.get("/api/games/nonexistent/export.csv").status_code == 404
    assert client.get("/api/games/..%2Fbad/export.csv").status_code in (404, 422)

    client.post(f"/api/games/{gid}/pitch", json={"kind": "strike", "mph": 85.5, "source": "abs"})
    client.post(f"/api/games/{gid}/pitch", json={"kind": "ball"})

    res = client.get(f"/api/games/{gid}/export.csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert f'filename="game-{gid}.csv"' in res.headers.get("content-disposition", "")

    reader = list(csv.reader(io.StringIO(res.text)))
    assert len(reader) == 3
    assert reader[0] == ["inning", "half", "kind", "balls", "strikes", "outs", "away_runs", "home_runs", "mph", "source"]

    assert reader[1][0] == "1"
    assert reader[1][1] == "top"
    assert reader[1][2] == "strike"
    assert reader[1][8] == "85.5"
    assert reader[1][9] == "abs"

    assert reader[2][2] == "ball"
    assert reader[2][8] == ""
    assert reader[2][9] == ""

