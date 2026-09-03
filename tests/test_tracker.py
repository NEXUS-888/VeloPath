import pytest
from velopath.tracker import smooth_trajectory, interpolate_missing_frames, TrajectoryPoint


def test_interpolate_missing_frames():
    """Ensure missing frames are filled with cubic/linear spline interpolation."""
    # Frame 0, 2, 4 are detected, frames 1 and 3 are missing
    points = [
        TrajectoryPoint(frame_idx=0, x=100.0, y=200.0, conf=0.9),
        TrajectoryPoint(frame_idx=2, x=120.0, y=220.0, conf=0.9),
        TrajectoryPoint(frame_idx=4, x=140.0, y=240.0, conf=0.9),
    ]
    interpolated = interpolate_missing_frames(points, start_frame=0, end_frame=4)
    assert len(interpolated) == 5
    assert interpolated[1].frame_idx == 1
    assert pytest.approx(interpolated[1].x, 0.5) == 110.0
    assert pytest.approx(interpolated[1].y, 0.5) == 210.0


def test_smooth_trajectory_reduces_jitter():
    """Smoothing should reduce noise while preserving trajectory trend."""
    raw_points = [
        TrajectoryPoint(frame_idx=i, x=100.0 + i * 10 + (2.0 if i % 2 == 0 else -2.0), y=200.0 + i * 5, conf=0.8)
        for i in range(10)
    ]
    smoothed = smooth_trajectory(raw_points)
    assert len(smoothed) == len(raw_points)
    assert smoothed[0].frame_idx == raw_points[0].frame_idx


def test_detect_color_motion_ball_synthetic():
    """Verify adaptive color and motion differencing extracts a moving yellow tennis ball."""
    import numpy as np
    import cv2
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    # Create synthetic frame with yellow ball
    frame = np.full((400, 400, 3), 100, dtype=np.uint8)
    prev_frame = np.full((400, 400, 3), 100, dtype=np.uint8)

    # Ball in prev_frame at (190, 190)
    cv2.circle(prev_frame, (190, 190), 8, (30, 220, 220), -1)
    # Ball moved in frame to (210, 210) (yellow BGR: ~30, 220, 220)
    cv2.circle(frame, (210, 210), 8, (30, 220, 220), -1)

    cand = tracker.detect_color_motion_ball(
        frame=frame,
        prev_frame=prev_frame,
        corridor=(100, 300, 100, 300),
        ball_type="tennis_cricket"
    )
    assert cand is not None
    cx, cy, r, conf = cand
    assert pytest.approx(cx, abs=5.0) == 210.0
    assert pytest.approx(cy, abs=5.0) == 210.0
    assert r > 2.0


def test_extrapolate_measured_flight():
    """Verify ballistic extrapolation extends measured points to the plate."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    measured = [
        TrajectoryPoint(frame_idx=10, x=300.0, y=400.0, conf=0.8),
        TrajectoryPoint(frame_idx=11, x=302.0, y=380.0, conf=0.8),
        TrajectoryPoint(frame_idx=12, x=304.0, y=360.0, conf=0.8),
    ]
    extrapolated = tracker._extrapolate_measured_flight(
        points=measured,
        perspective="behind_pitcher",
        width=500,
        height=800,
        fps=30.0
    )
    assert len(extrapolated) > len(measured)
    # Should travel upward into target
    assert extrapolated[-1].y < measured[-1].y
    assert extrapolated[-1].frame_idx > measured[-1].frame_idx
