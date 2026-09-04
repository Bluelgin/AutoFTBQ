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
    echo ================================================
    echo   关于 Windows 安全中心误报:
    echo ================================================
    echo  - 已默认禁用 UPX 压缩并写入版本信息，以降低误报概率。
    echo  - 若仍被 Defender 拦截，可运行仓库里的:
    echo      add_defender_exclusion.bat
    echo    把它复制到 exe 旁边双击，即可自动加入白名单。
    echo  - 首次运行时若出现 SmartScreen 提示，
    echo    点“更多信息” -^> “仍要运行”即可。
    echo.
    pause
) else (
    echo.
    echo ❌ 打包失败，请检查错误信息
    pause
)
