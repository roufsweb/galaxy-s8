@echo off
echo =================================================================
echo   Samsung Galaxy S8 Ubuntu Remote Desktop Connector [roufsweb]
echo =================================================================
echo.
echo [*] Forwarding device ports over USB...
adb forward tcp:6080 tcp:6080
adb forward tcp:5901 tcp:5901
adb forward tcp:8123 tcp:8123
adb forward tcp:2222 tcp:22

echo [+] Port forwarding established:
echo     Native TigerVNC     : localhost:5901 (Password: ubuntu)
echo     Web Desktop (noVNC) : http://localhost:6080/vnc.html
echo     Home Assistant Web  : http://localhost:8123
echo     SSH Root Terminal   : localhost:2222 (Password: password)
echo.

if exist "%~dp0vncviewer.exe" (
    echo [*] Launching Native TigerVNC Viewer...
    start "" "%~dp0vncviewer.exe" localhost:5901
) else (
    echo [*] Launching Browser Remote Desktop (noVNC)...
    start http://localhost:6080/vnc.html
)
echo.
echo [+] Desktop session active. Press any key to close this window...
pause >nul
