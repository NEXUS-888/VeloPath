"""Synthetic training data generator (training/make_synthetic.py)."""
import glob
import importlib.util
import os
import random

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("make_synthetic", os.path.join(ROOT, "training", "make_synthetic.py"))
ms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ms)


def fake_baseballcv(root, n=3):
    """BaseballCV-like folder: 1280x720 green frames, one white ball (class 2) each, plus a glove (class 0)."""
    os.makedirs(os.path.join(root, "train", "images"))
    os.makedirs(os.path.join(root, "train", "labels"))
    for i in range(n):
        img = np.full((720, 1280, 3), (40, 120, 40), np.uint8)
        cv2.circle(img, (600 + 40 * i, 300), 9, (250, 250, 250), -1)
        cv2.imwrite(os.path.join(root, "train", "images", f"{i:07d}.jpg"), img)
        with open(os.path.join(root, "train", "labels", f"{i:07d}.txt"), "w") as f:
            f.write(f"2 {(600 + 40 * i) / 1280:.6f} {300 / 720:.6f} {20 / 1280:.6f} {20 / 720:.6f}\n0 0.5 0.5 0.1 0.1\n")


def write_clip(path, n=12):
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 30, (640, 360))
    for _ in range(n):
        out.write(np.full((360, 640, 3), (60, 90, 60), np.uint8))
    out.release()


def test_sprites_are_ball_crops(tmp_path):
    fake_baseballcv(str(tmp_path / "bcv"))
    sprites = ms.ball_sprites(str(tmp_path / "bcv"), rng=random.Random(0))
    assert len(sprites) == 3  # one ball per frame; the glove is ignored
    crop, bw, bh = sprites[0]
    assert abs(bw - 20) < 1 and crop[crop.shape[0] // 2, crop.shape[1] // 2].mean() > 200  # ball at the centre


def test_pasted_ball_lies_inside_its_label_box(tmp_path):
    fake_baseballcv(str(tmp_path / "bcv"))
    sprite = ms.ball_sprites(str(tmp_path / "bcv"), rng=random.Random(0))[0]
    rng = random.Random(3)
    for _ in range(20):
        bg = np.zeros((360, 640, 3), np.uint8)
        box = ms.paste_ball(bg, sprite, rng)
        assert box is not None
        x1, y1, x2, y2 = box
        changed = np.argwhere(bg.max(axis=2) > 60)
        assert changed[:, 1].min() >= x1 - 2 and changed[:, 1].max() <= x2 + 2
        assert changed[:, 0].min() >= y1 - 2 and changed[:, 0].max() <= y2 + 2
        assert 3 <= x2 - x1 <= 140  # 5-40px ball, up to a 2.5x streak


def test_tint_makes_a_white_ball_pink():
    white = np.full((12, 12, 3), 240, np.uint8)
    hsv = cv2.cvtColor(ms._tint(white, 165, random.Random(0)), cv2.COLOR_BGR2HSV)
    assert abs(int(hsv[6, 6, 0]) - 165) <= 2 and hsv[6, 6, 1] >= 110


def test_teacher_labels_confident_balls_and_drops_unsure_frames(tmp_path):
    clip = str(tmp_path / "c.mp4")
    write_clip(clip, n=6)
    calls = iter([[(10, 10, 20, 20, 0.9)], [(5, 5, 9, 9, 0.2)], [], [], [], []])
    pool = ms.background_pool([clip], lambda frame: next(calls), every=1)
    assert len(pool) == 5  # the frame with an unsure (0.2) detection is gone
    assert pool[0][1] == [(10, 10, 20, 20)]  # confident detection kept as a label
    assert all(boxes == [] for _, boxes in pool[1:])


def test_build_writes_matching_images_and_labels(tmp_path):
    fake_baseballcv(str(tmp_path / "bcv"))
    clip = str(tmp_path / "c.mp4")
    write_clip(clip)
    counts = ms.build(str(tmp_path / "bcv"), [clip], str(tmp_path / "out"), n=10, teacher=lambda f: [], every=4)
    imgs = sorted(glob.glob(str(tmp_path / "out" / "images" / "*.jpg")))
    labels = sorted(glob.glob(str(tmp_path / "out" / "labels" / "*.txt")))
    assert counts == {"sprites": 3, "real_frames": 3, "synthetic": 10}
    assert len(imgs) == len(labels) == 13
    rows = [l.split() for p in labels for l in open(p)]
    assert rows and all(r[0] == "2" and all(0 <= float(v) <= 1 for v in r[1:]) for r in rows)
