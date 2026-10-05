"""
End-to-end processing pipeline: Tracks ball, calculates speed, tests strike zone, and renders video.
"""
from typing import Dict, Any, Optional, List
import functools
import os
import threading
import cv2
import numpy as np

from velopath.tracker import PitchTracker, TrajectoryPoint
from velopath.physics import (
    calculate_velocity_mph,
    calculate_velocity_kmh,
    calculate_flight_time_ms,
    calculate_pitch_break,
    classify_pitch_type,
    calculate_advanced_velocity,
    estimate_trajectory_coverage,
)
from velopath.strike_zone import StrikeZone, evaluate_pitch, PitchCallResult, PLATE_WIDTH_IN
from velopath.renderer import PitchRenderer, output_size

BATTER_HEIGHT_IN = 72.0  # ABS uses the batter's listed height; without it assume 6 ft
_TRACK_LOCK = threading.Lock()  # YOLO predict isn't thread-safe and track_video leaves per-run state on the tracker


@functools.lru_cache(maxsize=1)
def get_tracker() -> PitchTracker:
    """One tracker per process: loading YOLO weights costs seconds per request."""
    return PitchTracker()


def judge_pitch(
    points: List[TrajectoryPoint],
    strike_zone: StrikeZone,
    is_normal_mode: bool,
    zone_calibrated: bool,
) -> PitchCallResult:
    """
    Plate crossing = last tracked point (the flight ends where the ball meets bat or glove, at the plate).
    It never depends on the zone, so the call can't be self-confirming. No real zone -> no call.
    """
    bx, by = float(points[-1].x), float(points[-1].y)
    if is_normal_mode or not zone_calibrated:
        return PitchCallResult(
            is_strike=is_normal_mode,
            call="BALL TRACKED" if is_normal_mode else "SET ZONE",
            plate_x=bx,
            plate_y=by,
            zone_x_min=strike_zone.x_min,
            zone_y_min=strike_zone.y_min,
            zone_x_max=strike_zone.x_max,
            zone_y_max=strike_zone.y_max,
            dist_to_center_in=0.0,
        )
    return evaluate_pitch((bx, by), strike_zone)


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
    mode: str = "baseball",
) -> Dict[str, Any]:
    """
    Complete end-to-end Pitch Lab analysis:
    Tracks ball trajectory, calculates speed (MPH), checks strike zone,
    and renders output video with Statcast 3D streamline and HUD card.
    Supports both Baseball Pitch Mode and Normal / Any Video Mode.
    """
    if not os.path.exists(input_video_path):
        raise FileNotFoundError(f"Video file not found: {input_video_path}")

    is_normal_mode = (mode or "baseball").lower().strip() in ["normal", "general"] or (perspective or "").lower().strip() in ["normal", "general"]
    show_strike_zone = not is_normal_mode

    renderer = PitchRenderer(graphic_style=graphic_style)

    # 1. Track ball throughout video
    with _TRACK_LOCK:
        tracker = get_tracker()
        trajectory_points, fps, (width, height) = tracker.track_video(
            input_video_path,
            conf_thresh=conf_thresh,
            ball_type=ball_type,
            perspective=perspective,
            mode=mode,
        )
        resolved_perspective = getattr(tracker, "last_resolved_perspective", None) or perspective
        plate = getattr(tracker, "last_plate", None)

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
            "mode": "normal" if is_normal_mode else "baseball",
            "show_strike_zone": show_strike_zone,
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
            "zone_calibrated": False,
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

    is_normal_mode = (mode or "baseball").lower().strip() in ["normal", "general"] or resolved_perspective in ["normal", "general"]

    # 2. Strike zone: user-set > detected home plate (17in wide sets px/in) > uncalibrated guess
    zone_calibrated = True
    if custom_strike_zone:
        strike_zone = StrikeZone(
            x_min=custom_strike_zone["x_min"],
            y_min=custom_strike_zone["y_min"],
            x_max=custom_strike_zone["x_max"],
            y_max=custom_strike_zone["y_max"],
        )
        show_strike_zone = True
    elif is_normal_mode:
        strike_zone = StrikeZone.get_preset_zone(width, height, view_type="behind_catcher")
        show_strike_zone = False
    elif plate:
        px, py, pw = plate
        strike_zone = StrikeZone.from_batter_height(BATTER_HEIGHT_IN, px, py, pixels_per_inch=pw / PLATE_WIDTH_IN)
        show_strike_zone = True
    else:
        strike_zone = StrikeZone.get_preset_zone(width, height, view_type=resolved_perspective)
        show_strike_zone = True
        zone_calibrated = False

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

    pitch_tag = "Ball Flight" if is_normal_mode else classify_pitch_type(velocity_mph, vert_break_in, horz_break_in)
    call_result = judge_pitch(trajectory_points, strike_zone, is_normal_mode, zone_calibrated)
    plate_pt = (call_result.plate_x, call_result.plate_y)

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
        call_result=call_result if zone_calibrated or is_normal_mode else None,
        pitch_number=pitch_number,
        pitch_tag=pitch_tag,
        flight_time_ms=flight_time_ms,
        show_strike_zone=show_strike_zone and zone_calibrated,
        graphic_style=graphic_style,
        trim_to_pitch=trim_to_pitch,
        hud_style=hud_style,
        max_dimension=max_dimension,
    )

    scale_x = out_w / float(width) if width > 0 else 1.0
    scale_y = out_h / float(height) if height > 0 else 1.0

    return {
        "pitch_detected": True,
        "mode": "normal" if is_normal_mode else "baseball",
        "show_strike_zone": show_strike_zone,
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
        "zone_calibrated": zone_calibrated,
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
    mode: str = "baseball",
    show_strike_zone: Optional[bool] = None,
) -> dict:
    """
    Fast re-render using existing tracked trajectory and updated strike zone or graphic theme.
    Supports both Baseball Pitch Mode and Normal / Any Video Mode.
    """
    cap = cv2.VideoCapture(input_video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    # The UI speaks the rendered video's pixels; work in source pixels like process_pitch_video
    out_w, out_h = output_size(width, height, max_dimension)
    sx, sy = out_w / float(width), out_h / float(height)
    pts = [
        TrajectoryPoint(frame_idx=int(p["frame"]), x=float(p["x"]) / sx, y=float(p["y"]) / sy, conf=0.9)
        for p in trajectory
    ]

    is_normal_mode = (mode or "baseball").lower().strip() in ["normal", "general"] or (perspective or "").lower().strip() in ["normal", "general"]

    if show_strike_zone is None:
        show_strike_zone = not is_normal_mode

    zone_calibrated = bool(custom_strike_zone)
    if custom_strike_zone:
        strike_zone = StrikeZone(
            x_min=float(custom_strike_zone["x_min"]) / sx,
            y_min=float(custom_strike_zone["y_min"]) / sy,
            x_max=float(custom_strike_zone["x_max"]) / sx,
            y_max=float(custom_strike_zone["y_max"]) / sy,
        )
    else:
        strike_zone = StrikeZone.get_preset_zone(width, height, view_type="behind_catcher")

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

    pitch_tag = "Ball Flight" if is_normal_mode else classify_pitch_type(velocity_mph, vert_break_in, horz_break_in)
    call_result = judge_pitch(pts, strike_zone, is_normal_mode, zone_calibrated)
    plate_pt = (call_result.plate_x, call_result.plate_y)

    renderer = PitchRenderer(graphic_style=graphic_style)
    out_w, out_h = renderer.render_complete_video(
        input_video_path=input_video_path,
        output_video_path=output_video_path,
        trajectory_points=pts,
        velocity_mph=velocity_mph,
        vert_break_in=vert_break_in,
        horz_break_in=horz_break_in,
        strike_zone=strike_zone,
        call_result=call_result if zone_calibrated or is_normal_mode else None,
        pitch_number=pitch_number,
        pitch_tag=pitch_tag,
        flight_time_ms=flight_time_ms,
        show_strike_zone=show_strike_zone and zone_calibrated,
        graphic_style=graphic_style,
        trim_to_pitch=trim_to_pitch,
        hud_style=hud_style,
        max_dimension=max_dimension,
    )

    return {
        "pitch_number": pitch_number,
        "mode": "normal" if is_normal_mode else "baseball",
        "show_strike_zone": show_strike_zone,
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
        "zone_calibrated": zone_calibrated,
        "strike_zone": {
            "x_min": round(strike_zone.x_min * sx, 1),
            "y_min": round(strike_zone.y_min * sy, 1),
            "x_max": round(strike_zone.x_max * sx, 1),
            "y_max": round(strike_zone.y_max * sy, 1),
        },
        "plate_crossing": {
            "x": round(plate_pt[0] * sx, 1),
            "y": round(plate_pt[1] * sy, 1),
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
