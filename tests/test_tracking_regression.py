"""Ground-truth tracking regression: tracker output vs hand-verified ball labels on real clips.
Clips are not in git; each case skips when its video is absent."""
import json
import os
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "tests", "fixtures", "ball_labels.json"), encoding="utf-8") as f:
    LABELS = json.load(f)


def score_track(points, labels, width, height):
    """Returns (recall, first_frame_err, last_frame_err): recall = labeled frames tracked within tol px."""
    tol = 0.008 * max(width, height)
    got = {p.frame_idx: (p.x, p.y) for p in points}
    hits = sum(1 for f, (x, y) in labels.items()
               if f in got and ((got[f][0] - x) ** 2 + (got[f][1] - y) ** 2) ** 0.5 <= tol)
    if not points:
        return 0.0, None, None
    return hits / len(labels), points[0].frame_idx - min(labels), points[-1].frame_idx - max(labels)


@pytest.mark.parametrize("clip", sorted(LABELS))
def test_tracking_matches_ground_truth(clip):
    path = os.path.join(ROOT, clip)
    if not os.path.exists(path):
        pytest.skip(f"clip not present: {clip}")
    from velopath.tracker import PitchTracker
    spec = LABELS[clip]
    labels = {int(f): xy for f, xy in spec["points"].items()}
    points, _, (w, h) = PitchTracker().track_video(path, mode=spec["mode"])
    recall, first_err, last_err = score_track(points, labels, w, h)
    print(f"{clip}: recall={recall:.2f} first_err={first_err} last_err={last_err}")
    assert recall >= 0.9
    assert first_err is not None and abs(first_err) <= 1 and abs(last_err) <= 1
