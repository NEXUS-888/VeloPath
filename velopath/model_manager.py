"""
VeloPath AI - Model Manager
Handles automatic model weights discovery, downloading, caching,
and seamless GPU (CUDA / MPS / CPU) device selection across platforms.
"""

import os
import sys
import urllib.request
from typing import Optional, Tuple

# Official BallDataLab / BaseballCV hosting endpoint for ball_trackingv4 (YOLOv11)
DEFAULT_WEIGHTS_URL = "https://data.balldatalab.com/index.php/s/YkGBwbFtsf34ky3/download/ball_tracking_v4-YOLOv11.pt"
MODEL_FILENAME = "ball_trackingv4.pt"


def get_project_root() -> str:
    """Returns absolute path to the project root directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_default_model_paths() -> list:
    """Returns prioritized list of candidate paths for ball_trackingv4.pt."""
    root = get_project_root()
    return [
        os.path.join(root, "models", MODEL_FILENAME),
        os.path.join(
            root, "BaseballCV", "models", "od", "YOLO", 
            "ball_tracking", "model_weights", MODEL_FILENAME
        ),
        os.path.join(os.path.expanduser("~"), ".cache", "velopath", MODEL_FILENAME),
    ]


def download_model_weights(target_path: str, url: str = DEFAULT_WEIGHTS_URL) -> str:
    """
    Downloads model weights with a clean progress bar.
    """
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    temp_target = target_path + ".downloading"
    
    print(f"\n[VeloPath AI] Model weights not found on this machine.")
    print(f"[VeloPath AI] Downloading {MODEL_FILENAME} (114 MB) from official repository...")
    print(f"[VeloPath AI] Source: {url}")
    print(f"[VeloPath AI] Destination: {target_path}")

    def reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100.0, (downloaded / float(total_size)) * 100.0)
            mb_down = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            bar_len = 30
            filled = int(bar_len * percent / 100.0)
            bar = "=" * filled + "-" * (bar_len - filled)
            sys.stdout.write(f"\r[{bar}] {percent:5.1f}% ({mb_down:5.1f} / {mb_total:5.1f} MB)")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, temp_target, reporthook=reporthook)
        print()
        if os.path.exists(temp_target) and os.path.getsize(temp_target) > 10 * 1024 * 1024:
            if os.path.exists(target_path):
                os.remove(target_path)
            os.rename(temp_target, target_path)
            print(f"[VeloPath AI] Model downloaded and verified successfully!\n")
            return target_path
        else:
            raise RuntimeError("Downloaded file is empty or too small.")
    except Exception as e:
        if os.path.exists(temp_target):
            os.remove(temp_target)
        raise RuntimeError(
            f"Failed to automatically download {MODEL_FILENAME}: {e}\n"
            f"You can manually download it from: {url}\n"
            f"and place it at: {target_path}"
        )


def reassemble_from_parts(target_path: str) -> Optional[str]:
    """
    Checks if repository split parts exist (models/weights_parts/ball_trackingv4.pt.part*)
    and combines them into a complete model file in milliseconds without network access.
    """
    root = get_project_root()
    part1 = os.path.join(root, "models", "weights_parts", "ball_trackingv4.pt.part1")
    part2 = os.path.join(root, "models", "weights_parts", "ball_trackingv4.pt.part2")
    
    if os.path.exists(part1) and os.path.exists(part2):
        print(f"[VeloPath AI] Reassembling model weights from repository packages...")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        temp_path = target_path + ".assembling"
        with open(temp_path, "wb") as f_out:
            with open(part1, "rb") as f1:
                f_out.write(f1.read())
            with open(part2, "rb") as f2:
                f_out.write(f2.read())
        if os.path.exists(target_path):
            os.remove(target_path)
        os.rename(temp_path, target_path)
        print(f"[VeloPath AI] Successfully assembled {os.path.basename(target_path)} ({os.path.getsize(target_path)/1024/1024:.1f} MB)!\n")
        return target_path
    return None


def resolve_model_path(auto_download: bool = True) -> Optional[str]:
    """
    Finds the model weights on disk, reassembles from repo parts, or downloads them.
    """
    candidates = get_default_model_paths()
    for path in candidates:
        if os.path.exists(path) and os.path.getsize(path) > 10 * 1024 * 1024:
            return os.path.abspath(path)

    # Reassemble from repo parts (instant, zero internet needed)
    target_path = candidates[0]  # models/ball_trackingv4.pt
    assembled = reassemble_from_parts(target_path)
    if assembled and os.path.exists(assembled):
        return os.path.abspath(assembled)

    if auto_download:
        try:
            return download_model_weights(target_path)
        except Exception as e:
            print(f"[VeloPath AI] Warning: {e}")
            return None
    return None


def get_acceleration_device() -> Tuple[str, str]:
    """
    Detects best available compute device across platforms (CUDA / MPS / CPU).
    Returns: (device_str, display_name)
    """
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            return ("0", f"NVIDIA GPU CUDA ({device_name})")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return ("mps", "Apple Silicon MPS GPU")
    except Exception:
        pass
    return ("cpu", "CPU (Corridor ROI Optimized)")
