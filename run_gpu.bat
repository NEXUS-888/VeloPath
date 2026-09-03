@echo off
title VeloPath AI - GPU Launcher
echo ========================================================
echo        VeloPath AI - High Performance GPU Launcher
echo ========================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.10+ from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

:: 2. Create virtual environment if not present
if not exist "venv\Scripts\activate.bat" (
    echo [*] Creating virtual environment (venv)...
    python -m venv venv
)

call venv\Scripts\activate.bat

:: 3. Check & Install PyTorch with CUDA support
echo [*] Checking PyTorch CUDA acceleration...
python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing PyTorch with NVIDIA CUDA 12.1 acceleration...
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
)

:: 4. Install remaining dependencies
echo [*] Checking dependencies...
pip install -r requirements.txt

:: 5. Auto-resolve & verify model weights
echo [*] Verifying model weights...
python -c "import velopath.model_manager as mm; p = mm.resolve_model_path(True); dev, name = mm.get_acceleration_device(); print(f'[VeloPath AI] Model: {p}'); print(f'[VeloPath AI] Acceleration: {name}')"

:: 6. Launch Server
echo.
echo ========================================================
echo   Server starting on: http://localhost:8000
echo   Network access:     http://0.0.0.0:8000
echo ========================================================
echo.
python -m uvicorn velopath.server:app --host 0.0.0.0 --port 8000
pause
