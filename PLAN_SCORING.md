# Game Scoring: plan for Antigravity (Claude verifies)

Goal: score a real baseball game inside VeloPath. Balls/strikes come from the app's strike-zone call;
everything the camera cannot see (foul, what happened to a ball in play, steals) is one tap.
Antigravity builds, self-checks and logs progress; Claude only reviews and writes verdicts in the **Review log** at the bottom
of this file (see "Workflow").

## 0. Ground rules (read first)

- Repo `D:\Projects\baseball-search`, branch `fix/tracking-regression`. Python 3.14, FastAPI, vanilla JS + Tailwind CDN
  (`static/app.js`, `static/index.html`). Windows; use Git Bash or PowerShell.
- Follow `AGENTS.md` (Ponytail): smallest code that works, stdlib first, **no new dependencies**, no abstractions
  nobody asked for, fix root causes.
- **Do NOT touch**: `velopath/tracker.py`, `pipeline.py`, `geometry3d.py`, `renderer.py`, `strike_zone.py`, `physics.py`,
  `remote_gpu.py`, `model_manager.py`, `launcher.py`, `worker/`, `training/`, any existing test file except by
  *adding* tests. Scoring is independent of tracking.
- **Commit only after the Review log says APPROVED for that phase.** Stage files by explicit name (the phase's files +
  `PLAN_SCORING.md`); never `git add -A` or `git add .` (the repo has untracked video folders). Never push.
- Only Antigravity writes the **Progress log**; only Claude writes the **Review log**. Never edit the other's section.
- `tools/verify_phase.py` is the shared check script. Do not edit it.
- Never edit or delete: `.gitignore` entries already there, `gpu_worker.json`, `worker/key.txt`.
- Baseline that must never regress: `python -m pytest tests/ -q -k "not regression" -p no:cacheprovider`
  -> **133 passed** today (Phase A included). The `regression` tests need video clips and are slow; skip them.

## 1. State today

- Done and committed (`35505e5`): `velopath/scorebook.py` (`Game` class) + `tests/test_scorebook.py`.
- **Phase A is implemented, tests green, APPROVED by Claude (see Review log), not yet committed**: `Game.dump/load`,
  `pitch(kind, info)`, and in `velopath/server.py` the routes below, with `GAMES_DIR` / `GAMES` globals.
- Remaining: Phases B, C, D.

### Rules already decided (do not change, do not re-derive)
- Pitches: `ball`, `strike` (called or swinging), `foul`, `hbp`, `in_play`. 4 balls = walk (forces runners only as needed).
  3 strikes = out. Foul is a strike only while strikes < 2. `hbp` = walk.
- After `in_play` the next call must be `play(outcome)`: `single|double|triple|home_run|out|error|sac_fly|double_play`.
  Hits move every runner the same number of bases. `error` puts the batter on first and forces runners. `sac_fly`
  scores the runner from third only if outs < 2. `double_play` removes the runner from first (else the lead runner).
- `adjust(bases, runs, outs)`: `bases` **replaces** the runners; `runs` and `outs` are **added**. For steals, wild
  pitches, pickoffs, scoring corrections.
- 3 outs end the half inning. Home team does not bat if ahead after the top of the last inning. Walk-off ends the game
  immediately. Tied after the last inning = extra innings. `undo()` reverts one action (pitch and play are separate).

### Phase A API (already built; Phases B-D use it)
| Route | Body | Returns | Errors |
|---|---|---|---|
| `POST /api/games` | `{away?, home?, innings?}` (defaults Away/Home/9; innings 1-20) | `{id, state}` | 422 |
| `GET /api/games/{id}` | - | state | 404 |
| `POST /api/games/{id}/pitch` | `{kind, mph?, source?}` (`source` = `abs`/`manual`) | state | 409 rule, 422 input |
| `POST /api/games/{id}/play` | `{outcome}` | state | 409 rule, 422 input |
| `POST /api/games/{id}/adjust` | `{bases?: [b,b,b], runs?: 0-10, outs?: 0-3}` | state | 409, 422 |
| `POST /api/games/{id}/undo` | - | state (no-op if nothing to undo) | 404 |

State = `{away, home, innings, inning, top, outs, balls, strikes, bases:[b,b,b], runs:[away,home],
line:{away:[...], home:[...]}, awaiting_play, over, winner, log:[{inning, top, kind, balls, strikes, outs, runs, mph?, source?}]}`.

---

## Phase B: scoreboard UI

Files: `static/index.html`, `static/app.js` only (+ one test file `tests/test_ui_markup.py`).

Add a new card **after "Card 2" (Strike Zone & Plate Alignment Inspector, around line 408 of index.html)** in the right
sidebar. Match the existing look: `glass-panel card-outer`, `text-[10px] uppercase tracking-wider font-semibold text-slate-400`
labels, pitchcyan accents, emerald (strike) / rose (ball) colours already used by the call badges.

Element ids (tests and Claude's review depend on these exact names):
- `#scoreCard` card root.
- Setup: `#scoreNewBtn` ("New game"); small form `#scoreAway`, `#scoreHome` (text, maxlength 40), `#scoreInnings` (number 1-20, default 9),
  `#scoreStartBtn`. Form hidden once a game exists.
- Display: `#scoreInningLabel` (e.g. "▲ 3" top / "▼ 3" bottom), `#scoreCount` ("2-1" balls-strikes), `#scoreOuts` (3 dots, filled = out),
  `#scoreDiamond` (inline SVG, 3 bases filled when occupied), `#scoreLine` (table: team rows x innings + R column),
  `#scoreFinal` (hidden until `over`: "Final: Tigers 3 - Lions 2").
- Buttons: `[data-pitch="ball|strike|foul|hbp|in_play"]`, `#scorePlayPicker` containing `[data-play="single|double|triple|home_run|out|error|sac_fly|double_play"]`
  (shown only while `awaiting_play`), `#scoreAdjustBtn`, `#scoreUndoBtn`.
- Adjust panel `#scoreAdjust`: three base toggles `[data-base="0|1|2"]`, `#scoreRunsPlus`, `#scoreOutsPlus`, `#scoreAdjustApply`.
- Phase C bar: `#scoreConfirm` (see below). Create it now, hidden.

Behaviour:
1. One function `scoreRender(state)` redraws everything from a state object; every API response goes through it.
2. One helper `scoreCall(path, body)` does `fetch`, throws on non-2xx with the server's `detail`, and shows errors in a small
   `#scoreError` line (not `alert`).
3. While `awaiting_play`: disable the five pitch buttons and show `#scorePlayPicker`. While `over`: disable all action
   buttons except Undo and "New game".
4. Remember the current game id in `localStorage` key `velopath.gameId`, wrapped in try/catch (storage can be blocked).
   On page load, if an id is stored: `GET /api/games/{id}`; on 404 clear it and show the setup form.
5. **Team names are user input: render with `textContent` only. Never `innerHTML`** for anything from state.
6. Must not interfere with the existing video / strike-zone code: no changes to existing functions, no new global variable
   names that collide (prefix everything `score`). Existing keyboard shortcuts must keep working: do not add global key
   handlers.

Acceptance:
- `node --check static/app.js` passes.
- New `tests/test_ui_markup.py`: `GET /` returns HTML containing every id listed above, and `static/app.js` contains no
  `innerHTML` assignment that touches score state (simple regex test on the score section is enough).
- `python -m pytest tests/ -q -k "not regression" -p no:cacheprovider` all green.
- Manual checklist (Claude will run it in a browser): new game -> ball, ball, strike -> count shows 2-1 -> in play ->
  picker appears, pitch buttons disabled -> single -> diamond shows a runner, picker gone -> undo twice -> count back to 2-1
  -> reload page -> same game restored -> 3 strikeouts flips the inning arrow.

## Phase C: feed the scoreboard from the pitch analysis

When `/api/process` or `/api/rerender` returns a result (`updateTelemetry(data)` in app.js already receives it) **and a game is active**,
show `#scoreConfirm`: "Pitch: STRIKE, 84.5 mph" with buttons **Add as is**, **Foul**, **In play**, **Hit batter**, **Skip**.

Rules (these prevent wrong counts, follow exactly):
1. Offer only when `data.pitch_detected === true`, `data.zone_calibrated === true` and `data.call` is `STRIKE` or `BALL`.
   For `SET ZONE`, `NO PITCH DETECTED` or normal mode: do not auto-suggest; the user uses the manual pitch buttons.
2. "Add as is" posts `{kind: data.call.toLowerCase(), mph: data.velocity_mph, source: "abs"}`.
   Foul / In play / Hit batter post `{kind: "foul"|"in_play"|"hbp", mph, source: "manual"}`. Skip just hides the bar.
3. **No double counting**: remember the last `data.video_id` added; a re-render of the same clip (zone drag, theme change) must
   not re-show the bar for a pitch already added. A new upload is a new `video_id`.
4. The bar never adds anything by itself; one tap per pitch (a wrong auto count in a real game is worse than a tap).
5. If the game is over or `awaiting_play`, show the bar disabled with the reason.

Acceptance: `node --check`; full suite green; Claude's browser check: process a clip with a calibrated zone while a game is
active -> bar appears -> Add -> count changes; drag the zone -> bar does not reappear for that clip.

## Phase D: log table and CSV export

1. `GET /api/games/{id}/export.csv` in `velopath/server.py`: header
   `inning,half,kind,balls,strikes,outs,away_runs,home_runs,mph,source`, one row per log entry, `half` = `top`/`bottom`,
   empty cell when `mph`/`source` missing. Content-Type `text/csv`, `Content-Disposition: attachment; filename="game-<id>.csv"`.
   Same game-id validation and 404 as the other routes. Use stdlib `csv` + `io.StringIO`.
2. UI: collapsible `#scoreLogToggle` / `#scoreLog` showing the last 30 events newest first ("Top 3 | ball 2-1 | 84.5 mph"),
   plus a `#scoreExport` link to the CSV.
3. Tests in `tests/test_server.py`: CSV header and one row per event, 404 for unknown id, a game id with path characters
   is rejected, mph column filled only where given, a team name containing a comma stays one CSV cell.

Acceptance: new tests pass, full suite green.

## Out of scope (do not build)
Lineups and per-batter strike zones, pitcher stats, login/accounts, full-game automatic pitch detection, live streaming.

---

## Workflow: Antigravity builds, a headless Claude reviews, no human in between

Roles
- **Antigravity** does everything expensive: code, tests, running checks, the browser walk-through, commits (after approval),
  and launching the review.
- **Claude** is launched by you with one command (`python tools/claude_review.py <X>`), as a fresh read-only headless session that
  loads the project memory on its own. It only prints a verdict; the script appends it to the **Review log**. Claude never edits code.
- The human is only needed when a script exits with code 3.

Step 0 (once, before Phase B): read the Review log. Phase A is APPROVED, so commit it, then the docs and tools:
1. `git add .gitignore tests/test_scorebook.py tests/test_server.py velopath/scorebook.py velopath/server.py`
   -> commit `feat(scorebook): persist games, pitch info, /api/games endpoints`
2. `git add PLAN_SCORING.md tools/verify_phase.py tools/claude_review.py tests/test_claude_review.py`
   -> commit `docs: scoring plan, phase verification and review scripts`

Per phase loop (B, then C, then D; one phase at a time)
1. Read this file in full, especially the newest Review log entry. If it says CHANGES REQUESTED, fix exactly those items first.
2. Write the phase's tests first and confirm they fail for the right reason. Then implement the minimum.
3. Self-check until clean: `python tools/verify_phase.py <X>` (no FAIL lines). For UI phases, do the manual checklist yourself in a
   browser against a running app (`python -m velopath.server`, port 8000), and save 2-3 screenshots outside the repo in
   `D:\Projects\scoring_evidence\<phase>\` (list the paths in your entry).
4. Max 5 fix loops. If still failing, write a `STUCK` entry (what fails, last output, your hypothesis) and stop.
5. Append a Progress entry (format below) with status `READY FOR REVIEW`, then run **`python tools/claude_review.py <X>`**.
   It prints the verdict and appends it to the Review log. Exit code:
   - **0 = APPROVED**: stage the phase's files by name plus `PLAN_SCORING.md`, commit `feat(scorebook): <what the phase added>`,
     then start the next phase (after Phase D: stop and tell the human you are finished).
   - **2 = CHANGES REQUESTED**: fix exactly the "must fix" items, re-run step 3, append a new entry `READY FOR REVIEW (round N)`,
     run the review command again.
   - **3 = NEEDS HUMAN** (you wrote STUCK, or more than 3 rounds): stop and tell the human why.
   - **1 = error** (reviewer gave no verdict): run the command once more; if it fails again, stop and tell the human.

Progress log entry format (short; the reviewer re-runs the mechanical checks itself):
```
### Phase X - READY FOR REVIEW | STUCK  (round N)
- files changed: a, b, c
- verify_phase.py: ALL CHECKS PASSED | failing lines
- pytest: N passed
- manual checklist: each step PASS/FAIL, evidence paths
- deviations from the plan: none | what and why
- open questions: none | ...
```

What `tools/claude_review.py` does (so you know what you are talking to)
1. Runs `tools/verify_phase.py`. If anything fails, it writes CHANGES REQUESTED itself, with the failing lines, and calls no model.
2. If clean, it launches headless Claude (read-only: Read, Grep, Glob, `git diff/show/status/log`) with your progress entry and the risk list
   for the phase; Claude inspects only the flagged code and answers with the verdict block only.
3. It appends the verdict to the Review log and exits with the code above. (Touching protected tracking files is caught by
   `verify_phase.py`, not by the model.)

## Progress log
(Antigravity appends below)

## Review log
(Claude writes below)

### Review of Phase A (round 1): APPROVED
- verified: full non-regression suite 133 passed; routes, lock around load-act-save, atomic write (tmp + `os.replace`),
  game-id regex before any filesystem access, 404/409/422 mapping all present and covered by tests.
- next: do Step 0 (commit Phase A, then docs/tool), then Phase B.

