@echo off
title VeloPath AI
echo ========================================================
echo                 VeloPath AI Launcher
echo ========================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH!
    pause
    exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
    echo [*] Creating virtual environment (venv)...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo [*] Installing/Verifying requirements...
pip install -r requirements.txt

echo [*] Verifying model weights...
python -c "import velopath.model_manager as mm; p = mm.resolve_model_path(True); dev, name = mm.get_acceleration_device(); print(f'[VeloPath AI] Model: {p}'); print(f'[VeloPath AI] Device: {name}')"

echo.
echo ========================================================
echo   Server starting on: http://localhost:8000
echo ========================================================
echo.
python -m uvicorn velopath.server:app --host 0.0.0.0 --port 8000
pause
