import pytest
from velopath.physics import (
    calculate_velocity_mph,
    calculate_velocity_kmh,
    calculate_flight_time_ms,
    calculate_pitch_break,
    classify_pitch_type,
    calculate_advanced_velocity,
    estimate_trajectory_coverage,
)


def test_calculate_velocity_mph_regulation():
    """
    Regulation 60.5 ft pitch taking 30 frames at 60 FPS (0.500s flight time).
    v = 60.5 ft / 0.5s = 121 ft/s = 82.5 MPH.
    """
    velocity_mph = calculate_velocity_mph(distance_ft=60.5, frames=30, fps=60.0)
    assert pytest.approx(velocity_mph, 0.2) == 82.5


def test_calculate_velocity_mph_softball():
    """
    Softball 43.0 ft pitch taking 40 frames at 60 FPS (0.666s flight time).
    v = 43 ft / (40/60) = 64.5 ft/s = 43.98 MPH.
    """
    velocity_mph = calculate_velocity_mph(distance_ft=43.0, frames=40, fps=60.0)
    assert pytest.approx(velocity_mph, 0.2) == 44.0


def test_calculate_velocity_kmh():
    """Verify km/h conversion from MPH (1 mph = 1.60934 km/h)."""
    mph = 82.5
    kmh = calculate_velocity_kmh(mph)
    assert pytest.approx(kmh, 0.2) == 132.77


def test_calculate_flight_time_ms():
    """30 frames at 60 FPS = 500 ms."""
    ms = calculate_flight_time_ms(frames=30, fps=60.0)
    assert pytest.approx(ms, 0.1) == 500.0


def test_velocity_zero_frames_raises():
    """Zero or negative frames should raise ValueError."""
    with pytest.raises(ValueError):
        calculate_velocity_mph(distance_ft=60.5, frames=0, fps=60.0)
    with pytest.raises(ValueError):
        calculate_velocity_mph(distance_ft=60.5, frames=-5, fps=60.0)


def test_calculate_pitch_break():
    """
    Test calculating horizontal and vertical movement deviation in inches
    from release point (x0, y0) to plate (x1, y1) relative to linear baseline.
    """
    trajectory = [
        (100.0, 200.0),
        (120.0, 240.0),
        (140.0, 290.0),
        (160.0, 350.0),
    ]
    horz_in, vert_in = calculate_pitch_break(trajectory, pixels_per_inch=2.0)
    assert isinstance(horz_in, float)
    assert isinstance(vert_in, float)


def test_classify_pitch_type():
    """Test pitch type classifier tags."""
    assert classify_pitch_type(velocity_mph=92.0, vert_break_in=-2.0, horz_break_in=1.0) == "Fastball"
    assert classify_pitch_type(velocity_mph=78.0, vert_break_in=8.0, horz_break_in=-4.0) == "Curveball"
    assert classify_pitch_type(velocity_mph=32.0, vert_break_in=12.0, horz_break_in=0.0) == "Dropball"


def test_calculate_advanced_velocity_with_drag():
    """
    Regulation 60.5 ft pitch taking 30 frames at 60 FPS (0.500s).
    Flight distance accounts for release extension (55.0 ft).
    Release speed should be ~78-82 MPH and plate speed should be ~71-76 MPH.
    """
    res = calculate_advanced_velocity(
        distance_ft=60.5,
        elapsed_frames=30.0,
        fps=60.0,
        coverage_fraction=1.0
    )
    assert 78.0 <= res["release_velocity_mph"] <= 82.0
    assert 71.0 <= res["plate_velocity_mph"] <= 76.0
    assert res["plate_velocity_mph"] < res["release_velocity_mph"]  # Drag slows it down
    assert pytest.approx(res["flight_time_ms"], 1.0) == 500.0


def test_calculate_advanced_velocity_partial_coverage():
    """
    CRITICAL REGRESSION TEST:
    A student throws a ball in a park. Total pitch takes ~22 frames at 30 FPS.
    The tracker only captures 11 frames (50% coverage).
    Without coverage scaling, 11 frames over 55 ft would explode to 106.4 MPH.
    WITH coverage fraction = 0.50, speed should be a realistic ~48-55 MPH!
    """
    res = calculate_advanced_velocity(
        distance_ft=60.5,
        elapsed_frames=11.0,
        fps=30.0,
        coverage_fraction=0.50
    )
    assert 48.0 <= res["release_velocity_mph"] <= 56.0
    assert res["release_velocity_mph"] < 65.0  # Must NOT be 100+ MPH!


def test_calculate_advanced_velocity_cricket_preset():
    """
    Cricket pitch distance: 58.0 ft (crease to crease).
    A medium-fast bowler delivery taking 28 frames at 60 FPS (0.467s).
    Speed should be ~85-92 MPH.
    """
    res = calculate_advanced_velocity(
        distance_ft=58.0,
        elapsed_frames=28.0,
        fps=60.0,
        coverage_fraction=1.0
    )
    assert 84.0 <= res["release_velocity_mph"] <= 93.0
    assert res["sport"] == "cricket" or res["effective_distance_ft"] == 58.0


def test_calculate_advanced_velocity_casual_preset():
    """
    Casual park / backyard throw: 35.0 ft.
    A casual throw taking 15 frames at 30 FPS (0.500s).
    Speed should be ~46-51 MPH.
    """
    res = calculate_advanced_velocity(
        distance_ft=35.0,
        elapsed_frames=15.0,
        fps=30.0,
        coverage_fraction=1.0
    )
    assert 45.0 <= res["release_velocity_mph"] <= 52.0


def test_estimate_trajectory_coverage():
    """
    Test calculating the coverage fraction of a tracked trajectory.
    If release is at y=1000, plate is at y=500 (total span 500px).
    If ball tracked from y=750 to y=500 (span 250px), coverage should be 0.50.
    """
    points = [(500.0, 750.0), (500.0, 625.0), (500.0, 500.0)]
    coverage = estimate_trajectory_coverage(
        trajectory_points=points,
        tunnel_start_y=1000.0,
        tunnel_end_y=500.0
    )
    assert pytest.approx(coverage, 0.05) == 0.50

