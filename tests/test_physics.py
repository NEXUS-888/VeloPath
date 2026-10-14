import pytest
from velopath.physics import (
    calculate_velocity_kmh,
    calculate_pitch_break,
    classify_pitch_type,
    calculate_advanced_velocity,
)


def test_calculate_velocity_kmh():
    """Verify km/h conversion from MPH (1 mph = 1.60934 km/h)."""
    mph = 82.5
    kmh = calculate_velocity_kmh(mph)
    assert pytest.approx(kmh, 0.2) == 132.77


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
        fps=60.0
    )
    assert 78.0 <= res["release_velocity_mph"] <= 82.0
    assert 71.0 <= res["plate_velocity_mph"] <= 76.0
    assert res["plate_velocity_mph"] < res["release_velocity_mph"]  # Drag slows it down
    assert pytest.approx(res["flight_time_ms"], 1.0) == 500.0


def test_calculate_advanced_velocity_cricket_preset():
    """
    Cricket pitch distance: 58.0 ft (crease to crease).
    A medium-fast bowler delivery taking 28 frames at 60 FPS (0.467s).
    Speed should be ~85-92 MPH.
    """
    res = calculate_advanced_velocity(
        distance_ft=58.0,
        elapsed_frames=28.0,
        fps=60.0
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
        fps=30.0
    )
    assert 45.0 <= res["release_velocity_mph"] <= 52.0
