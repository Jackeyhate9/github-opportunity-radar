@echo off
chcp 65001 >nul
title GitHub Opportunity Radar — Install

echo ========================================
echo   GitHub Opportunity Radar — Install
echo ========================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.11+ first.
    pause
    exit /b 1
)
python --version

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo ========================================
echo   Install complete!
echo.
echo   run_webui.bat     — Launch web interface
echo   run_scan.bat      — CLI scan
echo ========================================
pause
