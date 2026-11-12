@echo off
title S8 Imager - Universal Linux OS Flasher & Device Console
cd /d "%~dp0"
echo =====================================================================
echo   Galaxy S8 Universal OS Flasher ^& Hardware Console [roufsweb]
echo =====================================================================

if exist "%~dp0desktop-app\dist\S8_Imager.exe" (
    echo [*] Launching standalone S8_Imager.exe...
    start "" "%~dp0desktop-app\dist\S8_Imager.exe"
    exit /b 0
)

echo [*] Starting S8 Imager via Python...
python desktop-app\main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [*] Attempting fallback with py launcher...
    py desktop-app\main.py
    if %ERRORLEVEL% NEQ 0 (
        echo [!] Failed to start desktop app. Ensure Python 3.10+ is installed.
        pause
    )
)

