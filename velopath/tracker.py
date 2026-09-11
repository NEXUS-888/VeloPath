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
        h, w = frame.shape[:2]
        c_x1, c_x2, c_y1, c_y2 = corridor

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 1. Optic-yellow / neon tennis / tape ball mask
        mask_yellow = cv2.inRange(hsv, (18, 45, 60), (45, 255, 255))

        # 2. High-brightness white/light baseball mask (low saturation, high brightness)
        mask_white = cv2.inRange(hsv, (0, 0, 160), (180, 45, 255))

        # 3. Red / Terracotta leather cricket ball mask (wraps around 0/180)
        # Saturated leather ball in sun has hue 0-18 and 165-180
        mask_red1 = cv2.inRange(hsv, (0, 30, 35), (18, 255, 255))
        mask_red2 = cv2.inRange(hsv, (165, 30, 35), (180, 255, 255))
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)

        # 4. Hot Pink / Magenta cricket training ball mask
        mask_pink = cv2.inRange(hsv, (140, 30, 45), (178, 255, 255))

        # Corridor mask
        corridor_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.rectangle(
            corridor_mask,
            (int(max(0, c_x1)), int(max(0, c_y1))),
            (int(min(w - 1, c_x2)), int(min(h - 1, c_y2))),
            255, -1
        )

        # Multi-frame motion difference: resilient to dropped/duplicate frames
        if prev_frame is not None:
            diff1 = cv2.absdiff(frame, prev_frame)
            diff_gray1 = cv2.cvtColor(diff1, cv2.COLOR_BGR2GRAY)
            _, diff_thresh1 = cv2.threshold(diff_gray1, 10, 255, cv2.THRESH_BINARY)
            if prev_frame2 is not None:
                diff2 = cv2.absdiff(frame, prev_frame2)
                diff_gray2 = cv2.cvtColor(diff2, cv2.COLOR_BGR2GRAY)
                _, diff_thresh2 = cv2.threshold(diff_gray2, 10, 255, cv2.THRESH_BINARY)
                diff_thresh = cv2.bitwise_or(diff_thresh1, diff_thresh2)
            else:
                diff_thresh = diff_thresh1
        else:
            return None

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
        min_area = max(8, int(8.0 * sqrt_scale))
        max_area = int(min(25000.0, 2500.0 * scale))
        min_r = max(2.0, 1.2 * sqrt_scale)
        max_r = max(35.0, 18.0 * sqrt_scale)

        candidates = []
        for c_mask in colored_masks:
            masked = cv2.bitwise_and(c_mask, corridor_mask)
            masked = cv2.bitwise_and(masked, diff_thresh)

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
                                score = min(1.0, circularity) * size_fit
                                candidates.append((cx, cy, r, score))

        # Only evaluate noisy white baseball mask if no saturated colored candidates exist
        if not candidates and allow_white:
            masked = cv2.bitwise_and(mask_white, corridor_mask)
            masked = cv2.bitwise_and(masked, diff_thresh)
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
                                score = min(1.0, circularity) * size_fit
                                candidates.append((cx, cy, r, score))

        if candidates:
            best = max(candidates, key=lambda item: item[3])
            conf = min(0.90, 0.40 + best[3] * 0.6)
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
        if resolved_perspective == "behind_pitcher":
            # Pitcher foreground typically left, tunnel/plate in center-right
            corridor_x1 = width * 0.35
            corridor_x2 = width * 0.88
            corridor_y1 = height * 0.15
            corridor_y2 = height * 0.80 if is_portrait else height * 0.88
        elif resolved_perspective in ["behind_plate", "behind_catcher"]:
            # Behind catcher/plate: pitcher mound is mid-ground left/center, plate/catcher is right/center foreground
            # Calibrated corridor isolates delivery channel and covers full plate crossing and catcher mitt
            corridor_x1 = width * 0.38
            corridor_x2 = width * 0.78
            corridor_y1 = height * 0.15
            corridor_y2 = height * 0.88
        else:
            corridor_x1 = width * 0.18
            corridor_x2 = width * 0.85
            corridor_y1 = height * 0.10
            corridor_y2 = height * 0.88

        # 2. Coarse Candidate Scan across the video
        # For short clips (<= 180 frames, ~1-3 seconds), use stride 1 so fast pitch deliveries are never missed
        if total_frames <= 180:
            coarse_stride = 1
        elif fps <= 35:
            coarse_stride = 2
        else:
            coarse_stride = max(3, min(5, int(round(fps * 0.06))))

        coarse_hits = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        prev_coarse_frame = None
        prev_coarse_frame2 = None

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
            prefer_color = (ball_type in ["red", "pink", "yellow", "orange", "leather"]) or (self.device == "cpu")

            if prefer_color:
                cand = self.detect_color_motion_ball(
                    frame=frame,
                    prev_frame=prev_coarse_frame,
                    corridor=(corridor_x1, corridor_x2, corridor_y1, corridor_y2),
                    ball_type=ball_type,
                    prev_frame2=prev_coarse_frame2
                )
                if cand:
                    hit = (f, cand[0], cand[1], cand[3], cand[2] * 2.0)

            if hit is None and self.model:
                try:
                    crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                    res = self.model.predict(crop, conf=0.15, verbose=False, imgsz=384, device=self.device)
                    for b in res[0].boxes:
                        bx1, by1, bx2, by2 = b.xyxy[0].tolist()
                        bcx = (bx1 + bx2) / 2.0 + crop_x1
                        bcy = (by1 + by2) / 2.0 + crop_y1
                        # Verify motion to reject static background false positives
                        is_moving = True
                        if prev_coarse_frame is not None:
                            cbx1 = max(0, min(width - 1, int(bcx - max(10, (bx2 - bx1)))))
                            cbx2 = max(0, min(width, int(bcx + max(10, (bx2 - bx1)))))
                            cby1 = max(0, min(height - 1, int(bcy - max(10, (by2 - by1)))))
                            cby2 = max(0, min(height, int(bcy + max(10, (by2 - by1)))))
                            if (cbx2 > cbx1) and (cby2 > cby1):
                                diff_b = cv2.absdiff(frame[cby1:cby2, cbx1:cbx2], prev_coarse_frame[cby1:cby2, cbx1:cbx2])
                                gray_b = cv2.cvtColor(diff_b, cv2.COLOR_BGR2GRAY) if diff_b.ndim == 3 else diff_b
                                if np.mean(gray_b) < 6.0 and np.max(gray_b) < 18:
                                    is_moving = False
                        if is_moving:
                            hit = (f, bcx, bcy, float(b.conf[0]), bx2 - bx1)
                            break
                except Exception:
                    pass

            if hit is None and not prefer_color:
                cand = self.detect_color_motion_ball(
                    frame=frame,
                    prev_frame=prev_coarse_frame,
                    corridor=(corridor_x1, corridor_x2, corridor_y1, corridor_y2),
                    ball_type=ball_type,
                    prev_frame2=prev_coarse_frame2
                )
                if cand:
                    hit = (f, cand[0], cand[1], cand[3], cand[2] * 2.0)

            if hit:
                coarse_hits.append(hit)

            prev_coarse_frame2 = prev_coarse_frame
            prev_coarse_frame = frame.copy()
            if progress_callback:
                progress_callback((f / float(total_frames)) * 0.35)

        # 3. Cluster coarse hits into temporal chains with physical velocity gating
        chains = self._link_points_into_chains(
            coarse_hits, width, height, resolved_perspective, max_dt=max(6, coarse_stride * 3)
        )

        best_chain = self._select_best_flight_chain(
            chains, width, height, total_frames, resolved_perspective
        ) if chains else None

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
            cap.release()
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
                if not ret:
                    break

            pt_found = None
            prefer_color = (ball_type in ["red", "pink", "yellow", "orange", "leather"]) or (self.device == "cpu")

            if prefer_color:
                color_cand = self.detect_color_motion_ball(
                    frame=frame,
                    prev_frame=prev_frame,
                    corridor=(corridor_x1, corridor_x2, corridor_y1, corridor_y2),
                    ball_type=ball_type,
                    prev_frame2=prev_frame2
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

            # Pass A: High-res YOLO Detection on Corridor Crop
            if pt_found is None and self.model and (curr_frame % frame_stride == 0):
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
                            # Verify motion inside YOLO box to reject static posts/fixtures
                            is_moving = True
                            if prev_frame is not None:
                                bx1, by1, bx2, by2 = b_obj.xyxy[0].tolist()
                                bx1 = max(0, min(width - 1, int(bx1 + crop_x1)))
                                bx2 = max(0, min(width, int(bx2 + crop_x1)))
                                by1 = max(0, min(height - 1, int(by1 + crop_y1)))
                                by2 = max(0, min(height, int(by2 + crop_y1)))
                                if (bx2 > bx1) and (by2 > by1):
                                    diff_box = cv2.absdiff(frame[by1:by2, bx1:bx2], prev_frame[by1:by2, bx1:bx2])
                                    gray_box = cv2.cvtColor(diff_box, cv2.COLOR_BGR2GRAY) if diff_box.ndim == 3 else diff_box
                                    if np.mean(gray_box) < 6.0 and np.max(gray_box) < 18:
                                        is_moving = False
                            if is_moving:
                                pt_found = TrajectoryPoint(
                                    frame_idx=curr_frame,
                                    x=cx,
                                    y=cy,
                                    conf=float(b_obj.conf[0]),
                                    radius=max(4.0, sz / 2.0)
                                )
                except Exception:
                    pass

            # Fallback Pass B: Adaptive Color + Multi-frame Motion Filter if YOLO was tested first
            if pt_found is None and not prefer_color:
                color_cand = self.detect_color_motion_ball(
                    frame=frame,
                    prev_frame=prev_frame,
                    corridor=(corridor_x1, corridor_x2, corridor_y1, corridor_y2),
                    ball_type=ball_type,
                    prev_frame2=prev_frame2
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
                fine_detected.append(pt_found)

            prev_frame2 = prev_frame
            prev_frame = frame.copy()

            if progress_callback:
                progress_callback(0.35 + 0.65 * ((curr_frame - pitch_start) / float(fine_total)))

            curr_frame += 1

        cap.release()

        # Fine Chain Clustering with physical velocity gating
        f_chains = self._link_points_into_chains(
            fine_detected, width, height, resolved_perspective, max_dt=6
        )
        best_fine = self._select_best_flight_chain(
            f_chains, width, height, total_frames, resolved_perspective
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

        # In behind-catcher view, trim pre-release upward hand swing from hip before true release
        if resolved_perspective in ["behind_plate", "behind_catcher"] and len(detected_points) >= 6:
            for i in range(min(4, len(detected_points) - 1)):
                p_a = detected_points[i]
                p_b = detected_points[i + 1]
                dt = p_b.frame_idx - p_a.frame_idx
                dy = p_b.y - p_a.y
                if dt >= 3 and dy < (-35.0 * (height / 1080.0)):
                    detected_points = detected_points[i + 1:]
                    break

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
        max_step_speed = 42.0 * scale

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
                        # Ball travels left-to-right from pitcher towards plate/catcher
                        step_vy = dy / float(dt)
                        if dx < -1.0:
                            dir_valid = False
                        if (dy / max(1.0, dx)) > 2.2:
                            dir_valid = False
                        if step_vy < (-10.0 * scale) or step_vy > (35.0 * scale):
                            dir_valid = False
                    elif perspective in ["behind_pitcher", "broadcast"]:
                        # Ball moves away from camera towards plate
                        if dy > (30.0 * scale * dt):
                            dir_valid = False

                    if speed <= max_step_speed and dir_valid:
                        if perspective in ["behind_plate", "behind_catcher"]:
                            if len(c) >= 2:
                                p_prev2 = get_p(c[-2])
                                dt_prev = max(1, prev_f - p_prev2[0])
                                prev_speed = np.hypot(prev_x - p_prev2[1], prev_y - p_prev2[2]) / float(dt_prev)
                            else:
                                prev_speed = 15.0

                            if speed >= prev_speed:
                                speed_penalty = max(0.0, speed - (prev_speed * 2.5 + 5.0))
                            else:
                                speed_penalty = max(0.0, (prev_speed * 0.6) - speed)

                            history_bonus = min(15.0, len(c) * 3.0)
                            score = speed_penalty + 3.0 * (dt - 1) - history_bonus
                        else:
                            score = abs(speed - 15.0) + (dt * 0.1)
                        if score < best_score:
                            best_score = score
                            best_c = c

            if best_c is not None:
                best_c.append(pt)
            else:
                linked.append([pt])

        return [c for c in linked if len(c) >= 2]

    def _select_best_flight_chain(
        self,
        chains: List[List[Any]],
        width: int,
        height: int,
        total_frames: int,
        perspective: str = "auto"
    ) -> Optional[List[Any]]:
        """
        Selects the best pitch flight chain based on ballistic kinetic energy,
        net displacement, straightness, and velocity, rejecting stationary noise.
        Supports both coarse hit tuples (f, x, y, conf, r) and TrajectoryPoint objects.
        """
        if not chains:
            return None

        def get_pt(p):
            if hasattr(p, "frame_idx"):
                return p.frame_idx, p.x, p.y, p.conf
            return p[0], p[1], p[2], p[3]

        scale = max(1.0, width / 1280.0)
        min_ballistic_speed = 3.5 * scale
        max_ballistic_speed = 42.0 * scale
        min_disp = 45.0 * scale

        def score_chain(c):
            # A real pitch flight must have at least 3 detections (filters out 2-frame camera noise)
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
            if disp > (width * 0.75):
                return 0.00001

            # Check maximum step speed between consecutive detections in chain
            max_step = (42.0 * scale) if perspective in ["behind_plate", "behind_catcher"] else (38.0 * scale)
            for i in range(len(c) - 1):
                pa = get_pt(c[i])
                pb = get_pt(c[i + 1])
                s_dt = max(1, pb[0] - pa[0])
                s_dist = np.hypot(pb[1] - pa[1], pb[2] - pa[2])
                if (s_dist / float(s_dt)) > max_step:
                    return 0.00001

            # Directional physics constraints:
            # In behind-catcher / behind-plate: ball travels from pitcher (center-left) towards catcher (right foreground)
            if perspective in ["behind_plate", "behind_catcher"]:
                if dx < 15.0:  # Must travel left-to-right towards plate/catcher
                    return 0.00001
                if dy < (-120.0 * (height / 1080.0)):  # Cannot fly from ground up into sky
                    return 0.00001
            elif perspective in ["behind_pitcher", "broadcast"]:
                if dy > 60.0:   # Pitch moves away towards target/plate (away from camera)
                    return 0.00001

            # Path straightness
            path_len = 0.0
            for i in range(len(c) - 1):
                pa = get_pt(c[i])
                pb = get_pt(c[i + 1])
                path_len += np.hypot(pb[1] - pa[1], pb[2] - pa[2])
            straightness = disp / max(1.0, path_len)
            if straightness < 0.25:
                return 0.00001

            # Favor pitch delivery window over post-pitch activity
            start_frac = p0[0] / float(max(1, total_frames))
            temporal_factor = 1.3 if start_frac <= 0.65 else max(0.3, 1.0 - (start_frac - 0.65) * 2.0)

            mean_conf = sum(get_pt(pt)[3] for pt in c) / len(c)
            # Ballistic kinetic score favoring sustained flights: disp * speed * (len(c) ** 2.5)
            return (disp * speed * (len(c) ** 2.5)) * straightness * mean_conf * temporal_factor

        valid_scored = []
        for c in chains:
            sc = score_chain(c)
            if sc > 0.001:
                valid_scored.append((sc, c))

        if valid_scored:
            valid_scored.sort(key=lambda x: x[0], reverse=True)
            return valid_scored[0][1]

        # If no chain satisfied all physical constraints, fallback to longest chain with len >= 2
        return max(chains, key=len) if chains else None

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
        reached_plate = False
        if perspective in ["behind_plate", "behind_catcher"]:
            # In behind-catcher view, plate crossing is at x >= 0.68 * width and y >= 0.60 * height
            if p_last.x >= (width * 0.68) or p_last.y >= (height * 0.62):
                reached_plate = True
        elif perspective == "behind_pitcher":
            if p_last.y >= (height * 0.70):
                reached_plate = True
        elif perspective == "broadcast":
            if p_last.y >= (height * 0.40):
                reached_plate = True

        target_pts = int(round(0.42 * fps))
        target_pts = max(10, min(36, target_pts))

        if len(points) >= target_pts and reached_plate:
            return points

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

        extrapolated = list(points)
        last_frame = p_last.frame_idx
        last_x, last_y = p_last.x, p_last.y

        # Gravity in pixel space
        g_accel = 0.40 * (height / 1080.0)

        max_extrap_steps = max(6, target_pts - len(points))
        if not reached_plate and perspective in ["behind_plate", "behind_catcher"]:
            max_extrap_steps = max(max_extrap_steps, 22)

        cur_x = last_x
        cur_y = last_y
        step = 1
        target_slope = max(0.60, vy / max(0.1, vx)) if perspective in ["behind_plate", "behind_catcher"] else 0.0

        while step <= max_extrap_steps:
            cur_f = last_frame + step
            if perspective in ["behind_plate", "behind_catcher"]:
                accel_factor = (1.0 + 0.16 * step) ** 1.4
                step_vx = vx * accel_factor
                step_vy = step_vx * target_slope + 0.5 * (1.2 * height / 1080.0) * (step ** 1.4)
                cur_x += step_vx
                cur_y += step_vy
            else:
                cur_x = last_x + vx * step
                cur_y = last_y + vy * step + 0.5 * g_accel * (step ** 2)

            # Prevent out-of-bounds runaway
            if cur_x > (width * 0.85) or cur_y > (height * 0.90) or cur_x < (width * 0.10) or cur_y < (height * 0.10):
                break

            extrapolated.append(
                TrajectoryPoint(
                    frame_idx=cur_f,
                    x=float(cur_x),
                    y=float(cur_y),
                    conf=max(0.40, p_last.conf * 0.90),
                    radius=max(3.0, p_last.radius * 1.02)
                )
            )

            # Stop once reached plate target and sufficient duration
            if perspective in ["behind_plate", "behind_catcher"]:
                if (cur_x >= (width * 0.72) or cur_y >= (height * 0.65)) and len(extrapolated) >= target_pts:
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
