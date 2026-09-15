"""
End-to-end processing pipeline: Tracks ball, calculates speed, tests strike zone, and renders video.
"""
from typing import Dict, Any, Optional, Tuple, List
import os
import cv2
import numpy as np

from velopath.tracker import PitchTracker, TrajectoryPoint, interpolate_missing_frames, smooth_trajectory
from velopath.physics import (
    calculate_velocity_mph,
    calculate_velocity_kmh,
    calculate_flight_time_ms,
    calculate_pitch_break,
    classify_pitch_type,
    calculate_advanced_velocity,
    estimate_trajectory_coverage,
)
from velopath.strike_zone import StrikeZone, evaluate_pitch, PitchCallResult
from velopath.renderer import PitchRenderer


def find_plate_crossing_point(
    trajectory_points: List[TrajectoryPoint],
    strike_zone: StrikeZone,
    ball_radius: float = 12.0
) -> Tuple[float, float]:
    """
    Finds the trajectory point that crosses home plate and the strike zone.
    If the pitch passes through the strike zone, returns the intersection point.
    Otherwise, returns the point along the trajectory of closest approach to the strike zone center.
    """
    if not trajectory_points:
        return ((strike_zone.x_min + strike_zone.x_max) / 2.0, (strike_zone.y_min + strike_zone.y_max) / 2.0)

    sz_center_x = (strike_zone.x_min + strike_zone.x_max) / 2.0
    sz_center_y = (strike_zone.y_min + strike_zone.y_max) / 2.0

    min_dist = float("inf")
    closest_pt = trajectory_points[-1]
    intersecting_pt = None

    for pt in trajectory_points:
        dist = ((pt.x - sz_center_x) ** 2 + (pt.y - sz_center_y) ** 2) ** 0.5
        if dist < min_dist:
            min_dist = dist
            closest_pt = pt

        if (strike_zone.x_min - ball_radius <= pt.x <= strike_zone.x_max + ball_radius) and \
           (strike_zone.y_min - ball_radius <= pt.y <= strike_zone.y_max + ball_radius):
            if intersecting_pt is None:
                intersecting_pt = pt

    eval_pt = intersecting_pt if intersecting_pt is not None else closest_pt
    return (float(eval_pt.x), float(eval_pt.y))


def process_pitch_video(
    input_video_path: str,
    output_video_path: str,
    distance_ft: float = 60.5,
    custom_strike_zone: Optional[Dict[str, float]] = None,
    pitch_number: int = 1,
    conf_thresh: float = 0.15,
    graphic_style: str = "statcast_cyan",
    ball_type: str = "auto",
    perspective: str = "auto",
    trim_to_pitch: bool = False,
    hud_style: str = "none",
    max_dimension: Optional[int] = 1920,
) -> Dict[str, Any]:
    """
    Complete end-to-end Pitch Lab analysis:
    Tracks ball trajectory, calculates speed (MPH), checks strike zone,
    and renders output video with Statcast 3D streamline and HUD card.
    """
    if not os.path.exists(input_video_path):
        raise FileNotFoundError(f"Video file not found: {input_video_path}")

    tracker = PitchTracker()
    renderer = PitchRenderer(graphic_style=graphic_style)

    # 1. Track ball throughout video
    trajectory_points, fps, (width, height) = tracker.track_video(
        input_video_path,
        conf_thresh=conf_thresh,
        ball_type=ball_type,
        perspective=perspective,
    )

    cap = cv2.VideoCapture(input_video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    if not trajectory_points:
        # Clean No-Pitch handling (e.g. windup drill, truncated clip, or aborted take)
        os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
        out_w, out_h = renderer.render_complete_video(
            input_video_path=input_video_path,
            output_video_path=output_video_path,
            trajectory_points=[],
            velocity_mph=0.0,
            vert_break_in=0.0,
            horz_break_in=0.0,
            strike_zone=None,
            call_result=None,
            pitch_number=pitch_number,
            pitch_tag="No Pitch",
            flight_time_ms=0.0,
            show_strike_zone=False,
            graphic_style=graphic_style,
            trim_to_pitch=False,
            hud_style=hud_style,
            max_dimension=max_dimension,
        )
        return {
            "pitch_detected": False,
            "pitch_number": pitch_number,
            "velocity_mph": 0.0,
            "velocity_kmh": 0.0,
            "plate_velocity_mph": 0.0,
            "plate_velocity_kmh": 0.0,
            "flight_time_ms": 0.0,
            "effective_distance_ft": distance_ft,
            "coverage_fraction": 0.0,
            "sport": "baseball",
            "vert_break_in": 0.0,
            "horz_break_in": 0.0,
            "pitch_tag": "No Pitch",
            "is_strike": False,
            "call": "NO PITCH DETECTED",
            "strike_zone": None,
            "plate_crossing": None,
            "graphic_style": graphic_style,
            "ball_type": ball_type,
            "perspective": perspective,
            "release_frame": 0,
            "plate_frame": 0,
            "elapsed_frames": 0,
            "fps": fps,
            "video_resolution": {"width": out_w, "height": out_h},
            "output_video_path": output_video_path,
            "trajectory": []
        }

    # Only trim if trajectory is excessively long (> 1.5 seconds)
    max_flight_frames = int(round(1.5 * fps))
    if len(trajectory_points) > max_flight_frames:
        best_disp = -1
        best_idx = 0
        for i in range(len(trajectory_points) - max_flight_frames + 1):
            p0 = trajectory_points[i]
            p1 = trajectory_points[i + max_flight_frames - 1]
            disp = (p1.x - p0.x)**2 + (p1.y - p0.y)**2
            if disp > best_disp:
                best_disp = disp
                best_idx = i
        trajectory_points = trajectory_points[best_idx : best_idx + max_flight_frames]

    # 2. Calibrated Strike Zone (Broadcast center-field vs Mobile perspective)
    if custom_strike_zone:
        strike_zone = StrikeZone(
            x_min=custom_strike_zone["x_min"],
            y_min=custom_strike_zone["y_min"],
            x_max=custom_strike_zone["x_max"],
            y_max=custom_strike_zone["y_max"],
        )
    else:
        resolved_perspective = getattr(tracker, "last_resolved_perspective", None) or perspective
        plate_pt_hint = (trajectory_points[-1].x, trajectory_points[-1].y) if trajectory_points else None
        strike_zone = StrikeZone.get_preset_zone(
            width, height, view_type=resolved_perspective, plate_point=plate_pt_hint
        )

    # 3. Physically Grounded Timing & Aerodynamic Velocity
    release_frame = trajectory_points[0].frame_idx
    plate_frame = trajectory_points[-1].frame_idx
    elapsed_frames = max(1, plate_frame - release_frame)

    # Measured elapsed flight time
    cov = 1.0

    vel_data = calculate_advanced_velocity(
        distance_ft=distance_ft,
        elapsed_frames=float(elapsed_frames),
        fps=fps,
        coverage_fraction=cov,
        ball_type=ball_type
    )

    velocity_mph = vel_data["release_velocity_mph"]
    velocity_kmh = vel_data["release_velocity_kmh"]
    plate_velocity_mph = vel_data["plate_velocity_mph"]
    plate_velocity_kmh = vel_data["plate_velocity_kmh"]
    flight_time_ms = vel_data["flight_time_ms"]

    # 4. Pitch Movement & Break
    coords = [(p.x, p.y) for p in trajectory_points]
    px_per_in = max(0.5, (height * 0.15) / 17.0)
    horz_break_in, vert_break_in = calculate_pitch_break(coords, pixels_per_inch=px_per_in)
    pitch_tag = classify_pitch_type(velocity_mph, vert_break_in, horz_break_in)

    # Evaluate crossing point at home plate
    plate_pt = find_plate_crossing_point(trajectory_points, strike_zone, ball_radius=12.0)
    call_result = evaluate_pitch(
        plate_cross_point=plate_pt,
        strike_zone=strike_zone,
        ball_radius=12.0,
        pixels_per_inch=px_per_in
    )

    # 5. Render final Pitch Lab video
    os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
    out_w, out_h = renderer.render_complete_video(
        input_video_path=input_video_path,
        output_video_path=output_video_path,
        trajectory_points=trajectory_points,
        velocity_mph=velocity_mph,
        vert_break_in=vert_break_in,
        horz_break_in=horz_break_in,
        strike_zone=strike_zone,
        call_result=call_result,
        pitch_number=pitch_number,
        pitch_tag=pitch_tag,
        flight_time_ms=flight_time_ms,
        show_strike_zone=True,
        graphic_style=graphic_style,
        trim_to_pitch=trim_to_pitch,
        hud_style=hud_style,
        max_dimension=max_dimension,
    )

    scale_x = out_w / float(width) if width > 0 else 1.0
    scale_y = out_h / float(height) if height > 0 else 1.0

    return {
        "pitch_detected": True,
        "pitch_number": pitch_number,
        "velocity_mph": velocity_mph,
        "velocity_kmh": velocity_kmh,
        "plate_velocity_mph": plate_velocity_mph,
        "plate_velocity_kmh": plate_velocity_kmh,
        "flight_time_ms": flight_time_ms,
        "effective_distance_ft": vel_data["effective_distance_ft"],
        "coverage_fraction": vel_data["coverage_fraction"],
        "sport": vel_data["sport"],
        "vert_break_in": vert_break_in,
        "horz_break_in": horz_break_in,
        "pitch_tag": pitch_tag,
        "is_strike": call_result.is_strike,
        "call": call_result.call,
        "strike_zone": {
            "x_min": round(strike_zone.x_min * scale_x, 1),
            "y_min": round(strike_zone.y_min * scale_y, 1),
            "x_max": round(strike_zone.x_max * scale_x, 1),
            "y_max": round(strike_zone.y_max * scale_y, 1),
        },
        "plate_crossing": {
            "x": round(plate_pt[0] * scale_x, 1),
            "y": round(plate_pt[1] * scale_y, 1),
        },
        "graphic_style": graphic_style,
        "ball_type": ball_type,
        "perspective": resolved_perspective,
        "release_frame": release_frame,
        "plate_frame": plate_frame,
        "elapsed_frames": elapsed_frames,
        "fps": fps,
        "video_resolution": {"width": out_w, "height": out_h},
        "output_video_path": output_video_path,
        "trajectory": [
            {"frame": p.frame_idx, "x": round(p.x * scale_x, 1), "y": round(p.y * scale_y, 1)}
            for p in trajectory_points
        ]
    }


def _detect_motion_arc(
    video_path: str,
    total_frames: int,
    width: int,
    height: int
) -> list:
    """
    Fallback optical motion arc detector to track the ball when YOLO confidence
    drops due to low lighting or motion blur.
    """
    cap = cv2.VideoCapture(video_path)
    prev = None
    motion_pts = []
    f_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 0)

        if prev is not None:
            diff = cv2.absdiff(prev, gray)
            _, thresh = cv2.threshold(diff, 28, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter contours by small circular ball size scaled to resolution
            scale_area = max(0.5, (width * height) / (1280.0 * 720.0))
            candidates = []
            for c in contours:
                area = cv2.contourArea(c)
                if (15.0 * scale_area) <= area <= (1200.0 * scale_area):
                    (x, y), radius = cv2.minEnclosingCircle(c)
                    candidates.append((x, y, radius, area))

            if candidates:
                # Pick candidate closest to previous motion point if available
                if motion_pts:
                    last_pt = motion_pts[-1]
                    best = min(candidates, key=lambda c: (c[0] - last_pt.x)**2 + (c[1] - last_pt.y)**2)
                else:
                    best = max(candidates, key=lambda c: c[3])
                motion_pts.append(
                    TrajectoryPoint(frame_idx=f_idx, x=float(best[0]), y=float(best[1]), conf=0.7)
                )
        prev = gray
        f_idx += 1

    cap.release()
    if len(motion_pts) >= 4:
        smoothed = smooth_trajectory(motion_pts)
        return smoothed
    return []


def rerender_pitch(
    input_video_path: str,
    output_video_path: str,
    trajectory: list,
    distance_ft: float,
    custom_strike_zone: dict,
    graphic_style: str = "statcast_cyan",
    pitch_number: int = 1,
    ball_type: str = "auto",
    perspective: str = "auto",
    trim_to_pitch: bool = False,
    hud_style: str = "none",
    max_dimension: Optional[int] = 1920,
) -> dict:
    """
    Fast re-render using existing tracked trajectory and updated strike zone or graphic theme.
    """
    pts = [
        TrajectoryPoint(frame_idx=int(p["frame"]), x=float(p["x"]), y=float(p["y"]), conf=0.9)
        for p in trajectory
    ]
    cap = cv2.VideoCapture(input_video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    strike_zone = StrikeZone(
        x_min=float(custom_strike_zone["x_min"]),
        y_min=float(custom_strike_zone["y_min"]),
        x_max=float(custom_strike_zone["x_max"]),
        y_max=float(custom_strike_zone["y_max"]),
    )

    release_frame = pts[0].frame_idx
    plate_frame = pts[-1].frame_idx
    elapsed_frames = max(1, plate_frame - release_frame)

    # Measured elapsed flight time
    cov = 1.0

    vel_data = calculate_advanced_velocity(
        distance_ft=distance_ft,
        elapsed_frames=float(elapsed_frames),
        fps=fps,
        coverage_fraction=cov,
        ball_type=ball_type
    )

    velocity_mph = vel_data["release_velocity_mph"]
    velocity_kmh = vel_data["release_velocity_kmh"]
    plate_velocity_mph = vel_data["plate_velocity_mph"]
    plate_velocity_kmh = vel_data["plate_velocity_kmh"]
    flight_time_ms = vel_data["flight_time_ms"]

    coords = [(p.x, p.y) for p in pts]
    px_per_in = max(0.5, (height * 0.15) / 17.0)
    horz_break_in, vert_break_in = calculate_pitch_break(coords, pixels_per_inch=px_per_in)
    pitch_tag = classify_pitch_type(velocity_mph, vert_break_in, horz_break_in)

    plate_pt = find_plate_crossing_point(pts, strike_zone, ball_radius=12.0)
    call_result = evaluate_pitch(
        plate_cross_point=plate_pt,
        strike_zone=strike_zone,
        ball_radius=12.0,
        pixels_per_inch=px_per_in
    )

    renderer = PitchRenderer(graphic_style=graphic_style)
    out_w, out_h = renderer.render_complete_video(
        input_video_path=input_video_path,
        output_video_path=output_video_path,
        trajectory_points=pts,
        velocity_mph=velocity_mph,
        vert_break_in=vert_break_in,
        horz_break_in=horz_break_in,
        strike_zone=strike_zone,
        call_result=call_result,
        pitch_number=pitch_number,
        pitch_tag=pitch_tag,
        flight_time_ms=flight_time_ms,
        show_strike_zone=True,
        graphic_style=graphic_style,
        trim_to_pitch=trim_to_pitch,
        hud_style=hud_style,
        max_dimension=max_dimension,
    )

    return {
        "pitch_number": pitch_number,
        "velocity_mph": velocity_mph,
        "velocity_kmh": velocity_kmh,
        "plate_velocity_mph": plate_velocity_mph,
        "plate_velocity_kmh": plate_velocity_kmh,
        "flight_time_ms": flight_time_ms,
        "effective_distance_ft": vel_data["effective_distance_ft"],
        "coverage_fraction": vel_data["coverage_fraction"],
        "sport": vel_data["sport"],
        "vert_break_in": vert_break_in,
        "horz_break_in": horz_break_in,
        "pitch_tag": pitch_tag,
        "is_strike": call_result.is_strike,
        "call": call_result.call,
        "strike_zone": {
            "x_min": round(strike_zone.x_min, 1),
            "y_min": round(strike_zone.y_min, 1),
            "x_max": round(strike_zone.x_max, 1),
            "y_max": round(strike_zone.y_max, 1),
        },
        "plate_crossing": {
            "x": round(plate_pt[0], 1),
            "y": round(plate_pt[1], 1),
        },
        "graphic_style": graphic_style,
        "ball_type": ball_type,
        "perspective": perspective,
        "release_frame": release_frame,
        "plate_frame": plate_frame,
        "elapsed_frames": elapsed_frames,
        "fps": fps,
        "video_resolution": {"width": out_w, "height": out_h},
        "output_video_path": output_video_path,
        "trajectory": trajectory,
    }
