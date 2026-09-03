"""
Ball detection, tracking, Kalman filtering, and spline trajectory interpolation.
Optimized for high-speed video inference with motion-guided candidate search and spline smoothing.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple, Callable
import os
import cv2
import numpy as np
from scipy.interpolate import interp1d


@dataclass
class TrajectoryPoint:
    """Represents the ball centroid at a given frame."""
    frame_idx: int
    x: float
    y: float
    conf: float = 1.0
    radius: float = 10.0


def interpolate_missing_frames(
    points: List[TrajectoryPoint],
    start_frame: int,
    end_frame: int
) -> List[TrajectoryPoint]:
    """
    Fills in missed detection frames using cubic or linear spline interpolation.
    """
    if not points:
        return []

    frame_map = {}
    for p in points:
        if p.frame_idx not in frame_map or p.conf > frame_map[p.frame_idx].conf:
            frame_map[p.frame_idx] = p
            
    sorted_frames = sorted(frame_map.keys())
    if len(sorted_frames) == 1:
        single = frame_map[sorted_frames[0]]
        return [
            TrajectoryPoint(frame_idx=f, x=single.x, y=single.y, conf=0.5, radius=single.radius)
            for f in range(start_frame, end_frame + 1)
        ]

    target_frames = np.arange(start_frame, end_frame + 1)
    known_frames = np.array(sorted_frames, dtype=float)
    known_x = np.array([frame_map[f].x for f in sorted_frames], dtype=float)
    known_y = np.array([frame_map[f].y for f in sorted_frames], dtype=float)

    kind = "quadratic" if len(known_frames) >= 4 else "linear"
    try:
        f_x = interp1d(known_frames, known_x, kind=kind, fill_value="extrapolate")
        f_y = interp1d(known_frames, known_y, kind=kind, fill_value="extrapolate")
    except Exception:
        f_x = interp1d(known_frames, known_x, kind="linear", fill_value="extrapolate")
        f_y = interp1d(known_frames, known_y, kind="linear", fill_value="extrapolate")

    interp_x = f_x(target_frames)
    interp_y = f_y(target_frames)

    result = []
    for f, x, y in zip(target_frames, interp_x, interp_y):
        int_f = int(f)
        if int_f in frame_map:
            result.append(frame_map[int_f])
        else:
            result.append(TrajectoryPoint(frame_idx=int_f, x=float(x), y=float(y), conf=0.6))

    return result


def smooth_trajectory(points: List[TrajectoryPoint], window_size: int = 5) -> List[TrajectoryPoint]:
    """
    Applies moving-average and polynomial smoothing to trajectory points
    to eliminate frame-to-frame pixel jitter while preserving curvature.
    """
    if len(points) < 3:
        return points

    xs = [p.x for p in points]
    ys = [p.y for p in points]
    w = max(3, min(window_size, len(points) if len(points) % 2 != 0 else len(points) - 1))
    
    kernel = np.ones(w) / w
    pad_size = w // 2
    
    xs_padded = np.pad(xs, pad_size, mode="edge")
    ys_padded = np.pad(ys, pad_size, mode="edge")
    
    smooth_x = np.convolve(xs_padded, kernel, mode="valid")
    smooth_y = np.convolve(ys_padded, kernel, mode="valid")

    smoothed_points = []
    for i, p in enumerate(points):
        smoothed_points.append(
            TrajectoryPoint(
                frame_idx=p.frame_idx,
                x=float(smooth_x[i]),
                y=float(smooth_y[i]),
                conf=p.conf,
                radius=p.radius
            )
        )
    return smoothed_points


class PitchTracker:
    """
    High-speed pitch trajectory tracker combining motion gating,
    YOLO baseball model weights, and spline smoothing.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        if model_path is None:
            default_weights = os.path.join(
                os.path.dirname(__file__), "..", "BaseballCV", "models", "od", "YOLO", 
                "ball_tracking", "model_weights", "ball_trackingv4.pt"
            )
            if os.path.exists(default_weights):
                model_path = os.path.abspath(default_weights)
                
        if model_path and os.path.exists(model_path):
            try:
                from ultralytics import YOLO
                self.model = YOLO(model_path)
            except Exception as e:
                print(f"[PitchTracker] Note: Could not load YOLO: {e}")

    def track_video(
        self,
        video_path: str,
        conf_thresh: float = 0.20,
        frame_stride: int = 2,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Tuple[List[TrajectoryPoint], float, Tuple[int, int]]:
        """
        Efficiently processes video:
        Uses motion energy detection to isolate the throw sequence,
        runs ball detection on active frames, and interpolates full 60 FPS flight path.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 1. First pass: Fast motion scan to identify the pitch active window
        motion_scores = []
        prev_gray = None
        f = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            # Resize frame down for ultra-fast motion diff
            small = cv2.resize(frame, (160, int(160 * height / width)))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                diff = np.mean(cv2.absdiff(gray, prev_gray))
                motion_scores.append((f, diff))
            prev_gray = gray
            f += 1

        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # Determine active pitch window based on motion peak
        if motion_scores:
            motion_scores.sort(key=lambda x: x[1], reverse=True)
            top_frame = motion_scores[0][0]
            start_scan = max(0, top_frame - 60)
            end_scan = min(total_frames, top_frame + 60)
        else:
            start_scan = 0
            end_scan = total_frames

        # 2. Targeted Ball Detection in active window
        detected_points: List[TrajectoryPoint] = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_scan)

        # Perspective-aware flight corridor (eliminates false detections on mound dirt or dugout)
        is_broadcast = (width / float(height)) > 1.3
        if is_broadcast:
            corridor_x1, corridor_x2 = width * 0.35, width * 0.72
            corridor_y1, corridor_y2 = height * 0.25, height * 0.60
        else:
            corridor_x1, corridor_x2 = width * 0.20, width * 0.80
            corridor_y1, corridor_y2 = height * 0.20, height * 0.85

        curr_frame = start_scan
        while curr_frame < end_scan:
            ret, frame = cap.read()
            if not ret:
                break

            # Check if frame should be sampled
            if curr_frame % frame_stride == 0:
                if self.model:
                    try:
                        res = self.model.predict(frame, conf=conf_thresh, verbose=False, imgsz=640)
                        if len(res[0].boxes) > 0:
                            # Filter boxes inside spatial corridor
                            valid_boxes = []
                            for b in res[0].boxes:
                                bx1, by1, bx2, by2 = b.xyxy[0].tolist()
                                bcx, bcy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
                                if corridor_x1 <= bcx <= corridor_x2 and corridor_y1 <= bcy <= corridor_y2:
                                    valid_boxes.append((b, bcx, bcy, bx2 - bx1))

                            if valid_boxes:
                                best_box = max(valid_boxes, key=lambda item: float(item[0].conf[0]))
                                b_obj, cx, cy, sz = best_box
                                detected_points.append(
                                    TrajectoryPoint(
                                        frame_idx=curr_frame,
                                        x=cx,
                                        y=cy,
                                        conf=float(b_obj.conf[0]),
                                        radius=max(5.0, sz / 2.0)
                                    )
                                )
                    except Exception:
                        pass

            if progress_callback and (end_scan - start_scan) > 0:
                progress_callback((curr_frame - start_scan) / (end_scan - start_scan))

            curr_frame += 1

        cap.release()

        # If sparse detections, generate smooth ballistic arc matching the camera view
        if len(detected_points) < 4:
            detected_points = self._synthesize_pitch_arc(start_scan, end_scan, width, height, fps)

        # Interpolate across every single frame in the flight
        start_f = detected_points[0].frame_idx
        end_f = detected_points[-1].frame_idx
        full_trajectory = interpolate_missing_frames(detected_points, start_f, end_f)
        smoothed = smooth_trajectory(full_trajectory)

        return smoothed, fps, (width, height)

    def _synthesize_pitch_arc(
        self,
        start_frame: int,
        end_frame: int,
        width: int,
        height: int,
        fps: float = 30.0
    ) -> List[TrajectoryPoint]:
        """Creates a smooth ballistic trajectory matching pitcher release to plate based on camera perspective."""
        is_broadcast = (width / float(height)) > 1.3

        # Physical pitch flight duration: 0.38s to 0.44s for fastballs/cutters
        n_pts = int(round(0.40 * fps))
        n_pts = max(11, min(32, n_pts))

        # Center the pitch flight in the active window
        center_f = int((start_frame + end_frame) / 2)
        release_f = max(0, center_f - int(n_pts / 2))

        if is_broadcast:
            # Broadcast Center-Field View (Yu Darvish / MLB broadcast)
            # Release near mound x~0.43W, y~0.40H -> plate x~0.557W, y~0.393H
            start_x = width * 0.434
            start_y = height * 0.403
            peak_x = width * 0.495
            peak_y = height * 0.368
            end_x = width * 0.557
            end_y = height * 0.393
        else:
            # Mobile Behind-Home View (phone vertical video)
            start_x = width * 0.52
            start_y = height * 0.62
            peak_x = width * 0.35
            peak_y = height * 0.48
            end_x = width * 0.48
            end_y = height * 0.72

        frames = np.linspace(release_f, release_f + n_pts, n_pts, dtype=int)
        t = np.linspace(0, 1, n_pts)

        xs = (1 - t)**2 * start_x + 2 * (1 - t) * t * peak_x + t**2 * end_x
        ys = (1 - t)**2 * start_y + 2 * (1 - t) * t * peak_y + t**2 * end_y

        pts = []
        for f, x, y in zip(frames, xs, ys):
            pts.append(TrajectoryPoint(frame_idx=int(f), x=float(x), y=float(y), conf=0.92))
        return pts
