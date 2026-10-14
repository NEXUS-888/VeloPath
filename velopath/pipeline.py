"""
End-to-end processing pipeline: Tracks ball, calculates speed, tests strike zone, and renders video.
"""
from typing import Dict, Any, Optional, List, Callable, Tuple
import functools
import os
import threading
import cv2

from velopath.tracker import PitchTracker, TrajectoryPoint
from velopath.physics import calculate_pitch_break, classify_pitch_type, calculate_advanced_velocity, calculate_velocity_kmh
from velopath.geometry3d import Camera, camera_from_taps, fit_pitch_3d
from velopath.strike_zone import StrikeZone, evaluate_pitch, PitchCallResult, PLATE_WIDTH_IN
from velopath.renderer import PitchRenderer, output_size

BATTER_HEIGHT_IN = 72.0  # ABS uses the batter's listed height; without it assume 6 ft
_TRACK_LOCK = threading.Lock()  # YOLO predict isn't thread-safe and track_video leaves per-run state on the tracker


@functools.lru_cache(maxsize=1)
def get_tracker() -> PitchTracker:
    """One tracker per process: loading YOLO weights costs seconds per request."""
    return PitchTracker()


def _is_normal(mode: Optional[str], perspective: Optional[str]) -> bool:
    return (mode or "baseball").lower().strip() in ("normal", "general") or (perspective or "").lower().strip() in ("normal", "general")


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


def _analyze_and_render(
    input_video_path: str,
    output_video_path: str,
    pts: List[TrajectoryPoint],
    fps: float,
    width: int,
    height: int,
    strike_zone: StrikeZone,
    zone_calibrated: bool,
    is_normal_mode: bool,
    show_strike_zone: bool,
    distance_ft: float,
    ball_type: str,
    perspective: str,
    pitch_number: int,
    graphic_style: str,
    trim_to_pitch: bool,
    hud_style: str,
    max_dimension: Optional[int],
    report: Callable[[str, float], None],
    cam: Optional[Camera] = None,
) -> Dict[str, Any]:
    """Speed, break, call and the rendered video for a tracked flight (source pixels in, UI pixels out).
    Shared by process_pitch_video and rerender_pitch so the two can never disagree.
    With a camera from plate + rubber taps, speed and break come from a 3D fit (measurement "3d");
    otherwise speed is distance / frames and break a 2D estimate (measurement "2d", no pitch-type guess)."""
    release_frame, plate_frame = pts[0].frame_idx, pts[-1].frame_idx
    elapsed_frames = max(1, plate_frame - release_frame)
    vel = calculate_advanced_velocity(distance_ft=distance_ft, elapsed_frames=float(elapsed_frames), fps=fps, ball_type=ball_type)
    velocity_pm_mph = round(vel["release_velocity_mph"] / elapsed_frames, 1)  # +-1 frame of whole-frame timing
    px_per_in = strike_zone.width / PLATE_WIDTH_IN  # zone is 17in wide: calibrated zone -> real inches
    horz_break_in, vert_break_in = calculate_pitch_break([(p.x, p.y) for p in pts], pixels_per_inch=px_per_in)
    measured = [p for p in pts if p.radius > 0]  # frames where the ball's size was actually seen
    fit = fit_pitch_3d([p.frame_idx for p in measured], [(p.x, p.y) for p in measured],
                       [2 * p.radius for p in measured], fps, cam) if cam and not is_normal_mode else None
    if fit:
        vel.update(release_velocity_mph=fit["release_mph"], release_velocity_kmh=calculate_velocity_kmh(fit["release_mph"]),
                   plate_velocity_mph=fit["plate_mph"], plate_velocity_kmh=calculate_velocity_kmh(fit["plate_mph"]),
                   flight_time_ms=fit["flight_ms"])
        velocity_pm_mph = fit["release_pm_mph"]
        horz_break_in, vert_break_in = fit["hb_in"], fit["ivb_in"]  # induced vertical break: + = rise
        pitch_tag = classify_pitch_type(fit["release_mph"], -fit["ivb_in"], fit["hb_in"])  # classifier wants drop
    else:
        pitch_tag = "Ball Flight" if is_normal_mode else "Pitch"  # a 2D break estimate is too weak to name pitches
    call_result = judge_pitch(pts, strike_zone, is_normal_mode, zone_calibrated)

    os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
    report("Rendering video", 0.85)
    out_w, out_h = PitchRenderer(graphic_style=graphic_style).render_complete_video(
        input_video_path=input_video_path,
        output_video_path=output_video_path,
        trajectory_points=pts,
        velocity_mph=vel["release_velocity_mph"],
        vert_break_in=vert_break_in,
        horz_break_in=horz_break_in,
        strike_zone=strike_zone,
        call_result=call_result if zone_calibrated or is_normal_mode else None,  # no fake call on a guessed zone
        pitch_number=pitch_number,
        pitch_tag=pitch_tag,
        flight_time_ms=vel["flight_time_ms"],
        show_strike_zone=show_strike_zone and zone_calibrated,
        graphic_style=graphic_style,
        trim_to_pitch=trim_to_pitch,
        hud_style=hud_style,
        max_dimension=max_dimension,
    )
    sx = out_w / float(width) if width > 0 else 1.0
    sy = out_h / float(height) if height > 0 else 1.0
    return {
        "pitch_detected": True,
        "mode": "normal" if is_normal_mode else "baseball",
        "show_strike_zone": show_strike_zone,
        "pitch_number": pitch_number,
        "velocity_mph": vel["release_velocity_mph"],
        "velocity_pm_mph": velocity_pm_mph,
        "measurement": "3d" if fit else "2d",
        "fit_px_error": fit["fit_px_error"] if fit else None,
        "velocity_kmh": vel["release_velocity_kmh"],
        "plate_velocity_mph": vel["plate_velocity_mph"],
        "plate_velocity_kmh": vel["plate_velocity_kmh"],
        "flight_time_ms": vel["flight_time_ms"],
        "effective_distance_ft": vel["effective_distance_ft"],
        "sport": vel["sport"],
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
        "plate_crossing": {"x": round(call_result.plate_x * sx, 1), "y": round(call_result.plate_y * sy, 1)},
        "graphic_style": graphic_style,
        "ball_type": ball_type,
        "perspective": perspective,
        "release_frame": release_frame,
        "plate_frame": plate_frame,
        "elapsed_frames": elapsed_frames,
        "fps": fps,
        "video_resolution": {"width": out_w, "height": out_h},
        "output_video_path": output_video_path,
        "trajectory": [{"frame": p.frame_idx, "x": round(p.x * sx, 1), "y": round(p.y * sy, 1),
                        **({"d": round(2 * p.radius * sx, 2)} if p.radius > 0 else {})} for p in pts],
    }


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
    progress: Optional[Callable[[str, float], None]] = None,
    time_window: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """
    Tracks the ball, measures speed / break, makes the ABS call (when a real zone exists)
    and renders the output video. Supports Baseball Pitch Mode and Normal / Any Video Mode.
    """
    if not os.path.exists(input_video_path):
        raise FileNotFoundError(f"Video file not found: {input_video_path}")

    report = progress or (lambda stage, pct: None)  # (stage, 0..1) for the UI's progress screen
    report("Queued", 0.0)  # another upload may hold the tracker
    with _TRACK_LOCK:
        report("Tracking ball", 0.0)
        tracker = get_tracker()
        trajectory_points, fps, (width, height) = tracker.track_video(
            input_video_path,
            conf_thresh=conf_thresh,
            ball_type=ball_type,
            perspective=perspective,
            mode=mode,
            progress_callback=lambda frac: report("Tracking ball", 0.85 * frac),
            time_window=time_window,  # (start_s, end_s) the user marked around the pitch
        )
        resolved_perspective = getattr(tracker, "last_resolved_perspective", None) or perspective
        plate = getattr(tracker, "last_plate", None)
        gpu = getattr(getattr(tracker, "model", None), "gpu_name", None)
        compute = f"{gpu} (GPU worker)" if gpu and not tracker.model.using_fallback else "this computer"

    is_normal_mode = _is_normal(mode, resolved_perspective)
    if not trajectory_points:
        # Clean No-Pitch handling (e.g. windup drill, truncated clip, or aborted take)
        os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
        report("Rendering video", 0.85)
        out_w, out_h = PitchRenderer(graphic_style=graphic_style).render_complete_video(
            input_video_path=input_video_path,
            output_video_path=output_video_path,
            trajectory_points=[],
            velocity_mph=0.0,
            vert_break_in=0.0,
            horz_break_in=0.0,
            pitch_number=pitch_number,
            pitch_tag="No Pitch",
            flight_time_ms=0.0,
            show_strike_zone=False,
            graphic_style=graphic_style,
            hud_style=hud_style,
            max_dimension=max_dimension,
        )
        report("Done", 1.0)
        return {
            "pitch_detected": False,
            "compute": compute,
            "mode": "normal" if is_normal_mode else "baseball",
            "show_strike_zone": not is_normal_mode,
            "pitch_number": pitch_number,
            "velocity_mph": 0.0,
            "velocity_kmh": 0.0,
            "plate_velocity_mph": 0.0,
            "plate_velocity_kmh": 0.0,
            "flight_time_ms": 0.0,
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
            "perspective": resolved_perspective,
            "release_frame": 0,
            "plate_frame": 0,
            "elapsed_frames": 0,
            "fps": fps,
            "video_resolution": {"width": out_w, "height": out_h},
            "output_video_path": output_video_path,
            "trajectory": [],
        }

    # A pitch lasts well under 1.5s: keep the 1.5s stretch that moves the most
    max_flight_frames = int(round(1.5 * fps))
    if len(trajectory_points) > max_flight_frames:
        span = max_flight_frames - 1
        best = max(range(len(trajectory_points) - span),
                   key=lambda i: (trajectory_points[i + span].x - trajectory_points[i].x) ** 2
                   + (trajectory_points[i + span].y - trajectory_points[i].y) ** 2)
        trajectory_points = trajectory_points[best:best + max_flight_frames]

    # Strike zone: user-set > detected home plate (17in wide sets px/in) > uncalibrated guess (no call)
    zone_calibrated, show_strike_zone = True, not is_normal_mode
    if custom_strike_zone:
        strike_zone = StrikeZone(**{k: float(custom_strike_zone[k]) for k in ("x_min", "y_min", "x_max", "y_max")})
        show_strike_zone = True
    elif is_normal_mode:
        strike_zone = StrikeZone.get_preset_zone(width, height, view_type="behind_catcher")
    elif plate:
        px, py, pw = plate
        strike_zone = StrikeZone.from_batter_height(BATTER_HEIGHT_IN, px, py, pixels_per_inch=pw / PLATE_WIDTH_IN)
    else:
        strike_zone = StrikeZone.get_preset_zone(width, height, view_type=resolved_perspective)
        zone_calibrated = False

    result = _analyze_and_render(
        input_video_path, output_video_path, trajectory_points, fps, width, height, strike_zone, zone_calibrated,
        is_normal_mode, show_strike_zone, distance_ft, ball_type, resolved_perspective, pitch_number,
        graphic_style, trim_to_pitch, hud_style, max_dimension, report,
    )
    result["compute"] = compute
    report("Done", 1.0)
    return result


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
    plate_corners: Optional[list] = None,
    batter_height_in: float = BATTER_HEIGHT_IN,
    rubber_corners: Optional[list] = None,
) -> dict:
    """
    Fast re-render of an already tracked trajectory with a new strike zone or graphic style.
    The UI sends rendered-video pixels; everything here works in source pixels like process_pitch_video.
    """
    if not trajectory:
        raise ValueError("A tracked trajectory is required to re-render.")
    cap = cv2.VideoCapture(input_video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    out_w, out_h = output_size(width, height, max_dimension)
    sx, sy = out_w / float(width), out_h / float(height)
    pts = [TrajectoryPoint(frame_idx=int(p["frame"]), x=float(p["x"]) / sx, y=float(p["y"]) / sy, conf=0.9,
                           radius=float(p.get("d") or 0.0) / 2.0 / sx) for p in trajectory]

    is_normal_mode = _is_normal(mode, perspective)
    if show_strike_zone is None:
        show_strike_zone = not is_normal_mode

    # zone: one the user set (drag / Apply) > built from plate taps > uncalibrated guess.
    # Taps keep coming with later re-renders for the 3D camera, so they must not undo a hand-dragged zone.
    zone_calibrated = bool(plate_corners or custom_strike_zone)
    if custom_strike_zone:
        strike_zone = StrikeZone(
            x_min=float(custom_strike_zone["x_min"]) / sx,
            y_min=float(custom_strike_zone["y_min"]) / sy,
            x_max=float(custom_strike_zone["x_max"]) / sx,
            y_max=float(custom_strike_zone["y_max"]) / sy,
        )
    elif plate_corners:  # user tapped the plate's front corners on the rendered video
        (ax, ay), (bx, by) = plate_corners
        strike_zone = StrikeZone.from_plate_corners((ax / sx, ay / sy), (bx / sx, by / sy), batter_height_in)
    else:
        strike_zone = StrikeZone.get_preset_zone(width, height, view_type="behind_catcher")

    # plate + rubber taps -> camera geometry for the 3D fit (None if the view can't resolve depth)
    cam = None
    if plate_corners and rubber_corners:
        cam = camera_from_taps([(x / sx, y / sy) for x, y in plate_corners],
                               [(x / sx, y / sy) for x, y in rubber_corners], (width, height))

    return _analyze_and_render(
        input_video_path, output_video_path, pts, fps, width, height, strike_zone, zone_calibrated,
        is_normal_mode, show_strike_zone, distance_ft, ball_type, perspective, pitch_number,
        graphic_style, trim_to_pitch, hud_style, max_dimension, lambda stage, pct: None, cam=cam,
    )
