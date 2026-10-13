"""
Training data for a small VeloPath ball detector, built from the user's own clips (runs in Colab).

1. Sprites: real ball crops (with their natural motion blur) cut from BaseballCV's labelled frames.
2. Backgrounds: frames sampled from the user's phone clips. A teacher (the big ball_trackingv4 model)
   checks each frame: confident balls become labels (distillation), unsure frames are dropped so a
   real but unlabelled ball is never taught as background.
3. Paste 0-2 sprites per image: size 5-40px, motion streak, brightness, white / pink / yellow.
4. Write YOLO images/ and labels/ (class 2 = baseball, as in BaseballCV and ball_trackingv4).
"""
import argparse
import glob
import math
import os
import random

import cv2
import numpy as np

BALL = 2
IMG_EXTS = (".jpg", ".jpeg", ".png")


def ball_sprites(bcv_root, limit=2000, rng=random):
    """(crop, ball_w, ball_h) cut around class-2 boxes in BaseballCV's train split, ball centred in the crop."""
    out = []
    label_paths = sorted(glob.glob(os.path.join(bcv_root, "train", "labels", "*.txt")))
    rng.shuffle(label_paths)
    for lp in label_paths:
        stem = os.path.splitext(os.path.basename(lp))[0]
        img_path = next((p for p in (os.path.join(bcv_root, "train", "images", stem + e) for e in IMG_EXTS)
                         if os.path.exists(p)), None)
        img = cv2.imread(img_path) if img_path else None
        if img is None:
            continue
        H, W = img.shape[:2]
        for line in open(lp, encoding="utf-8", errors="ignore"):
            parts = line.split()
            if len(parts) != 5 or int(float(parts[0])) != BALL:
                continue
            x, y, w, h = (float(v) for v in parts[1:])
            bw, bh = w * W, h * H
            if bw < 6 or bh < 6:  # too few pixels to make a believable sprite
                continue
            half = 0.75 * max(bw, bh)
            x0, y0 = int(round(x * W - half)), int(round(y * H - half))
            x1, y1 = int(round(x * W + half)), int(round(y * H + half))
            if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
                continue
            out.append((img[y0:y1, x0:x1].copy(), bw, bh))
        if len(out) >= limit:
            break
    return out


def _tint(patch, hue, rng):
    """Recolour the bright (ball) pixels: pink / yellow training balls from white ones."""
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    bright = (hsv[..., 2] > 90) & (hsv[..., 1] < 90)
    hsv[..., 0][bright] = hue
    hsv[..., 1][bright] = rng.randint(120, 220)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def paste_ball(img, sprite, rng, d=None):
    """Blend one sprite into img (in place). Returns the ball box (x1, y1, x2, y2) or None if it does not fit."""
    crop, bw, bh = sprite
    H, W = img.shape[:2]
    d = d or math.exp(rng.uniform(math.log(5), math.log(40)))  # target ball width in px
    s = d / bw
    patch = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    ph, pw = patch.shape[:2]
    mask = np.zeros((ph, pw), np.float32)
    # 0.85x the ball: the feathered edge must stay on the ball, or the crop's old background shows as a halo
    cv2.ellipse(mask, (pw // 2, ph // 2), (max(1, int(round(0.85 * bw * s / 2))), max(1, int(round(0.85 * bh * s / 2)))),
                0, 0, 360, 1.0, -1)
    r = rng.random()
    if r < 0.15:
        patch = _tint(patch, rng.randint(150, 175), rng)  # pink / magenta
    elif r < 0.25:
        patch = _tint(patch, rng.randint(25, 35), rng)  # optic yellow
    patch = np.clip(patch.astype(np.float32) * rng.uniform(0.8, 1.15), 0, 255)
    if rng.random() < 0.7:  # motion streak along the flight direction
        L = int(round(rng.uniform(0, 2.5 * d)))
        if L >= 2:
            pad = L // 2 + 2
            patch = cv2.copyMakeBorder(patch, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
            mask = cv2.copyMakeBorder(mask, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
            k = np.zeros((L, L), np.float32)
            a = rng.uniform(0, math.pi)
            c = (L - 1) / 2.0
            cv2.line(k, (int(round(c - c * math.cos(a))), int(round(c - c * math.sin(a)))),
                     (int(round(c + c * math.cos(a))), int(round(c + c * math.sin(a)))), 1.0, 1)
            k /= max(k.sum(), 1e-6)
            # premultiplied: smear only the ball's own colour, never the crop's old background
            smeared = cv2.filter2D(patch * mask[..., None], -1, k)
            mask = cv2.filter2D(mask, -1, k)
            patch = smeared / np.maximum(mask, 1e-3)[..., None]
            ph, pw = patch.shape[:2]
    mask = cv2.GaussianBlur(mask, (0, 0), max(0.5, 0.05 * d))
    if pw >= W or ph >= H:
        return None
    x0, y0 = rng.randint(0, W - pw), rng.randint(0, H - ph)
    roi = img[y0:y0 + ph, x0:x0 + pw].astype(np.float32)
    m = mask[..., None]
    img[y0:y0 + ph, x0:x0 + pw] = np.clip(roi * (1 - m) + patch * m, 0, 255).astype(np.uint8)
    ys, xs = np.nonzero(mask > 0.3)
    if xs.size == 0:
        return None
    return (x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1)


def clip_frames(path, every, max_side):
    """Every `every`-th frame of a video, shrunk so the long side is at most max_side."""
    cap = cv2.VideoCapture(path)
    f = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if f % every == 0:
            ok, frame = cap.retrieve()
            if ok:
                s = min(1.0, max_side / float(max(frame.shape[:2])))
                yield cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else frame
        f += 1
    cap.release()


def background_pool(clips, teacher, every=3, max_side=1280, keep=0.4, unsure=0.1):
    """(frame, ball boxes) from the clips. teacher(frame) -> [(x1, y1, x2, y2, conf)] ball detections.
    Confident detections become labels; a frame with any unsure detection is dropped."""
    pool = []
    for path in clips:
        for frame in clip_frames(path, every, max_side):
            dets = teacher(frame)
            if any(unsure <= d[4] < keep for d in dets):
                continue
            pool.append((frame, [d[:4] for d in dets if d[4] >= keep]))
    return pool


def write_yolo(out_dir, name, img, boxes, quality):
    H, W = img.shape[:2]
    cv2.imwrite(os.path.join(out_dir, "images", name + ".jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    with open(os.path.join(out_dir, "labels", name + ".txt"), "w") as f:
        for x1, y1, x2, y2 in boxes:
            f.write(f"{BALL} {(x1 + x2) / 2 / W:.6f} {(y1 + y2) / 2 / H:.6f} {(x2 - x1) / W:.6f} {(y2 - y1) / H:.6f}\n")


def build(bcv_root, clips, out_dir, n, teacher, every=3, seed=0):
    """Writes the real (teacher-labelled) frames once, then n synthetic images. Returns counts."""
    rng = random.Random(seed)
    os.makedirs(os.path.join(out_dir, "images"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "labels"), exist_ok=True)
    sprites = ball_sprites(bcv_root, rng=rng)
    pool = background_pool(clips, teacher, every=every)
    if not sprites or not pool:
        raise SystemExit(f"Need ball sprites ({len(sprites)}) and background frames ({len(pool)}).")
    for i, (frame, boxes) in enumerate(pool):
        write_yolo(out_dir, f"real_{i:05d}", frame, boxes, 95)
    for i in range(n):
        frame, boxes = rng.choice(pool)
        img, boxes = frame.copy(), list(boxes)
        for _ in range(0 if rng.random() < 0.15 else (1 if rng.random() < 0.85 else 2)):
            box = paste_ball(img, rng.choice(sprites), rng)
            if box:
                boxes.append(box)
        if rng.random() < 0.5:
            img = np.clip(img + np.random.default_rng(i).normal(0, rng.uniform(2, 6), img.shape), 0, 255).astype(np.uint8)
        write_yolo(out_dir, f"synth_{i:05d}", img, boxes, rng.randint(70, 95))
    return {"sprites": len(sprites), "real_frames": len(pool), "synthetic": n}


def yolo_teacher(weights, imgsz=1280, unsure=0.1, device=None):
    """The big model as teacher: ball boxes with confidence >= unsure."""
    from ultralytics import YOLO
    model = YOLO(weights)

    def teach(frame):
        b = model.predict(frame, imgsz=imgsz, conf=unsure, classes=[BALL], verbose=False, device=device)[0].boxes
        return [(*xyxy, c) for xyxy, c in zip(b.xyxy.tolist(), b.conf.tolist())]
    return teach


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseballcv", required=True, help="unzipped baseball_rubber_home_glove folder")
    ap.add_argument("--clips", required=True, help="folder with your training videos")
    ap.add_argument("--teacher", required=True, help="big model weights (ball_trackingv4.pt)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--every", type=int, default=3, help="take every Nth frame of each clip")
    a = ap.parse_args()
    clips = sorted(p for p in glob.glob(os.path.join(a.clips, "*")) if p.lower().endswith((".mp4", ".mov", ".avi", ".mkv")))
    print(f"{len(clips)} clips:", [os.path.basename(c) for c in clips])
    print(build(a.baseballcv, clips, a.out, a.n, yolo_teacher(a.teacher), every=a.every))
