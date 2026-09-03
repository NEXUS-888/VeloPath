import pytest
from velopath.strike_zone import StrikeZone, evaluate_pitch


def test_strike_zone_detection_inside():
    """Ball crossing directly in middle of strike zone is a STRIKE."""
    zone = StrikeZone(x_min=100, y_min=200, x_max=200, y_max=350)
    result = evaluate_pitch(plate_cross_point=(150, 275), strike_zone=zone, ball_radius=10)
    assert result.is_strike is True
    assert result.call == "STRIKE"


def test_strike_zone_detection_outside():
    """Ball crossing far outside is a BALL."""
    zone = StrikeZone(x_min=100, y_min=200, x_max=200, y_max=350)
    result = evaluate_pitch(plate_cross_point=(50, 100), strike_zone=zone, ball_radius=10)
    assert result.is_strike is False
    assert result.call == "BALL"


def test_strike_zone_edge_buffer():
    """
    ABS rule: Ball clipping the outside edge by its radius is counted as a STRIKE.
    Zone x_min is 100, ball center is at 95 with radius 10 (extends to 105, overlapping by 5px).
    """
    zone = StrikeZone(x_min=100, y_min=200, x_max=200, y_max=350)
    result = evaluate_pitch(plate_cross_point=(95, 250), strike_zone=zone, ball_radius=10)
    assert result.is_strike is True
    assert result.call == "STRIKE"


def test_strike_zone_dynamic_dimensions():
    """Strike zone top and bottom should scale with batter height."""
    zone = StrikeZone.from_batter_height(batter_height_inches=72.0, home_plate_x=150, home_plate_y=400, pixels_per_inch=3.0)
    assert zone.y_max > zone.y_min
    assert zone.x_max > zone.x_min
