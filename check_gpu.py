"""
VeloPath AI - GPU Diagnostic Check
Verifies NVIDIA GPU hardware, drivers, PyTorch CUDA installation, and device detection.
"""
import sys
import os
import subprocess

def main():
    print("=" * 60)
    print("         VeloPath AI - GPU Acceleration Diagnostics")
    print("=" * 60 + "\n")

    # 1. Hardware Detection
    print("[1/3] Detecting NVIDIA GPU hardware...")
    nvidia_hw = False
    smi_out = ""
    for p in ["nvidia-smi", r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"]:
        try:
            smi_out = subprocess.check_output([p], text=True, stderr=subprocess.DEVNULL)
            nvidia_hw = True
            break
        except Exception:
            pass

    if not nvidia_hw:
        try:
            ps_cmd = 'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'
            out = subprocess.check_output(['powershell', '-NoProfile', '-Command', ps_cmd], text=True, stderr=subprocess.DEVNULL)
            if 'nvidia' in out.lower():
                nvidia_hw = True
                smi_out = out.strip()
        except Exception:
            pass

    if nvidia_hw:
        print("  -> NVIDIA GPU hardware: DETECTED")
    else:
        print("  -> NVIDIA GPU hardware: NOT DETECTED (System appears to be CPU/Intel only)")

    # 2. PyTorch & CUDA Detection
    print("\n[2/3] Checking PyTorch and CUDA runtime...")
    try:
        import torch
        print(f"  -> PyTorch version: {torch.__version__}")
        cuda_available = torch.cuda.is_available()
        print(f"  -> CUDA available in PyTorch: {cuda_available}")
        if cuda_available:
            cnt = torch.cuda.device_count()
            name = torch.cuda.get_device_name(0)
            capability = torch.cuda.get_device_capability(0)
            cuda_ver = torch.version.cuda
            print(f"  -> GPU count: {cnt}")
            print(f"  -> Active GPU: {name}")
            print(f"  -> Compute Capability: {capability[0]}.{capability[1]}")
            print(f"  -> CUDA Build Version: {cuda_ver}")
        else:
            print("  -> PyTorch was installed without CUDA, or NVIDIA driver is not responding.")
    except ImportError:
        print("  -> PyTorch is NOT installed in this Python environment.")
        cuda_available = False

    # 3. Model Manager Device Resolution
    print("\n[3/3] Checking VeloPath compute device selection...")
    try:
        from velopath.model_manager import get_acceleration_device
        dev_id, dev_name = get_acceleration_device()
        print(f"  -> VeloPath Device: {dev_name} (id: {dev_id})")
    except Exception as e:
        print(f"  -> Could not resolve device: {e}")

    # Summary & Actionable Advice
    print("\n" + "=" * 60)
    if cuda_available:
        print(" [SUCCESS] NVIDIA GPU Acceleration is FULLY ACTIVE and ready!")
        print(" VeloPath will track pitches at maximum speed using CUDA.")
    elif nvidia_hw:
        print(" [ACTION NEEDED] NVIDIA hardware is present, but CUDA is not active.")
        print(" How to fix:")
        print("  1. Update NVIDIA GPU drivers: https://www.nvidia.com/drivers")
        print("  2. Run 'gpu.bat' which automatically installs PyTorch with CUDA 12.1.")
        print("  3. Make sure the laptop is plugged into the wall charger.")
    else:
        print(" [INFO] No NVIDIA GPU hardware detected on this machine.")
        print(" VeloPath will run in Corridor-Optimized CPU mode via 'run.bat'.")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
