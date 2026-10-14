"""3D pitch reconstruction from one camera: synthetic pitches with known speed / break through a virtual camera."""
import math

import numpy as np
import pytest

from velopath.geometry3d import camera_from_taps, fit_pitch_3d

W, H, F = 1920, 1080, 1500.0
PLATE_TO_RUBBER = 709.0  # in: plate front edge to rubber front
G = 386.09  # in/s^2


def make_camera(tilt_deg=0.0, cam_height=60.0, plate_z=200.0, behind="catcher"):
    """World: x right (catcher's view), y up, z from plate front edge toward the pitcher. Returns a projector."""
    t = math.radians(tilt_deg)  # camera pitched down by t

    def to_cam(p):
        x, y, z = p
        if behind == "catcher":
            zc, xc = z + plate_z, x                      # looking toward the pitcher
        else:
            zc, xc = (PLATE_TO_RUBBER + plate_z) - z, -x  # behind the pitcher, looking at the plate
        yc = cam_height - y                              # image y points down
        # pitch the camera down by t
        return np.array([xc, yc * math.cos(t) - zc * math.sin(t), yc * math.sin(t) + zc * math.cos(t)])

    def project(p):
        X, Y, Z = to_cam(p)
        return np.array([W / 2 + F * X / Z, H / 2 + F * Y / Z]), Z
    return project


def taps(project):
    plate = [project((-8.5, 0, 0))[0], project((8.5, 0, 0))[0]]
    rubber = [project((-12, 10, PLATE_TO_RUBBER))[0], project((12, 10, PLATE_TO_RUBBER))[0]]
    return plate, rubber


def pitch(project, mph=85.0, ivb=15.0, hb=-8.0, fps=60.0, pos_noise=0.5, size_noise=1.0, seed=0):
    """Release 55 ft out, 6 ft high; spin accel chosen so the true break over the flight is (hb, ivb)."""
    rng = np.random.default_rng(seed)
    p0 = np.array([-18.0, 72.0, 660.0])
    vz = -mph * 17.6
    drag0 = 1.54e-4 * vz * vz
    T = (-vz - np.sqrt(vz * vz - 2 * drag0 * 660.0)) / drag0  # release (z=660) to plate front (z=0) under drag
    a_spin = np.array([2 * hb / T**2, 2 * ivb / T**2, 0.0])
    v0 = np.array([12.0, -30.0, vz])
    drag = 1.54e-4 * float(v0 @ v0)  # real pitches slow ~8-9 mph over the flight
    a = a_spin + np.array([0, -G, drag])  # vz < 0, so +z is against the motion
    frames, uv, d = [], [], []
    for i in range(400):
        t = i / fps
        p = p0 + v0 * t + 0.5 * a * t * t
        if p[2] < -24:  # caught 2 ft behind the plate front
            break
        (u, v), Z = project(p)
        frames.append(i)
        uv.append((u + rng.normal(0, pos_noise), v + rng.normal(0, pos_noise)))
        d.append(F * 2.9 / Z + rng.normal(0, size_noise))
    return frames, np.array(uv), np.array(d), fps


@pytest.mark.parametrize("tilt", [0.0, 6.0])
@pytest.mark.parametrize("behind", ["catcher", "pitcher"])
def test_recovers_speed_and_break(tilt, behind):
    """Over 8 noisy pitches (0.5px position, 1px size noise): unbiased within tolerance and tight spread.
    Behind the catcher the ball starts ~5px wide, so speed is looser there."""
    project = make_camera(tilt_deg=tilt, behind=behind, plate_z=200.0 if behind == "catcher" else 240.0)
    cam = camera_from_taps(*taps(project), (W, H))
    assert cam is not None and abs(cam.f - F) / F < 0.03
    rs = [fit_pitch_3d(*pitch(project, seed=s), cam) for s in range(8)]
    assert all(r is not None and r["flight_ms"] > 0 for r in rs)
    mph, ivb, hb = (np.array([r[k] for r in rs]) for k in ("release_mph", "ivb_in", "hb_in"))
    mph_sd = 4.0 if behind == "catcher" else 2.0
    assert abs(mph.mean() - 85.0) <= 2.5 and mph.std() <= mph_sd
    assert abs(ivb.mean() - 15.0) <= 1.5 and ivb.std() <= 1.5
    assert abs(hb.mean() + 8.0) <= 1.5 and hb.std() <= 1.5
    # the reported +- is honest: same order as the real spread
    pm = np.mean([r["release_pm_mph"] for r in rs])
    assert 0.33 * mph.std() <= pm <= 3.0 * max(mph.std(), 0.5)


def test_curveball_drops():
    project = make_camera(tilt_deg=4.0)
    cam = camera_from_taps(*taps(project), (W, H))
    frames, uv, d, fps = pitch(project, mph=75.0, ivb=-12.0, hb=6.0, seed=3)
    r = fit_pitch_3d(frames, uv, d, fps, cam)
    assert r["ivb_in"] == pytest.approx(-12.0, abs=3.0) and r["hb_in"] == pytest.approx(6.0, abs=3.0)


def test_camera_too_far_away_is_refused():
    """From ~400 ft (center field) plate and rubber shrink alike; depth can't be resolved."""
    project = make_camera(plate_z=4800.0)
    assert camera_from_taps(*taps(project), (W, H)) is None


def test_too_few_points_is_refused():
    project = make_camera()
    cam = camera_from_taps(*taps(project), (W, H))
    frames, uv, d, fps = pitch(project)
    assert fit_pitch_3d(frames[:4], uv[:4], d[:4], fps, cam) is None


def _blank_video(path, w, h, fps, n):
    import cv2
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for _ in range(n):
        out.write(np.zeros((h, w, 3), dtype=np.uint8))
    out.release()


def test_rerender_with_plate_and_rubber_taps_measures_in_3d(tmp_path):
    """Pipeline end to end: a synthetic 85 mph / IVB 15 / HB -8 pitch, tapped plate + rubber -> 3D numbers."""
    from velopath.pipeline import rerender_pitch
    project = make_camera(tilt_deg=4.0)
    plate, rubber = taps(project)
    frames, uv, d, fps = pitch(project, size_noise=0.5, pos_noise=0.3, seed=1)
    video = str(tmp_path / "v.mp4")
    _blank_video(video, W, H, int(fps), max(frames) + 5)
    traj = [{"frame": f, "x": float(x), "y": float(y), "d": float(dd)} for f, (x, y), dd in zip(frames, uv, d)]
    res = rerender_pitch(video, str(tmp_path / "o.mp4"), traj, 60.5, None, max_dimension=None,
                         plate_corners=[list(map(float, p)) for p in plate],
                         rubber_corners=[list(map(float, p)) for p in rubber])
    assert res["measurement"] == "3d"
    assert res["velocity_mph"] == pytest.approx(85.0, abs=3.0)
    assert res["vert_break_in"] == pytest.approx(15.0, abs=3.0)   # induced vertical break, + = rise
    assert res["horz_break_in"] == pytest.approx(-8.0, abs=3.0)
    assert res["pitch_tag"] != "Pitch" and res["zone_calibrated"] is True


def test_without_rubber_taps_stays_2d_and_does_not_guess_pitch_type(tmp_path):
    from velopath.pipeline import rerender_pitch
    project = make_camera()
    plate, _ = taps(project)
    frames, uv, d, fps = pitch(project)
    video = str(tmp_path / "v.mp4")
    _blank_video(video, W, H, int(fps), max(frames) + 5)
    traj = [{"frame": f, "x": float(x), "y": float(y)} for f, (x, y) in zip(frames, uv)]  # old clients: no "d"
    res = rerender_pitch(video, str(tmp_path / "o.mp4"), traj, 60.5, None, max_dimension=None,
                         plate_corners=[list(map(float, p)) for p in plate])
    assert res["measurement"] == "2d" and res["pitch_tag"] == "Pitch"
