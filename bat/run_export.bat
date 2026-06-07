@echo off
chcp 65001 >nul
title GitHub 创业机会雷达 - 导出

cd /d "%~dp0.."

echo ========================================
echo   GitHub 创业机会雷达 - 导出报告
echo ========================================
echo.

if exist "venv" (
    call venv\Scripts\activate.bat
)

echo 选择导出格式:
echo   1. CSV
echo   2. JSON
echo   3. Markdown
echo.

set /p fmt="请输入数字 (1/2/3, 默认 1): "

if "%fmt%"=="2" (
    python app.py export --format json
) else if "%fmt%"=="3" (
    python app.py export --format md
) else (
    python app.py export --format csv
)

if %errorlevel% neq 0 (
    echo 导出失败，请先运行扫描
    pause
    exit /b 1
)

echo.
echo 导出完成! 文件保存在 outputs/ 目录
pause
