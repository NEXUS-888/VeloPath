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


def estimate_trajectory_coverage(
    trajectory_points: List[Tuple[float, float]],
    tunnel_start_y: float,
    tunnel_end_y: float,
    min_coverage: float = 0.20
) -> float:
    """
    Estimate what fraction of the total pitch tunnel was traversed by the tracked points.
    
    Args:
        trajectory_points: List of (x, y) coordinates.
        tunnel_start_y: Estimated vertical release position.
        tunnel_end_y: Vertical plate / strike zone position.
        min_coverage: Minimum clamp to prevent division by zero or extreme over-scaling.
        
    Returns:
        Coverage fraction in range [min_coverage, 1.0].
    """
    if len(trajectory_points) < 2:
        return 1.0
        
    total_span = abs(tunnel_end_y - tunnel_start_y)
    if total_span < 15.0:
        return 1.0
        
    y_first = trajectory_points[0][1]
    y_last = trajectory_points[-1][1]
    tracked_span = abs(y_last - y_first)
    
    fraction = tracked_span / float(total_span)
    return float(np.clip(fraction, min_coverage, 1.0))


def calculate_advanced_velocity(
    distance_ft: float,
    elapsed_frames: float,
    fps: float,
    coverage_fraction: float = 1.0,
    ball_type: str = "baseball"
) -> dict:
    """
    Physically grounded velocity calculation using Alan Nathan aerodynamic drag model.
    Accounts for:
    1. Pitcher release extension (e.g. 5.5 ft for regulation baseball).
    2. Partial trajectory coverage fraction (prevents partial tracks from exploding speed).
    3. Aerodynamic drag deceleration (release speed vs plate arrival speed).
    
    Args:
        distance_ft: Presumed mound/bowler to plate/crease distance (e.g. 60.5, 58.0, 46.0, 43.0, 35.0).
        elapsed_frames: Number of elapsed frames between first and last tracked detection.
        fps: Video frames per second.
        coverage_fraction: Estimated fraction of the full pitch tunnel tracked (0.1 to 1.0).
        ball_type: 'baseball', 'tennis_cricket', or 'softball'.
        
    Returns:
        Dictionary with:
            release_velocity_mph: Estimated speed at release point (MPH).
            release_velocity_kmh: Speed at release point (km/h).
            plate_velocity_mph: Estimated speed crossing the plate (MPH).
            plate_velocity_kmh: Speed crossing the plate (km/h).
            avg_velocity_mph: Average velocity over the flight (MPH).
            flight_time_ms: Total physical flight time (ms).
            effective_distance_ft: Distance actually traveled by the tracked points (ft).
            coverage_fraction: Coverage ratio applied.
            sport: Detected sport category based on distance.
    """
    if elapsed_frames <= 0 or fps <= 0 or distance_ft <= 0:
        raise ValueError("Inputs must be strictly positive.")

    cov = float(np.clip(coverage_fraction, 0.15, 1.0))

    # Determine sport category and nominal flight tunnel distance (subtracting release extension)
    if distance_ft >= 59.5:
        # MLB / High School / College Baseball (60.5 ft rubber to plate)
        # Pitcher release extension: ~5.5 ft (ball released 55.0 ft from plate)
        nominal_flight_dist = 55.0
        sport = "baseball"
    elif 56.0 <= distance_ft < 59.5:
        # Cricket: bowling crease to popping crease is 58.0 ft
        nominal_flight_dist = 58.0
        sport = "cricket"
    elif 44.0 <= distance_ft < 50.0:
        # Little League / Youth Baseball (46.0 ft rubber to plate)
        nominal_flight_dist = 42.0
        sport = "youth_baseball"
    elif 40.0 <= distance_ft < 44.0:
        # Softball Fastpitch (43.0 ft rubber to plate)
        nominal_flight_dist = 40.0
        sport = "softball"
    else:
        # Casual throw / park / backyard (e.g. 30 - 38 ft)
        nominal_flight_dist = distance_ft
        sport = "casual_throw"

    # Effective distance traversed by the tracked frames
    effective_dist_ft = nominal_flight_dist * cov
    time_s = elapsed_frames / float(fps)

    # Raw average velocity in feet per second
    v_avg_fps = effective_dist_ft / max(0.01, time_s)
    v_avg_mph = v_avg_fps * (3600.0 / 5280.0)

    # Aerodynamic drag adjustment (Alan Nathan model, Cd = 0.31, rho = 1.225 kg/m^3)
    # k_drag approx 0.00115 / ft. Release speed is ~5% higher than average, plate is ~5% lower.
    drag_factor = 0.05 if nominal_flight_dist >= 45.0 else 0.03
    release_mph = round(float(v_avg_mph * (1.0 + drag_factor)), 1)
    plate_mph = round(float(v_avg_mph * (1.0 - drag_factor)), 1)
    avg_mph = round(float(v_avg_mph), 1)

    # Full flight time in ms (actual measured elapsed time)
    full_flight_time_ms = round(float(time_s * 1000.0), 1)

    return {
        "release_velocity_mph": release_mph,
        "release_velocity_kmh": calculate_velocity_kmh(release_mph),
        "plate_velocity_mph": plate_mph,
        "plate_velocity_kmh": calculate_velocity_kmh(plate_mph),
        "avg_velocity_mph": avg_mph,
        "avg_velocity_kmh": calculate_velocity_kmh(avg_mph),
        "flight_time_ms": full_flight_time_ms,
        "effective_distance_ft": round(float(effective_dist_ft), 1),
        "coverage_fraction": round(float(cov), 2),
        "sport": sport
    }


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
