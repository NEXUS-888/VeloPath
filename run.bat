@echo off
title VeloPath AI
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

:: 2. Auto-create virtual environment if missing (shares system packages for instant startup)
if not exist "venv\Scripts\activate.bat" (
    echo [*] Setting up virtual environment venv...
    %PY_CMD% -m venv --system-site-packages venv
)

:: 3. Activate venv
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat

:: 4. Launch VeloPath AI application
python velopath\launcher.py
if errorlevel 1 (
    echo.
    echo [!] Server stopped with an error.
    pause
)
