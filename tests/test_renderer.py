import os
import tempfile
import cv2
import numpy as np
import pytest
from unittest.mock import patch

from velopath.renderer import PitchRenderer
from velopath.tracker import TrajectoryPoint
from velopath.strike_zone import StrikeZone


@pytest.fixture
def sample_video():
    """Creates a temporary 30-frame 1920x1080 test video."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        video_path = f.name

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = 30.0
    w, h = 1920, 1080
    out = cv2.VideoWriter(video_path, fourcc, fps, (w, h))
    for i in range(30):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (i * 5, 40, 40)
        out.write(frame)
    out.release()

    yield video_path

    if os.path.exists(video_path):
        os.remove(video_path)


def test_draw_overlays_roi():
    renderer = PitchRenderer()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    sz = StrikeZone(x_min=500, y_min=250, x_max=780, y_max=500)
    pts = [TrajectoryPoint(frame_idx=f, x=600.0 + f * 2, y=300.0 + f * 3) for f in range(10, 25)]

    # 1. Strike Zone
    res_sz = renderer.draw_strike_zone(frame, sz)
    assert res_sz.shape == (720, 1280, 3)

    # 2. Glowing Ribbon
    res_rib = renderer.draw_glowing_ribbon(res_sz, pts, current_frame_idx=20)
    assert res_rib.shape == (720, 1280, 3)

    # 3. Minimal Badge
    res_badge = renderer.draw_minimal_badge(res_rib, velocity_mph=94.2)
    assert res_badge.shape == (720, 1280, 3)

    # 4. HUD Card
    res_card = renderer.draw_hud_card(res_rib, pitch_number=1, velocity_mph=94.2, vert_break_in=-12.1, horz_break_in=4.3)
    assert res_card.shape == (720, 1280, 3)


def test_render_complete_video_fast_pipe(sample_video, tmp_path):
    renderer = PitchRenderer()
    out_path = str(tmp_path / "out_fast.mp4")
    pts = [TrajectoryPoint(frame_idx=f, x=960.0, y=400.0 + f * 10) for f in range(10, 20)]
    sz = StrikeZone(x_min=850, y_min=450, x_max=1070, y_max=750)

    out_w, out_h = renderer.render_complete_video(
        input_video_path=sample_video,
        output_video_path=out_path,
        trajectory_points=pts,
        velocity_mph=93.0,
        vert_break_in=-10.0,
        horz_break_in=3.0,
        strike_zone=sz,
        trim_to_pitch=False,
    )

    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 0
    assert (out_w, out_h) == (1920, 1080)

    cap = cv2.VideoCapture(out_path)
    assert cap.isOpened()
    assert int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) == 1920
    assert int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) == 1080
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 30
    ret, frame = cap.read()
    assert ret is True
    assert frame.shape == (1080, 1920, 3)
    cap.release()


def test_render_complete_video_trimming(sample_video, tmp_path):
    renderer = PitchRenderer()
    out_path = str(tmp_path / "out_trimmed.mp4")
    pts = [TrajectoryPoint(frame_idx=f, x=960.0, y=400.0 + f * 10) for f in range(14, 16)]
    sz = StrikeZone(x_min=850, y_min=450, x_max=1070, y_max=750)

    renderer.render_complete_video(
        input_video_path=sample_video,
        output_video_path=out_path,
        trajectory_points=pts,
        velocity_mph=91.5,
        vert_break_in=-8.0,
        horz_break_in=2.0,
        strike_zone=sz,
        trim_to_pitch=True,
    )

    cap = cv2.VideoCapture(out_path)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    assert count == 25


def test_render_complete_video_max_dimension_scaling(sample_video, tmp_path):
    renderer = PitchRenderer()
    out_path = str(tmp_path / "out_720p.mp4")
    pts = [TrajectoryPoint(frame_idx=f, x=960.0, y=500.0) for f in range(10, 20)]

    out_w, out_h = renderer.render_complete_video(
        input_video_path=sample_video,
        output_video_path=out_path,
        trajectory_points=pts,
        velocity_mph=90.0,
        vert_break_in=-5.0,
        horz_break_in=1.0,
        max_dimension=1280,
        trim_to_pitch=False,
    )

    assert (out_w, out_h) == (1280, 720)
    cap = cv2.VideoCapture(out_path)
    assert int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) == 1280
    assert int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) == 720
    cap.release()


def test_render_complete_video_fallback_when_ffmpeg_fails(sample_video, tmp_path):
    renderer = PitchRenderer()
    out_path = str(tmp_path / "out_fallback.mp4")
    pts = [TrajectoryPoint(frame_idx=f, x=960.0, y=500.0) for f in range(10, 20)]

    with patch("subprocess.Popen", side_effect=OSError("FFmpeg unavailable")):
        renderer.render_complete_video(
            input_video_path=sample_video,
            output_video_path=out_path,
            trajectory_points=pts,
            velocity_mph=90.0,
            vert_break_in=-5.0,
            horz_break_in=1.0,
            trim_to_pitch=False,
        )

    assert os.path.exists(out_path)
    cap = cv2.VideoCapture(out_path)
    assert cap.isOpened()
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 30
    cap.release()
