"""
Decide whether the small model is good enough: track held-out clips with
  big    - current ball_trackingv4 only (today's app)
  hybrid - small model scans whole frames, big model refines windows
  small  - small model only
and report frames, recall and time. Run from the project root:
  python training/compare_models.py path/to/ball_small_yolo11s.pt
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from velopath.tracker import PitchTracker  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = json.load(open(os.path.join(ROOT, "tests", "fixtures", "ball_labels.json"), encoding="utf-8"))
HELD_OUT = ["not good tracking/Test !.mp4", "test videos/20260923_140455.MOV.mp4"]  # never used in training


def recall(points, reference, w, h):
    """Share of reference frames tracked within 0.8% of the frame size; plus start/end frame errors."""
    tol = 0.008 * max(w, h)
    got = {p.frame_idx: (p.x, p.y) for p in points}
    hits = sum(1 for f, (x, y) in reference.items() if f in got and ((got[f][0] - x) ** 2 + (got[f][1] - y) ** 2) ** 0.5 <= tol)
    if not points:
        return 0.0, None, None
    return hits / len(reference), points[0].frame_idx - min(reference), points[-1].frame_idx - max(reference)


def main(small_path):
    from ultralytics import YOLO
    tracker = PitchTracker()  # loads the big model (and models/ball_small_yolo11s.pt if present)
    big, small = tracker.model, YOLO(small_path, task="detect")
    setups = {"big": (big, None), "hybrid": (big, small), "small": (small, small)}
    for clip in HELD_OUT:
        path = os.path.join(ROOT, clip)
        if not os.path.exists(path):
            print(f"skip (missing): {clip}")
            continue
        reference, kind = None, "ground truth"
        if clip in LABELS:
            reference = {int(f): xy for f, xy in LABELS[clip]["points"].items()}
        print(f"\n== {clip}")
        for name, (refine_model, scan_model) in setups.items():
            tracker.model, tracker.scan_model = refine_model, scan_model
            t = time.monotonic()
            pts, fps, (w, h) = tracker.track_video(path)
            dt = time.monotonic() - t
            if reference is None:  # no hand labels: the big model's (eye-checked) track is the reference
                reference, kind = {p.frame_idx: (p.x, p.y) for p in pts}, "big-model track"
            r, e0, e1 = recall(pts, reference, w, h)
            span = f"{pts[0].frame_idx}-{pts[-1].frame_idx}" if pts else "none"
            print(f"  {name:7s} {dt:6.1f}s  frames {span:9s}  recall vs {kind}: {r:.2f}  start/end error: {e0}/{e1}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "models", "ball_small_yolo11s.pt"))
