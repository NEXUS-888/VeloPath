"""
Physics and kinematics engine for pitch velocity, flight time, and movement break calculation.
"""
from typing import List, Tuple
import numpy as np


def calculate_velocity_mph(distance_ft: float, frames: int, fps: float) -> float:
    """
    Calculate pitch velocity in Miles Per Hour (MPH).
    
    Args:
        distance_ft: Pitch flight distance in feet (e.g., 60.5 for MLB, 43.0 for softball).
        frames: Number of elapsed frames between pitch release and plate arrival.
        fps: Frame rate of the video (e.g. 30.0, 60.0, 120.0).
        
    Returns:
        Velocity in MPH (rounded to 1 decimal place).
    """
    if frames <= 0:
        raise ValueError("Frames elapsed must be strictly positive.")
    if distance_ft <= 0:
        raise ValueError("Distance must be strictly positive.")
    if fps <= 0:
        raise ValueError("FPS must be strictly positive.")
        
    time_seconds = frames / fps
    velocity_fps = distance_ft / time_seconds # feet per second
    velocity_mph = velocity_fps * (3600.0 / 5280.0) # 1 ft/s = 0.681818 MPH
    return round(float(velocity_mph), 1)


def calculate_velocity_kmh(velocity_mph: float) -> float:
    """Convert velocity from MPH to km/h."""
    return round(float(velocity_mph * 1.60934), 1)


def calculate_flight_time_ms(frames: int, fps: float) -> float:
    """Calculate flight time in milliseconds."""
    if frames < 0 or fps <= 0:
        raise ValueError("Invalid frames or fps.")
    return round(float((frames / fps) * 1000.0), 1)


def calculate_pitch_break(
    trajectory_points: List[Tuple[float, float]],
    pixels_per_inch: float = 2.5
) -> Tuple[float, float]:
    """
    Calculate the horizontal and vertical pitch movement (break) relative to a
    hypothetical straight linear trajectory from release to plate.
    
    Args:
        trajectory_points: List of (x, y) coordinates from release to plate.
        pixels_per_inch: Spatial calibration factor.
        
    Returns:
        (horizontal_break_inches, vertical_break_inches)
    """
    if len(trajectory_points) < 3 or pixels_per_inch <= 0:
        return (0.0, 0.0)
        
    p_start = np.array(trajectory_points[0], dtype=np.float64)
    p_end = np.array(trajectory_points[-1], dtype=np.float64)
    
    # Linear baseline vector
    line_vec = p_end - p_start
    line_len = np.linalg.norm(line_vec)
    if line_len == 0:
        return (0.0, 0.0)
        
    # Calculate midpoint or maximum deviation
    # In pixel coordinates: x increases rightward, y increases downward
    mid_idx = len(trajectory_points) // 2
    actual_mid = np.array(trajectory_points[mid_idx], dtype=np.float64)
    
    # Expected linear position at this fraction of the flight
    fraction = mid_idx / (len(trajectory_points) - 1)
    linear_pos = p_start + fraction * line_vec
    
    deviation = actual_mid - linear_pos
    
    # Horizontal break: positive means breaking to the right, negative to the left
    horz_in = round(float(deviation[0] / pixels_per_inch), 1)
    # Vertical break: positive means breaking downward (drop), negative means rising
    vert_in = round(float(deviation[1] / pixels_per_inch), 1)
    
    return (horz_in, vert_in)


def classify_pitch_type(velocity_mph: float, vert_break_in: float, horz_break_in: float) -> str:
    """
    Classify pitch type based on velocity and break characteristics.
    """
    if velocity_mph >= 85.0:
        if abs(horz_break_in) >= 4.0:
            return "Cutter" if horz_break_in < 0 else "Sinker"
        return "Fastball"
    elif velocity_mph >= 70.0:
        if vert_break_in >= 5.0 and abs(horz_break_in) >= 3.0:
            return "Curveball"
        elif abs(horz_break_in) >= 5.0:
            return "Slider"
        return "Changeup"
    else:
        # Slower pitch / softball / youth
        if vert_break_in >= 6.0:
            return "Dropball"
        elif abs(horz_break_in) >= 4.0:
            return "Sweeper"
        return "Off-speed"
