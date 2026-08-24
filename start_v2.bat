@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements-v2.txt
if errorlevel 1 goto :error
python v2_main.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo AutoFTBQ v2 failed to start. Review the message above.
pause
exit /b 1
