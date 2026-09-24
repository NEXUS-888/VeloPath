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
    """Verify upward batter swing or cloud drift is rejected in behind-catcher view."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    width, height = 1920, 1080

    # Upward swing into sky (y decreases from 700 to 200 in behind_catcher view)
    upward_noise = [
        (f, 960.0 + (f - 20) * 5.0, 700.0 - (f - 20) * 35.0, 0.60, 15.0)
        for f in range(20, 30)
    ]
    best = tracker._select_best_flight_chain(
        [upward_noise],
        width=width,
        height=height,
        total_frames=100,
        perspective="behind_catcher"
    )
    assert best is None, "Upward motion into the sky must be rejected in behind-catcher view"


def test_lateral_motion_is_not_a_pitch():
    """A moving object must progress toward the plate, not merely cross the frame."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    lateral_noise = [
        (f, 30.0 + (f - 10) * 12.0, 740.0, 0.65, 12.0)
        for f in range(10, 18)
    ]

    assert tracker._select_best_flight_chain(
        [lateral_noise], width=384, height=848, total_frames=180,
        perspective="auto", fps=60.0,
    ) is None


def test_behind_pitcher_flight_chain_selected():
    """Verify ball traveling from foreground pitcher to distance plate (dy < 0) is selected in behind-pitcher view."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    width, height = 1920, 1080

    # Real pitch traveling away from camera toward home plate in distance (y from 800 to 450)
    pitch_chain = [
        (f, 960.0 + (f - 30) * 5.0, 800.0 - (f - 30) * 25.0, 0.70, 15.0)
        for f in range(30, 44)
    ]
    # Stationary noise / spectator movement
    noise_chain = [
        (f, 400.0 + (f % 2), 600.0 + (f % 2), 0.40, 15.0)
        for f in range(10, 40)
    ]

    best = tracker._select_best_flight_chain(
        [noise_chain, pitch_chain],
        width=width,
        height=height,
        total_frames=100,
        perspective="behind_pitcher"
    )
    assert best == pitch_chain, "Behind-pitcher pitch delivery towards plate must be selected"


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


def test_broadcast_flight_chain_selected():
    """Verify diagonal pitch delivery from mound across to home plate is selected in broadcast view."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    width, height = 1280, 720

    # Broadcast centerfield pitch: pitcher on left (x~350, y~400) to catcher on right (x~800, y~520)
    pitch_chain = [
        (f, 350.0 + (f - 40) * 35.0, 400.0 + (f - 40) * 10.0, 0.75, 12.0)
        for f in range(40, 53)
    ]
    # Dugout / spectator movement
    noise_chain = [
        (f, 150.0 + (f % 2), 650.0 + (f % 2), 0.35, 15.0)
        for f in range(10, 40)
    ]

    best = tracker._select_best_flight_chain(
        [noise_chain, pitch_chain],
        width=width,
        height=height,
        total_frames=90,
        perspective="auto"
    )
    assert best == pitch_chain, "Broadcast pitch delivery across field must be selected"
    assert tracker.last_resolved_perspective == "broadcast", "Perspective must resolve to broadcast"


def test_normal_mode_tracks_arbitrary_trajectory():
    """
    Verify that casual throws (e.g. right-to-left throw across the frame or upward toss)
    are accepted and scored in normal mode, even though baseball pitch tunnels would reject them.
    """
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    width, height = 1280, 720

    # Right-to-left throw: x decreases from 1000 to 300, slight downward drop y: 300 -> 360
    casual_throw = [
        (f, 1000.0 - (f - 20) * 50.0, 300.0 + (f - 20) * 4.0, 0.7, 12.0)
        for f in range(20, 34)
    ]
    # Stationary noise
    noise_chain = [
        (f, 200.0, 200.0, 0.4, 10.0)
        for f in range(5, 15)
    ]

    # In baseball mode ("auto"), right-to-left throw with dx < -15 and small dy is rejected
    best_baseball = tracker._select_best_flight_chain(
        [noise_chain, casual_throw],
        width=width,
        height=height,
        total_frames=60,
        perspective="auto"
    )
    assert best_baseball is None, "Baseball mode should reject pure right-to-left casual throw"

    # In normal mode ("normal"), casual throw is successfully recognized
    best_normal = tracker._select_best_flight_chain(
        [noise_chain, casual_throw],
        width=width,
        height=height,
        total_frames=60,
        perspective="normal"
    )
    assert best_normal == casual_throw, "Normal mode must track casual right-to-left throw"
    assert tracker.last_resolved_perspective == "normal"


def test_normal_mode_links_reverse_direction_points():
    """Verify points moving in reverse or upward direction are linked when perspective='normal'."""
    from velopath.tracker import PitchTracker

    tracker = PitchTracker()
    points = [
        (10, 800.0, 400.0, 0.8),
        (11, 750.0, 380.0, 0.8),  # dx = -50, dy = -20 (upward and leftward)
        (12, 700.0, 360.0, 0.8),
    ]
    chains = tracker._link_points_into_chains(points, width=1280, height=720, perspective="normal")
    assert len(chains) == 1
    assert len(chains[0]) == 3


def test_pipeline_normal_mode_disables_strike_zone(tmp_path):
    """Verify process_pitch_video with mode='normal' produces BALL TRACKED and disables strike zone overlay."""
    import cv2
    import numpy as np
    from velopath.pipeline import process_pitch_video

    # Generate a synthetic casual video with a ball moving right-to-left
    vid_path = str(tmp_path / "casual_throw.mp4")
    out_path = str(tmp_path / "out_casual.mp4")
    w, h, fps = 640, 360, 30
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(vid_path, fourcc, fps, (w, h))

    for f in range(25):
        frame = np.full((h, w, 3), 60, dtype=np.uint8)
        if 5 <= f <= 20:
            bx = int(500 - (f - 5) * 20)  # right to left: 500 down to 200
            by = int(120 + (f - 5) * 4)
            cv2.circle(frame, (bx, by), 7, (240, 240, 240), -1)
        writer.write(frame)
    writer.release()

    res = process_pitch_video(
        input_video_path=vid_path,
        output_video_path=out_path,
        mode="normal"
    )

    assert res["mode"] == "normal"
    assert res["show_strike_zone"] is False
    assert res["call"] == "BALL TRACKED"
    assert res["pitch_tag"] == "Ball Flight"

