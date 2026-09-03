@echo off
title VeloPath AI - GPU Launcher
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat

python velopath\launcher.py --gpu
