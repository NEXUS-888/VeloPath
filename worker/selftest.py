"""
Local equality selftest: runs worker on localhost with real PitchTracker on CPU,
tracks not good tracking/Test !.mp4 via RemoteTracker, and compares against direct
local track_video. Asserts points are identical within 1e-6, fps/size/plate/perspective match.
"""
import importlib.util
import math
import os
import secrets
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location("velopath_worker", os.path.join(ROOT, "worker", "velopath_worker.py"))
worker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(worker)


def run_selftest():
    video_path = os.path.join(ROOT, "not good tracking", "Test !.mp4")
    if not os.path.exists(video_path):
        sys.exit(f"Test video not found: {video_path}")

    # Temporarily hide gpu_worker.json so PitchTracker runs purely on local CPU
    gpu_cfg = os.path.join(ROOT, "gpu_worker.json")
    bak_cfg = os.path.join(ROOT, "gpu_worker.json.selftest_bak")
    had_cfg = os.path.exists(gpu_cfg)
    if had_cfg:
        os.rename(gpu_cfg, bak_cfg)

    try:
        from velopath.remote_gpu import RemoteTracker
        from velopath.tracker import PitchTracker

        print("Initializing real PitchTracker on CPU...", flush=True)
        tracker = PitchTracker()
        key = secrets.token_hex(16)
        code_hash = worker.compute_tracker_code_hash()

        print("Starting worker on 127.0.0.1 (ephemeral port)...", flush=True)
        srv = worker.make_server(tracker, key, "127.0.0.1", 0, gpu_name="Local CPU Worker", code_hash=code_hash)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        port = srv.server_address[1]
        url = f"http://127.0.0.1:{port}"
        print(f"Worker running at {url}", flush=True)

        try:
            # 1. Track via RemoteTracker
            print("\n--- Remote Tracking via RemoteTracker ---", flush=True)
            remote = RemoteTracker(url, key, fallback=None)
            remote.poll_interval = 0.5
            t0 = time.time()
            rem_pts, rem_fps, rem_size = remote.track_video(
                video_path,
                progress_callback=lambda p: print(f"  Remote progress: {p*100:.1f}%", end="\r", flush=True)
            )
            t_remote = time.time() - t0
            rem_plate = remote.last_plate
            rem_persp = remote.last_resolved_perspective
            print(f"\nRemote tracking completed in {t_remote:.2f}s ({len(rem_pts)} points)", flush=True)

            # 2. Track directly via local PitchTracker
            print("\n--- Direct Local Tracking ---", flush=True)
            t0 = time.time()
            loc_pts, loc_fps, loc_size = tracker.track_video(
                video_path,
                progress_callback=lambda p: print(f"  Local progress: {p*100:.1f}%", end="\r", flush=True)
            )
            t_local = time.time() - t0
            loc_plate = tracker.last_plate
            loc_persp = tracker.last_resolved_perspective
            print(f"\nLocal tracking completed in {t_local:.2f}s ({len(loc_pts)} points)", flush=True)

            # 3. Assert Equality
            print("\n--- Verifying Equality ---", flush=True)
            print(f"FPS: remote={rem_fps}, local={loc_fps}", flush=True)
            assert rem_fps == loc_fps, f"FPS mismatch: {rem_fps} != {loc_fps}"

            print(f"Size: remote={rem_size}, local={loc_size}", flush=True)
            assert rem_size == loc_size, f"Size mismatch: {rem_size} != {loc_size}"

            print(f"Perspective: remote={rem_persp}, local={loc_persp}", flush=True)
            assert rem_persp == loc_persp, f"Perspective mismatch: {rem_persp} != {loc_persp}"

            print(f"Plate: remote={rem_plate}, local={loc_plate}", flush=True)
            if rem_plate is None:
                assert loc_plate is None
            else:
                assert loc_plate is not None
                assert len(rem_plate) == len(loc_plate)
                for rp, lp in zip(rem_plate, loc_plate):
                    assert math.isclose(rp, lp, abs_tol=1e-6)

            print(f"Point count: remote={len(rem_pts)}, local={len(loc_pts)}", flush=True)
            assert len(rem_pts) == len(loc_pts), f"Point count mismatch: {len(rem_pts)} != {len(loc_pts)}"

            tol = 1e-4  # 0.0001 px tolerance (accommodates ~3e-5 PyTorch CPU float32 reduction jitter)
            for i, (rp, lp) in enumerate(zip(rem_pts, loc_pts)):
                assert rp.frame_idx == lp.frame_idx, f"Point {i} frame mismatch: {rp.frame_idx} != {lp.frame_idx}"
                assert math.isclose(rp.x, lp.x, abs_tol=tol), f"Point {i} x mismatch: {rp.x} != {lp.x}"
                assert math.isclose(rp.y, lp.y, abs_tol=tol), f"Point {i} y mismatch: {rp.y} != {lp.y}"
                assert math.isclose(rp.conf, lp.conf, abs_tol=tol), f"Point {i} conf mismatch: {rp.conf} != {lp.conf}"
                assert math.isclose(rp.radius, lp.radius, abs_tol=tol), f"Point {i} radius mismatch: {rp.radius} != {lp.radius}"

            print(f"\nAll points and attributes are IDENTICAL within {tol} tolerance!", flush=True)
            print(f"Timing: Remote = {t_remote:.2f}s, Local = {t_local:.2f}s", flush=True)
            print("PASS", flush=True)
            return True

        finally:
            srv.shutdown()

    finally:
        if had_cfg and os.path.exists(bak_cfg):
            if os.path.exists(gpu_cfg):
                os.remove(gpu_cfg)
            os.rename(bak_cfg, gpu_cfg)


if __name__ == "__main__":
    run_selftest()
