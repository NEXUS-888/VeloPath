"""
3D pitch reconstruction from one camera on the pitch line (behind the catcher or behind the pitcher).

Calibration: the user taps the plate's two front corners (17in apart) and the rubber's two ends (24in),
which are 709in apart along the pitch line. For segments parallel to the image plane, pixel length
L = f * real / Z, so  f = 709 / |24/L_rubber - 17/L_plate|  and every tapped point gets a depth.
The same points give the ground's orientation in the camera, hence the direction of gravity.

Fit: a constant-acceleration flight p(t) = p0 + v0 t + a t^2 / 2 (9 numbers; drag folds into a),
matched to the ball's image position (precise) and apparent size (a 2.9in ball: Z = f * 2.9 / d,
noisy), anchored by release ~54 ft out and the catch at the plate. Spin acceleration = a - gravity gives the break.
"""
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

PLATE_WIDTH_IN, RUBBER_WIDTH_IN, BALL_DIAM_IN = 17.0, 24.0, 2.9
PLATE_TO_RUBBER_IN = 709.0  # rubber front to plate front edge (60.5 ft to the plate's back point minus 17in)
MOUND_RISE_IN = 10.0
RELEASE_FROM_PLATE_IN = PLATE_TO_RUBBER_IN - 60.0  # release ~5 ft in front of the rubber (amateur stride)
G_IN_S2 = 386.09
DRAG_K_PER_IN = 1.54e-4  # 0.5*rho*Cd*A/m for a baseball (rho 1.2, Cd 0.35, A 42cm^2, m 145g): decel = k*v^2
IN_S_PER_MPH = 17.6


@dataclass
class Camera:
    f: float
    cx: float
    cy: float
    plate: np.ndarray   # plate front-edge centre, camera coords (x right, y down, z forward), inches
    up: np.ndarray      # world up, camera coords
    toward_pitcher: np.ndarray  # horizontal unit vector plate -> rubber
    catcher_right: np.ndarray   # horizontal unit vector to the catcher's right
    behind: str         # "catcher" or "pitcher"


def _unit(v):
    return v / np.linalg.norm(v)


def camera_from_taps(plate_corners: Sequence, rubber_ends: Sequence, image_size, min_depth_ratio=1.3) -> Optional[Camera]:
    """Camera from 4 taps (pixels, any order within each pair). None if the geometry can't resolve depth,
    e.g. a far camera (center field) where plate and rubber shrink alike."""
    (pa, pb), (ra, rb) = np.asarray(plate_corners, float), np.asarray(rubber_ends, float)
    lp, lr = np.linalg.norm(pb - pa), np.linalg.norm(rb - ra)
    if lp < 2 or lr < 2:
        return None
    diff = abs(RUBBER_WIDTH_IN / lr - PLATE_WIDTH_IN / lp)
    if diff < 1e-9:
        return None
    f = PLATE_TO_RUBBER_IN / diff
    zp, zr = f * PLATE_WIDTH_IN / lp, f * RUBBER_WIDTH_IN / lr
    if max(zp, zr) / min(zp, zr) < min_depth_ratio:
        return None
    cx, cy = image_size[0] / 2.0, image_size[1] / 2.0

    def back(px, z):
        return np.array([(px[0] - cx) * z / f, (px[1] - cy) * z / f, z])

    plate = back((pa + pb) / 2, zp)
    rubber = back((ra + rb) / 2, zr)
    across = back(pb, zp) - back(pa, zp)  # along the plate's front edge (horizontal)
    along = rubber - plate                # pitch line, plus the 10in mound rise
    up = _unit(np.cross(across, along))
    if up[1] > 0:  # image y points down, so world up must have negative y
        up = -up
    toward = _unit(along - np.dot(along, up) * up)
    return Camera(f=f, cx=cx, cy=cy, plate=plate, up=up, toward_pitcher=toward,
                  catcher_right=_unit(np.cross(toward, up)), behind="catcher" if zr > zp else "pitcher")


def fit_pitch_3d(frames: Sequence[int], uv: Sequence, diam_px: Sequence[float], fps: float, cam: Camera,
                 pos_sigma=1.0) -> Optional[dict]:
    """Constant-acceleration 3D fit. frames: frame indices; uv: ball centres (px); diam_px: apparent ball
    diameters (px). Returns speeds (mph), induced vertical / horizontal break (in, catcher's view,
    up / catcher's right positive), flight time and the fit's pixel error; None if it can't be trusted."""
    from scipy.optimize import least_squares

    frames, uv, d = np.asarray(frames, float), np.asarray(uv, float), np.asarray(diam_px, float)
    ok = d > 1.0
    frames, uv, d = frames[ok], uv[ok], d[ok]
    if len(frames) < 6:
        return None
    t = (frames - frames[0]) / fps
    f, cx, cy = cam.f, cam.cx, cam.cy

    # start from the size-derived depths (noisy) and a per-axis quadratic
    z0 = np.clip(f * BALL_DIAM_IN / d, 24.0, 4000.0)
    pts = np.stack([(uv[:, 0] - cx) * z0 / f, (uv[:, 1] - cy) * z0 / f, z0], axis=1)
    c = [np.polyfit(t, pts[:, k], 2) for k in range(3)]
    x0 = np.concatenate([[c[k][2] for k in range(3)], [c[k][1] for k in range(3)], [2 * c[k][0] for k in range(3)]])
    size_sigma = np.maximum(1.0, 0.1 * d)

    def path(params, tt):
        p0, v0, a = params[:3], params[3:6], params[6:]
        return p0 + np.outer(tt, v0) + 0.5 * np.outer(tt * tt, a)

    def residuals(params):
        p = path(params, t)
        z = np.maximum(p[:, 2], 1.0)
        ru = (cx + f * p[:, 0] / z - uv[:, 0]) / pos_sigma
        rv = (cy + f * p[:, 1] / z - uv[:, 1]) / pos_sigma
        rd = (f * BALL_DIAM_IN / z - d) / size_sigma
        # soft anchors from the tracker's contract: the flight starts at release and ends at the glove/bat.
        # From behind the catcher the ball starts ~5px wide, so size alone cannot pin its early depth.
        s_start = np.dot(p[0] - cam.plate, cam.toward_pitcher)
        s_end = np.dot(p[-1] - cam.plate, cam.toward_pitcher)
        # drag is known physics: along-path deceleration ~ k v^2 (about 345 in/s^2 at 85 mph); it keeps a far,
        # tiny ball from trading speed against deceleration
        v_mid = params[3:6] + params[6:] * t[-1] / 2
        speed = np.linalg.norm(v_mid)
        a_along = np.dot(params[6:], v_mid) / max(speed, 1.0)
        return np.concatenate([ru, rv, rd, [(s_start - RELEASE_FROM_PLATE_IN) / 48.0, (s_end + 12.0) / 15.0,
                                            (a_along + DRAG_K_PER_IN * speed ** 2) / 150.0]])

    fit = least_squares(residuals, x0, loss="soft_l1", f_scale=2.0, max_nfev=4000)
    if not fit.success:
        return None
    p0, v0, a = fit.x[:3], fit.x[3:6], fit.x[6:]

    # plate crossing: s(t) = 0 (front edge of the plate), sub-frame
    s0 = np.dot(p0 - cam.plate, cam.toward_pitcher)
    sv, sa = np.dot(v0, cam.toward_pitcher), np.dot(a, cam.toward_pitcher)
    roots = np.roots([0.5 * sa, sv, s0]) if abs(sa) > 1e-9 else np.array([-s0 / sv]) if abs(sv) > 1e-9 else np.array([])
    roots = [r.real for r in np.atleast_1d(roots) if abs(r.imag) < 1e-9 and 0 < r.real < t[-1] + 0.2]
    t_plate = min(roots) if roots else t[-1]

    a_spin = a + G_IN_S2 * cam.up  # remove gravity (which points along -up)
    release_mph = np.linalg.norm(v0) / IN_S_PER_MPH
    # 1-sigma speed error from the fit's own uncertainty (Jacobian covariance), so the UI can show +-
    J = fit.jac
    dof = max(1, len(fit.fun) - len(fit.x))
    cov = np.linalg.pinv(J.T @ J) * (2 * fit.cost / dof)
    g = v0 / np.linalg.norm(v0)
    release_sd = float(np.sqrt(max(0.0, g @ cov[3:6, 3:6] @ g))) / IN_S_PER_MPH
    plate_mph = np.linalg.norm(v0 + a * t_plate) / IN_S_PER_MPH
    px_err = float(np.sqrt(np.mean(np.square(np.concatenate([fit.fun[: len(t)], fit.fun[len(t): 2 * len(t)]])))) * pos_sigma)
    if not 20 <= release_mph <= 120 or t_plate <= 0:
        return None
    return {
        "release_mph": round(float(release_mph), 1),
        "release_pm_mph": round(release_sd, 1),
        "plate_mph": round(float(plate_mph), 1),
        "ivb_in": round(float(0.5 * np.dot(a_spin, cam.up) * t_plate ** 2), 1),
        "hb_in": round(float(0.5 * np.dot(a_spin, cam.catcher_right) * t_plate ** 2), 1),
        "flight_ms": round(float(t_plate * 1000.0), 1),
        "fit_px_error": round(px_err, 2),
        "release_dist_ft": round(float(s0 / 12.0), 1),
    }
