@echo off
echo =================================================================
echo   Samsung Galaxy S8 Ubuntu Remote Desktop Connector [roufsweb]
echo =================================================================
echo.
echo [*] Forwarding device ports over USB...
adb forward tcp:6080 tcp:6080
adb forward tcp:5901 tcp:5901
adb forward tcp:2222 tcp:22

echo [+] Port forwarding established:
echo     Web Desktop (noVNC) : http://localhost:6080/vnc.html
echo     Native TigerVNC     : localhost:5901
echo     SSH Root Terminal   : localhost:2222
echo.
echo [*] Launching browser remote desktop (Password: ubuntu)...
start http://localhost:6080/vnc.html
echo.
echo [+] Press any key to exit connector...
pause >nul

