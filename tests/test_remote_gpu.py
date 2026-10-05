"""Remote GPU worker: the friend's laptop runs worker/velopath_worker.py; RemoteYolo calls it like a local YOLO."""
import importlib.util
import json
import os
import threading

import cv2
import numpy as np
import pytest

from velopath.remote_gpu import RemoteYolo, connect_remote

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
