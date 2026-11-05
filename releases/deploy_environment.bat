@echo off
echo =================================================================
echo   Samsung Galaxy S8 Linux Environment Deployer [roufsweb]
echo =================================================================
echo.
echo [*] Waiting for Samsung Galaxy S8 in ADB mode...
adb wait-for-device
echo [+] Device connected:
adb devices
echo.

echo [*] Creating /data/linux directory on internal UFS storage...
adb shell "mkdir -p /data/linux"

echo [*] Deploying boot supervisor and hardware scripts...
adb push ..\boot\start_all.sh /data/linux/start_all.sh
adb push ..\src\network\connect_wifi.sh /data/linux/connect_wifi.sh
adb push ..\src\control\s8ctl.py /data/linux/s8ctl.py
adb shell "chmod +x /data/linux/*.sh /data/linux/*.py"

echo.
echo [*] Checking for rootfs.img in releases directory...
if exist "rootfs.img" (
    echo [*] Pushing rootfs.img to /data/linux/rootfs.img (this may take 2-3 minutes)...
    adb push rootfs.img /data/linux/rootfs.img
) else (
    echo [!] NOTE: rootfs.img not found in releases\ directory.
    echo     If you already have rootfs.img on the phone, the system is ready.
    echo     Otherwise, place your rootfs.img in the releases\ folder and re-run.
)

echo.
echo [*] Executing master startup supervisor...
adb shell "/sbin/sh /data/linux/start_all.sh"

echo.
echo =================================================================
echo   Deployment completed! Starting desktop connection...
echo =================================================================
call connect_desktop.bat

