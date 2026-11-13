#!/bin/sh
# Portable modular installer for Galaxy S8 Hardware Pack (Ubuntu / Debian / Kali / Alpine / Arch / OpenWrt / HAOS)
# Usage: sudo ./install.sh [--profile=all|core|audio|wifi|desktop]
set -e
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOTFS="$SELF_DIR/rootfs"
PROFILE="all"

for arg in "$@"; do
    case "$arg" in
        --profile=*) PROFILE="${arg#--profile=}" ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] Run as root (sudo ./install.sh)" >&2
    exit 1
fi

echo "[galaxy-s8-hw] Installing Galaxy S8 Hardware Pack (profile=$PROFILE) into / ..."
mkdir -p /usr/local/bin /usr/local/libexec /usr/local/share /etc
case "$PROFILE" in
    core)
        cp -a "$ROOTFS/usr/local/bin/s8ctl" /usr/local/bin/ 2>/dev/null || true
        cp -a "$ROOTFS/usr/local/bin/s8-hardware-init.sh" /usr/local/bin/ 2>/dev/null || true
        cp -a "$ROOTFS/usr/local/bin/s8-usb-gadget.sh" /usr/local/bin/ 2>/dev/null || true
        cp -a "$ROOTFS/usr/local/libexec"/* /usr/local/libexec/ 2>/dev/null || true
        cp -a "$ROOTFS/etc"/* /etc/ 2>/dev/null || true
        ;;
    audio)
        cp -a "$ROOTFS/etc/asound.conf" /etc/ 2>/dev/null || true
        cp -a "$ROOTFS/usr/local/bin/init_audio.sh" /usr/local/bin/ 2>/dev/null || true
        cp -a "$ROOTFS/usr/local/share/s8-audio" /usr/local/share/ 2>/dev/null || true
        ;;
    wifi)
        cp -a "$ROOTFS/usr/local/bin/s8_wifi.py" /usr/local/bin/ 2>/dev/null || true
        cp -a "$ROOTFS/usr/local/bin/s8_wifi_portal.py" /usr/local/bin/ 2>/dev/null || true
        ;;
    desktop)
        cp -a "$ROOTFS/usr/local/bin/exynos_dp_bridge" "$ROOTFS/usr/local/bin/s8-dp-bridge.sh" "$ROOTFS/usr/local/bin/s8-vnc-setup.sh" /usr/local/bin/ 2>/dev/null || true
        cp -a "$ROOTFS/usr/local/bin/start_gnome_macos.sh" /usr/local/bin/ 2>/dev/null || true
        ;;
    *)
        cp -a "$ROOTFS"/* /
        ;;
esac
chmod +x /usr/local/bin/s8* /usr/local/bin/exynos_dp_bridge /usr/local/bin/init_audio.sh /usr/local/bin/start_bluetooth.sh /usr/local/libexec/galaxy-s8-hw-setup.sh 2>/dev/null || true
chmod +x /etc/init.d/s8-hardware 2>/dev/null || true

export S8_INSTALL_PROFILE="$PROFILE"
if [ -x /usr/local/libexec/galaxy-s8-hw-setup.sh ]; then
    exec /usr/local/libexec/galaxy-s8-hw-setup.sh
fi
exit 0

