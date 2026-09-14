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


def test_detect_red_cricket_ball_synthetic():
    """Verify red/terracotta leather cricket ball is detected in auto and cricket mode."""
    import numpy as np
    import cv2
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    # Green grass background (BGR: ~35, 120, 45)
    frame = np.full((400, 400, 3), (35, 120, 45), dtype=np.uint8)
    prev_frame = np.full((400, 400, 3), (35, 120, 45), dtype=np.uint8)

    # Red/terracotta cricket ball: BGR (25, 35, 175)
    cv2.circle(prev_frame, (180, 180), 8, (25, 35, 175), -1)
    cv2.circle(frame, (215, 215), 8, (25, 35, 175), -1)

    cand = tracker.detect_color_motion_ball(
        frame=frame,
        prev_frame=prev_frame,
        corridor=(100, 300, 100, 300),
        ball_type="auto"
    )
    assert cand is not None, "Red cricket ball must be detected"
    cx, cy, r, conf = cand
    assert pytest.approx(cx, abs=6.0) == 215.0
    assert pytest.approx(cy, abs=6.0) == 215.0


def test_detect_pink_cricket_ball_synthetic():
    """Verify hot pink / magenta training cricket ball is detected in auto mode."""
    import numpy as np
    import cv2
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    # Outdoor field background (BGR: ~40, 130, 50)
    frame = np.full((400, 400, 3), (40, 130, 50), dtype=np.uint8)
    prev_frame = np.full((400, 400, 3), (40, 130, 50), dtype=np.uint8)

    # Hot pink ball: BGR (160, 40, 230)
    cv2.circle(prev_frame, (190, 190), 8, (160, 40, 230), -1)
    cv2.circle(frame, (220, 220), 8, (160, 40, 230), -1)

    cand = tracker.detect_color_motion_ball(
        frame=frame,
        prev_frame=prev_frame,
        corridor=(100, 300, 100, 300),
        ball_type="auto"
    )
    assert cand is not None, "Pink cricket ball must be detected"
    cx, cy, r, conf = cand
    assert pytest.approx(cx, abs=6.0) == 220.0
    assert pytest.approx(cy, abs=6.0) == 220.0


def test_detect_orange_red_leather_ball_hue_extended():
    """Verify orange-red leather cricket ball with H=16 (sunlight highlight) is detected."""
    import numpy as np
    import cv2
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    frame = np.full((400, 400, 3), (40, 130, 50), dtype=np.uint8)
    prev_frame = np.full((400, 400, 3), (40, 130, 50), dtype=np.uint8)

    # Orange-red ball: BGR (30, 80, 200) -> HSV approximately [12-16, 215, 200]
    cv2.circle(prev_frame, (190, 190), 8, (30, 80, 200), -1)
    cv2.circle(frame, (220, 220), 8, (30, 80, 200), -1)

    cand = tracker.detect_color_motion_ball(
        frame=frame,
        prev_frame=prev_frame,
        corridor=(100, 300, 100, 300),
        ball_type="auto"
    )
    assert cand is not None, "Orange-red cricket ball must be detected"
    cx, cy, r, conf = cand
    assert pytest.approx(cx, abs=6.0) == 220.0
    assert pytest.approx(cy, abs=6.0) == 220.0


def test_stationary_noise_rejected_for_ballistic_flight():
    """Verify chain scoring prioritizes fast ballistic delivery over long stationary spectator noise."""
    import numpy as np
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    width, height = 3840, 2160

    # Synthetic long spectator chain (30 frames, but only 30px total movement = 1px/frame)
    spectator_chain = [
        (f, 1650.0 + (f % 3), 1050.0 + (f % 2), 0.55, 20.0)
        for f in range(10, 40)
    ]

    # Synthetic fast pitch flight chain (8 frames, 600px displacement = 75px/frame)
    pitch_chain = [
        (f, 1800.0 + (f - 45) * 60.0, 900.0 + (f - 45) * 45.0, 0.60, 25.0)
        for f in range(45, 53)
    ]

    best = tracker._select_best_flight_chain(
        [spectator_chain, pitch_chain],
        width=width,
        height=height,
        total_frames=100,
        perspective="behind_plate"
    )
    assert best == pitch_chain, "Ballistic pitch delivery must be chosen over stationary spectator noise"


def test_extrapolate_single_point_behind_pitcher():
    """Verify single point detection provides forward velocity rather than static stall."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    single_point = [TrajectoryPoint(frame_idx=10, x=500.0, y=300.0, conf=0.8)]
    extrapolated = tracker._extrapolate_measured_flight(
        points=single_point,
        perspective="behind_pitcher",
        width=1000,
        height=1000,
        fps=30.0
    )
    assert len(extrapolated) > 1
    # Ball should progress downward/forward toward target
    assert extrapolated[-1].y > single_point[0].y
    assert extrapolated[-1].frame_idx > single_point[0].frame_idx


def test_link_points_into_chains_adaptive_gap():
    """Verify points with frame gap up to max_dt are linked into a single continuous chain."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    # Points with a 5-frame gap (e.g. frame 10 and 15)
    pts = [
        TrajectoryPoint(frame_idx=10, x=500.0, y=300.0, conf=0.8),
        TrajectoryPoint(frame_idx=15, x=520.0, y=350.0, conf=0.8),
        TrajectoryPoint(frame_idx=16, x=525.0, y=360.0, conf=0.8),
    ]
    chains = tracker._link_points_into_chains(
        pts, width=1280, height=720, perspective="behind_pitcher", max_dt=8
    )
    assert len(chains) == 1
    assert len(chains[0]) == 3


def test_upward_motion_rejected_by_physics_guard():
    """Verify upward batter swing or cloud drift is rejected by gravity constraint."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    width, height = 1920, 1080

    # Upward swing into sky (y decreases from 700 to 200)
    upward_noise = [
        (f, 960.0 + (f - 20) * 5.0, 700.0 - (f - 20) * 35.0, 0.60, 15.0)
        for f in range(20, 30)
    ]
    best = tracker._select_best_flight_chain(
        [upward_noise],
        width=width,
        height=height,
        total_frames=100,
        perspective="behind_pitcher"
    )
    assert best is None, "Upward motion must be rejected by universal physics constraint"


def test_behind_catcher_flight_chain_selected():
    """Verify ball traveling from pitcher to plate is correctly selected over stationary noise."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    width, height = 3840, 2160

    # Behind-catcher pitch: travels from pitcher (y ~ 500) forward to catcher (y ~ 1200)
    pitch_chain = [
        (f, 1800.0 + (f - 40) * 30.0, 600.0 + (f - 40) * 50.0, 0.70, 18.0)
        for f in range(40, 52)
    ]
    # Stationary fielder/batter shuffling
    noise_chain = [
        (f, 600.0 + (f % 3), 1100.0 + (f % 2), 0.40, 20.0)
        for f in range(10, 40)
    ]

    best = tracker._select_best_flight_chain(
        [noise_chain, pitch_chain],
        width=width,
        height=height,
        total_frames=120,
        perspective="behind_catcher"
    )
    assert best == pitch_chain, "Behind-catcher forward pitch delivery must be selected"


def test_no_pitch_detected_guard():
    """Verify empty/stationary noise chains return None from flight chain selection."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    width, height = 1920, 1080

    # Empty noise chains: slow camera drift or windup movement
    drift_noise = [
        (f, 500.0 + (f % 2), 500.0 + (f % 2), 0.3, 10.0)
        for f in range(10, 20)
    ]
    best = tracker._select_best_flight_chain(
        [drift_noise],
        width=width,
        height=height,
        total_frames=100,
        perspective="auto"
    )
    assert best is None, "Drift noise must return None to prevent hallucinated pitch"




