@echo off
chcp 65001 >nul
title GitHub Opportunity Radar

cd /d "%~dp0"

if exist "venv" ( call venv\Scripts\activate.bat 2>nul )

:menu
cls
echo ========================================
echo   GitHub Opportunity Radar
echo ========================================
echo.
echo   [1] 启动 Web UI (gradio)
echo   [2] 扫描仓库
echo   [3] 导出报告
echo   [4] 趋势预测演示 (Baseline)
echo   [5] 趋势预测演示 (TimesFM — 需先 ENABLE_TIMESFM=true)
echo   [6] 一键安装依赖
echo   [0] 退出
echo.
set /p c="请选择 (0-6): "

if "%c%"=="1" goto web
if "%c%"=="2" goto scan
if "%c%"=="3" goto export
if "%c%"=="4" goto demo_baseline
if "%c%"=="5" goto demo_timesfm
if "%c%"=="6" goto install
if "%c%"=="0" exit /b
goto menu

:web
cls
echo 启动 Web UI...
python app.py web
pause
goto menu

:scan
cls
echo 开始扫描仓库...
python app.py scan
pause
goto menu

:export
cls
echo 格式: 1=CSV  2=JSON  3=MD
set /p f=": "
if "%f%"=="2" python app.py export --format json
if "%f%"=="3" python app.py export --format md
if "%f%"=="1" python app.py export --format csv
pause
goto menu

:demo_baseline
cls
echo ======== Baseline 趋势预测演示 ========
echo.
python app.py forecast demo --horizon 30
pause
goto menu

:demo_timesfm
cls
setlocal
set "ENABLE_TIMESFM=true"
echo ======== TimesFM 趋势预测演示 ========
echo.
echo 注意: 首次运行会从 HuggingFace Hub 下载模型 (~500MB)
echo 需要稳定的网络连接。如果下载失败会自动降级到 Baseline。
echo.
pause
python app.py forecast demo --horizon 30
endlocal
pause
goto menu

:install
cls
echo 安装依赖...
pip install -r requirements.txt
echo.
echo 如需 TimesFM 预测: 安装后设置 ENABLE_TIMESFM=true 再选 [5]
pause
goto menu
