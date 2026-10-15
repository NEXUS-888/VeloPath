"""
Compact check for a scoring phase. Usage: python tools/verify_phase.py B|C|D [--fast]
Prints one PASS/FAIL line per check (a reviewer reads ~15 lines); exit code 1 if anything fails.
--fast skips the full test run. Antigravity runs this before asking for review; Claude runs it to review.
"""
import re
import subprocess
import sys

PHASES = {
    "B": {"allow": {"static/index.html", "static/app.js", "tests/test_ui_markup.py"},
          "ids": ["scoreCard", "scoreNewBtn", "scoreAway", "scoreHome", "scoreInnings", "scoreStartBtn", "scoreInningLabel",
                  "scoreCount", "scoreOuts", "scoreDiamond", "scoreLine", "scoreFinal", "scorePlayPicker", "scoreAdjustBtn",
                  "scoreUndoBtn", "scoreAdjust", "scoreAdjustApply", "scoreRunsPlus", "scoreOutsPlus", "scoreConfirm", "scoreError"],
          "attrs": {'data-pitch="': 5, 'data-play="': 8, 'data-base="': 3}},
    "C": {"allow": {"static/index.html", "static/app.js", "tests/test_ui_markup.py"}, "ids": ["scoreConfirm"], "attrs": {}},
    "D": {"allow": {"velopath/server.py", "tests/test_server.py", "static/index.html", "static/app.js", "tests/test_ui_markup.py"},
          "ids": ["scoreLogToggle", "scoreLog", "scoreExport"], "attrs": {}, "text": {"velopath/server.py": "export.csv"}},
}
ALWAYS = {"PLAN_SCORING.md"}  # the progress log lives there
FORBIDDEN = ("velopath/tracker.py", "velopath/pipeline.py", "velopath/geometry3d.py", "velopath/renderer.py",
             "velopath/strike_zone.py", "velopath/physics.py", "velopath/remote_gpu.py", "velopath/model_manager.py",
             "velopath/launcher.py", "worker/", "training/", "tools/")
STANDING = ("CLAUDE_PLAN_REVIEW.md", "normal/", "test videos/", "drive_upload/", "not good tracking/", "scoring_evidence/")
RISKY = re.compile(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function")

fails = []


def report(ok, name, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f": {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def run(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def main(phase, fast):
    spec = PHASES[phase]
    changed = []
    for line in run("git", "status", "--porcelain").stdout.splitlines():
        path = line[3:].strip().strip('"')
        if "->" not in path and not path.startswith(STANDING):
            changed.append(path)
    report(not [p for p in changed if p.startswith(FORBIDDEN)], "protected files untouched",
           ", ".join(p for p in changed if p.startswith(FORBIDDEN)))
    stray = [p for p in changed if p not in spec["allow"] | ALWAYS and not p.startswith(FORBIDDEN)]
    report(not stray, f"only phase {phase} files changed", ", ".join(stray))

    if not fast:
        out = run(sys.executable, "-m", "pytest", "tests/", "-q", "-k", "not regression", "-p", "no:cacheprovider").stdout
        last = out.strip().splitlines()[-1] if out.strip() else "no output"
        report(re.search(r"\d+ passed", last) is not None and "failed" not in last and "error" not in last,
               "tests", last)
    node = run("node", "--check", "static/app.js")
    report(node.returncode == 0, "node --check static/app.js", node.stderr.strip()[:200])

    html = open("static/index.html", encoding="utf-8").read()
    missing = [i for i in spec["ids"] if f'id="{i}"' not in html]
    report(not missing, "required element ids present", ", ".join(missing))
    thin = [f"{a} x{html.count(a)} (need {n})" for a, n in spec["attrs"].items() if html.count(a) < n]
    report(not thin, "buttons present", "; ".join(thin))
    for path, needle in spec.get("text", {}).items():
        report(needle in open(path, encoding="utf-8").read(), f"{path} mentions {needle}")

    added = [l[1:].strip() for l in run("git", "diff", "-U0", "HEAD", "--", "static", "velopath").stdout.splitlines()
             if l.startswith("+") and not l.startswith("+++")]
    risky = [l[:110] for l in added if RISKY.search(l)]
    report(not risky, "no HTML-injection patterns in added lines", " | ".join(risky[:4]))
    print("\nALL CHECKS PASSED" if not fails else f"\n{len(fails)} CHECK(S) FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in PHASES:
        sys.exit("usage: python tools/verify_phase.py B|C|D [--fast]")
    sys.exit(main(sys.argv[1], "--fast" in sys.argv))
