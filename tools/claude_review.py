"""
Antigravity's one-command review: python tools/claude_review.py B|C|D [--dry-run]

1. Runs tools/verify_phase.py (free). Failures -> a CHANGES REQUESTED verdict without calling any model.
2. Otherwise launches a fresh headless Claude Code in the repo (it loads project memory + AGENTS.md by itself),
   read-only, for the judgment part of the review. Claude only prints the verdict.
3. This script appends the verdict to the Review log in PLAN_SCORING.md (Claude never edits files).
Exit code: 0 APPROVED, 2 CHANGES REQUESTED, 3 a human is needed (STUCK or round limit), 1 error.
Env: VELOPATH_REVIEW_MODEL (default sonnet), VELOPATH_REVIEW_BUDGET_USD (default 1.00).
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "PLAN_SCORING.md")
MAX_ROUNDS = 3
MODEL = os.environ.get("VELOPATH_REVIEW_MODEL", "sonnet")
BUDGET = os.environ.get("VELOPATH_REVIEW_BUDGET_USD", "1.00")

COMMON_RISKS = ("HTML injection (user text must go through textContent), path traversal on game ids, load-act-save without the lock, "
                "non-atomic writes, an uncalibrated or guessed call being offered or auto-added, double counting on re-render, "
                "global names colliding with existing app.js names, existing functions or shortcuts changed.")
PHASE_CHECKS = {
    "B": "Team names rendered with textContent; all score identifiers prefixed `score`; play picker shown only while awaiting_play; "
         "pitch buttons disabled while awaiting_play or over; localStorage access wrapped in try/catch; page reload restores the game "
         "(GET on load, 404 clears the stored id); evidence screenshots listed in the progress entry.",
    "C": "The confirm bar is offered only when pitch_detected && zone_calibrated && call is STRIKE or BALL (never for SET ZONE, "
         "NO PITCH DETECTED or normal mode); nothing is ever added without a tap; the same video_id is never offered twice; "
         "mph comes from velocity_mph; source is 'abs' only for 'Add as is'; disabled with a reason when over or awaiting_play.",
    "D": "CSV built with the csv module (a team name containing a comma stays one cell); the route validates the game id like the "
         "other routes and returns 404; Content-Disposition attachment; mph/source cells empty when missing; log UI uses textContent.",
}


def read_plan(path=PLAN):
    with open(path, encoding="utf-8") as f:
        return f.read()


def round_number(plan, phase):
    return len(re.findall(rf"^### Review of Phase {phase}\b", plan, re.M)) + 1


def progress_entry(plan, phase):
    """(status, text) of the newest '### Phase X - READY FOR REVIEW|STUCK' entry, or (None, None)."""
    found = list(re.finditer(rf"^### Phase {phase} - (READY FOR REVIEW|STUCK)[^\n]*$", plan, re.M))
    if not found:
        return None, None
    m = found[-1]
    nxt = re.search(r"^##", plan[m.end():], re.M)  # next heading, any level
    return m.group(1), plan[m.start(): m.end() + (nxt.start() if nxt else len(plan) - m.end())].strip()


def mechanical_verdict(phase, n, verify_out):
    fails = [l.strip() for l in verify_out.splitlines() if l.startswith("FAIL")]
    items = "\n".join(f"  {i}. {l}" for i, l in enumerate(fails, 1)) or "  1. tools/verify_phase.py did not pass (see its output)"
    return (f"### Review of Phase {phase} (round {n}): CHANGES REQUESTED\n"
            f"- verified: tools/verify_phase.py {phase} reported failures; no model review was run\n- must fix:\n{items}")


def extract_verdict(output, phase, n):
    """The verdict block from Claude's output with its header normalised to this round, or None."""
    m = re.search(rf"^### Review of Phase {phase} \(round \d+\): (APPROVED|CHANGES REQUESTED)[^\n]*$", output, re.M)
    if not m:
        return None, None
    return f"### Review of Phase {phase} (round {n}): {m.group(1)}" + output[m.end():].rstrip(), m.group(1)


def build_prompt(phase, n, verify_out, entry, stat):
    return f"""You are the reviewer in the PLAN_SCORING.md workflow of VeloPath (you already have the project memory loaded).
Review Phase {phase}, round {n}. You are READ-ONLY: never edit or create files.

The mechanical checks already passed:
{verify_out.strip()}

Antigravity's progress entry:
{entry[:3500]}

Changed files (git diff --stat HEAD):
{stat[:1500]}

Your job is judgment only. Inspect just the code that matters for these risks, using Read, Grep and `git diff -U0 HEAD -- <file>`:
- Always: {COMMON_RISKS}
- Phase {phase}: {PHASE_CHECKS[phase]}
Do not re-read whole files, do not re-run tests, do not review style.

Reply with ONLY this block, nothing before or after it:
### Review of Phase {phase} (round {n}): APPROVED
or
### Review of Phase {phase} (round {n}): CHANGES REQUESTED
- verified: <one line: what you inspected>
- must fix: (only when changes are requested)
  1. <file:line> <what is wrong> -> <expected behaviour or test to add>
Approve unless there is a real must-fix item. Every must-fix item must be actionable by a coding agent without asking you anything."""


def claude_exe():
    """The real claude executable: on Windows `claude` is an npm shim that Python cannot launch (and a .cmd would mangle the prompt)."""
    exe = os.environ.get("VELOPATH_CLAUDE_EXE") or shutil.which("claude") or "claude"
    if not exe.lower().endswith(".exe"):
        real = os.path.join(os.path.dirname(exe), "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
        exe = real if os.path.exists(real) else exe
    return exe


def run_claude(prompt):
    cmd = [claude_exe(), "-p", "--model", MODEL, "--strict-mcp-config", "--no-session-persistence",
           "--permission-mode", "dontAsk", "--max-budget-usd", BUDGET,
           "--allowedTools", "Read", "Grep", "Glob", "Bash(git diff:*)", "Bash(git show:*)", "Bash(git status:*)", "Bash(git log:*)",
           "--output-format", "text"]
    r = subprocess.run(cmd, cwd=ROOT, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    return r.stdout


def append_verdict(text):
    with open(PLAN, "a", encoding="utf-8") as f:
        f.write("\n" + text.strip() + "\n")


def main(phase, dry_run=False):
    plan = read_plan()
    n = round_number(plan, phase)
    status, entry = progress_entry(plan, phase)

    def finish(text, code):
        print(text)
        if not dry_run:
            append_verdict(text)
        return code

    if n > MAX_ROUNDS:
        return finish(f"### Review of Phase {phase} (round {n}): NEEDS HUMAN\n- more than {MAX_ROUNDS} review rounds; stop and ask the human", 3)
    if status is None:
        return finish(f"### Review of Phase {phase} (round {n}): CHANGES REQUESTED\n- verified: no '### Phase {phase} - READY FOR REVIEW' "
                      f"entry in the Progress log\n- must fix:\n  1. append the progress entry in the documented format, then run this again", 2)
    if status == "STUCK":
        return finish(f"### Review of Phase {phase} (round {n}): NEEDS HUMAN\n- Antigravity reported STUCK; see its entry", 3)

    v = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "verify_phase.py"), phase],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if v.returncode != 0:
        return finish(mechanical_verdict(phase, n, v.stdout), 2)

    stat = subprocess.run(["git", "diff", "--stat", "HEAD"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    prompt = build_prompt(phase, n, v.stdout, entry, stat)
    if dry_run:
        print(prompt)
        return 0
    verdict, kind = extract_verdict(run_claude(prompt), phase, n)
    if verdict is None:
        print("ERROR: the reviewer returned no verdict block; nothing was written. Run again.", file=sys.stderr)
        return 1
    return finish(verdict, 0 if kind == "APPROVED" else 2)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1 or args[0] not in PHASE_CHECKS:
        sys.exit("usage: python tools/claude_review.py B|C|D [--dry-run]")
    sys.exit(main(args[0], "--dry-run" in sys.argv))
