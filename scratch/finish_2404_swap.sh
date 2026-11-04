#!/sbin/sh
set -e
export PATH=/sbin:/system/bin:/system/xbin:/usr/bin:/bin
export TMPDIR=/tmp

echo "=== Finishing Step [6/7]: Installing tigervnc-tools & X11 dev headers in Ubuntu 24.04.5 ==="
grep -q "/mnt/ubuntu/noble/proc " /proc/mounts || mount -t proc proc /mnt/ubuntu/noble/proc
grep -q "/mnt/ubuntu/noble/sys " /proc/mounts || mount -o bind /sys /mnt/ubuntu/noble/sys
grep -q "/mnt/ubuntu/noble/dev " /proc/mounts || mount -o bind /dev /mnt/ubuntu/noble/dev
grep -q "/mnt/ubuntu/noble/dev/pts " /proc/mounts || mount -t devpts devpts /mnt/ubuntu/noble/dev/pts
grep -q "/mnt/ubuntu/noble/dev/shm " /proc/mounts || mount -t tmpfs -o size=512M tmpfs /mnt/ubuntu/noble/dev/shm
grep -q "/mnt/ubuntu/noble/run " /proc/mounts || mount -t tmpfs -o size=128M,mode=755 tmpfs /mnt/ubuntu/noble/run

mkdir -p /mnt/ubuntu/noble/root/.vnc /mnt/ubuntu/noble/etc/wpa_supplicant
cp -f /mnt/ubuntu/root/.vnc/passwd /mnt/ubuntu/noble/root/.vnc/passwd 2>/dev/null || true
chmod 600 /mnt/ubuntu/noble/root/.vnc/passwd 2>/dev/null || true
cp -f /mnt/ubuntu/etc/wpa_supplicant/wpa_supplicant.conf /mnt/ubuntu/noble/etc/wpa_supplicant/wpa_supplicant.conf 2>/dev/null || true

chroot /mnt/ubuntu/noble /bin/bash -c '
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export DEBIAN_FRONTEND=noninteractive
export TMPDIR=/tmp
apt-get install -y --no-install-recommends tigervnc-tools libx11-dev libxext-dev
echo ubuntu | vncpasswd -f > /root/.vnc/passwd
chmod 600 /root/.vnc/passwd
'

echo "=== Step [7/7]: Atomically Swapping Ubuntu 24.04.5 LTS + macOS Sonoma Desktop into /mnt/ubuntu ==="
umount /mnt/ubuntu/noble/proc 2>/dev/null || true
umount /mnt/ubuntu/noble/sys 2>/dev/null || true
umount /mnt/ubuntu/noble/dev/pts 2>/dev/null || true
umount /mnt/ubuntu/noble/dev/shm 2>/dev/null || true
umount /mnt/ubuntu/noble/dev 2>/dev/null || true
umount /mnt/ubuntu/noble/run 2>/dev/null || true

for p in Xtigervnc websockify xfce4-session xfce4-panel xfconfd dbus-daemon sshd dockerd containerd plank; do
    killall -9 $p 2>/dev/null || true
done

mkdir -p /mnt/ubuntu/.old2004
for item in /mnt/ubuntu/*; do
    base=$(basename "$item")
    case "$base" in
        noble|proc|sys|dev|run|tmp|data|.old2004|lost+found) ;;
        *) mv "$item" /mnt/ubuntu/.old2004/ 2>/dev/null || rm -rf "$item" ;;
    esac
done

for item in /mnt/ubuntu/noble/*; do
    base=$(basename "$item")
    case "$base" in
        proc|sys|dev|run|tmp|data|lost+found) ;;
        *) mv "$item" /mnt/ubuntu/ ;;
    esac
done

rm -rf /mnt/ubuntu/.old2004 /mnt/ubuntu/noble /mnt/ubuntu/tmp/.X1-lock /mnt/ubuntu/tmp/.X11-unix

# Start all services in Ubuntu 24.04.5 LTS
/sbin/sh /data/linux/start_all.sh

echo "=== Compiling exynos_dp_bridge & Installing s8ctl inside Ubuntu 24.04.5 LTS ==="
cp -f /data/linux/exynos_dp_bridge.c /mnt/ubuntu/usr/local/src/exynos_dp_bridge.c
cp -f /data/linux/s8ctl.py /mnt/ubuntu/usr/local/bin/s8ctl
chmod 755 /mnt/ubuntu/usr/local/bin/s8ctl

chroot /mnt/ubuntu /bin/bash -c '
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
gcc -O2 -DUSE_X11 /usr/local/src/exynos_dp_bridge.c -o /usr/local/bin/exynos_dp_bridge -lX11 -lXext
chmod 755 /usr/local/bin/exynos_dp_bridge
/usr/local/bin/s8ctl audio speaker || true
/usr/local/bin/s8ctl bt on || true
/usr/local/bin/s8ctl status
cat /etc/os-release | head -n 6
'

# Haptic ready notification (2 pulses)
echo 180 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
sleep 1
echo 180 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true

