#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
export TERM=linux

mount -t proc proc /proc 2>/dev/null
mount -t sysfs sys /sys 2>/dev/null
mount -t devtmpfs devtmpfs /dev 2>/dev/null
mkdir -p /dev/pts /dev/shm /run
mount -t devpts devpts /dev/pts 2>/dev/null
mount -t tmpfs tmpfs /dev/shm 2>/dev/null
mount -t tmpfs tmpfs /run 2>/dev/null

echo "==================================================="
echo "  Samsung Galaxy S8 Exynos 8895 Native Linux OS    "
echo "  Running Ubuntu 20.04 LTS AArch64 Bare Metal      "
echo "==================================================="

# Start USB Serial Console if ttyGS0 exists
if [ -c /dev/ttyGS0 ]; then
    echo "Starting root console on /dev/ttyGS0 (USB Serial)..."
    (
        while true; do
            /bin/bash --login < /dev/ttyGS0 > /dev/ttyGS0 2>&1
            sleep 1
        done
    ) &
fi

# Primary Console (HDMI / DisplayPort framebuffer console)
while true; do
    /bin/bash --login < /dev/console > /dev/console 2>&1
    sleep 1
done

