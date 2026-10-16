"""
Rebuilds velopath_gpu_worker.zip containing worker files, minimal velopath package,
and model weights so the worker can run standalone on the friend's GPU.
"""
import argparse
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER_DIR = os.path.join(ROOT, "worker")
DEFAULT_OUT = os.path.join(ROOT, "velopath_gpu_worker.zip")


def find_or_assemble_weights() -> dict:
    """Finds or reassembles the big and small model weights."""
    sys.path.insert(0, ROOT)
    from velopath.model_manager import (
        MODEL_FILENAME,
        SMALL_MODEL_FILENAME,
        reassemble_from_parts,
        reassemble_small_from_parts,
    )

    models_to_pack = {}

    # 1. Big model: ball_trackingv4.pt
    big_candidates = [
        os.path.join(ROOT, "models", MODEL_FILENAME),
        os.path.join(WORKER_DIR, MODEL_FILENAME),
    ]
    big_path = next((p for p in big_candidates if os.path.exists(p) and os.path.getsize(p) > 10_000_000), None)
    if not big_path:
        target = os.path.join(ROOT, "models", MODEL_FILENAME)
        big_path = reassemble_from_parts(target)
    if big_path and os.path.exists(big_path):
        models_to_pack[MODEL_FILENAME] = big_path

    # 2. Small model: ball_small_yolo11s.pt
    small_candidates = [
        os.path.join(ROOT, "models", SMALL_MODEL_FILENAME),
        os.path.join(WORKER_DIR, SMALL_MODEL_FILENAME),
    ]
    small_path = next((p for p in small_candidates if os.path.exists(p) and os.path.getsize(p) > 10_000_000), None)
    if not small_path:
        target = os.path.join(ROOT, "models", SMALL_MODEL_FILENAME)
        small_path = reassemble_small_from_parts(target)
    if small_path and os.path.exists(small_path):
        models_to_pack[SMALL_MODEL_FILENAME] = small_path

    return models_to_pack


def package_worker(out_zip: str = DEFAULT_OUT, with_key: bool = False):
    """Builds the standalone worker zip package."""
    os.makedirs(os.path.dirname(os.path.abspath(out_zip)), exist_ok=True)
    temp_zip = out_zip + ".building"

    with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # 1. Worker files
        for fname in os.listdir(WORKER_DIR):
            fpath = os.path.join(WORKER_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            if fname.endswith(".pt") or fname.endswith(".pyc") or fname == "package.py":
                continue
            if fname == "key.txt" and not with_key:
                continue
            z.write(fpath, arcname=fname)
            print(f"  + {fname}")

        # 2. Minimal velopath package
        velopath_files = ["__init__.py", "tracker.py", "model_manager.py", "remote_gpu.py"]
        for vname in velopath_files:
            vpath = os.path.join(ROOT, "velopath", vname)
            if os.path.exists(vpath):
                arcname = os.path.join("velopath", vname)
                z.write(vpath, arcname=arcname)
                print(f"  + {arcname}")

        # 3. Model weights into models/
        models = find_or_assemble_weights()
        for mname, mpath in models.items():
            arcname = os.path.join("models", mname)
            z.write(mpath, arcname=arcname)
            mb = os.path.getsize(mpath) / (1024 * 1024)
            print(f"  + {arcname} ({mb:.1f} MB)")

    if os.path.exists(out_zip):
        os.remove(out_zip)
    os.rename(temp_zip, out_zip)
    total_mb = os.path.getsize(out_zip) / (1024 * 1024)
    print(f"\nBuilt {out_zip} ({total_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Package VeloPath GPU Worker")
    parser.add_argument("--with-key", action="store_true", help="Include key.txt in the zip package")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Path for the output zip file")
    args = parser.parse_args()

    package_worker(out_zip=args.out, with_key=args.with_key)


if __name__ == "__main__":
    main()
