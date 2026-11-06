@echo off
title Galaxy S8 (SM-G950N) 1-Click OS Flasher
cd /d "%~dp0"
echo =====================================================================
echo    SAMSUNG GALAXY S8 (SM-G950N) 1-CLICK AUTONOMOUS OS FLASHER
echo =====================================================================
echo.
python s8_flasher.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Flashing encountered an issue. See details above.
    pause
    exit /b 1
)
echo.
echo Press any key to exit...
pause >nul

