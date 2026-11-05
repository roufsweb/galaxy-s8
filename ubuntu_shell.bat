@echo off
REM ============================================================================
REM Galaxy S8 Native Ubuntu 24.04.5 LTS ARM64 Interactive Shell [roufsweb]
REM ============================================================================

where adb >nul 2>nul
if %errorlevel% neq 0 (
    set ADB="C:\Users\rakib\AppData\Local\Android\Sdk\platform-tools\adb.exe"
) else (
    set ADB=adb
)

echo [*] Ensuring Ubuntu 24.04.5 LTS ARM64 rootfs is mounted...
%ADB% shell "mkdir -p /mnt/ubuntu; if ! mountpoint -q /mnt/ubuntu; then mount -t ext4 /dev/block/loop0 /mnt/ubuntu 2>/dev/null || mount -o loop /data/linux/rootfs.img /mnt/ubuntu 2>/dev/null; fi"

if "%~1"=="" (
    echo [*] Entering interactive Ubuntu 24.04.5 LTS ARM64 root shell...
    %ADB% shell -t "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin TERM=xterm-256color chroot /mnt/ubuntu /bin/bash --login"
) else (
    %ADB% shell "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin chroot /mnt/ubuntu /bin/bash -c \"%*\""
)
