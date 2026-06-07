@echo off
chcp 65001 >nul
title GitHub Opportunity Radar — Scan

cd /d "%~dp0.."

if exist "venv" ( call venv\Scripts\activate.bat )

echo ========================================
echo   GitHub Opportunity Radar — Scan
echo ========================================
echo.
echo   Scrapes github.com/trending + github.com/search
echo   No API tokens required
echo.
echo   To clear cache: python app.py scan --clear-cache
echo.

python app.py scan
if %errorlevel% neq 0 (
    echo.
    echo   Scan failed. Check internet connection or try again later.
    pause
    exit /b 1
)

echo.
echo   Done! Results saved to outputs/ and cached in data/radar.sqlite
pause
