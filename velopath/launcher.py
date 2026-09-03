"""
VeloPath AI - Cross-Platform Application Launcher
Handles dependency checks, GPU CUDA acceleration setup, model weights verification,
and server startup cleanly without shell/batch script parser limitations.
"""

import sys
import os
import subprocess
import argparse

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

def get_local_ip() -> str:
    """Finds machine local IPv4 address."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def has_nvidia_hardware() -> bool:
    """Detects whether an NVIDIA GPU is physically present on this computer."""
    try:
        subprocess.check_call(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        pass
    try:
        # PowerShell video controller check
        ps_cmd = 'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'
        out = subprocess.check_output(['powershell', '-Command', ps_cmd], text=True, stderr=subprocess.DEVNULL)
        return 'nvidia' in out.lower()
    except Exception:
        pass
    return False

def check_and_install_gpu_torch():
    """Ensures PyTorch with CUDA support is installed for NVIDIA GPUs."""
    try:
        import torch
        if torch.cuda.is_available():
            print(f"[VeloPath AI] Active CUDA GPU detected: {torch.cuda.get_device_name(0)}")
            return
    except ImportError:
        pass

    if not has_nvidia_hardware():
        print("[VeloPath AI] No NVIDIA GPU hardware detected on this machine. Running in optimized CPU mode.")
        return

    print("\n" + "=" * 60)
    print(" NVIDIA GPU hardware found! Installing PyTorch with CUDA 12.1...")
    print(" This enables 10-15x faster ball tracking on your GPU!")
    print("=" * 60 + "\n")

    cmd = [
        sys.executable, "-m", "pip", "install",
        "torch", "torchvision",
        "--index-url", "https://download.pytorch.org/whl/cu121"
    ]
    try:
        subprocess.check_call(cmd)
    except Exception as e:
        print(f"[VeloPath AI] Note: Could not auto-install CUDA PyTorch: {e}")

def check_requirements():
    """Installs required packages if missing."""
    req_file = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
    if os.path.exists(req_file):
        try:
            import fastapi
            import uvicorn
            import cv2
            import ultralytics
        except ImportError:
            print("[VeloPath AI] Installing dependencies from requirements.txt...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])

def check_and_free_port(port: int) -> int:
    """
    Checks if target port is occupied.
    If occupied by an existing process, attempts to release it or selects the next free port.
    """
    import socket
    def in_use(p):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', p)) == 0

    if not in_use(port):
        return port

    print(f"\n[VeloPath AI] Port {port} is already in use by another process.")

    # Check if existing process is already VeloPath
    try:
        import urllib.request, json
        req = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
        data = json.loads(req.read().decode())
        if data.get("app") == "VeloPath AI":
            print(f"[*] An existing VeloPath server is ALREADY active on http://localhost:{port}!")
    except Exception:
        pass

    # Try to terminate previous instance holding port on Windows
    try:
        cmd = f"netstat -ano | findstr LISTENING | findstr :{port}"
        lines = subprocess.check_output(cmd, shell=True, text=True).strip().splitlines()
        for line in lines:
            parts = line.split()
            if len(parts) >= 5:
                pid = int(parts[-1])
                if pid != os.getpid():
                    print(f"[*] Releasing port {port} (stopping previous instance PID {pid})...")
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    import time
                    time.sleep(1)
    except Exception:
        pass

    if not in_use(port):
        print(f"[*] Port {port} is now free!")
        return port

    # If still in use, automatically pick next available port (e.g. 8001, 8002)
    for next_p in range(port + 1, port + 20):
        if not in_use(next_p):
            print(f"[*] Redirecting server to free port {next_p}...")
            return next_p

    return port

def main():
    parser = argparse.ArgumentParser(description="VeloPath AI Launcher")
    parser.add_argument("--gpu", action="store_true", help="Ensure NVIDIA CUDA GPU acceleration is enabled")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("         VeloPath AI - Pitch Tracking & Strike Zone")
    print("=" * 60 + "\n")

    # 1. Port Availability Check & Auto-Release
    active_port = check_and_free_port(args.port)

    # 2. GPU Check
    if args.gpu:
        check_and_install_gpu_torch()

    # 3. Dependencies
    check_requirements()

    # 4. Model Weights Resolution
    from velopath.model_manager import resolve_model_path, get_acceleration_device
    model_path = resolve_model_path(auto_download=True)
    device_id, device_name = get_acceleration_device()

    print(f"[*] Model Weights:       {model_path}")
    print(f"[*] Compute Device:      {device_name}")
    
    local_ip = get_local_ip()
    print("\n" + "-" * 60)
    print(f"  Web Interface (Local):   http://localhost:{active_port}")
    print(f"  Web Interface (Network): http://{local_ip}:{active_port}")
    print("-" * 60 + "\n")

    # 5. Start Server
    import uvicorn
    try:
        uvicorn.run("velopath.server:app", host=args.host, port=active_port, reload=False)
    except Exception as e:
        print(f"\n[VeloPath AI Error] Server terminated: {e}")

if __name__ == "__main__":
    main()
