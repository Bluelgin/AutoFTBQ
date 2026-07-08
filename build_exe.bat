@echo off
chcp 65001 >nul
echo ================================
echo  AutoFTBQ 打包工具
echo ================================
echo.

echo 正在检测 PyInstaller...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo 未安装 PyInstaller，正在安装...
    pip install pyinstaller -q
    echo 安装完成!
)

echo.
echo 正在打包成 exe（约1-2分钟）...
pyinstaller AutoFTBQ.spec

if %errorlevel% equ 0 (
    echo.
    echo ✅ 打包成功!
    echo 输出位置: dist\AutoFTBQ\AutoFTBQ.exe
    echo.
    pause
) else (
    echo.
    echo ❌ 打包失败，请检查错误信息
    pause
)
