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
