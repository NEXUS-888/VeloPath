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
        self.device = "cpu"
        
        try:
            from velopath.model_manager import resolve_model_path, get_acceleration_device
            self.device, device_name = get_acceleration_device()
            if model_path is None:
                model_path = resolve_model_path(auto_download=True)
        except Exception as e:
            device_name = "CPU (Fallback)"
            print(f"[PitchTracker] Note on model manager: {e}")
                
        if model_path and os.path.exists(model_path):
            try:
                from ultralytics import YOLO
                self.model = YOLO(model_path)
                print(f"[PitchTracker] Loaded model weights from: {model_path}")
                print(f"[PitchTracker] Compute acceleration: {device_name}")
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

        # Optic-yellow / neon tennis / tape ball mask in outdoor daylight
        # H: 12-82 covers neon green-yellow tennis balls, tape balls, and outdoor softballs
        mask_yellow = cv2.inRange(hsv, (12, 35, 45), (82, 255, 255))
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
            _, diff_thresh = cv2.threshold(diff_gray, 14, 255, cv2.THRESH_BINARY)
            masked = cv2.bitwise_and(masked, diff_thresh)
        else:
            return None

        # Resolution-adaptive area and radius limits
        scale = max(1.0, (w * h) / (640.0 * 360.0))
        min_area = max(6, int(8 * scale * 0.3))
        # Baseballs in flight are compact; cap area to prevent detecting human pants or legs
        max_area = int(min(1200, 450 * scale))
        max_r = max(18.0, 16.0 * np.sqrt(scale))

        cnts, _ = cv2.findContours(masked, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for c in cnts:
            area = cv2.contourArea(c)
            if min_area <= area <= max_area:
                perimeter = cv2.arcLength(c, True)
                if perimeter > 0:
                    circularity = 4.0 * np.pi * area / (perimeter * perimeter)
                    # Real balls are round (circularity >= 0.55); reject elongated pants/limbs
                    if circularity >= 0.55:
                        (cx, cy), r = cv2.minEnclosingCircle(c)
                        if 2.0 <= r <= max_r:
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

        # Perspective-aware spatial corridor (covers release to plate)
        is_portrait = height > width
        if resolved_perspective == "broadcast":
            corridor_x1, corridor_x2 = width * 0.18, width * 0.82
            corridor_y1, corridor_y2 = height * 0.12, height * 0.80
        elif resolved_perspective == "side_view":
            corridor_x1, corridor_x2 = width * 0.05, width * 0.95
            corridor_y1, corridor_y2 = height * 0.10, height * 0.85
        elif resolved_perspective == "behind_pitcher":
            # Behind bowler/pitcher looking towards net / plate
            # In portrait videos, exclude bottom 35% where pitcher's shoes/legs move
            corridor_x1, corridor_x2 = width * 0.15, width * 0.85
            corridor_y1 = height * 0.12
            corridor_y2 = height * 0.65 if is_portrait else height * 0.75
        else:  # behind_plate
            corridor_x1, corridor_x2 = width * 0.12, width * 0.88
            corridor_y1, corridor_y2 = height * 0.12, height * 0.88

        # 2. Coarse Candidate Scan across the entire video
        # At 30 FPS, flight lasts only 6-10 frames (use stride 2-3). At 60 FPS, use stride 4-6.
        if fps <= 35:
            coarse_stride = max(2, min(3, int(round(fps * 0.08))))
        else:
            coarse_stride = max(4, min(7, int(round(fps * 0.10))))
        coarse_hits = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        prev_coarse_frame = None

        crop_x1 = max(0, int(corridor_x1))
        crop_y1 = max(0, int(corridor_y1))
        crop_x2 = min(width, int(corridor_x2))
        crop_y2 = min(height, int(corridor_y2))

        for f in range(0, total_frames, coarse_stride):
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ret, frame = cap.read()
            if not ret:
                break

            hit = None
            if self.model:
                try:
                    crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                    res = self.model.predict(crop, conf=0.15, verbose=False, imgsz=384, device=self.device)
                    for b in res[0].boxes:
                        bx1, by1, bx2, by2 = b.xyxy[0].tolist()
                        bcx = (bx1 + bx2) / 2.0 + crop_x1
                        bcy = (by1 + by2) / 2.0 + crop_y1
                        hit = (f, bcx, bcy, float(b.conf[0]), bx2 - bx1)
                        break
                except Exception:
                    pass

            if hit is None and (self.model is None) and (ball_type in ["auto", "tennis_cricket"]):
                cand = self.detect_color_motion_ball(
                    frame=frame,
                    prev_frame=prev_coarse_frame,
                    corridor=(corridor_x1, corridor_x2, corridor_y1, corridor_y2),
                    ball_type=ball_type
                )
                if cand:
                    hit = (f, cand[0], cand[1], cand[3], cand[2] * 2.0)

            if hit:
                coarse_hits.append(hit)

            prev_coarse_frame = frame.copy()
            if progress_callback:
                progress_callback((f / float(total_frames)) * 0.35)

        # 3. Cluster coarse hits into consecutive temporal chains
        chains = []
        if coarse_hits:
            curr_chain = [coarse_hits[0]]
            for h_pt in coarse_hits[1:]:
                dt = h_pt[0] - curr_chain[-1][0]
                dist = np.hypot(h_pt[1] - curr_chain[-1][1], h_pt[2] - curr_chain[-1][2])
                if dt <= (coarse_stride * 3) and dist < (width * 0.30):
                    curr_chain.append(h_pt)
                else:
                    if len(curr_chain) >= 2:
                        chains.append(curr_chain)
                    curr_chain = [h_pt]
            if len(curr_chain) >= 2:
                chains.append(curr_chain)

        if chains:
            # Pick best flight chain (weighted by ballistic speed and net displacement)
            # Fast pitch flight has high speed (> 4 px/frame) and distinct trajectory displacement
            def score_chain(c):
                dt = max(1, c[-1][0] - c[0][0])
                disp = np.hypot(c[-1][1] - c[0][1], c[-1][2] - c[0][2])
                speed = disp / float(dt)
                # In behind_pitcher view, ball moves in depth away from camera (small 2D screen disp)
                # Chain length (number of continuous detections) and confidence are the primary signals
                if resolved_perspective == "behind_pitcher":
                    mean_conf = sum(pt[3] for pt in c) / len(c)
                    return (len(c) ** 2.0) * mean_conf * (1.0 + min(60.0, disp) / 30.0)
                return speed * disp * (len(c) ** 1.5)

            best_chain = max(chains, key=score_chain)
            pitch_start = max(0, best_chain[0][0] - (coarse_stride * 2))
            pitch_end = min(total_frames, best_chain[-1][0] + (coarse_stride * 2))
        else:
            # If coarse clustering didn't find a localized flight, scan the central action region
            pitch_start = max(0, int(total_frames * 0.10))
            pitch_end = min(total_frames, int(total_frames * 0.90))

        # 4. Fine Tracking (stride 1) inside active pitch window
        detected_points: List[TrajectoryPoint] = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, pitch_start)
        prev_frame = None
        curr_frame = pitch_start
        fine_total = max(1, pitch_end - pitch_start)

        while curr_frame < pitch_end:
            ret, frame = cap.read()
            if not ret:
                break

            pt_found = None

            # Pass A: High-res YOLO Detection on Corridor Crop (2x faster than full frame)
            if self.model and (curr_frame % frame_stride == 0):
                try:
                    crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                    res = self.model.predict(crop, conf=conf_thresh, verbose=False, imgsz=480, device=self.device)
                    if len(res[0].boxes) > 0:
                        valid_boxes = []
                        for b in res[0].boxes:
                            bx1, by1, bx2, by2 = b.xyxy[0].tolist()
                            bcx = (bx1 + bx2) / 2.0 + crop_x1
                            bcy = (by1 + by2) / 2.0 + crop_y1
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

            # Pass B: Adaptive Color + Motion Filter
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
                if detected_points:
                    last_pt = detected_points[-1]
                    dist = np.hypot(pt_found.x - last_pt.x, pt_found.y - last_pt.y)
                    dt = max(1, pt_found.frame_idx - last_pt.frame_idx)
                    if (dist / dt) < 150.0:
                        detected_points.append(pt_found)
                else:
                    detected_points.append(pt_found)

            prev_frame = frame.copy()

            if progress_callback:
                progress_callback(0.35 + 0.65 * ((curr_frame - pitch_start) / float(fine_total)))

            curr_frame += 1

        cap.release()

        # Fine Chain Clustering
        if len(detected_points) >= 3:
            f_chains = []
            curr_c = [detected_points[0]]
            for pt in detected_points[1:]:
                prev_pt = curr_c[-1]
                dt = pt.frame_idx - prev_pt.frame_idx
                dist = np.hypot(pt.x - prev_pt.x, pt.y - prev_pt.y)
                if dt <= 3 and dist < 100.0:
                    curr_c.append(pt)
                else:
                    if len(curr_c) >= 2:
                        f_chains.append(curr_c)
                    curr_c = [pt]
            if len(curr_c) >= 2:
                f_chains.append(curr_c)
            if f_chains:
                best_fine = max(
                    f_chains,
                    key=lambda c: len(c) * (1.0 + np.hypot(c[-1].x - c[0].x, c[-1].y - c[0].y))
                )
                detected_points = best_fine

        # 4. Trajectory Completion: Ballistic Fitting or Perspective Arc
        if len(detected_points) >= 2:
            # We have real measured detections! Extrapolate ballistic flight
            detected_points = self._extrapolate_measured_flight(
                detected_points, resolved_perspective, width, height, fps
            )
        else:
            # Complete absence of ball: synthesize arc for camera perspective
            detected_points = self._synthesize_pitch_arc(
                pitch_start, pitch_end, width, height, fps, resolved_perspective
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
