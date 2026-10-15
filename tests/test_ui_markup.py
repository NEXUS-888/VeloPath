import re
from fastapi.testclient import TestClient
from velopath.server import app

REQUIRED_IDS = [
    "scoreCard", "scoreNewBtn", "scoreAway", "scoreHome", "scoreInnings", "scoreStartBtn",
    "scoreInningLabel", "scoreCount", "scoreOuts", "scoreDiamond", "scoreLine", "scoreFinal",
    "scorePlayPicker", "scoreAdjustBtn", "scoreUndoBtn", "scoreAdjust", "scoreAdjustApply",
    "scoreRunsPlus", "scoreOutsPlus", "scoreConfirm", "scoreError",
]

REQUIRED_ATTRS = {
    'data-pitch="ball"': 1,
    'data-pitch="strike"': 1,
    'data-pitch="foul"': 1,
    'data-pitch="hbp"': 1,
    'data-pitch="in_play"': 1,
    'data-play="single"': 1,
    'data-play="double"': 1,
    'data-play="triple"': 1,
    'data-play="home_run"': 1,
    'data-play="out"': 1,
    'data-play="error"': 1,
    'data-play="sac_fly"': 1,
    'data-play="double_play"': 1,
    'data-base="0"': 1,
    'data-base="1"': 1,
    'data-base="2"': 1,
}


def test_ui_markup_contains_all_ids():
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    for elem_id in REQUIRED_IDS:
        assert f'id="{elem_id}"' in html, f"Missing element with id='{elem_id}' in index.html"
    for attr, count in REQUIRED_ATTRS.items():
        assert html.count(attr) >= count, f"Missing attribute {attr} in index.html"


def test_no_inner_html_in_score_code():
    with open("static/app.js", encoding="utf-8") as f:
        js = f.read()
    score_funcs = re.findall(r"function\s+score\w+[^{]*\{[\s\S]*?\n\}", js)
    for func in score_funcs:
        assert "innerHTML" not in func, f"Found innerHTML in score function:\n{func}"


def test_phase_c_confirm_bar_markup_and_rules():
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    for btn_id in ["scoreConfirmAdd", "scoreConfirmFoul", "scoreConfirmInPlay", "scoreConfirmHbp", "scoreConfirmSkip"]:
        assert f'id="{btn_id}"' in html, f"Missing id='{btn_id}' in index.html"

    with open("static/app.js", encoding="utf-8") as f:
        js = f.read()

    assert "scoreOfferConfirm" in js, "Missing scoreOfferConfirm function in app.js"
    assert "pitch_detected" in js
    assert "zone_calibrated" in js
    assert "velocity_mph" in js

    skip_handler = re.search(r"scoreConfirmSkip\.addEventListener\([^)]*\)\s*=>\s*\{([\s\S]*?)\}\);", js)
    assert skip_handler is not None, "scoreConfirmSkip click listener not found"
    assert "scoreLastAddedVideoId" in skip_handler.group(1) or "scoreLastOfferedVideoId" in skip_handler.group(1), \
        "Skip handler must record the video_id to avoid double offering"


