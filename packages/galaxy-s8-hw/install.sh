#!/bin/bash
# Portable universal installer for Galaxy S8 Hardware Pack (Ubuntu / Debian / Kali / Alpine / Arch)
set -e
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOTFS="$SELF_DIR/rootfs"

if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] Run as root (sudo ./install.sh)" >&2
    exit 1
fi

echo "[galaxy-s8-hw] Installing Galaxy S8 Hardware Pack into / ..."
cp -a "$ROOTFS"/* /
chmod +x /usr/local/bin/s8* /usr/local/bin/exynos_dp_bridge /usr/local/bin/init_audio.sh /usr/local/bin/start_bluetooth.sh /usr/local/libexec/galaxy-s8-hw-setup.sh 2>/dev/null || true
chmod +x /etc/init.d/s8-hardware 2>/dev/null || true

exec /usr/local/libexec/galaxy-s8-hw-setup.sh

