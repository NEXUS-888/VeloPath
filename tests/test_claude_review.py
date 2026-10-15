"""The review wrapper's parsing, so the Antigravity <-> Claude loop can't silently misread the plan file."""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("claude_review", os.path.join(ROOT, "tools", "claude_review.py"))
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)

PLAN = """
## Progress log
### Phase B - READY FOR REVIEW  (round 1)
- files changed: static/app.js
### Phase B - READY FOR REVIEW  (round 2)
- files changed: static/app.js, static/index.html
- pytest: 140 passed
## Review log
### Review of Phase A (round 1): APPROVED
### Review of Phase B (round 1): CHANGES REQUESTED
"""


def test_round_number_counts_earlier_reviews_of_that_phase_only():
    assert cr.round_number(PLAN, "B") == 2
    assert cr.round_number(PLAN, "A") == 2
    assert cr.round_number(PLAN, "C") == 1


def test_newest_progress_entry_wins_and_stops_at_the_next_heading():
    status, text = cr.progress_entry(PLAN, "B")
    assert status == "READY FOR REVIEW" and "round 2" in text and "140 passed" in text
    assert "Review of Phase A" not in text and "round 1)" not in text.splitlines()[0]
    assert cr.progress_entry(PLAN, "C") == (None, None)


def test_stuck_entry_is_detected():
    assert cr.progress_entry("### Phase C - STUCK\n- fails: x\n", "C")[0] == "STUCK"


def test_verdict_is_extracted_and_renumbered_for_this_round():
    out = "Sure, here it is:\n### Review of Phase B (round 7): CHANGES REQUESTED\n- verified: app.js\n- must fix:\n  1. a -> b\n"
    verdict, kind = cr.extract_verdict(out, "B", 2)
    assert kind == "CHANGES REQUESTED"
    assert verdict.startswith("### Review of Phase B (round 2): CHANGES REQUESTED") and "1. a -> b" in verdict
    assert "Sure, here" not in verdict


def test_garbage_output_gives_no_verdict_and_wrong_phase_is_ignored():
    assert cr.extract_verdict("I think it looks fine!", "B", 1) == (None, None)
    assert cr.extract_verdict("### Review of Phase C (round 1): APPROVED", "B", 1) == (None, None)


def test_mechanical_verdict_lists_each_failing_check():
    out = "PASS  tests\nFAIL  required element ids present: scoreCard\nFAIL  node --check static/app.js: boom\n"
    v = cr.mechanical_verdict("B", 1, out)
    assert v.startswith("### Review of Phase B (round 1): CHANGES REQUESTED")
    assert "1. FAIL  required element ids present: scoreCard" in v and "2. FAIL  node --check" in v and "PASS" not in v
