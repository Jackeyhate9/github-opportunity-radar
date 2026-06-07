@echo off
chcp 65001 >nul
title GitHub Opportunity Radar — Live Web UI

cd /d "%~dp0.."

if exist "venv" ( call venv\Scripts\activate.bat )

echo ========================================
echo   GitHub Opportunity Radar — Web UI
echo ========================================
echo.
echo   Scrapes github.com/trending + github.com/search
echo   No API tokens required
echo   Opens at: http://127.0.0.1:7860
echo.
echo   Ctrl+C to stop
echo.

python app.py web
pause
