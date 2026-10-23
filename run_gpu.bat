@echo off
title VeloPath AI - GPU Launcher
cd /d "%~dp0"

:: 1. Locate compatible Python executable for PyTorch CUDA (requires Python 3.10, 3.11, or 3.12)
set "PY_CMD="

:: Check for Python 3.11, 3.12, 3.10 via Windows 'py' launcher first (best CUDA support)
py -3.11 --version >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=py -3.11"
    goto :found_py
)
py -3.12 --version >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=py -3.12"
    goto :found_py
)
py -3.10 --version >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=py -3.10"
    goto :found_py
)

:: Otherwise check default python or py
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    goto :found_py
)
where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=py"
    goto :found_py
)

:found_py
if "%PY_CMD%"=="" (
    echo.
    echo ========================================================
    echo  [ERROR] Python was not found on your system PATH!
    echo ========================================================
    echo  Please install Python 3.11 or 3.12 from:
    echo  https://www.python.org/downloads/release/python-3119/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Auto-create virtual environment if missing
if not exist "venv\Scripts\activate.bat" (
    echo [*] Setting up virtual environment venv using %PY_CMD%...
    %PY_CMD% -m venv venv
)

:: 3. Activate venv
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat

:: 4. Check for Python 3.13+ incompatibility with PyTorch CUDA
set "PY_TOO_NEW=0"
python -c "import sys; exit(1 if sys.version_info >= (3, 13) else 0)" >nul 2>nul
if errorlevel 1 set "PY_TOO_NEW=1"

if "%PY_TOO_NEW%"=="1" (
    echo.
    echo ========================================================
    echo  [NOTICE] Python 3.13+ detected!
    echo ========================================================
    echo  Official PyTorch CUDA does not support Python 3.13 or 3.14 yet.
    echo  To enable full NVIDIA GPU acceleration, install Python 3.11:
    echo  https://www.python.org/downloads/release/python-3119/
    echo.
    echo  The server will run in CPU mode for now.
    echo ========================================================
    echo.
    timeout /t 3 >nul
)

:: 5. Verify / Install CUDA PyTorch and Dependencies
echo.
echo ========================================================
echo  Checking NVIDIA GPU and CUDA PyTorch Acceleration...
echo ========================================================
python -c "import torch; assert torch.cuda.is_available()" >nul 2>nul
if errorlevel 1 (
    if "%PY_TOO_NEW%"=="0" (
        echo [*] CUDA PyTorch is not active in this environment.
        echo [*] Installing/Updating PyTorch with CUDA 12.1 acceleration...
        echo [*] Note: First-time download is ~2.5 GB. Please keep this window open...
        python -m pip install --upgrade torch torchvision --index-url https://download.pytorch.org/whl/cu121
    )
    echo [*] Verifying application dependencies...
    python -m pip install -r requirements.txt
)

:: 6. Diagnostic Check
echo [*] Testing GPU Acceleration:
python -c "import torch; ok = torch.cuda.is_available(); name = torch.cuda.get_device_name(0) if ok else 'NONE'; print(f'    CUDA Active:     {ok}'); print(f'    Device Name:     {name}'); print(f'    PyTorch Version: {torch.__version__}'); exit(0 if ok else 1)"
if errorlevel 1 (
    echo.
    echo --------------------------------------------------------
    echo  [NOTICE] PyTorch is running on CPU.
    if "%PY_TOO_NEW%"=="1" (
        echo  Reason: Python 3.13/3.14 does not support CUDA PyTorch.
        echo  Solution: Install Python 3.11 or 3.12 from python.org
    ) else (
        echo  If this laptop has an NVIDIA GPU:
        echo   1. Update your NVIDIA GPU driver: https://www.nvidia.com/drivers
        echo   2. Plug in the laptop power charger (battery mode limits GPU)
    )
    echo  The app will proceed in CPU mode.
    echo --------------------------------------------------------
    echo.
    timeout /t 4 >nul
) else (
    echo.
    echo [OK] NVIDIA GPU Acceleration is ACTIVE!
    echo.
)

:: 7. Launch VeloPath AI with GPU flag
python velopath\launcher.py --gpu
if errorlevel 1 (
    echo.
    echo [!] Server stopped with an error.
    pause
)
