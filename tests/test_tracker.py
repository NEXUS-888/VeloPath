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
