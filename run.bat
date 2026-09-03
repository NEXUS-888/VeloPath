@echo off
title VeloPath AI
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat

python velopath\launcher.py
