@echo off
title VeloPath GPU Worker
cd /d "%~dp0"

rem uv installs Python, CUDA PyTorch and the model runtime by itself (first run downloads ~3 GB)
where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv ^(one time^)...
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

uv run velopath_worker.py
echo.
echo The worker stopped. Read the message above, then press any key to close.
pause >nul
