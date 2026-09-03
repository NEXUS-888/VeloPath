import pytest
from velopath.physics import (
    calculate_velocity_mph,
    calculate_velocity_kmh,
    calculate_flight_time_ms,
    calculate_pitch_break,
    classify_pitch_type,
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
