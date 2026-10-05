"""ABS call must come from real geometry (home plate or a user-set zone), never from the ball itself."""
import cv2
import numpy as np
import pytest
from unittest.mock import patch

from velopath.pipeline import process_pitch_video, rerender_pitch
from velopath.tracker import PitchTracker, TrajectoryPoint

W, H = 640, 360
# Plate centred (320, 300), 34px wide -> 2 px/in. 72in batter -> zone x 303..337, y ~223..261.
PLATE = (320.0, 300.0, 34.0)


@pytest.fixture
def blank_video(tmp_path):
    path = str(tmp_path / "blank.mp4")
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 30, (W, H))
    for _ in range(30):
        out.write(np.zeros((H, W, 3), dtype=np.uint8))
    out.release()
    return path


def flight(end_x, end_y, n=15):
    """Straight flight from the left edge ending at (end_x, end_y)."""
    return [TrajectoryPoint(frame_idx=5 + i, x=40 + (end_x - 40) * i / (n - 1), y=200 + (end_y - 200) * i / (n - 1))
            for i in range(n)]


def run(video, tmp_path, pts, plate, **kw):
    class FakeTracker:
        last_resolved_perspective = "broadcast"
        last_plate = plate

        def track_video(self, *a, **k):
            return pts, 30.0, (W, H)

    with patch("velopath.pipeline.get_tracker", FakeTracker):
        return process_pitch_video(video, str(tmp_path / "out.mp4"), max_dimension=None, **kw)


def test_plate_anchored_zone_calls_strike(blank_video, tmp_path):
    res = run(blank_video, tmp_path, flight(320, 240), PLATE)
    assert res["zone_calibrated"] is True
    assert res["call"] == "STRIKE"
    z = res["strike_zone"]
    assert z["x_min"] == pytest.approx(303, abs=1) and z["x_max"] == pytest.approx(337, abs=1)
    assert z["y_max"] == pytest.approx(300 - 0.27 * 72 * 2, abs=1)


def test_plate_anchored_zone_calls_ball_for_high_pitch(blank_video, tmp_path):
    """Old pipeline centred the zone on the last ball point, so this was always a STRIKE."""
    res = run(blank_video, tmp_path, flight(320, 150), PLATE)
    assert res["call"] == "BALL"
    assert res["is_strike"] is False


def test_no_plate_no_zone_makes_no_call(blank_video, tmp_path):
    res = run(blank_video, tmp_path, flight(320, 240), None)
    assert res["zone_calibrated"] is False
    assert res["is_strike"] is False
    assert res["call"] == "SET ZONE"
    assert res["strike_zone"] is not None  # a starting guess the user can drag


def test_custom_zone_is_a_calibrated_call(blank_video, tmp_path):
    zone = {"x_min": 300, "y_min": 100, "x_max": 340, "y_max": 160}
    res = run(blank_video, tmp_path, flight(320, 150), None, custom_strike_zone=zone)
    assert res["zone_calibrated"] is True
    assert res["call"] == "STRIKE"


def test_rerender_judges_plate_crossing_not_any_point_in_zone(blank_video, tmp_path):
    """Ball passes through the zone mid-flight but crosses the plate far below it: BALL."""
    traj = [{"frame": 5 + i, "x": 40 + 40 * i, "y": 130 + 15 * i} for i in range(14)]  # ends (560, 325)
    zone = {"x_min": 150, "y_min": 140, "x_max": 250, "y_max": 220}  # traj passes (200, 182)
    res = rerender_pitch(blank_video, str(tmp_path / "re.mp4"), traj, 60.5, zone, max_dimension=None)
    assert res["call"] == "BALL"
    assert res["zone_calibrated"] is True
    assert res["plate_crossing"] == {"x": 560, "y": 325}


class _Boxes:
    def __init__(self, rows):
        self.xyxy = np.array([r[2:] for r in rows], dtype=float).reshape(-1, 4)
        self.conf = np.array([r[1] for r in rows], dtype=float)
        self.cls = np.array([r[0] for r in rows], dtype=float)


class _FakeModel:
    """Every frame: a static home plate box; a ball moving across frames 5..20."""
    names = {0: "glove", 1: "homeplate", 2: "baseball", 3: "rubber"}

    def __init__(self):
        self.f = -1

    def predict(self, img, classes=None, **kw):
        if img.shape[:2] == (H, W):  # full-frame scan; refine windows are smaller crops
            self.f += 1
        rows = [(1, 0.8, 303, 295, 337, 305)]
        if 5 <= self.f <= 20:
            x, y = 40 + 30 * (self.f - 5), 150 + 4 * (self.f - 5)
            rows.append((2, 0.9, x - 5, y - 5, x + 5, y + 5))
        rows = [r for r in rows if classes is None or r[0] in classes]
        return [type("R", (), {"boxes": _Boxes(rows)})()]


def test_tracker_reports_home_plate_from_its_scan(blank_video):
    tracker = PitchTracker.__new__(PitchTracker)
    tracker.model, tracker.device, tracker._normal_model = _FakeModel(), "cpu", None
    tracker.track_video(blank_video)
    assert tracker.last_plate == pytest.approx(PLATE, abs=0.5)


def test_pipeline_reuses_one_tracker_across_videos(blank_video, tmp_path):
    """Loading YOLO per request costs seconds; the pipeline keeps one tracker."""
    import velopath.pipeline as pipeline
    built = []

    class CountingTracker:
        last_resolved_perspective, last_plate = "broadcast", None

        def __init__(self):
            built.append(self)

        def track_video(self, *a, **k):
            return flight(320, 240), 30.0, (W, H)

    pipeline.get_tracker.cache_clear()
    try:
        with patch("velopath.pipeline.PitchTracker", CountingTracker):
            for _ in range(2):
                process_pitch_video(blank_video, str(tmp_path / "out.mp4"), max_dimension=None)
    finally:
        pipeline.get_tracker.cache_clear()
    assert len(built) == 1
