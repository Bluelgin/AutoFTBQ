@echo off
chcp 65001 >nul
title AutoFTBQ 安装程序

echo.
echo ╔══════════════════════════════════════════╗
echo ║     AutoFTBQ - MC FTB任务书生成器       ║
echo ║           自动安装程序 v1.0              ║
echo ╚══════════════════════════════════════════╝
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 建议以管理员身份运行以获得最佳体验
    echo.
)

:: 检查Python
echo [1/3] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python，正在尝试安装...
    echo.
    echo 请访问 https://www.python.org/downloads/ 下载Python 3.10+
    echo 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo       已检测到 Python %%v

:: 安装requests依赖（exe已包含，但保留源码运行支持）
echo [2/3] 安装依赖库...
python -m pip install requests --quiet 2>nul
if %errorlevel% neq 0 (
    echo [提示] pip安装可能失败，exe版本无需此依赖
)

:: 复制文件到安装目录
echo [3/3] 安装 AutoFTBQ...
set "INSTALL_DIR=%USERPROFILE%\AutoFTBQ"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: 检查是否有exe
if exist "%~dp0dist\AutoFTBQ.exe" (
    copy /y "%~dp0dist\AutoFTBQ.exe" "%INSTALL_DIR%\AutoFTBQ.exe" >nul
    echo       AutoFTBQ.exe → %INSTALL_DIR%
) else (
    echo       [提示] 未找到预编译exe，将使用源码运行
)

:: 复制源码
xcopy /y /q "%~dp0source\*.py" "%INSTALL_DIR%\source\" >nul 2>&1
echo       源码文件 → %INSTALL_DIR%\source\

:: 创建桌面快捷方式
set "DESKTOP=%USERPROFILE%\Desktop"
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\AutoFTBQ"

if not exist "%STARTMENU%" mkdir "%STARTMENU%"

:: 创建快捷方式（使用VBS）
set "VBS=%TEMP%\create_shortcut.vbs"
echo Set WshShell = WScript.CreateObject("WScript.Shell") > "%VBS%"
if exist "%INSTALL_DIR%\AutoFTBQ.exe" (
    echo Set Shortcut = WshShell.CreateShortcut("%DESKTOP%\AutoFTBQ.lnk") >> "%VBS%"
    echo Shortcut.TargetPath = "%INSTALL_DIR%\AutoFTBQ.exe" >> "%VBS%"
    echo Shortcut.WorkingDirectory = "%INSTALL_DIR%" >> "%VBS%"
    echo Shortcut.Save >> "%VBS%"
    echo Set Shortcut2 = WshShell.CreateShortcut("%STARTMENU%\AutoFTBQ.lnk") >> "%VBS%"
    echo Shortcut2.TargetPath = "%INSTALL_DIR%\AutoFTBQ.exe" >> "%VBS%"
    echo Shortcut2.WorkingDirectory = "%INSTALL_DIR%" >> "%VBS%"
    echo Shortcut2.Save >> "%VBS%"
) else (
    echo Set Shortcut = WshShell.CreateShortcut("%DESKTOP%\AutoFTBQ.lnk") >> "%VBS%"
    echo Shortcut.TargetPath = "pythonw.exe" >> "%VBS%"
    echo Shortcut.Arguments = "%INSTALL_DIR%\source\main.py" >> "%VBS%"
    echo Shortcut.WorkingDirectory = "%INSTALL_DIR%\source" >> "%VBS%"
    echo Shortcut.Save >> "%VBS%"
    echo Set Shortcut2 = WshShell.CreateShortcut("%STARTMENU%\AutoFTBQ.lnk") >> "%VBS%"
    echo Shortcut2.TargetPath = "pythonw.exe" >> "%VBS%"
    echo Shortcut2.Arguments = "%INSTALL_DIR%\source\main.py" >> "%VBS%"
    echo Shortcut2.WorkingDirectory = "%INSTALL_DIR%\source" >> "%VBS%"
    echo Shortcut2.Save >> "%VBS%"
)
cscript //nologo "%VBS%" >nul 2>&1
del "%VBS%" >nul

echo.
echo ╔══════════════════════════════════════════╗
echo ║  ✓ 安装完成！                           ║
echo ║  桌面已创建快捷方式                      ║
echo ║  开始菜单 → AutoFTBQ                    ║
echo ║                                         ║
echo ║  安装位置: %INSTALL_DIR%                ║
echo ╚══════════════════════════════════════════╝
echo.

:: 询问是否立即运行
set /p RUN="是否立即运行 AutoFTBQ？(Y/N): "
if /i "%RUN%"=="Y" (
    if exist "%INSTALL_DIR%\AutoFTBQ.exe" (
        start "" "%INSTALL_DIR%\AutoFTBQ.exe"
    ) else (
        start "" pythonw "%INSTALL_DIR%\source\main.py"
    )
)

pause