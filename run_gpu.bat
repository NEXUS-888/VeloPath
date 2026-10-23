@echo off
title VeloPath AI - GPU Launcher
cd /d "%~dp0"

:: 1. Locate Python executable (python or py launcher)
set "PY_CMD="
where python >nul 2>nul
if %errorlevel% equ 0 set "PY_CMD=python"
if "%PY_CMD%"=="" (
    where py >nul 2>nul
    if %errorlevel% equ 0 set "PY_CMD=py"
)

if "%PY_CMD%"=="" (
    echo.
    echo ========================================================
    echo  [ERROR] Python was not found on your system PATH!
    echo ========================================================
    echo  Please install Python 3.10+ from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Auto-create virtual environment if missing
if not exist "venv\Scripts\activate.bat" (
    echo [*] Setting up virtual environment venv...
    %PY_CMD% -m venv venv
)

:: 3. Activate venv
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat

:: 4. Verify / Install CUDA PyTorch and Dependencies
echo.
echo ========================================================
echo  Checking NVIDIA GPU and CUDA PyTorch Acceleration...
echo ========================================================
python -c "import torch; assert torch.cuda.is_available()" >nul 2>nul
if errorlevel 1 (
    echo [*] CUDA PyTorch is not active in this environment.
    echo [*] Installing/Updating PyTorch with CUDA 12.1 acceleration...
    echo [*] Note: First-time download is ~2.5 GB. Please keep this window open...
    python -m pip install --upgrade torch torchvision --index-url https://download.pytorch.org/whl/cu121
    echo [*] Verifying application dependencies...
    python -m pip install -r requirements.txt
)

:: 5. Diagnostic Check
echo [*] Testing GPU Acceleration:
python -c "import torch; ok = torch.cuda.is_available(); name = torch.cuda.get_device_name(0) if ok else 'NONE'; print(f'    CUDA Active:     {ok}'); print(f'    Device Name:     {name}'); print(f'    PyTorch Version: {torch.__version__}'); exit(0 if ok else 1)"
if errorlevel 1 (
    echo.
    echo --------------------------------------------------------
    echo  [NOTICE] PyTorch is running on CPU because CUDA was not detected.
    echo  If this laptop has an NVIDIA GPU:
    echo   1. Update your NVIDIA GPU driver: https://www.nvidia.com/drivers
    echo   2. Plug in the laptop power charger (battery mode limits GPU)
    echo  The app will proceed in CPU mode.
    echo --------------------------------------------------------
    echo.
    timeout /t 5 >nul
) else (
    echo.
    echo [OK] NVIDIA GPU Acceleration is ACTIVE!
    echo.
)

:: 6. Launch VeloPath AI with GPU flag
python velopath\launcher.py --gpu
if errorlevel 1 (
    echo.
    echo [!] Server stopped with an error.
    pause
)
