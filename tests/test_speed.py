"""Visible progress while a clip processes."""
import threading

import pytest
from fastapi.testclient import TestClient



def test_progress_endpoint_reports_running_job(monkeypatch, tmp_path):
    import velopath.server as server
    started, release = threading.Event(), threading.Event()

    def slow_pipeline(**kw):
        kw["progress"]("Tracking ball", 0.5)
        started.set()
        release.wait(10)
        return {"pitch_detected": False}

    monkeypatch.setattr(server, "process_pitch_video", slow_pipeline)
    monkeypatch.setattr(server, "UPLOADS_DIR", str(tmp_path))
    with TestClient(server.app) as client:
        out = {}
        upload = threading.Thread(target=lambda: out.update(r=client.post(
            "/api/process", files={"file": ("a.mp4", b"x")}, data={"job_id": "abc123"})))
        upload.start()
        try:
            assert started.wait(5)
            p = client.get("/api/progress/abc123").json()
        finally:
            release.set()
            upload.join()
        assert p["stage"] == "Tracking ball" and p["pct"] == 50 and p["elapsed_s"] >= 0
        assert out["r"].json()["processing_time_s"] >= 0
        assert client.get("/api/progress/abc123").status_code == 404  # finished jobs are dropped


@pytest.mark.parametrize("job_id", ["../x", "a" * 40, "a b"])
def test_process_rejects_unsafe_job_id(job_id, tmp_path, monkeypatch):
    import velopath.server as server
    monkeypatch.setattr(server, "UPLOADS_DIR", str(tmp_path))
    with TestClient(server.app) as client:
        r = client.post("/api/process", files={"file": ("a.mp4", b"x")}, data={"job_id": job_id})
    assert r.status_code == 422


def test_pipeline_reports_stages_in_order(tmp_path):
    from test_abs_call import run, flight
    import cv2
    import numpy as np
    video = str(tmp_path / "v.mp4")
    out = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*"mp4v"), 30, (640, 360))
    for _ in range(30):
        out.write(np.zeros((360, 640, 3), dtype=np.uint8))
    out.release()
    seen = []
    run(video, tmp_path, flight(320, 240), None, progress=lambda stage, pct: seen.append((stage, pct)))
    stages = [s for s, _ in seen]
    assert stages.index("Tracking ball") < stages.index("Rendering video")
    assert seen[-1] == ("Done", 1.0)
    assert [p for _, p in seen] == sorted(p for _, p in seen)


def test_small_model_is_found_only_when_present(tmp_path, monkeypatch):
    import velopath.model_manager as mm
    monkeypatch.setattr(mm, "get_project_root", lambda: str(tmp_path))
    assert mm.resolve_small_model_path() is None
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "ball_small_yolo11s.pt").write_bytes(b"x")
    assert mm.resolve_small_model_path() == str(tmp_path / "models" / "ball_small_yolo11s.pt")
