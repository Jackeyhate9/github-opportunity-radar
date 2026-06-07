@echo off
chcp 65001 >nul
title GitHub Opportunity Radar

cd /d "%~dp0"

echo ========================================
echo   GitHub Opportunity Radar — Live
echo ========================================
echo.
echo   1. Launch Web UI (gradio)
echo   2. Run CLI scan
echo   3. Export latest report
echo   4. Install dependencies
echo   5. Exit
echo.

set /p c="Choose (1-5): "

if exist "venv" ( call venv\Scripts\activate.bat )

if "%c%"=="1" ( python app.py web
) else if "%c%"=="2" ( python app.py scan & pause
) else if "%c%"=="3" (
    echo Format: 1=CSV 2=JSON 3=MD
    set /p f=": "
    if "%f%"=="2" ( python app.py export --format json
    ) else if "%f%"=="3" ( python app.py export --format md
    ) else ( python app.py export --format csv )
    pause
) else if "%c%"=="4" ( pip install -r requirements.txt & pause
) else ( exit /b )
