import pytest
from velopath.tracker import interpolate_missing_frames, select_flight, TrajectoryPoint


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


def _frames(hits):
    return [int(h[0]) for h in hits] if hits else None


def test_select_flight_prefers_moving_ball_over_stationary_noise():
    noise = [(f, 1650.0 + (f % 3), 1050.0 + (f % 2), 0.55, 20.0) for f in range(10, 40)]
    pitch = [(f, 1800.0 + (f - 45) * 60.0, 900.0 + (f - 45) * 45.0, 0.6, 25.0) for f in range(45, 53)]
    assert _frames(select_flight(noise + pitch, 3840, 2160)) == list(range(45, 53))


def test_select_flight_returns_none_for_drift_only():
    drift = [(f, 500.0 + (f % 2), 500.0 + (f % 2), 0.3, 10.0) for f in range(10, 20)]
    assert select_flight(drift, 1920, 1080) is None


def test_select_flight_false_hand_hit_does_not_steal_release():
    """Regression for Test !.mp4: a pitcher-hand hit 3 frames before release must not cut the flight start."""
    flight = [(f, 348 + (f - 51) * 31.0, 297 - (f - 51) * 9.0 + 0.9 * (f - 51) ** 2, 0.8, 12.0) for f in range(51, 66)]
    hand = [(48, 434.0, 342.0, 0.71, 14.0), (45, 335.0, 367.0, 0.62, 14.0), (46, 358.0, 385.0, 0.36, 14.0)]
    assert _frames(select_flight(sorted(hand + flight), 1280, 720)) == list(range(51, 66))


def test_select_flight_any_direction():
    """Camera-angle agnostic: right-to-left and upward flights are flights too."""
    leftward = [(f, 1000.0 - (f - 20) * 50.0, 300.0 + (f - 20) * 4.0, 0.7, 12.0) for f in range(20, 34)]
    upward = [(f, 960.0 + (f - 20) * 5.0, 700.0 - (f - 20) * 35.0, 0.6, 15.0) for f in range(20, 30)]
    assert _frames(select_flight(leftward, 1280, 720)) == list(range(20, 34))
    assert _frames(select_flight(upward, 1920, 1080)) == list(range(20, 30))


def test_select_flight_picks_on_path_hit_per_frame():
    flight = [(f, 100.0 + f * 20.0, 300.0 + f * 5.0, 0.5, 10.0) for f in range(10)]
    clutter = [(f, 900.0, 100.0 + f * 3.0, 0.9, 10.0) for f in range(10)]
    got = select_flight(flight + clutter, 1280, 720)
    assert _frames(got) == list(range(10)) and all(h[1] < 400 for h in got)



def test_select_flight_accepts_ball_flying_away_from_camera():
    """Behind-pitcher phone view: the ball barely moves in the image but shrinks 31px -> 14px."""
    away = [(f, 545.0 - (f - 55), 756.0 - 3.0 * (f - 55) + 0.1 * (f - 55) ** 2, 0.7, 31.0 - 0.6 * (f - 55))
            for f in range(55, 84)]
    logo = [(f, 300.0 + (f % 2), 300.0, 0.8, 20.0) for f in range(0, 60)]
    assert _frames(select_flight(logo + away, 1080, 1920)) == list(range(55, 84))
