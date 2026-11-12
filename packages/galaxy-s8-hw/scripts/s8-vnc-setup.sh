#!/bin/bash
# s8-vnc-setup.sh -- Optional helper to install & enable OpenSSH, TigerVNC, noVNC, ALSA & X11 DisplayPort support once online
set -e
export DEBIAN_FRONTEND=noninteractive

echo "[s8-vnc-setup] Installing OpenSSH, VNC, XFCE Session, ALSA & X11 runtime dependencies..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y --no-install-recommends openssh-server tigervnc-standalone-server tigervnc-tools novnc websockify alsa-utils libx11-6 libxext6 libxfixes3 dnsmasq xfce4-session xfwm4 xfce4-panel xfdesktop4 xterm dbus-x11
elif command -v pacman >/dev/null 2>&1; then
    pacman -Sy --noconfirm openssh tigervnc alsa-utils libx11 libxext libxfixes dnsmasq xfce4
elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache openssh tigervnc alsa-utils libx11 libxext libxfixes dnsmasq xfce4
fi

mkdir -p /root/.vnc
cat > /root/.vnc/xstartup <<'XSTART'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XDG_RUNTIME_DIR=/run/user/0
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
if command -v startxfce4 >/dev/null 2>&1; then
    exec dbus-run-session startxfce4
elif command -v xfce4-session >/dev/null 2>&1; then
    exec dbus-run-session xfce4-session
elif command -v xterm >/dev/null 2>&1; then
    exec xterm
fi
XSTART
chmod +x /root/.vnc/xstartup

# If OpenSSH server was installed, retire temporary minimal SSH seed cleanly
if [ -x /usr/sbin/sshd ] && [ -d /run/systemd/system ]; then
    systemctl disable --now s8-seed-ssh.service 2>/dev/null || true
    sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config 2>/dev/null || true
    sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config 2>/dev/null || true
    systemctl enable --now ssh.service 2>/dev/null || systemctl enable --now sshd.service 2>/dev/null || true
fi

if [ -d /run/systemd/system ]; then
    systemctl restart s8-usb-gadget.service s8-vnc.service s8-novnc-ws.service s8-dp-bridge.service 2>/dev/null || true
fi
echo "[s8-vnc-setup] Desktop VNC (:1 / noVNC :6080) & OpenSSH configured cleanly."

