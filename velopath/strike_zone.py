"""
Strike Zone calibration and Automated Ball-Strike (ABS) umpiring evaluation.
"""
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class StrikeZone:
    """Represents a 2D bounding box strike zone."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @classmethod
    def from_batter_height(
        cls,
        batter_height_inches: float,
        home_plate_x: float,
        home_plate_y: float,
        pixels_per_inch: float = 2.5
    ) -> "StrikeZone":
        """
        Calculates dynamic strike zone dimensions based on batter height.
        MLB Rule 3.00:
        Top: Midpoint between shoulders and pants top (~53.5% of height)
        Bottom: Hollow beneath the kneecap (~27% of height)
        Width: 17 inches across home plate.
        """
        width_px = 17.0 * pixels_per_inch
        zone_height_in = (0.535 - 0.270) * batter_height_inches
        height_px = zone_height_in * pixels_per_inch

        x_min = home_plate_x - (width_px / 2.0)
        x_max = home_plate_x + (width_px / 2.0)
        
        # y increases downwards in image coordinates
        y_max = home_plate_y - (0.270 * batter_height_inches * pixels_per_inch)
        y_min = y_max - height_px

        return cls(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)

    @classmethod
    def get_preset_zone(cls, width: int, height: int, view_type: str = "auto") -> "StrikeZone":
        """
        Returns calibrated strike zone for Broadcast or Mobile camera perspective.
        Properly scaled to match regulation MLB home plate and batter strike zone.
        """
        is_broadcast = (view_type == "broadcast") or (view_type == "auto" and (width / float(height)) > 1.3)
        if view_type == "behind_pitcher":
            # Pitcher foreground, batter & catcher in mid-distance in front of net
            cx = width * 0.48
            cy = height * 0.42
            zw = width * 0.14
            zh = height * 0.12
            return cls(
                x_min=cx - (zw / 2.0),
                y_min=cy - (zh / 2.0),
                x_max=cx + (zw / 2.0),
                y_max=cy + (zh / 2.0)
            )
        elif is_broadcast:
            # Broadcast Center-Field Camera (Home plate in front of catcher)
            # Tightly calibrated: 118px wide by 126px tall in 1080p
            cx = width * 0.558
            cy = height * 0.405
            zw = width * 0.062
            zh = height * 0.116
            return cls(
                x_min=cx - (zw / 2.0),
                y_min=cy - (zh / 2.0),
                x_max=cx + (zw / 2.0),
                y_max=cy + (zh / 2.0)
            )
        else:
            # Behind-Home / Mobile Smartphone Camera (Home plate in lower center foreground)
            zone_w = width * 0.24
            zone_h = height * 0.17
            zx_center = width * 0.50
            zy_center = height * 0.68
            return cls(
                x_min=zx_center - (zone_w / 2.0),
                y_min=zy_center - (zone_h / 2.0),
                x_max=zx_center + (zone_w / 2.0),
                y_max=zy_center + (zone_h / 2.0)
            )


@dataclass
class PitchCallResult:
    """Result of strike zone evaluation."""
    is_strike: bool
    call: str  # "STRIKE" or "BALL"
    plate_x: float
    plate_y: float
    zone_x_min: float
    zone_y_min: float
    zone_x_max: float
    zone_y_max: float
    dist_to_center_in: float


def evaluate_pitch(
    plate_cross_point: Tuple[float, float],
    strike_zone: StrikeZone,
    ball_radius: float = 10.0,
    pixels_per_inch: float = 2.5
) -> PitchCallResult:
    """
    Evaluates whether a pitch crossing the plate is a STRIKE or a BALL.
    According to official ABS rules: if ANY part of the baseball intersects
    the strike zone box (including the ball radius buffer), it is a STRIKE.
    """
    bx, by = plate_cross_point

    # Expanded zone by ball radius for full intersection check
    eff_x_min = strike_zone.x_min - ball_radius
    eff_x_max = strike_zone.x_max + ball_radius
    eff_y_min = strike_zone.y_min - ball_radius
    eff_y_max = strike_zone.y_max + ball_radius

    is_strike = (eff_x_min <= bx <= eff_x_max) and (eff_y_min <= by <= eff_y_max)
    call = "STRIKE" if is_strike else "BALL"

    # Distance to center in inches
    center_x = (strike_zone.x_min + strike_zone.x_max) / 2.0
    center_y = (strike_zone.y_min + strike_zone.y_max) / 2.0
    dist_px = ((bx - center_x) ** 2 + (by - center_y) ** 2) ** 0.5
    dist_in = round(float(dist_px / max(pixels_per_inch, 0.1)), 1)

    return PitchCallResult(
        is_strike=is_strike,
        call=call,
        plate_x=bx,
        plate_y=by,
        zone_x_min=strike_zone.x_min,
        zone_y_min=strike_zone.y_min,
        zone_x_max=strike_zone.x_max,
        zone_y_max=strike_zone.y_max,
        dist_to_center_in=dist_in,
    )
