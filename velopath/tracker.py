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

    try:
        from scipy.interpolate import PchipInterpolator
        if len(known_frames) >= 3:
            f_x = PchipInterpolator(known_frames, known_x, extrapolate=True)
            f_y = PchipInterpolator(known_frames, known_y, extrapolate=True)
        else:
            f_x = interp1d(known_frames, known_x, kind="linear", fill_value="extrapolate")
            f_y = interp1d(known_frames, known_y, kind="linear", fill_value="extrapolate")
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

        if self.device == "cpu":
            try:
                import torch
                if hasattr(torch, "set_num_threads"):
                    torch.set_num_threads(os.cpu_count() or 4)
            except Exception:
                pass
                
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
        ball_type: str = "auto",
        prev_frame2: Optional[np.ndarray] = None
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Detects bright yellow/neon tennis balls, white baseballs, red leather cricket balls,
        and hot pink training balls using adaptive HSV filtering, multi-frame differencing,
        and size-fit scoring.
        Returns: (cx, cy, radius, confidence) or None.
        """
        if frame is None or prev_frame is None:
            return None
        h, w = frame.shape[:2]
        c_x1, c_x2, c_y1, c_y2 = corridor
        roi_x1 = max(0, int(c_x1))
        roi_x2 = min(w, int(c_x2))
        roi_y1 = max(0, int(c_y1))
        roi_y2 = min(h, int(c_y2))
        if roi_x2 <= roi_x1 or roi_y2 <= roi_y1:
            return None

        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        prev_roi = prev_frame[roi_y1:roi_y2, roi_x1:roi_x2]
        prev_roi2 = prev_frame2[roi_y1:roi_y2, roi_x1:roi_x2] if prev_frame2 is not None else None

        # Multi-frame motion difference inside corridor ROI
        diff1 = cv2.absdiff(roi, prev_roi)
        diff_gray1 = cv2.cvtColor(diff1, cv2.COLOR_BGR2GRAY)
        _, diff_thresh1 = cv2.threshold(diff_gray1, 18, 255, cv2.THRESH_BINARY)
        if prev_roi2 is not None:
            diff2 = cv2.absdiff(roi, prev_roi2)
            diff_gray2 = cv2.cvtColor(diff2, cv2.COLOR_BGR2GRAY)
            _, diff_thresh2 = cv2.threshold(diff_gray2, 18, 255, cv2.THRESH_BINARY)
            diff_thresh = cv2.bitwise_or(diff_thresh1, diff_thresh2)
        else:
            diff_thresh = diff_thresh1

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # 1. Optic-yellow / neon tennis / training ball mask (tolerant to motion blur and daylight)
        mask_yellow = cv2.inRange(hsv, (20, 50, 60), (55, 255, 255))

        # 2. High-brightness white/light baseball mask (low saturation, high brightness)
        mask_white = cv2.inRange(hsv, (0, 0, 160), (180, 45, 255))

        # 3. Red / Terracotta leather cricket ball mask (wraps around 0/180)
        # Saturated leather ball in sun has hue 0-18 and 165-180
        mask_red1 = cv2.inRange(hsv, (0, 30, 35), (18, 255, 255))
        mask_red2 = cv2.inRange(hsv, (165, 30, 35), (180, 255, 255))
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)

        # 4. Hot Pink / Magenta cricket training ball mask
        mask_pink = cv2.inRange(hsv, (140, 30, 45), (178, 255, 255))

        # Build candidate masks based on ball_type
        if ball_type in ["pink", "pink_cricket", "training"]:
            colored_masks = [mask_pink]
            allow_white = False
        elif ball_type in ["red", "cricket", "leather_cricket"]:
            colored_masks = [mask_red]
            allow_white = False
        elif ball_type in ["tennis_cricket", "tennis", "yellow"]:
            colored_masks = [mask_yellow]
            allow_white = False
        elif ball_type == "baseball":
            colored_masks = []
            allow_white = True
        else:  # auto: check saturated chromatic balls first, only fallback to white if none found
            colored_masks = [mask_pink, mask_red, mask_yellow]
            allow_white = True

        # Resolution-adaptive area and radius limits
        scale = max(1.0, (w * h) / (640.0 * 360.0))
        sqrt_scale = float(np.sqrt(scale))
        min_area = max(8, int(2.5 * sqrt_scale))
        max_area = int(min(25000.0, 2500.0 * scale))
        min_r = max(2.5, 0.8 * sqrt_scale)
        max_r = max(35.0, 18.0 * sqrt_scale)

        candidates = []
        for c_mask in colored_masks:
            masked = cv2.bitwise_and(c_mask, diff_thresh)

            cnts, _ = cv2.findContours(masked, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts:
                area = cv2.contourArea(c)
                if min_area <= area <= max_area:
                    perimeter = cv2.arcLength(c, True)
                    if perimeter > 0:
                        circularity = 4.0 * np.pi * area / (perimeter * perimeter)
                        # Pitched balls in fast motion create motion streaks (circularity >= 0.14)
                        if circularity >= 0.14:
                            (cx, cy), r = cv2.minEnclosingCircle(c)
                            if min_r <= r <= max_r:
                                # Depth-tolerant size fit: balls released in the distance have small r (~1.2-2.5*sqrt_scale)
                                # and expand to ~12.0*sqrt_scale at home plate in foreground
                                if (1.2 * sqrt_scale) <= r <= (12.0 * sqrt_scale):
                                    size_fit = 1.0
                                else:
                                    target_mid = 5.0 * sqrt_scale
                                    size_fit = 1.0 / (1.0 + abs(r - target_mid) / (1.0 * target_mid))
                                area_bonus = min(2.5, max(0.5, (area / (min_area * 3.5)) ** 0.5))
                                score = min(1.0, circularity) * size_fit * area_bonus
                                candidates.append((cx + roi_x1, cy + roi_y1, r, score))

        # Only evaluate noisy white baseball mask if no saturated colored candidates exist
        if not candidates and allow_white:
            masked = cv2.bitwise_and(mask_white, diff_thresh)
            cnts, _ = cv2.findContours(masked, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts:
                area = cv2.contourArea(c)
                if min_area <= area <= max_area:
                    perimeter = cv2.arcLength(c, True)
                    if perimeter > 0:
                        circularity = 4.0 * np.pi * area / (perimeter * perimeter)
                        if circularity >= 0.14:
                            (cx, cy), r = cv2.minEnclosingCircle(c)
                            if min_r <= r <= max_r:
                                if (1.2 * sqrt_scale) <= r <= (12.0 * sqrt_scale):
                                    size_fit = 1.0
                                else:
                                    target_mid = 5.0 * sqrt_scale
                                    size_fit = 1.0 / (1.0 + abs(r - target_mid) / (1.0 * target_mid))
                                area_bonus = min(2.5, max(0.5, (area / (min_area * 3.5)) ** 0.5))
                                score = min(1.0, circularity) * size_fit * area_bonus
                                candidates.append((cx + roi_x1, cy + roi_y1, r, score))

        if candidates:
            best = max(candidates, key=lambda item: item[3])
            conf = min(0.70, 0.35 + best[3] * 0.35)
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
        is_portrait = height > width
        raw_persp = (perspective or "auto").lower().strip()
        if raw_persp in ["behind_plate", "behind_catcher", "catcher", "plate"]:
            resolved_perspective = "behind_catcher"
        elif raw_persp in ["behind_pitcher", "pitcher", "bowler"]:
            resolved_perspective = "behind_pitcher"
        elif raw_persp in ["broadcast", "tv"]:
            resolved_perspective = "broadcast"
        else:
            resolved_perspective = "auto"

        # Perspective-aware spatial corridor (covers release to plate, filters sky/clouds)
        corridor_x1 = width * 0.05
        corridor_x2 = width * 0.95
        corridor_y1 = height * 0.15 if (resolved_perspective == "behind_catcher" or not is_portrait) else height * 0.05
        corridor_y2 = height * 0.95

        # 2. Coarse Candidate Scan across the video
        # For short clips (<= 180 frames, ~1-3 seconds), use stride 1 so fast pitch deliveries are never missed
        if total_frames <= 180:
            coarse_stride = 1
        elif fps <= 35:
            coarse_stride = 2
        else:
            coarse_stride = max(2, min(4, int(round(fps * 0.05))))

        coarse_hits = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        prev_coarse_frame = None
        prev_coarse_frame2 = None

        crop_x1 = max(0, int(corridor_x1))
        crop_y1 = max(0, int(corridor_y1))
        crop_x2 = min(width, int(corridor_x2))
        crop_y2 = min(height, int(corridor_y2))

        curr_coarse_f = 0
        while curr_coarse_f < total_frames:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            f = curr_coarse_f
            curr_coarse_f += 1
            if f % coarse_stride != 0:
                continue

            hit = None
            # Pass 1: Quick adaptive color + multi-frame motion differencing
            cand = self.detect_color_motion_ball(
                frame=frame,
                prev_frame=prev_coarse_frame,
                corridor=(corridor_x1, corridor_x2, corridor_y1, corridor_y2),
                ball_type=ball_type,
                prev_frame2=prev_coarse_frame2
            )
            if cand and (self.model is None or ball_type != "auto" or cand[3] >= (0.45 if ball_type != "baseball" else 0.58)):
                hit = (f, cand[0], cand[1], cand[3], cand[2] * 2.0)

            # Pass 2: High-accuracy YOLO baseball model with motion pre-gate
            if hit is None and self.model:
                has_motion = True
                if prev_coarse_frame is not None:
                    c_small = cv2.resize(frame[crop_y1:crop_y2, crop_x1:crop_x2], (384, 192))
                    p_small = cv2.resize(prev_coarse_frame[crop_y1:crop_y2, crop_x1:crop_x2], (384, 192))
                    diff = cv2.absdiff(c_small, p_small)
                    if int(np.max(diff)) < 15:
                        has_motion = False

                if has_motion:
                    try:
                        crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                        res = self.model.predict(crop, conf=0.12, verbose=False, imgsz=384, device=self.device)
                        yolo_cands = []
                        for b in res[0].boxes:
                            bx1, by1, bx2, by2 = b.xyxy[0].tolist()
                            bcx = (bx1 + bx2) / 2.0 + crop_x1
                            bcy = (by1 + by2) / 2.0 + crop_y1
                            yolo_cands.append((f, bcx, bcy, float(b.conf[0]), bx2 - bx1))
                        if yolo_cands:
                            yolo_cands.sort(key=lambda x: x[3], reverse=True)
                            hit = yolo_cands[0]
                    except Exception:
                        pass

            # Fallback to color/motion candidate if YOLO found nothing
            if hit is None and cand and cand[3] >= 0.45:
                hit = (f, cand[0], cand[1], cand[3], cand[2] * 2.0)
            elif hit is not None and cand and ball_type in ["red", "pink", "yellow", "orange", "leather"] and cand[3] > 0.58 and cand[3] > hit[3]:
                hit = (f, cand[0], cand[1], cand[3], cand[2] * 2.0)

            if hit:
                # Discard hits in upper sky for ground-level camera setups
                if not is_portrait and hit[2] < (height * 0.18):
                    hit = None
            if hit:
                coarse_hits.append(hit)

            prev_coarse_frame2 = prev_coarse_frame
            prev_coarse_frame = frame.copy()
            if progress_callback:
                progress_callback((f / float(total_frames)) * 0.35)

        # 3. Cluster coarse hits into temporal chains with physical velocity gating
        chains = self._link_points_into_chains(
            coarse_hits, width, height, resolved_perspective, max_dt=max(8, coarse_stride * 4)
        )

        best_chain = self._select_best_flight_chain(
            chains, width, height, total_frames, resolved_perspective, fps=fps
        ) if chains else None

        if resolved_perspective == "auto" and getattr(self, "last_resolved_perspective", None):
            resolved_perspective = self.last_resolved_perspective

        if best_chain:
            expected_flight_frames = int(round(0.65 * fps))
            pitch_start = max(0, best_chain[0][0] - int(round(0.40 * fps)))
            pitch_end = min(total_frames, max(best_chain[-1][0] + int(round(0.35 * fps)), best_chain[0][0] + expected_flight_frames))
        else:
            # If coarse clustering didn't find a localized flight, scan the central action region
            pitch_start = max(0, int(total_frames * 0.10))
            pitch_end = min(total_frames, int(total_frames * 0.90))

        # 4. Fine Tracking (stride 1) inside active pitch window
        fine_detected: List[TrajectoryPoint] = []
        if coarse_stride == 1 and coarse_hits:
            fine_detected = [
                TrajectoryPoint(
                    frame_idx=int(h[0]),
                    x=float(h[1]),
                    y=float(h[2]),
                    conf=float(h[3]),
                    radius=max(4.0, float(h[4]) / 2.0)
                ) for h in coarse_hits
            ]
            if progress_callback:
                progress_callback(1.0)
        else:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pitch_start)
            prev_frame = None
            prev_frame2 = None
            curr_frame = pitch_start
            fine_total = max(1, pitch_end - pitch_start)

            while curr_frame < pitch_end:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                pt_found = None

                # Pass A: Quick adaptive color + multi-frame motion differencing
                color_cand = self.detect_color_motion_ball(
                    frame=frame,
                    prev_frame=prev_frame,
                    corridor=(corridor_x1, corridor_x2, corridor_y1, corridor_y2),
                    ball_type=ball_type,
                    prev_frame2=prev_frame2
                )
                if color_cand and (self.model is None or ball_type != "auto" or color_cand[3] >= (0.45 if ball_type != "baseball" else 0.58)):
                    cx, cy, r, c_conf = color_cand
                    pt_found = TrajectoryPoint(
                        frame_idx=curr_frame,
                        x=cx,
                        y=cy,
                        conf=c_conf,
                        radius=max(4.0, r)
                    )

                # Pass B: High-accuracy YOLO baseball model (with motion pre-gate)
                if pt_found is None and self.model and (curr_frame % frame_stride == 0):
                    has_motion = True
                    if prev_frame is not None:
                        c_small = cv2.resize(frame[crop_y1:crop_y2, crop_x1:crop_x2], (384, 192))
                        p_small = cv2.resize(prev_frame[crop_y1:crop_y2, crop_x1:crop_x2], (384, 192))
                        diff = cv2.absdiff(c_small, p_small)
                        if int(np.max(diff)) < 15:
                            has_motion = False

                    if has_motion:
                        try:
                            crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                            res = self.model.predict(crop, conf=conf_thresh, verbose=False, imgsz=384, device=self.device)
                            if len(res[0].boxes) > 0:
                                valid_boxes = []
                                for b in res[0].boxes:
                                    bx1, by1, bx2, by2 = b.xyxy[0].tolist()
                                    bcx = (bx1 + bx2) / 2.0 + crop_x1
                                    bcy = (by1 + by2) / 2.0 + crop_y1
                                    valid_boxes.append((b, bcx, bcy, float(b.conf[0]), bx2 - bx1))
                                if valid_boxes:
                                    valid_boxes.sort(key=lambda item: item[3], reverse=True)
                                    b_obj, cx, cy, c_conf, sz = valid_boxes[0]
                                    pt_found = TrajectoryPoint(
                                        frame_idx=curr_frame,
                                        x=cx,
                                        y=cy,
                                        conf=c_conf,
                                        radius=max(4.0, sz / 2.0)
                                    )
                        except Exception:
                            pass

                # Fallback to color/motion candidate if YOLO found nothing
                if pt_found is None and color_cand and color_cand[3] >= 0.45:
                    cx, cy, r, c_conf = color_cand
                    pt_found = TrajectoryPoint(
                        frame_idx=curr_frame,
                        x=cx,
                        y=cy,
                        conf=c_conf,
                        radius=max(4.0, r)
                    )
                elif pt_found is not None and color_cand and ball_type in ["red", "pink", "yellow", "orange", "leather"] and color_cand[3] > 0.65 and color_cand[3] > pt_found.conf:
                    cx, cy, r, c_conf = color_cand
                    pt_found = TrajectoryPoint(
                        frame_idx=curr_frame,
                        x=cx,
                        y=cy,
                        conf=c_conf,
                        radius=max(4.0, r)
                    )

                if pt_found:
                    fine_detected.append(pt_found)

                prev_frame2 = prev_frame
                prev_frame = frame.copy()

                if progress_callback:
                    progress_callback(0.35 + 0.65 * ((curr_frame - pitch_start) / float(fine_total)))

                curr_frame += 1

        cap.release()

        # Fine Chain Clustering with physical velocity gating
        f_chains = self._link_points_into_chains(
            fine_detected, width, height, resolved_perspective, max_dt=max(8, frame_stride * 4)
        )
        best_fine = self._select_best_flight_chain(
            f_chains, width, height, total_frames, resolved_perspective, fps=fps
        ) if f_chains else None

        if best_fine:
            detected_points = best_fine
        elif best_chain:
            # Fallback to coarse scan chain if fine tracking missed consecutive frames
            detected_points = [
                TrajectoryPoint(
                    frame_idx=int(h[0]),
                    x=float(h[1]),
                    y=float(h[2]),
                    conf=float(h[3]),
                    radius=max(4.0, float(h[4]) / 2.0)
                ) for h in best_chain
            ]
        else:
            detected_points = []

        if detected_points:
            converted_pts = []
            for p in detected_points:
                if hasattr(p, "frame_idx"):
                    converted_pts.append(p)
                else:
                    converted_pts.append(TrajectoryPoint(frame_idx=int(p[0]), x=float(p[1]), y=float(p[2]), conf=float(p[3]), radius=max(4.0, float(p[4]) / 2.0)))
            detected_points = converted_pts

        # In behind-catcher view, filter out sky/clouds and trim pre-release upward hand swing and post-catch glove motion
        if resolved_perspective in ["behind_plate", "behind_catcher"]:
            detected_points = [p for p in detected_points if p.y >= (height * 0.18)]
            if len(detected_points) >= 4:
                # 1. Trim pre-release windup (pitcher hand moving upward before ball is released)
                for i in range(min(4, len(detected_points) - 1)):
                    p_a = detected_points[i]
                    p_b = detected_points[i + 1]
                    dt = p_b.frame_idx - p_a.frame_idx
                    dy = p_b.y - p_a.y
                    if dt >= 3 and dy < (-35.0 * (height / 1080.0)):
                        detected_points = detected_points[i + 1:]
                        break

                # 2. Trim post-catch catcher glove motion once ball arrives at plate/catcher
                trim_idx = None
                scale_val = max(1.0, width / 1280.0)
                for i in range(len(detected_points) - 1):
                    p_curr = detected_points[i]
                    p_next = detected_points[i + 1]
                    if p_curr.y >= (height * 0.55) or p_curr.x >= (width * 0.62):
                        dt = max(1, p_next.frame_idx - p_curr.frame_idx)
                        speed = np.hypot(p_next.x - p_curr.x, p_next.y - p_curr.y) / float(dt)
                        dy = p_next.y - p_curr.y
                        dx = p_next.x - p_curr.x
                        if dy < (-10.0 * (height / 1080.0)) or (dy > (14.0 * (height / 720.0)) and dy > 1.8 * abs(dx)) or (speed < 4.0 * scale_val and dt >= 2):
                            trim_idx = i + 1
                            break
                if trim_idx is not None and trim_idx >= 3:
                    detected_points = detected_points[:trim_idx]

        # 4. Trajectory Completion: Ballistic Fitting or No-Pitch Return
        if len(detected_points) >= 2:
            # We have real measured detections! Extrapolate ballistic flight
            detected_points = self._extrapolate_measured_flight(
                detected_points, resolved_perspective, width, height, fps
            )
            start_f = detected_points[0].frame_idx
            end_f = detected_points[-1].frame_idx
            full_trajectory = interpolate_missing_frames(detected_points, start_f, end_f)
            smoothed = smooth_trajectory(full_trajectory)
            self.last_resolved_perspective = resolved_perspective
            return smoothed, fps, (width, height)

        self.last_resolved_perspective = resolved_perspective
        return [], fps, (width, height)

    def _link_points_into_chains(
        self,
        points: List[Any],
        width: int,
        height: int,
        perspective: str = "auto",
        max_dt: int = 3
    ) -> List[List[Any]]:
        """
        Links detection hits into temporal trajectory chains with physical
        step-velocity bounding and direction gating.
        Supports both coarse hit tuples (f, x, y, conf, r) and TrajectoryPoint objects.
        """
        if not points:
            return []

        def get_p(p):
            if hasattr(p, "frame_idx"):
                return p.frame_idx, p.x, p.y, p.conf
            return p[0], p[1], p[2], p[3]

        scale = max(1.0, width / 1280.0)
        max_step_speed = 95.0 * scale

        linked: List[List[Any]] = []
        for pt in points:
            pf, px, py, _ = get_p(pt)
            best_c = None
            best_score = float("inf")
            for c in linked:
                prev_f, prev_x, prev_y, _ = get_p(c[-1])
                dt = pf - prev_f
                if 1 <= dt <= max_dt:
                    dx = px - prev_x
                    dy = py - prev_y
                    dist = np.hypot(dx, dy)
                    speed = dist / float(dt)

                    dir_valid = True
                    if perspective in ["behind_plate", "behind_catcher"]:
                        # In behind-catcher view: ball travels from pitcher towards plate/catcher
                        if dx < -15.0 * scale:
                            dir_valid = False
                    elif perspective in ["behind_pitcher", "broadcast"]:
                        # Ball moves towards target/plate (away from camera or across tunnel)
                        # Pitches naturally drop due to gravity
                        pass

                    if speed <= max_step_speed and dir_valid:
                        if len(c) >= 2:
                            p_prev2 = get_p(c[-2])
                            dt_prev = max(1, prev_f - p_prev2[0])
                            vx_prev = (prev_x - p_prev2[1]) / float(dt_prev)
                            vy_prev = (prev_y - p_prev2[2]) / float(dt_prev)
                            pred_x = prev_x + vx_prev * dt
                            pred_y = prev_y + vy_prev * dt
                            pred_err = np.hypot(px - pred_x, py - pred_y)
                            score = pred_err + (dt - 1) * 4.0
                        else:
                            score = (speed / max_step_speed) * 12.0 + (dt - 1) * 4.0

                        if score < best_score:
                            best_score = score
                            best_c = c

            if best_c is not None:
                best_c.append(pt)
            else:
                linked.append([pt])

        return [c for c in linked if len(c) >= 2]

    def _score_chains_for_perspective(
        self,
        chains: List[List[Any]],
        width: int,
        height: int,
        total_frames: int,
        perspective: str,
        fps: float = 30.0,
    ) -> Tuple[Optional[List[Any]], float]:
        """Scores candidate chains against ballistic flight constraints for a given perspective."""
        if not chains:
            return None, 0.0

        def get_pt(p):
            if hasattr(p, "frame_idx"):
                return p.frame_idx, p.x, p.y, p.conf
            return p[0], p[1], p[2], p[3]

        scale = max(1.0, width / 1280.0)
        min_ballistic_speed = 0.8 * scale
        max_ballistic_speed = 95.0 * scale
        min_disp = 20.0 * scale

        def score_chain(c):
            if len(c) < 3:
                return 0.00001
            p0 = get_pt(c[0])
            p1 = get_pt(c[-1])
            dt = max(1, p1[0] - p0[0])
            dx = p1[1] - p0[1]
            dy = p1[2] - p0[2]
            disp = np.hypot(dx, dy)
            speed = disp / float(dt)

            # Reject stationary human movement or impossible teleportation jumps
            if disp < min_disp or speed < min_ballistic_speed or speed > max_ballistic_speed:
                return 0.00001

            # Reject sweeping camera pans across entire screen
            if disp > (width * 0.85):
                return 0.00001

            # Side-view rejection: Model and ABS strike zones require tunnel perspectives (behind-catcher / broadcast)
            if abs(dx) > (width * 0.35) and abs(dx) > (1.8 * max(1.0, abs(dy))):
                return 0.00001

            # Margin guard: pitches travel down the field tunnel, not locked to sideline edges
            if (p0[1] > (width * 0.88) and p1[1] > (width * 0.88)) or (p0[1] < (width * 0.12) and p1[1] < (width * 0.12)):
                return 0.00001

            # Check maximum step speed between consecutive detections in chain
            max_step = 95.0 * scale
            for i in range(len(c) - 1):
                pa = get_pt(c[i])
                pb = get_pt(c[i + 1])
                s_dt = max(1, pb[0] - pa[0])
                s_dist = np.hypot(pb[1] - pa[1], pb[2] - pa[2])
                if (s_dist / float(s_dt)) > max_step:
                    return 0.00001

            # Perspective-specific directional physics constraints
            if perspective in ["behind_plate", "behind_catcher"]:
                # In behind-catcher view: ball travels from pitcher toward catcher/camera (dy > 0)
                if dy < (-25.0 * (height / 1080.0)):
                    return 0.00001
                if dx < -15.0 * scale:
                    return 0.00001
                # Reject chains confined entirely to mound without progressing forward
                if p0[1] < (width * 0.50) and p1[1] < (width * 0.50) and p1[2] < (height * 0.70) and disp < (width * 0.20):
                    return 0.00001
            elif perspective in ["behind_pitcher", "broadcast"]:
                # In behind-pitcher view: ball travels away from camera toward home plate in distance (dy < 0)
                if dy > (25.0 * (height / 1080.0)):
                    return 0.00001
                if disp < (width * 0.08):
                    return 0.00001

            # Path straightness
            path_len = 0.0
            for i in range(len(c) - 1):
                pa = get_pt(c[i])
                pb = get_pt(c[i + 1])
                path_len += np.hypot(pb[1] - pa[1], pb[2] - pa[2])
            straightness = disp / max(1.0, path_len)
            if straightness < 0.20:
                return 0.00001

            # Favor pitch delivery window over post-pitch activity
            start_frac = p0[0] / float(max(1, total_frames))
            temporal_factor = 1.3 if start_frac <= 0.65 else max(0.3, 1.0 - (start_frac - 0.65) * 2.0)

            # Expected pitch duration (~0.25s - 0.85s)
            expected_frames = 0.45 * fps
            dur_ratio = dt / max(1.0, expected_frames)
            dur_factor = 1.2 if 0.3 <= dur_ratio <= 2.2 else max(0.4, 1.0 - abs(1.0 - dur_ratio) * 0.4)

            mean_conf = sum(get_pt(pt)[3] for pt in c) / len(c)
            len_bonus = min(22.0, float(len(c))) ** 1.3

            # Flight progress toward target
            if perspective in ["behind_plate", "behind_catcher"]:
                target_progress = max(0.0, (dx / float(width)) + (dy / float(height)))
                progress_bonus = 1.0 + 3.0 * target_progress
            elif perspective in ["behind_pitcher", "broadcast"]:
                target_progress = max(0.0, -dy / float(height))
                progress_bonus = 1.0 + 3.0 * target_progress
            else:
                progress_bonus = 1.0

            return len_bonus * (mean_conf ** 1.5) * (straightness ** 2.0) * temporal_factor * dur_factor * progress_bonus

        valid_scored = []
        for c in chains:
            sc = score_chain(c)
            if sc > 0.05:
                valid_scored.append((sc, c))

        if valid_scored:
            valid_scored.sort(key=lambda x: x[0], reverse=True)
            return valid_scored[0][1], valid_scored[0][0]

        return None, 0.0

    def _select_best_flight_chain(
        self,
        chains: List[List[Any]],
        width: int,
        height: int,
        total_frames: int,
        perspective: str = "auto",
        fps: float = 30.0,
    ) -> Optional[List[Any]]:
        """
        Selects the best pitch flight chain based on ballistic kinetic energy,
        net displacement, straightness, and velocity, rejecting stationary noise.
        Supports both coarse hit tuples (f, x, y, conf, r) and TrajectoryPoint objects.
        """
        if not chains:
            return None

        if perspective == "auto":
            chain_bp, score_bp = self._score_chains_for_perspective(chains, width, height, total_frames, "behind_pitcher", fps)
            chain_bc, score_bc = self._score_chains_for_perspective(chains, width, height, total_frames, "behind_catcher", fps)
            if score_bc > score_bp and score_bc > 0.05:
                self.last_resolved_perspective = "behind_catcher"
                return chain_bc
            elif score_bp > 0.05:
                self.last_resolved_perspective = "behind_pitcher"
                return chain_bp
            return None

        best_chain, _ = self._score_chains_for_perspective(chains, width, height, total_frames, perspective, fps)
        return best_chain

    def _extrapolate_measured_flight(
        self,
        points: List[TrajectoryPoint],
        perspective: str,
        width: int,
        height: int,
        fps: float
    ) -> List[TrajectoryPoint]:
        """Extrapolates detected points through full flight duration using ballistic kinematics."""
        if not points:
            return points

        p_last = points[-1]
        # Calculate terminal velocity vector from recent detected points
        if len(points) >= 4:
            p_ref = points[-4]
        elif len(points) >= 2:
            p_ref = points[0]
        else:
            p_ref = points[-1]

        dt = max(1, p_last.frame_idx - p_ref.frame_idx)
        vx = (p_last.x - p_ref.x) / float(dt)
        vy = (p_last.y - p_ref.y) / float(dt)

        reached_plate = False
        if perspective in ["behind_plate", "behind_catcher"]:
            # In behind-catcher view, plate crossing requires reaching the plate/catcher region
            if (p_last.x >= (width * 0.62) and p_last.y >= (height * 0.38)) or p_last.x >= (width * 0.72) or p_last.y >= (height * 0.70):
                reached_plate = True
        elif perspective in ["behind_pitcher", "broadcast"]:
            if p_last.y <= (height * 0.55):
                reached_plate = True

        target_pts = int(round(0.42 * fps))
        target_pts = max(10, min(36, target_pts))

        if len(points) >= target_pts and reached_plate:
            return points

        extrapolated = list(points)
        last_frame = p_last.frame_idx
        last_x, last_y = p_last.x, p_last.y

        # Gravity in pixel space
        g_accel = 0.40 * (height / 1080.0)
        scale_x = width / 1280.0
        scale_y = height / 720.0

        max_extrap_steps = max(8, target_pts - len(points))
        if not reached_plate:
            if perspective in ["behind_plate", "behind_catcher"]:
                max_extrap_steps = max(max_extrap_steps, 35)
                # Ensure minimum forward progress velocity towards catcher
                vx = max(vx, 8.0 * scale_x)
                vy = max(vy, 10.0 * scale_y)
            elif perspective in ["behind_pitcher", "broadcast"]:
                max_extrap_steps = max(max_extrap_steps, 20)
                if abs(vy) < 0.1:
                    vy = -6.0 * scale_y

        cur_x = last_x
        cur_y = last_y
        step = 1
        target_slope = max(0.55, min(1.8, vy / max(0.1, vx))) if perspective in ["behind_plate", "behind_catcher"] else 0.0

        while step <= max_extrap_steps:
            cur_f = last_frame + step
            if perspective in ["behind_plate", "behind_catcher"]:
                accel_factor = (1.0 + 0.12 * step) ** 1.3
                step_vx = vx * accel_factor
                step_vy = step_vx * target_slope + 0.5 * (1.2 * height / 1080.0) * (step ** 1.3)
                cur_x += step_vx
                cur_y += step_vy
            else:
                cur_x = last_x + vx * step
                cur_y = last_y + vy * step + 0.5 * g_accel * (step ** 2)

            # Prevent out-of-bounds runaway
            if cur_x > (width * 0.95) or cur_y > (height * 0.92) or cur_x < (width * 0.05) or cur_y < (height * 0.05):
                break

            extrapolated.append(
                TrajectoryPoint(
                    frame_idx=cur_f,
                    x=float(cur_x),
                    y=float(cur_y),
                    conf=max(0.40, p_last.conf * 0.90),
                    radius=max(3.0, p_last.radius * 1.05)
                )
            )

            # Stop once reached plate target
            if perspective in ["behind_plate", "behind_catcher"]:
                if (cur_x >= (width * 0.70) and cur_y >= (height * 0.62)) or cur_x >= (width * 0.76) or cur_y >= (height * 0.74):
                    break
            elif len(extrapolated) >= target_pts:
                break

            step += 1

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
        elif perspective in ["behind_plate", "behind_catcher"]:
            # Behind Catcher looking towards pitcher
            start_x = width * 0.46
            start_y = height * 0.24
            peak_x = width * 0.55
            peak_y = height * 0.22
            end_x = width * 0.72
            end_y = height * 0.65
        else:
            # Broadcast / Mobile Behind-Home View
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
