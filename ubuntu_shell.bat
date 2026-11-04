@echo off
REM ============================================================================
REM Galaxy S8 (SM-G950N) Native Ubuntu 20.04.5 LTS ARM64 Interactive Shell
REM Automatically mounts /dev/block/sda24 (/data) and /data/linux/rootfs.img,
REM binds /proc, /sys, /dev, /dev/pts, clears Android LD_LIBRARY_PATH, and
REM launches an interactive root bash session inside Ubuntu 20.04 ARM64.
REM ============================================================================

set ADB="C:\Users\rakib\AppData\Local\Android\Sdk\platform-tools\adb.exe"

echo [*] Preparing Ubuntu 20.04.5 LTS ARM64 environment on Galaxy S8...
%ADB% shell "mkdir -p /data /mnt/ubuntu; mountpoint -q /data || mount -t ext4 /dev/block/sda24 /data; if ! mountpoint -q /mnt/ubuntu; then losetup /dev/block/loop0 /data/linux/rootfs.img 2>/dev/null; mount -t ext4 /dev/block/loop0 /mnt/ubuntu || mount -o loop /data/linux/rootfs.img /mnt/ubuntu; fi; mountpoint -q /mnt/ubuntu/proc || mount -t proc proc /mnt/ubuntu/proc; mountpoint -q /mnt/ubuntu/sys || mount -t sysfs sysfs /mnt/ubuntu/sys; mountpoint -q /mnt/ubuntu/dev || mount -o bind /dev /mnt/ubuntu/dev; mountpoint -q /mnt/ubuntu/dev/pts || mount -t devpts devpts /mnt/ubuntu/dev/pts; mkdir -p /mnt/ubuntu/run /mnt/ubuntu/tmp"

if "%~1"=="" (
    echo [*] Entering interactive Ubuntu 20.04.5 LTS ARM64 root shell...
    %ADB% shell -t "env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root TERM=xterm-256color DEBIAN_FRONTEND=noninteractive chroot /mnt/ubuntu /bin/bash --login"
) else (
    %ADB% shell "env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root TERM=xterm-256color DEBIAN_FRONTEND=noninteractive chroot /mnt/ubuntu /bin/bash -c \"%*\""
)
