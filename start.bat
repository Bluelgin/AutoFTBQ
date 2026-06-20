@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ============================================
echo   MCFTPSMER - MC FTB Quest Book Generator
echo ============================================
echo.
echo 正在启动应用...
echo.
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [错误] 启动失败！请检查 Python 和 tkinter 是否已安装。
    echo.
    pause
)