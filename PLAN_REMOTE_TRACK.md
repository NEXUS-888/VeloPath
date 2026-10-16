# PLAN_REMOTE_TRACK.md - run the whole ball tracking on the friend's GPU

Written 2026-10-16 by Claude. Antigravity builds it; Claude reviews at the end (Review log at the bottom).
Read first: `AGENTS.md` (Ponytail: fewest lines, reuse, stdlib, no new dependencies), `training/README.md` (models), `worker/README.txt`.

## Goal
Today `velopath/remote_gpu.py:RemoteYolo` sends ONE JPEG PER YOLO CALL to the friend's GPU; the tracker logic (scan, flight selection,
refine, rescans) runs on this laptop, so there are hundreds of network round trips and a big upload. Replace it with:

1. This laptop uploads the **video file once** (compressed, 10-30x smaller than per-frame JPEGs) with the tracking parameters.
2. The friend's laptop runs the **real `PitchTracker.track_video`** next to its GPU (hybrid: small YOLO11s scans at 1280, big
   `ball_trackingv4` refines, exactly as on this laptop) and returns only the **result**: trajectory points, fps, size, plate, perspective.
3. This laptop does everything else locally as today (physics, 3D, ABS, rendering, scoreboard). Nothing else changes.
4. Any failure (worker off, busy, timeout, code mismatch, file too big) -> **fall back to the local CPU tracker automatically**.

Contract of the seam (already in `velopath/pipeline.py`, around line 194):
`tracker.track_video(path, conf_thresh, ball_type, perspective, mode, progress_callback, time_window) -> (points, fps, (w, h))`
plus attributes `tracker.last_plate` (tuple or None) and `tracker.last_resolved_perspective` (str) read afterwards,
plus `tracker.model.gpu_name` / `.using_fallback` for the UI "compute" label. `TrajectoryPoint(frame_idx, x, y, conf, radius)` is in `velopath/tracker.py`.

## Rules (do not break)
- **Do NOT edit**: `velopath/tracker.py` logic, `geometry3d.py`, `renderer.py`, `strike_zone.py`, `physics.py`, `scorebook.py`, `static/`, `training/`, `models/`.
  The remote result must equal the local result, so the worker must run the same `tracker.py`, not a rewrite.
- Allowed to edit: `velopath/remote_gpu.py`, `velopath/pipeline.py` (only the tracker selection and the compute label), `worker/*`,
  new `worker/package.py`, `worker/selftest.py`, `tests/test_remote_gpu.py`, `tests/test_worker.py`, `.gitignore` if needed, and the logs in this file.
- Secrets: never print, commit or paste `worker/key.txt` or `gpu_worker.json`. Both are gitignored. `*.pt` files are gitignored.
- Git: commit each step separately with `git add <explicit files>` (never `git add -A`), never push, end commit messages with
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Tests first (write a failing test, then the code).
  `pytest tests/ -q -k "not regression"` must stay green.
- stdlib only for HTTP (`http.server`, `http.client`, `threading`, `secrets`, `hashlib`, `tempfile`, `json`). No new dependencies.

## Protocol (worker <-> client)
All requests carry the header `X-VeloPath-Key` (same constant-time `hmac.compare_digest` check as now).
- `GET /health` -> `{"ok": true, "gpu": "...", "names": {...}, "code": "<sha256 of tracker.py bytes>", "busy": false}`
- `POST /track?conf=0.15&ball=auto&persp=auto&mode=baseball&start=<s>&end=<s>`, body = raw video bytes (`Content-Length` required)
  -> `202 {"job": "<32 hex>"}` right after the upload is saved to a temp file; `409 {"error": "busy"}` if a job is running;
  `413` if over `MAX_VIDEO_BYTES` (400 MB); `401` bad key. `start`/`end` are optional (the pitch window).
- `GET /job/<id>` -> `{"state": "running", "progress": 0.0-1.0}` or `{"state": "done", "result": {...}}` or `{"state": "error", "error": "..."}`;
  unknown id -> 404. The id must match `[0-9a-f]{32}` before it is used for anything.
- result = `{"points": [[frame_idx, x, y, conf, radius], ...], "fps": f, "size": [w, h], "plate": [...] or null, "perspective": "..."}`
- The server must be a `ThreadingHTTPServer` (polls must answer while a job runs). The job runs in ONE background thread, one job at a time
  (YOLO is not thread-safe). The temp video is deleted when the job ends (success or error). Finished jobs are kept 10 minutes, then dropped.
  Bind to the Tailscale IP only (existing `tailscale_ip()`).
- The old `POST /predict` stays until the cleanup step (Step 6).

## Steps (each: test first, then code, then commit)
**Step 1 - worker job server** (`worker/velopath_worker.py`, `tests/test_worker.py`).
`make_server(tracker, key, host, port, gpu_name, code_hash)` takes an injected tracker so tests use a `FakeTracker`
(returns fixed points, sleeps briefly, calls `progress_callback`). Tests: 401 without key; upload gives 202 + job id; polling shows running then
done with the exact points; a second upload while running gives 409; a bad job id gives 404; 413 when too big (use a tiny `MAX_VIDEO_BYTES` override);
temp file removed after the job; a tracker exception gives `state: error` and the server stays alive; `/health` includes `code` and `busy`.
`main()` builds the real `PitchTracker()` (CUDA) after the existing GPU checks and warm-up.

**Step 2 - package the code for the worker** (`worker/package.py`).
One command `python worker/package.py` rebuilds `velopath_gpu_worker.zip` containing: the current `worker/` files (never `key.txt` unless `--with-key`;
the owner hands the key over separately) plus a minimal `velopath/` package (`__init__.py`, `tracker.py`, `model_manager.py`, `remote_gpu.py`) and `models/`
with both weights if present (`ball_trackingv4.pt`, `ball_small_yolo11s.pt`). The big model may need `reassemble_from_parts`: check
`model_manager.get_default_model_paths` and make `get_project_root()` resolve to the worker folder inside the zip.
Update the dependency header of `velopath_worker.py` (add `opencv-python-headless`, `numpy`, `scipy` next to ultralytics/torch; they are already project dependencies).
Test: unzip to a temp dir and run `python -c "import velopath.tracker"` using only the zip's contents (the repo is not on the path).

**Step 3 - client** (`velopath/remote_gpu.py`, `tests/test_remote_gpu.py`).
New `RemoteTracker(url, key, fallback)` with the same `track_video(...)` signature as `PitchTracker` and the attributes `last_plate`,
`last_resolved_perspective`, `model.gpu_name`, `model.using_fallback` (small adapter object or properties). Flow: `/health` check
(also compare `code` with `sha256(velopath/tracker.py)`; on mismatch log "worker runs different tracker code, using this computer" and fall back),
upload the file by streaming (`http.client`, chunked reads, never load 400 MB into memory), poll `/job/<id>` every 1 s calling
`progress_callback(0.1 + 0.9 * progress)` (the upload counts as the first 10%), map the points to `TrajectoryPoint`, set the attributes.
On ANY exception, 409, 413, timeout (upload 10 min, job 15 min) or worker `error`: print one `[RemoteGPU]` line and run `fallback.track_video(...)`
with the same arguments; mark `using_fallback` so the UI says "this computer". After a failure do not retry the worker for 30 s (as `RETRY_AFTER_S` does today).
A wrong key raises `PermissionError` (not hidden), as today. Tests use the real worker `make_server` on localhost with `FakeTracker`:
happy path equals the fake's points; busy gives fallback; worker killed mid-job gives fallback; code mismatch gives fallback; wrong key raises.

**Step 4 - wire into the pipeline** (`velopath/pipeline.py`, small).
Keep the local `PitchTracker`; when `gpu_worker.json` exists and the worker answers `/health`, `_analyze_and_render` calls `RemoteTracker.track_video`
instead. The `/health` check runs for EVERY clip (5 s timeout), not once at server start, so starting or stopping the friend's worker never needs an app restart; if it does not answer, that clip runs locally. Keep `_TRACK_LOCK` and the "compute" label logic (`"<gpu> (GPU worker)"` vs `"this computer"`). Tests: with a fake remote tracker injected,
`process_video` still returns the same fields (`compute`, trajectory, `zone_calibrated`, ...); with none configured nothing changes. Existing tests stay green.

**Step 5 - local equality test (no GPU needed)**.
`worker/selftest.py`: start the real worker on `127.0.0.1` with the REAL `PitchTracker()` on this CPU, track `not good tracking/Test !.mp4`
through `RemoteTracker`, and assert the points are identical to a direct local `track_video` (same frames, positions within 1e-6, same fps/size/plate).
This proves the whole path before the friend is involved. Record the timing.

**Step 6 - cleanup (only after Step 5 passes)**.
Delete the per-frame path: `RemoteYolo`, `_Boxes`, `_Result`, `POST /predict`. The only edit allowed in `velopath/tracker.py` is removing the 3-line
`connect_remote` block (around lines 180-183). Update `worker/README.txt` and add a "Remote GPU" paragraph to `training/README.md`. Tests that covered the old
path are replaced by the new ones. Rebuild the zip with `python worker/package.py`.

## Acceptance (all must hold)
1. `pytest tests/ -q -k "not regression"` is green and `python worker/selftest.py` prints PASS (remote result identical to local).
2. With `gpu_worker.json` absent or the worker off, the app behaves exactly as before (local CPU tracking).
3. Killing the worker mid-clip makes the clip finish on this CPU, and the UI "compute" says "this computer".
4. No secret is tracked by git, and the zip has no `key.txt` by default.
5. The `velopath/tracker.py` diff is empty after Step 5, and only the 3-line block is removed after Step 6.

## Real GPU test (human + friend, after the plan is done)
Friend: install Tailscale and accept the invite, unzip, double-click `start_worker.bat` (first run downloads ~3 GB).
Owner: put `{"url": "http://<friend tailscale ip>:8765", "key": "<key>"}` in `gpu_worker.json`, run the app, process `test videos/20260923_140455.MOV.mp4`.
Expect the log `[RemoteGPU] Using GPU worker ...`, the "compute" label showing the GPU name, and a trajectory matching the local run.
Expected time about 10-20 s instead of 77 s (an estimate; never measured on a real GPU).

## Progress log (Antigravity appends, one entry per step)
Format: `### Step N - DONE` or `### Step N - STUCK`, then: files changed, the `pytest` result line, what was verified, anything surprising.
If a step fails twice, write STUCK with the error and stop.

## Review log (Claude appends)
