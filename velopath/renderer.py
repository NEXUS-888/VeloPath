"""
Pitch Lab visual renderer: Glowing trajectory ribbon, strike zone overlay, and HUD cards.
Refined for dynamic scaling across both portrait smartphone (384px) and 1080p widescreen formats.
"""
import os
import subprocess
from typing import List, Tuple, Optional
import cv2
import numpy as np
from velopath.tracker import TrajectoryPoint
from velopath.strike_zone import StrikeZone, PitchCallResult


GRAPHIC_THEMES = {
    "statcast_cyan": {
        "name": "Statcast 3D Cyan",
        "primary": (255, 230, 0),      # BGR: Electric Cyan (#00E5FF)
        "glow": (240, 150, 0),         # BGR: Cyan Glow Bloom
        "core": (255, 255, 255),       # Pure White Laser Core
    },
    "neon_gold": {
        "name": "VeloPath Neon Gold",
        "primary": (0, 215, 255),      # BGR: Bright Gold (#FFD700)
        "glow": (0, 130, 255),         # BGR: Warm Amber Glow
        "core": (255, 255, 255),
    },
    "electric_violet": {
        "name": "Electric Violet",
        "primary": (251, 64, 224),     # BGR: Neon Violet (#E040FB)
        "glow": (200, 20, 160),        # BGR: Deep Purple
        "core": (255, 255, 255),
    },
    "laser_emerald": {
        "name": "Laser Emerald",
        "primary": (118, 230, 0),      # BGR: Spring Green (#00E676)
        "glow": (50, 180, 0),
        "core": (255, 255, 255),
    }
}


class PitchRenderer:
    """
    Renders high-definition Statcast 3D trajectory streamline graphics,
    broadcast-accurate strike zone box, and bottom telemetry HUD card onto video frames.
    """
    def __init__(
        self,
        ribbon_color: Optional[Tuple[int, int, int]] = None,
        glow_color: Optional[Tuple[int, int, int]] = None,
        graphic_style: str = "statcast_cyan",
        max_trail_length: Optional[int] = None,
    ):
        theme = GRAPHIC_THEMES.get(graphic_style, GRAPHIC_THEMES["statcast_cyan"])
        self.graphic_style = graphic_style
        self.ribbon_color = ribbon_color or theme["primary"]
        self.glow_color = glow_color or theme["glow"]
        self.core_color = theme.get("core", (255, 255, 255))
        self.max_trail_length = max_trail_length

    def set_graphic_style(self, style_name: str) -> None:
        """Dynamically switch graphic theme."""
        theme = GRAPHIC_THEMES.get(style_name, GRAPHIC_THEMES["statcast_cyan"])
        self.graphic_style = style_name
        self.ribbon_color = theme["primary"]
        self.glow_color = theme["glow"]
        self.core_color = theme.get("core", (255, 255, 255))

    def draw_glowing_ribbon(
        self,
        frame: np.ndarray,
        points: List[TrajectoryPoint],
        current_frame_idx: int,
    ) -> np.ndarray:
        """
        Renders a slim, aerodynamic Statcast 3D laser streamline with multi-layer
        emissive bloom, white-hot center laser core, and glowing baseball marker.
        """
        active_points = [p for p in points if p.frame_idx <= current_frame_idx]
        if len(active_points) < 2:
            return frame

        h, w = frame.shape[:2]

        # Unique points sorted by frame
        unique_pts = []
        seen = set()
        for p in points:
            if p.frame_idx not in seen and p.frame_idx <= current_frame_idx:
                seen.add(p.frame_idx)
                unique_pts.append(p)
        unique_pts.sort(key=lambda p: p.frame_idx)

        if len(unique_pts) < 2:
            return frame

        frames = np.array([p.frame_idx for p in unique_pts], dtype=float)
        xs = np.array([p.x for p in unique_pts], dtype=float)
        ys = np.array([p.y for p in unique_pts], dtype=float)

        # High-resolution cubic spline interpolation
        try:
            from scipy.interpolate import CubicSpline
            if len(frames) >= 3:
                cs_x = CubicSpline(frames, xs, bc_type='natural')
                cs_y = CubicSpline(frames, ys, bc_type='natural')
            else:
                from scipy.interpolate import interp1d
                cs_x = interp1d(frames, xs, kind='linear', fill_value="extrapolate")
                cs_y = interp1d(frames, ys, kind='linear', fill_value="extrapolate")
        except Exception:
            from scipy.interpolate import interp1d
            cs_x = interp1d(frames, xs, kind='linear', fill_value="extrapolate")
            cs_y = interp1d(frames, ys, kind='linear', fill_value="extrapolate")

        curr_end_f = min(current_frame_idx, unique_pts[-1].frame_idx)
        n_samples = max(30, int((curr_end_f - frames[0] + 1) * 14))
        sub_t = np.linspace(frames[0], curr_end_f, n_samples)
        sub_x = cs_x(sub_t)
        sub_y = cs_y(sub_t)

        curve_pts = np.vstack([sub_x, sub_y]).T
        dx = np.gradient(curve_pts[:, 0])
        dy = np.gradient(curve_pts[:, 1])
        norms = np.sqrt(dx**2 + dy**2)
        dx /= np.maximum(norms, 1e-6)
        dy /= np.maximum(norms, 1e-6)
        nx, ny = -dy, dx

        # Realistic Statcast streamline radius: slim at release, matching baseball radius at plate
        scale = max(0.4, min(1.2, w / 1600.0))
        radii = np.linspace(1.8 * scale, 5.5 * scale, len(curve_pts))
        left_edge = curve_pts + np.stack([nx, ny], axis=1) * radii[:, None]
        right_edge = curve_pts - np.stack([nx, ny], axis=1) * radii[:, None]

        # 1. Outer Bloom Glow Layer (soft ambient illumination)
        bloom_overlay = np.zeros_like(frame)
        bloom_w = radii[:, None] + (4.0 * scale)
        bloom_poly = np.vstack([
            curve_pts + np.stack([nx, ny], axis=1) * bloom_w,
            (curve_pts - np.stack([nx, ny], axis=1) * bloom_w)[::-1]
        ]).astype(np.int32)
        cv2.fillPoly(bloom_overlay, [bloom_poly], self.glow_color)
        bloom_blurred = cv2.GaussianBlur(bloom_overlay, (15, 15), 0)
        frame = cv2.addWeighted(bloom_blurred, 0.45, frame, 1.0, 0)

        # 2. Sleek Semi-Translucent Streamline Body
        body_overlay = frame.copy()
        tube_poly = np.vstack([left_edge, right_edge[::-1]]).astype(np.int32)
        cv2.fillPoly(body_overlay, [tube_poly], self.ribbon_color)
        frame = cv2.addWeighted(body_overlay, 0.40, frame, 0.60, 0)

        # 3. Dual Anti-Aliased Boundary Rails
        line_w = max(1, int(1.2 * scale))
        cv2.polylines(frame, [left_edge.astype(np.int32)], False, self.ribbon_color, line_w, lineType=cv2.LINE_AA)
        cv2.polylines(frame, [right_edge.astype(np.int32)], False, self.ribbon_color, line_w, lineType=cv2.LINE_AA)

        # 4. Hyper-Bright Laser Core Line down the center
        core_pts = curve_pts.astype(np.int32)
        cv2.polylines(frame, [core_pts], False, self.core_color, max(1, int(1.6 * scale)), lineType=cv2.LINE_AA)

        # 5. Glowing 3D Ball Marker with luminous aura
        curr_head = (int(curve_pts[-1, 0]), int(curve_pts[-1, 1]))
        ball_r = max(4, int(radii[-1] + 1.5))
        # Outer aura
        aura_overlay = frame.copy()
        cv2.circle(aura_overlay, curr_head, ball_r + int(5 * scale), self.glow_color, -1, lineType=cv2.LINE_AA)
        frame = cv2.addWeighted(aura_overlay, 0.40, frame, 0.60, 0)
        # Main ball sphere
        cv2.circle(frame, curr_head, ball_r, (255, 255, 255), -1, lineType=cv2.LINE_AA)
        cv2.circle(frame, curr_head, ball_r, self.ribbon_color, max(1, int(1.2 * scale)), lineType=cv2.LINE_AA)

        return frame

    def draw_strike_zone(
        self,
        frame: np.ndarray,
        strike_zone: StrikeZone,
        call_result: Optional[PitchCallResult] = None
    ) -> np.ndarray:
        """
        Renders a sleek, modern broadcast-style strike zone (Apple TV / ESPN K-Zone aesthetic)
        with thin anti-aliased border, corner brackets, and subtle 3x3 dashed grid.
        """
        x1, y1 = int(round(strike_zone.x_min)), int(round(strike_zone.y_min))
        x2, y2 = int(round(strike_zone.x_max)), int(round(strike_zone.y_max))
        w = x2 - x1
        h = y2 - y1
        if w <= 0 or h <= 0:
            return frame

        if call_result:
            theme_color = (0, 230, 118) if call_result.is_strike else (60, 60, 255)
        else:
            theme_color = (255, 220, 0)

        # 1. Soft Translucent Fill (8% opacity so players behind are crystal clear)
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), theme_color, -1)
        frame = cv2.addWeighted(overlay, 0.08, frame, 0.92, 0)

        # 2. Sleek 1px Anti-Aliased Outer Border
        cv2.rectangle(frame, (x1, y1), (x2, y2), theme_color, 1, lineType=cv2.LINE_AA)

        # 3. High-Tech Corner Brackets
        corner_len = max(8, int(min(w, h) * 0.18))
        bw = 2
        # Top-left
        cv2.line(frame, (x1, y1), (x1 + corner_len, y1), theme_color, bw, lineType=cv2.LINE_AA)
        cv2.line(frame, (x1, y1), (x1, y1 + corner_len), theme_color, bw, lineType=cv2.LINE_AA)
        # Top-right
        cv2.line(frame, (x2, y1), (x2 - corner_len, y1), theme_color, bw, lineType=cv2.LINE_AA)
        cv2.line(frame, (x2, y1), (x2, y1 + corner_len), theme_color, bw, lineType=cv2.LINE_AA)
        # Bottom-left
        cv2.line(frame, (x1, y2), (x1 + corner_len, y2), theme_color, bw, lineType=cv2.LINE_AA)
        cv2.line(frame, (x1, y2), (x1, y2 - corner_len), theme_color, bw, lineType=cv2.LINE_AA)
        # Bottom-right
        cv2.line(frame, (x2, y2), (x2 - corner_len, y2), theme_color, bw, lineType=cv2.LINE_AA)
        cv2.line(frame, (x2, y2), (x2, y2 - corner_len), theme_color, bw, lineType=cv2.LINE_AA)

        # 4. Subtle 3x3 Inner Grid
        grid_overlay = frame.copy()
        for i in [1, 2]:
            gx = x1 + int(i * w / 3)
            gy = y1 + int(i * h / 3)
            cv2.line(grid_overlay, (gx, y1), (gx, y2), (240, 240, 240), 1, lineType=cv2.LINE_AA)
            cv2.line(grid_overlay, (x1, gy), (x2, gy), (240, 240, 240), 1, lineType=cv2.LINE_AA)
        frame = cv2.addWeighted(grid_overlay, 0.35, frame, 0.65, 0)

        return frame

    def draw_hud_card(
        self,
        frame: np.ndarray,
        pitch_number: int,
        velocity_mph: float,
        vert_break_in: float,
        horz_break_in: float,
        call_result: Optional[PitchCallResult] = None,
        pitch_tag: str = "Dropball",
        flight_time_ms: Optional[float] = None,
    ) -> np.ndarray:
        """
        Renders the signature Pitch Lab telemetric HUD card with
        responsive scaling and layout for both widescreen broadcast and mobile formats.
        """
        h, w = frame.shape[:2]
        is_widescreen = (w / float(h)) > 1.3
        scale = max(0.65, min(1.8, w / 600.0))

        if is_widescreen:
            # Compact sleek card in bottom-left so home plate & batter remain visible
            card_w = int(min(420, w * 0.35))
            card_h = int(min(115, h * 0.16))
            card_x1 = 20
            card_y1 = h - card_h - 20
            card_x2 = card_x1 + card_w
            card_y2 = card_y1 + card_h

            overlay = frame.copy()
            cv2.rectangle(overlay, (card_x1, card_y1), (card_x2, card_y2), (18, 18, 18), -1)
            cv2.rectangle(overlay, (card_x1, card_y1), (card_x2, card_y2), (55, 55, 55), 1)
            frame = cv2.addWeighted(overlay, 0.90, frame, 0.10, 0)

            font = cv2.FONT_HERSHEY_SIMPLEX

            # Title & Badge
            cv2.putText(frame, f"Pitch #{pitch_number}", (card_x1 + 14, card_y1 + 26), font, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
            badge_text = call_result.call if call_result else pitch_tag
            badge_color = (0, 230, 118) if (call_result and call_result.is_strike) else ((60, 60, 255) if call_result else (0, 190, 255))
            badge_size = cv2.getTextSize(badge_text, font, 0.5, 2)[0]
            bx2 = card_x2 - 12
            bx1 = bx2 - badge_size[0] - 12
            by1 = card_y1 + 8
            by2 = by1 + badge_size[1] + 10
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (35, 35, 35), -1)
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), badge_color, 1)
            cv2.putText(frame, badge_text, (bx1 + 6, by2 - 4), font, 0.5, badge_color, 2, cv2.LINE_AA)

            # Velocity
            cv2.putText(frame, "Velocity", (card_x1 + 14, card_y1 + 50), font, 0.40, (160, 160, 160), 1, cv2.LINE_AA)
            vel_text = f"{velocity_mph:.1f}"
            cv2.putText(frame, vel_text, (card_x1 + 14, card_y1 + 90), font, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
            vel_w = cv2.getTextSize(vel_text, font, 1.1, 2)[0][0]
            cv2.putText(frame, " mph", (card_x1 + 14 + vel_w + 3, card_y1 + 90), font, 0.48, (180, 180, 180), 1, cv2.LINE_AA)

            # Right columns
            r_col = card_x1 + int(card_w * 0.54)
            cv2.putText(frame, "Flight", (r_col, card_y1 + 50), font, 0.38, (160, 160, 160), 1, cv2.LINE_AA)
            flight_str = f"{flight_time_ms:.0f} ms" if flight_time_ms else "400 ms"
            cv2.putText(frame, flight_str, (r_col, card_y1 + 84), font, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

            r_col2 = r_col + int((card_x2 - r_col) * 0.52)
            cv2.putText(frame, "Break", (r_col2, card_y1 + 50), font, 0.38, (160, 160, 160), 1, cv2.LINE_AA)
            cv2.putText(frame, f"{vert_break_in:+.1f}\"", (r_col2, card_y1 + 84), font, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
            return frame

        card_h = int(min(150, h * 0.20))
        card_w = int(w * 0.94)
        card_x1 = int((w - card_w) / 2)
        card_y1 = h - card_h - 16
        card_x2 = card_x1 + card_w
        card_y2 = card_y1 + card_h

        overlay = frame.copy()
        cv2.rectangle(overlay, (card_x1, card_y1), (card_x2, card_y2), (18, 18, 18), -1)
        cv2.rectangle(overlay, (card_x1, card_y1), (card_x2, card_y2), (55, 55, 55), 1)
        frame = cv2.addWeighted(overlay, 0.90, frame, 0.10, 0)

        font = cv2.FONT_HERSHEY_SIMPLEX

        # Row 1: Title & Badge
        pitch_title = f"Pitch #{pitch_number}"
        cv2.putText(frame, pitch_title, (card_x1 + 12, card_y1 + int(28 * scale)), font, 0.6 * scale, (255, 255, 255), 2, cv2.LINE_AA)

        badge_text = call_result.call if call_result else pitch_tag
        badge_color = (0, 230, 118) if (call_result and call_result.is_strike) else ((60, 60, 255) if call_result else (0, 190, 255))

        badge_size = cv2.getTextSize(badge_text, font, 0.5 * scale, 2)[0]
        bx2 = card_x2 - 12
        bx1 = bx2 - badge_size[0] - 14
        by1 = card_y1 + 10
        by2 = by1 + badge_size[1] + 12
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), (35, 35, 35), -1)
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), badge_color, 1)
        cv2.putText(frame, badge_text, (bx1 + 7, by2 - 4), font, 0.5 * scale, badge_color, 2, cv2.LINE_AA)

        # Row 2: Velocity
        cv2.putText(frame, "Velocity", (card_x1 + 12, card_y1 + int(52 * scale)), font, 0.4 * scale, (160, 160, 160), 1, cv2.LINE_AA)

        vel_text = f"{velocity_mph:.1f}"
        cv2.putText(frame, vel_text, (card_x1 + 12, card_y1 + int(94 * scale)), font, 1.0 * scale, (255, 255, 255), 2, cv2.LINE_AA)
        vel_w = cv2.getTextSize(vel_text, font, 1.0 * scale, 2)[0][0]
        cv2.putText(frame, " mph", (card_x1 + 12 + vel_w + 3, card_y1 + int(94 * scale)), font, 0.45 * scale, (180, 180, 180), 1, cv2.LINE_AA)

        # Row 3: Right Columns - Vert, Horz, Flight
        col_x = card_x1 + int(card_w * 0.48)
        col_spacing = int((card_x2 - col_x) / 3)

        # Vert
        cv2.putText(frame, "Vert", (col_x, card_y1 + int(56 * scale)), font, 0.36 * scale, (150, 150, 150), 1, cv2.LINE_AA)
        cv2.putText(frame, f"{vert_break_in:+.1f} in", (col_x, card_y1 + int(86 * scale)), font, 0.42 * scale, (255, 255, 255), 1, cv2.LINE_AA)

        # Horz
        cv2.putText(frame, "Horz", (col_x + col_spacing, card_y1 + int(56 * scale)), font, 0.36 * scale, (150, 150, 150), 1, cv2.LINE_AA)
        cv2.putText(frame, f"{horz_break_in:+.1f} in", (col_x + col_spacing, card_y1 + int(86 * scale)), font, 0.42 * scale, (255, 255, 255), 1, cv2.LINE_AA)

        # Flight
        flight_str = f"{flight_time_ms:.0f} ms" if flight_time_ms else "450 ms"
        cv2.putText(frame, "Flight", (col_x + col_spacing * 2, card_y1 + int(56 * scale)), font, 0.36 * scale, (150, 150, 150), 1, cv2.LINE_AA)
        cv2.putText(frame, flight_str, (col_x + col_spacing * 2, card_y1 + int(86 * scale)), font, 0.42 * scale, (255, 255, 255), 1, cv2.LINE_AA)

        return frame

    def render_complete_video(
        self,
        input_video_path: str,
        output_video_path: str,
        trajectory_points: List[TrajectoryPoint],
        velocity_mph: float,
        vert_break_in: float,
        horz_break_in: float,
        strike_zone: Optional[StrikeZone] = None,
        call_result: Optional[PitchCallResult] = None,
        pitch_number: int = 1,
        pitch_tag: str = "Dropball",
        flight_time_ms: Optional[float] = None,
        show_strike_zone: bool = True,
        graphic_style: str = "statcast_cyan",
    ) -> None:
        """
        Renders the complete Pitch Lab video with Statcast 3D trajectory streamline,
        HUD card, and broadcast strike zone box.
        """
        if graphic_style:
            self.set_graphic_style(graphic_style)
        cap = cv2.VideoCapture(input_video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Input video not found: {input_video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 1. Strike Zone overlay
            if show_strike_zone and strike_zone:
                frame = self.draw_strike_zone(frame, strike_zone, call_result)

            # 2. Glowing yellow trajectory ribbon
            frame = self.draw_glowing_ribbon(frame, trajectory_points, frame_idx)

            # 3. Bottom HUD Card
            if trajectory_points and frame_idx >= trajectory_points[0].frame_idx:
                frame = self.draw_hud_card(
                    frame=frame,
                    pitch_number=pitch_number,
                    velocity_mph=velocity_mph,
                    vert_break_in=vert_break_in,
                    horz_break_in=horz_break_in,
                    call_result=call_result,
                    pitch_tag=pitch_tag,
                    flight_time_ms=flight_time_ms,
                )

            out.write(frame)
            frame_idx += 1

        cap.release()
        out.release()

        # Convert to Web-compatible H.264 (avc1) with faststart for Chrome/Edge/Safari
        self._convert_to_web_h264(output_video_path)

    def _convert_to_web_h264(self, video_path: str) -> None:
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            temp_path = video_path + ".tmp.mp4"
            cmd = [
                ffmpeg_exe, "-y",
                "-i", video_path,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "ultrafast",
                "-movflags", "+faststart",
                temp_path
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_path):
                if os.path.exists(video_path):
                    os.remove(video_path)
                os.rename(temp_path, video_path)
        except Exception as e:
            print(f"[PitchRenderer] Web H264 conversion note: {e}")
