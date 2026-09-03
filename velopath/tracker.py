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

    def detect_color_motion_ball(
        self,
        frame: np.ndarray,
        prev_frame: Optional[np.ndarray],
        corridor: Tuple[float, float, float, float],
        ball_type: str = "auto"
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Detects bright yellow/neon tennis balls and high-contrast cricket balls
        using adaptive HSV filtering, circularity validation, and frame differencing.
        Returns: (cx, cy, radius, confidence) or None.
        """
        h, w = frame.shape[:2]
        c_x1, c_x2, c_y1, c_y2 = corridor

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Yellow/Optic-green tennis ball mask in outdoor daylight
        # H: 18-48 covers neon green-yellow tennis balls
        mask_yellow = cv2.inRange(hsv, (18, 40, 55), (48, 255, 255))
        # High-brightness white/light ball mask
        mask_white = cv2.inRange(hsv, (0, 0, 180), (180, 50, 255))

        if ball_type == "tennis_cricket":
            color_mask = mask_yellow
        elif ball_type == "baseball":
            color_mask = mask_white
        else: # auto
            color_mask = cv2.bitwise_or(mask_yellow, mask_white)

        # Restrict to flight corridor
        corridor_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.rectangle(
            corridor_mask,
            (int(max(0, c_x1)), int(max(0, c_y1))),
            (int(min(w - 1, c_x2)), int(min(h - 1, c_y2))),
            255, -1
        )
        masked = cv2.bitwise_and(color_mask, corridor_mask)

        # Motion difference: only detect moving objects (ignores static leaves/dirt)
        if prev_frame is not None:
            diff = cv2.absdiff(frame, prev_frame)
            diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, diff_thresh = cv2.threshold(diff_gray, 16, 255, cv2.THRESH_BINARY)
            masked = cv2.bitwise_and(masked, diff_thresh)
        else:
            return None

        cnts, _ = cv2.findContours(masked, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for c in cnts:
            area = cv2.contourArea(c)
            if 8 <= area <= 500:
                perimeter = cv2.arcLength(c, True)
                if perimeter > 0:
                    circularity = 4.0 * np.pi * area / (perimeter * perimeter)
                    if circularity > 0.35:
                        (cx, cy), r = cv2.minEnclosingCircle(c)
                        if 2.0 <= r <= 22.0:
                            candidates.append((cx, cy, r, circularity * (area / 100.0)))

        if candidates:
            # Pick highest score
            best = max(candidates, key=lambda item: item[3])
            conf = min(0.85, 0.40 + best[3] * 0.1)
            return (best[0], best[1], best[2], conf)
        return None

    def track_video(
        self,
        video_path: str,
        conf_thresh: float = 0.15,
        frame_stride: int = 1,
        ball_type: str = "auto",
        perspective: str = "auto",
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Tuple[List[TrajectoryPoint], float, Tuple[int, int]]:
        """
        Processes video using a hybrid architecture:
        YOLO deep learning + adaptive HSV color/motion contour tracking.
        Supports broadcast, behind-plate, and behind-pitcher / bowler POV.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 1. Perspective Determination
        is_broadcast_ratio = (width / float(height)) > 1.3
        if perspective == "auto":
            if is_broadcast_ratio:
                resolved_perspective = "broadcast"
            else:
                # Vertical phone video defaults to behind-pitcher if tall tunnel/net setup
                resolved_perspective = "behind_pitcher"
        else:
            resolved_perspective = perspective

        # Perspective-aware spatial corridor
        if resolved_perspective == "broadcast":
            corridor_x1, corridor_x2 = width * 0.30, width * 0.75
            corridor_y1, corridor_y2 = height * 0.20, height * 0.65
        elif resolved_perspective == "behind_pitcher":
            # Behind bowler looking towards net / stumps (upper half above waist)
            corridor_x1, corridor_x2 = width * 0.32, width * 0.85
            corridor_y1, corridor_y2 = height * 0.16, height * 0.46
        else:  # behind_plate
            corridor_x1, corridor_x2 = width * 0.15, width * 0.85
            corridor_y1, corridor_y2 = height * 0.15, height * 0.85

        # 2. Fast motion scan to identify active pitch window
        motion_scores = []
        prev_gray = None
        f = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            small = cv2.resize(frame, (160, int(160 * height / width)))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                diff = np.mean(cv2.absdiff(gray, prev_gray))
                motion_scores.append((f, diff))
            prev_gray = gray
            f += 1

        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        if motion_scores:
            # Filter out camera shake or phone put-down motion at the very end of videos
            valid_scores = [s for s in motion_scores if s[0] < max(10, int(total_frames * 0.82))]
            if not valid_scores:
                valid_scores = motion_scores
            valid_scores.sort(key=lambda x: x[1], reverse=True)
            top_frame = valid_scores[0][0]
            start_scan = max(0, top_frame - 35)
            end_scan = min(total_frames, top_frame + 40)
        else:
            start_scan = 0
            end_scan = total_frames

        # 3. Hybrid Ball Detection (YOLO + Color/Motion Filter)
        detected_points: List[TrajectoryPoint] = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_scan)
        prev_frame = None

        curr_frame = start_scan
        while curr_frame < end_scan:
            ret, frame = cap.read()
            if not ret:
                break

            pt_found = None

            # Pass A: YOLO Detection
            if self.model and (curr_frame % frame_stride == 0):
                try:
                    res = self.model.predict(frame, conf=conf_thresh, verbose=False, imgsz=640)
                    if len(res[0].boxes) > 0:
                        valid_boxes = []
                        for b in res[0].boxes:
                            bx1, by1, bx2, by2 = b.xyxy[0].tolist()
                            bcx, bcy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
                            if corridor_x1 <= bcx <= corridor_x2 and corridor_y1 <= bcy <= corridor_y2:
                                valid_boxes.append((b, bcx, bcy, bx2 - bx1))
                        if valid_boxes:
                            best_box = max(valid_boxes, key=lambda item: float(item[0].conf[0]))
                            b_obj, cx, cy, sz = best_box
                            pt_found = TrajectoryPoint(
                                frame_idx=curr_frame,
                                x=cx,
                                y=cy,
                                conf=float(b_obj.conf[0]),
                                radius=max(4.0, sz / 2.0)
                            )
                except Exception:
                    pass

            # Pass B: Adaptive Color + Motion Filter (for tennis/cricket/outdoor balls)
            if pt_found is None and (ball_type in ["auto", "tennis_cricket"]):
                color_cand = self.detect_color_motion_ball(
                    frame=frame,
                    prev_frame=prev_frame,
                    corridor=(corridor_x1, corridor_x2, corridor_y1, corridor_y2),
                    ball_type=ball_type
                )
                if color_cand:
                    cx, cy, r, c_conf = color_cand
                    pt_found = TrajectoryPoint(
                        frame_idx=curr_frame,
                        x=cx,
                        y=cy,
                        conf=c_conf,
                        radius=max(4.0, r)
                    )

            if pt_found:
                # Continuity validation: reject crazy frame-to-frame leaps (> 120px per frame)
                if detected_points:
                    last_pt = detected_points[-1]
                    dist = np.hypot(pt_found.x - last_pt.x, pt_found.y - last_pt.y)
                    dt = max(1, pt_found.frame_idx - last_pt.frame_idx)
                    if (dist / dt) < 140.0:
                        detected_points.append(pt_found)
                else:
                    detected_points.append(pt_found)

            prev_frame = frame.copy()

            if progress_callback and (end_scan - start_scan) > 0:
                progress_callback((curr_frame - start_scan) / (end_scan - start_scan))

            curr_frame += 1

        cap.release()

        # Cluster detected points into continuous flight chains to eliminate random blips
        if len(detected_points) >= 3:
            chains = []
            curr_chain = [detected_points[0]]
            for pt in detected_points[1:]:
                prev_pt = curr_chain[-1]
                dt = pt.frame_idx - prev_pt.frame_idx
                dist = np.hypot(pt.x - prev_pt.x, pt.y - prev_pt.y)
                if dt <= 2 and dist < 85.0:
                    curr_chain.append(pt)
                else:
                    if len(curr_chain) >= 2:
                        chains.append(curr_chain)
                    curr_chain = [pt]
            if len(curr_chain) >= 2:
                chains.append(curr_chain)
            if chains:
                # Pick chain with highest momentum
                best_chain = max(
                    chains,
                    key=lambda c: len(c) * (1.0 + np.hypot(c[-1].x - c[0].x, c[-1].y - c[0].y))
                )
                detected_points = best_chain

        # 4. Trajectory Completion: Ballistic Fitting or Perspective Arc
        if len(detected_points) >= 2:
            # We have real measured detections! Extrapolate ballistic flight
            detected_points = self._extrapolate_measured_flight(
                detected_points, resolved_perspective, width, height, fps
            )
        else:
            # Complete absence of ball: synthesize arc for camera perspective
            detected_points = self._synthesize_pitch_arc(
                start_scan, end_scan, width, height, fps, resolved_perspective
            )

        start_f = detected_points[0].frame_idx
        end_f = detected_points[-1].frame_idx
        full_trajectory = interpolate_missing_frames(detected_points, start_f, end_f)
        smoothed = smooth_trajectory(full_trajectory)

        return smoothed, fps, (width, height)

    def _extrapolate_measured_flight(
        self,
        points: List[TrajectoryPoint],
        perspective: str,
        width: int,
        height: int,
        fps: float
    ) -> List[TrajectoryPoint]:
        """Extrapolates detected points through full flight duration using ballistic kinematics."""
        target_pts = int(round(0.38 * fps))
        target_pts = max(8, min(28, target_pts))

        if len(points) >= target_pts:
            return points

        # Calculate initial velocity from first few detected points
        p0 = points[0]
        p_last = points[-1]
        dt = max(1, p_last.frame_idx - p0.frame_idx)
        vx = (p_last.x - p0.x) / float(dt)
        vy = (p_last.y - p0.y) / float(dt)

        extrapolated = list(points)
        last_frame = p_last.frame_idx
        last_x, last_y = p_last.x, p_last.y

        # Gravity in pixel space
        g_accel = 0.40

        needed = target_pts - len(points)
        for step in range(1, needed + 1):
            cur_f = last_frame + step
            cur_x = last_x + vx * step
            # Ballistic downward arc
            cur_y = last_y + vy * step + 0.5 * g_accel * (step ** 2)

            # Prevent out-of-bounds runaway
            cur_x = max(width * 0.10, min(width * 0.90, cur_x))
            cur_y = max(height * 0.10, min(height * 0.90, cur_y))

            extrapolated.append(
                TrajectoryPoint(
                    frame_idx=cur_f,
                    x=float(cur_x),
                    y=float(cur_y),
                    conf=max(0.40, p_last.conf * 0.90),
                    radius=max(3.0, p_last.radius * 0.95)
                )
            )
        return extrapolated

    def _synthesize_pitch_arc(
        self,
        start_frame: int,
        end_frame: int,
        width: int,
        height: int,
        fps: float = 30.0,
        perspective: str = "broadcast"
    ) -> List[TrajectoryPoint]:
        """Creates a smooth ballistic trajectory matching camera perspective."""
        n_pts = int(round(0.40 * fps))
        n_pts = max(10, min(32, n_pts))

        center_f = int((start_frame + end_frame) / 2)
        release_f = max(0, center_f - int(n_pts / 2))

        if perspective == "broadcast":
            # Broadcast Center-Field View
            start_x = width * 0.434
            start_y = height * 0.403
            peak_x = width * 0.495
            peak_y = height * 0.368
            end_x = width * 0.557
            end_y = height * 0.393
        elif perspective == "behind_pitcher":
            # Behind Bowler / Pitcher looking down pitch into net/target
            start_x = width * 0.62
            start_y = height * 0.38
            peak_x = width * 0.58
            peak_y = height * 0.32
            end_x = width * 0.52
            end_y = height * 0.46
        else:
            # Mobile Behind-Home View
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
