#!/sbin/sh
cp /data/linux/exynos_dp_bridge.c /mnt/ubuntu/usr/local/src/exynos_dp_bridge.c

chroot /mnt/ubuntu /bin/bash -c "
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export DISPLAY=:1
killall -9 exynos_dp_bridge 2>/dev/null || true
gcc -O3 /usr/local/src/exynos_dp_bridge.c -o /usr/local/bin/exynos_dp_bridge -lX11 -lXext
chmod +x /usr/local/bin/exynos_dp_bridge
nohup /usr/local/bin/exynos_dp_bridge > /var/log/exynos_dp_bridge.log 2>&1 &
sleep 1
ps aux | grep -E '[e]xynos_dp_bridge'
cat /var/log/exynos_dp_bridge.log
"

