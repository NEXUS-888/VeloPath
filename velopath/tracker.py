"""
Ball detection, tracking, Kalman filtering, and spline trajectory interpolation.
Optimized for high-speed video inference with motion-guided candidate search and spline smoothing.
"""
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple, Callable
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
            result.append(TrajectoryPoint(frame_idx=int_f, x=float(x), y=float(y), conf=0.6, radius=0.0))  # size not measured

    return result


def select_flight(hits: List[tuple], width: int, height: int, max_gap: int = 4,
                  iters: int = 600, seed: int = 0) -> Optional[List[tuple]]:
    """
    Picks the ball flight among per-frame detection hits (frame, x, y, conf, size).
    Camera-angle agnostic: a flight is the longest gap-free run of hits lying on one
    smooth quadratic image path (RANSAC) that actually moves: across the frame, or in depth
    (ball size changes >= 1.5x, e.g. filmed from behind the pitcher).
    Returns one hit per frame, sorted by frame, or None.
    """
    if len(hits) < 4:
        return None
    h = np.asarray([p[:3] for p in hits], dtype=float)
    size = np.asarray([max(1.0, float(p[4])) if len(p) > 4 else 1.0 for p in hits])
    t, xy = h[:, 0], h[:, 1:3]
    tol = max(4.0, 0.006 * max(width, height))
    min_disp = 0.05 * min(width, height)
    rng = np.random.default_rng(seed)

    def run_around(cx, cy, t_ref):
        err = np.hypot(np.polyval(cx, t) - xy[:, 0], np.polyval(cy, t) - xy[:, 1])
        best_per_frame = {}
        for i in np.flatnonzero(err < tol):
            if t[i] not in best_per_frame or err[i] < err[best_per_frame[t[i]]]:
                best_per_frame[t[i]] = i
        if t_ref not in best_per_frame:
            return []
        frames = sorted(best_per_frame)
        lo = hi = frames.index(t_ref)
        while lo > 0 and frames[lo] - frames[lo - 1] <= max_gap:
            lo -= 1
        while hi < len(frames) - 1 and frames[hi + 1] - frames[hi] <= max_gap:
            hi += 1
        return [best_per_frame[f] for f in frames[lo:hi + 1]]

    def refit(run):
        deg = 3 if len(run) >= 8 else 2  # long flights bend under perspective; cubic tracks that
        return run_around(np.polyfit(t[run], xy[run, 0], deg), np.polyfit(t[run], xy[run, 1], deg), t[run[len(run) // 2]]) or run

    best: List[int] = []
    for _ in range(iters):
        a = rng.integers(len(h))
        near = np.flatnonzero((t != t[a]) & (np.abs(t - t[a]) <= 3 * max_gap))
        if near.size < 2:
            continue
        s = np.r_[a, rng.choice(near, 2, replace=False)]
        if np.unique(t[s]).size < 3:
            continue
        run = run_around(np.polyfit(t[s], xy[s, 0], 2), np.polyfit(t[s], xy[s, 1], 2), t[s[0]])
        if len(run) < 3:
            continue
        run = refit(refit(run))  # absorb every hit consistent with the run's own fit
        ends = size[run[:3]].mean(), size[run[-3:]].mean()
        moved = np.hypot(*(xy[run[-1]] - xy[run[0]])) >= min_disp or max(ends) >= 1.5 * min(ends)
        if len(run) > len(best) and moved:
            best = run
    return [hits[i] for i in best] if len(best) >= 4 else None

def predict_at(hits: List[tuple], f: int, k: int = 6) -> Tuple[float, float]:
    """Ball (x, y) at frame f from a quadratic through the k hits nearest in time. Local, so it follows
    paths that perspective bends, and extrapolates past the ends from the freshest hits."""
    near = sorted(hits, key=lambda h: abs(h[0] - f))[:k]
    t = [h[0] for h in near]
    deg = min(2, len(near) - 1)
    return (float(np.polyval(np.polyfit(t, [h[1] for h in near], deg), f)),
            float(np.polyval(np.polyfit(t, [h[2] for h in near], deg), f)))


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
            self.device, self.device_name = get_acceleration_device()
            device_name = self.device_name
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
                if self.device == "0":
                    try:
                        self.model.to("cuda")
                    except Exception:
                        pass
                print(f"[PitchTracker] Loaded model weights from: {model_path}")
                print(f"[PitchTracker] Compute acceleration: {device_name}")
            except Exception as e:
                print(f"[PitchTracker] Note: Could not load YOLO: {e}")

        self._normal_model = None
        # hybrid: if the small fast model is present it scans whole frames; the big model above refines windows
        self.scan_model = None
        try:
            from velopath.model_manager import resolve_small_model_path
            small = resolve_small_model_path()
            if small:
                from ultralytics import YOLO
                self.scan_model = YOLO(small, task="detect")
                if self.device == "0":
                    try:
                        self.scan_model.to("cuda")
                    except Exception:
                        pass
                print(f"[PitchTracker] Fast scan model: {small}")
        except Exception as e:
            print(f"[PitchTracker] Note: small scan model not used: {e}")

    def _get_model(self, is_normal: bool = False):
        if is_normal:
            if self._normal_model is None:
                candidates = ["yolov8n.pt", os.path.join(os.path.dirname(__file__), "..", "yolov8n.pt")]
                for cand in candidates:
                    if os.path.exists(cand):
                        try:
                            from ultralytics import YOLO
                            self._normal_model = YOLO(cand)
                            break
                        except Exception:
                            pass
                if self._normal_model is None:
                    try:
                        from ultralytics import YOLO
                        self._normal_model = YOLO("yolov8n.pt")
                    except Exception:
                        self._normal_model = self.model
            return self._normal_model or self.model
        return self.model

    def _get_target_classes(self, model, is_normal: bool = False) -> Optional[List[int]]:
        if model is None or not hasattr(model, "names") or not model.names:
            return None
        names = model.names
        if not is_normal:
            # In baseball model: class 2 is baseball. Avoid 0 (glove) and 1 (homeplate)
            for k, v in names.items():
                if str(v).lower() in ["baseball", "ball"]:
                    return [int(k)]
            if 2 in names and "baseball" in str(names[2]).lower():
                return [2]
        # In normal/general mode: sports ball (class 32 in COCO) or any ball
        for k, v in names.items():
            if str(v).lower() in ["sports ball", "ball", "baseball"]:
                return [int(k)]
        if 32 in names:
            return [32]
        return None

    def detect_color_motion_ball(
        self,
        frame: np.ndarray,
        prev_frame: Optional[np.ndarray],
        corridor: Tuple[float, float, float, float],
        ball_type: str = "auto",
        prev_frame2: Optional[np.ndarray] = None,
        return_all: bool = False,
        max_candidates: int = 6
    ) -> Any:
        """
        Detects bright yellow/neon tennis balls, white baseballs, red leather cricket balls,
        and hot pink training balls using adaptive HSV filtering, multi-frame differencing,
        and shape/streak-fit scoring.
        Returns: (cx, cy, radius, confidence) or None (or List of candidates if return_all=True).
        """
        if frame is None or prev_frame is None:
            return [] if return_all else None
        h, w = frame.shape[:2]
        c_x1, c_x2, c_y1, c_y2 = corridor
        roi_x1 = max(0, int(c_x1))
        roi_x2 = min(w, int(c_x2))
        roi_y1 = max(0, int(c_y1))
        roi_y2 = min(h, int(c_y2))
        if roi_x2 <= roi_x1 or roi_y2 <= roi_y1:
            return [] if return_all else None

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
            diff_thresh = cv2.bitwise_and(diff_thresh1, diff_thresh2)  # AND keeps only the ball at t (OR adds ghosts)
        else:
            diff_thresh = diff_thresh1

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # 1. Optic-yellow / neon tennis / training ball mask (tolerant to motion blur and daylight)
        mask_yellow = cv2.inRange(hsv, (20, 50, 60), (55, 255, 255))

        # 2. High-brightness white/light baseball mask (saturation up to 75 allows grass-tinted motion blur)
        mask_white = cv2.inRange(hsv, (0, 0, 140), (180, 75, 255))

        # 3. Red / Terracotta leather cricket ball mask (wraps around 0/180)
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

        def eval_contours(cnts):
            c_found = []
            for c in cnts:
                area = cv2.contourArea(c)
                if min_area <= area <= max_area:
                    perimeter = cv2.arcLength(c, True)
                    rx, ry, rw, rh = cv2.boundingRect(c)
                    aspect = max(rw, rh) / max(1.0, min(rw, rh))
                    thickness = min(rw, rh)
                    is_circ = (perimeter > 0) and ((4.0 * np.pi * area / (perimeter * perimeter)) >= 0.14)
                    is_streak = (aspect >= 1.6) and (thickness <= 14.0 * sqrt_scale)
                    if is_circ or is_streak:
                        (cx, cy), r = cv2.minEnclosingCircle(c)
                        if min_r <= r <= max_r or (is_streak and thickness >= min_r):
                            if (1.0 * sqrt_scale) <= r <= (14.0 * sqrt_scale):
                                size_fit = 1.0
                            else:
                                target_mid = 5.0 * sqrt_scale
                                size_fit = 1.0 / (1.0 + abs(r - target_mid) / (1.0 * target_mid))
                            area_bonus = min(2.5, max(0.5, (area / (min_area * 3.5)) ** 0.5))
                            shape_score = min(1.0, (4.0 * np.pi * area / (perimeter * perimeter))) if is_circ else 0.75
                            score = shape_score * size_fit * area_bonus
                            c_found.append((cx + roi_x1, cy + roi_y1, r, score))
            return c_found

        candidates = []
        for c_mask in colored_masks:
            masked = cv2.bitwise_and(c_mask, diff_thresh)
            cnts, _ = cv2.findContours(masked, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            candidates.extend(eval_contours(cnts))

        # Evaluate white mask when allowed
        if allow_white:
            masked = cv2.bitwise_and(mask_white, diff_thresh)
            cnts, _ = cv2.findContours(masked, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            candidates.extend(eval_contours(cnts))

        if candidates:
            candidates.sort(key=lambda item: item[3], reverse=True)
            if return_all:
                res_all = []
                for item in candidates[:max_candidates]:
                    c_conf = min(0.70, 0.35 + item[3] * 0.35)
                    res_all.append((item[0], item[1], item[2], c_conf))
                return res_all
            best = candidates[0]
            conf = min(0.70, 0.35 + best[3] * 0.35)
            return (best[0], best[1], best[2], conf)
        return [] if return_all else None

    def _yolo_hits(self, model, img, classes, imgsz: int, conf: float, ox: float = 0.0, oy: float = 0.0) -> List[tuple]:
        """Returns (cx, cy, conf, width, cls) for every box YOLO finds in img, in full-frame coordinates."""
        kwargs = {"conf": conf, "verbose": False, "imgsz": imgsz, "device": self.device}
        if classes is not None:
            kwargs["classes"] = classes
        res = model.predict(img, **kwargs)[0].boxes
        return [((b[0] + b[2]) / 2.0 + ox, (b[1] + b[3]) / 2.0 + oy, float(c), float(b[2] - b[0]), int(k))
                for b, c, k in zip(res.xyxy.tolist(), res.conf.tolist(), res.cls.tolist())]

    def _refine_flight(self, video_path, model, classes, flight, width, height, total_frames, pad=6, win=320, lo=0):
        """Re-detects the ball at native resolution in a small window around the predicted path,
        `pad` frames before the start and walking forward until the ball is lost for `pad` frames
        or stops (caught), so small/far balls are not lost to downscaling.
        Colour/motion only fills frames YOLO misses between YOLO-confirmed hits: it never steers the
        prediction or extends the flight (after bat contact the window is full of moving blobs)."""
        first, last = int(flight[0][0]), int(flight[-1][0])
        f0 = max(lo, first - pad)
        gate = 2.0 * max(4.0, 0.006 * max(width, height))
        min_step = gate / 4.0  # px/frame; a held or caught ball moves less than this
        cap = cv2.VideoCapture(video_path)
        f = max(0, f0 - 2) - 1  # two frames early: the motion fallback differences against them
        cap.set(cv2.CAP_PROP_POS_FRAMES, f + 1)
        hits, filled = list(flight), []
        have = {h[0] for h in flight}
        cur = prev = None
        while f < min(total_frames - 1, last + pad):
            f += 1
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            prev2, prev, cur = prev, cur, frame
            if f < f0 or f in have:
                continue
            px, py = predict_at(hits, f)
            x1 = int(min(max(0, px - win / 2), max(0, width - win)))
            y1 = int(min(max(0, py - win / 2), max(0, height - win)))
            near = [(np.hypot(x - px, y - py), x, y, c, w) for x, y, c, w, _ in
                    self._yolo_hits(model, frame[y1:y1 + win, x1:x1 + win], classes, win, 0.05, x1, y1)]
            near = [n for n in near if n[0] <= gate]
            if not near:  # ball too small for YOLO: colour/motion inside the gate, kept only if YOLO brackets it
                motion = [(np.hypot(x - px, y - py), x, y, c, 2.0 * r) for x, y, r, c in self.detect_color_motion_ball(
                    cur, prev, (x1, x1 + win, y1, y1 + win), "auto", prev2, return_all=True)]
                motion = [n for n in motion if n[0] <= gate]
                if motion:
                    filled.append((f, *min(motion)[1:]))
                continue
            _, x, y, c, w = min(near)
            if not first <= f <= last:  # extending: the nearest known hit must be left behind at flight speed
                n = min(hits, key=lambda h: abs(h[0] - f))
                if np.hypot(x - n[1], y - n[2]) < min_step * abs(f - n[0]):
                    continue
            hits.append((f, x, y, c, w))
            first, last = min(first, f), max(last, f)
        cap.release()
        hits += [h for h in filled if first < h[0] < last]
        return select_flight(hits, width, height) or flight

    def track_video(
        self,
        video_path: str,
        conf_thresh: float = 0.15,
        ball_type: str = "auto",
        perspective: str = "auto",
        progress_callback: Optional[Callable[[float], None]] = None,
        mode: str = "baseball",
        time_window: Optional[Tuple[float, float]] = None,
    ) -> Tuple[List[TrajectoryPoint], float, Tuple[int, int]]:
        """
        1. Scan: YOLO on every frame (stride 2 for long clips) at 640px; colour/motion
           candidates are used only if YOLO yields no flight.
        2. Select: the flight is the longest consistent moving quadratic path (select_flight).
        3. Refine: native-resolution windows along the path fill gaps and recover the true ends.
        Returns measured ball centres from first to last flight frame, gaps filled by PCHIP.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Could not open video: {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        # only the user-marked pitch is searched: cost scales with the window, not the clip
        lo, hi = 0, total_frames
        if time_window:
            lo = max(0, min(total_frames, int(time_window[0] * fps)))
            hi = max(lo, min(total_frames, int(np.ceil(time_window[1] * fps)) + 1))
            cap.set(cv2.CAP_PROP_POS_FRAMES, lo)
        n = float(max(1, hi - lo))

        raw_persp = (perspective or "auto").lower().strip()
        is_normal = (mode or "baseball").lower().strip() in ["normal", "general"] or raw_persp in ["normal", "general"]
        model = self._get_model(is_normal)
        classes = self._get_target_classes(model, is_normal)
        small = getattr(self, "scan_model", None)
        scanner = small if small is not None and not is_normal else model
        # home plate rides along in the ball scan for free; it anchors the strike zone (pipeline)
        plate_cls = None if is_normal or scanner is None else next(
            (int(k) for k, v in getattr(scanner, "names", {}).items() if str(v).lower() == "homeplate"), None)
        scan_classes = classes + [plate_cls] if classes is not None and plate_cls is not None else classes
        # full-frame scan only seeds the flight; _refine_flight restores native resolution.
        # The small model was trained at 1280 and is cheap enough to scan there.
        scan_sz = 1280 if scanner is not model else 640
        stride = 1 if hi - lo <= 300 else 2

        yolo_hits, motion_hits, plates = [], [], []
        prev, prev2 = None, None
        for f in range(lo, hi):
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            if f % stride == 0:
                if model is not None:
                    for x, y, c, w, k in self._yolo_hits(scanner, frame, scan_classes, scan_sz, conf_thresh):
                        if k == plate_cls:
                            plates.append((x, y, w))
                        else:
                            yolo_hits.append((f, x, y, c, w))
                motion_hits += [(f, x, y, c, 2.0 * r) for x, y, r, c in self.detect_color_motion_ball(
                    frame, prev, (0, width, 0, height), ball_type, prev2, return_all=True)]
                prev2, prev = prev, frame
            if progress_callback:
                progress_callback(0.8 * (f - lo) / n)
        cap.release()
        # (cx, cy, width) of the plate; a few hits required so one stray box can't place the zone
        self.last_plate = tuple(float(v) for v in np.median(plates, axis=0)) if len(plates) >= 3 else None

        flight = select_flight(yolo_hits, width, height)
        if not flight and model is not None and max(width, height) > 1.5 * scan_sz:
            # ball can shrink below YOLO's reach at 640 on HD/portrait frames: one slower 1280 pass
            # (every other frame) before trusting colour/motion, which latches onto arms and sleeves
            cap = cv2.VideoCapture(video_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, lo)
            for f in range(lo, hi):
                if progress_callback:
                    progress_callback(0.8 + 0.15 * (f - lo) / n)
                if f % 2 and cap.grab():
                    continue
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                yolo_hits += [(f, x, y, c, w) for x, y, c, w, _ in self._yolo_hits(model, frame, classes, 1280, conf_thresh)]
            cap.release()
            flight = select_flight(yolo_hits, width, height)
        flight = flight or select_flight(motion_hits, width, height)
        if flight and model is not None:
            for _ in range(2):
                flight = self._refine_flight(video_path, model, classes, flight, width, height, hi, lo=lo)
        if progress_callback:
            progress_callback(1.0)

        if not flight:
            self.last_resolved_perspective = "normal" if is_normal else raw_persp
            return [], fps, (width, height)

        dx, dy = flight[-1][1] - flight[0][1], flight[-1][2] - flight[0][2]
        if is_normal:
            self.last_resolved_perspective = "normal"
        elif raw_persp != "auto":
            self.last_resolved_perspective = raw_persp
        else:
            grow = np.mean([h[4] for h in flight[-3:]]) / max(1.0, np.mean([h[4] for h in flight[:3]]))
            if grow <= 1 / 1.5 or grow >= 1.5:  # ball shrinks flying away / grows flying toward the camera
                self.last_resolved_perspective = "behind_pitcher" if grow < 1 else "behind_catcher"
            else:
                self.last_resolved_perspective = "broadcast" if abs(dx) > abs(dy) else ("behind_catcher" if dy > 0 else "behind_pitcher")

        points = [TrajectoryPoint(frame_idx=int(f), x=float(x), y=float(y), conf=float(c), radius=float(w) / 2.0)
                  for f, x, y, c, w in flight]
        return interpolate_missing_frames(points, points[0].frame_idx, points[-1].frame_idx), fps, (width, height)
