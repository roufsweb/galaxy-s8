@echo off
echo =================================================================
echo   Samsung Galaxy S8 Native Ubuntu Root Shell [roufsweb]
echo =================================================================
echo.
echo [*] Entering native Ubuntu 24.04.5 LTS environment...
adb shell "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin chroot /mnt/ubuntu /bin/bash -l"

