@echo off
chcp 65001 >nul
title AutoFTBQ - 解除 Microsoft Defender 误报
echo.
echo ================================================
echo    AutoFTBQ - 解除 Windows 安全中心误报
echo ================================================
echo.
echo 用途：把 AutoFTBQ（exe 及其所在文件夹）加入
echo       Windows 安全中心的白名单，避免被打包后的
echo       exe 误报为病毒并删除。
echo.

REM ---- 1. 请求管理员权限（如果当前不是管理员）----
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 需要管理员权限，正在请求提权...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%~1' -Verb RunAs -WorkingDirectory '%~dp0'"
    exit /b
)

set "SCRIPT_DIR=%~dp0"
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%SCRIPT_DIR%"

echo 目标路径: %TARGET%
echo 正在添加 Windows 安全中心排除项...
echo.

powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Add-MpPreference -ExclusionPath '%TARGET%' -Force; Write-Host '[OK] 已添加排除项: %TARGET%'"

if %errorlevel% equ 0 (
    echo.
    echo ================================================
    echo   ✅ 添加成功！
    echo ================================================
    echo.
    echo  已加入排除列表:
    echo    %TARGET%
    echo.
    echo  后续说明：
    echo   - 若 exe 已被 Defender 删除，请重新下载/解压到该目录。
    echo   - 若仍提示，可手动确认：
    echo       设置 → 隐私和安全性 → Windows 安全中心
    echo       → 病毒和威胁防护 → 管理设置 → 排除项
    echo   - SmartScreen 首次运行提示时，点“更多信息 → 仍要运行”。
    echo   - 本项目为 GPL-3.0 开源，源码在 GitHub 可查，
    echo     若仍被误报，欢迎在 Releases 页面反馈。
) else (
    echo.
    echo   ❌ 添加失败。请以管理员身份重新运行本脚本，
    echo      或在 Windows 安全中心中手动添加排除项。
)
echo.
pause
