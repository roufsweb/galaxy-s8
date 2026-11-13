#!/bin/sh
# Shared post-install hardware setup invoked by Debian postinst, APK/Pacman, and universal install.sh
# Compatible with POSIX /bin/sh across Ubuntu, Debian, Kali, Arch, Alpine (ash), OpenWrt (procd), and Home Assistant OS.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "[galaxy-s8-hw] Configuring Exynos 8895 aid_* supplementary groups & full hardware permissions..."
add_group_gid() {
    name="$1"
    gid="$2"
    if ! grep -q "^${name}:" /etc/group 2>/dev/null; then
        if command -v getent >/dev/null 2>&1 && getent group "$gid" >/dev/null 2>&1; then
            echo "${name}:x:${gid}:" >> /etc/group
        elif command -v groupadd >/dev/null 2>&1; then
            groupadd -g "$gid" "$name" 2>/dev/null || echo "${name}:x:${gid}:" >> /etc/group
        else
            echo "${name}:x:${gid}:" >> /etc/group
        fi
    fi
}

add_group_gid aid_graphics 1003
add_group_gid aid_input 1004
add_group_gid aid_audio 1005
add_group_gid aid_sdcard_rw 1015
add_group_gid aid_net_bt_admin 3001
add_group_gid aid_net_bt 3002
add_group_gid aid_inet 3003
add_group_gid aid_net_raw 3004
add_group_gid aid_net_admin 3005

EXTRA_S8_GROUPS="aid_inet,aid_net_raw,aid_net_admin,aid_net_bt_admin,aid_net_bt,aid_graphics,aid_input,aid_audio,aid_sdcard_rw"
if command -v usermod >/dev/null 2>&1; then
    for u in root _apt systemd-network systemd-resolve messagebus avahi www-data gdm lightdm dnsmasq homeassistant docker; do
        if id "$u" >/dev/null 2>&1; then
            usermod -a -G "$EXTRA_S8_GROUPS" "$u" 2>/dev/null || true
        fi
    done
    for u in $(awk -F: '$3>=1000 && $3<65534 {print $1}' /etc/passwd 2>/dev/null); do
        usermod -a -G "$EXTRA_S8_GROUPS" "$u" 2>/dev/null || true
    done
fi

if [ -f /etc/adduser.conf ]; then
    sed -i '/^ADD_EXTRA_GROUPS=/d' /etc/adduser.conf 2>/dev/null || true
    sed -i '/^EXTRA_GROUPS=/d' /etc/adduser.conf 2>/dev/null || true
    echo 'ADD_EXTRA_GROUPS=1' >> /etc/adduser.conf
    echo 'EXTRA_GROUPS="dialout cdrom floppy audio video plugdev input users aid_inet aid_net_raw aid_net_admin aid_net_bt_admin aid_net_bt aid_graphics aid_input aid_audio aid_sdcard_rw"' >> /etc/adduser.conf
fi

# Prevent NetworkManager from tearing down USB RNDIS or Broadcom P2P/softap interfaces
if [ -d /etc/NetworkManager ] || command -v nmcli >/dev/null 2>&1; then
    mkdir -p /etc/NetworkManager/conf.d
    cat > /etc/NetworkManager/conf.d/99-s8-rndis-unmanaged.conf <<'NMCONF'
[keyfile]
unmanaged-devices=interface-name:rndis0;interface-name:usb0;interface-name:p2p0;interface-name:swlan0

[connection]
wifi.powersave = 2
NMCONF
fi

# Kernel 4.4.111 apt sandbox + iptables-legacy compatibility (Debian / Ubuntu / Kali)
if [ -d /etc/apt/apt.conf.d ]; then
    cat > /etc/apt/apt.conf.d/99-s8-sandbox <<'APTCONF'
APT::Sandbox::User "root";
APT::Sandbox::Seccomp "false";
APTCONF
fi

if command -v update-alternatives >/dev/null 2>&1; then
    [ -x /usr/sbin/iptables-legacy ] && update-alternatives --set iptables /usr/sbin/iptables-legacy >/dev/null 2>&1 || true
    [ -x /usr/sbin/ip6tables-legacy ] && update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy >/dev/null 2>&1 || true
fi

# Guard OpenBLAS/OMP multi-thread spin on Exynos 8895 big.LITTLE cores
if [ -f /etc/environment ] || [ -d /etc ]; then
    touch /etc/environment 2>/dev/null || true
    grep -q "^OPENBLAS_NUM_THREADS=" /etc/environment 2>/dev/null || printf "OPENBLAS_NUM_THREADS=1\nOMP_NUM_THREADS=1\nGOTO_NUM_THREADS=1\n" >> /etc/environment 2>/dev/null || true
fi

mkdir -p /usr/bin
for tool in s8ctl s8-dp s8_wifi.py exynos_dp_bridge s8_input_bridge s8_button_daemon; do
    if [ -e "/usr/local/bin/$tool" ] && [ ! -e "/usr/bin/$tool" ]; then
        ln -sf "/usr/local/bin/$tool" "/usr/bin/$tool" 2>/dev/null || true
    fi
done

# Ensure wpa_supplicant and NetworkManager start AFTER s8-hardware loads BCM4361 firmware
if [ -d /etc/systemd/system ]; then
    mkdir -p /etc/systemd/system/wpa_supplicant.service.d /etc/systemd/system/NetworkManager.service.d
    cat > /etc/systemd/system/wpa_supplicant.service.d/99-s8-hw.conf <<'WPACONF'
[Unit]
After=s8-hardware.service
Wants=s8-hardware.service

[Service]
SupplementaryGroups=aid_inet aid_net_raw aid_net_admin
WPACONF
    cat > /etc/systemd/system/NetworkManager.service.d/99-s8-hw.conf <<'NMDCONF'
[Unit]
After=s8-hardware.service wpa_supplicant.service
Wants=s8-hardware.service

[Service]
SupplementaryGroups=aid_inet aid_net_raw aid_net_admin
NMDCONF
fi

# Configure logind so s8_button_daemon owns short/double/long power button behavior
mkdir -p /etc/systemd/logind.conf.d 2>/dev/null || true
cat > /etc/systemd/logind.conf.d/99-s8-power.conf <<'CONF'
[Login]
HandlePowerKey=ignore
HandlePowerKeyLongPress=ignore
CONF

# Record installed hardware pack version
echo "1.0.3" > /etc/s8-hw-version

# 1. Systemd runtime / offline enablement (Ubuntu, Debian, Kali, Arch, HAOS)
if [ -d /run/systemd/system ] && command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload 2>/dev/null || true
    command -v udevadm >/dev/null 2>&1 && udevadm control --reload-rules 2>/dev/null || true
    systemctl try-restart systemd-logind 2>/dev/null || true

    if [ ! -e /dev/pts/ptmx ] && systemctl list-unit-files snapd.service >/dev/null 2>&1; then
        systemctl disable --now snapd.seeded.service snapd.apparmor.service snapd.service snapd.socket 2>/dev/null || true
        systemctl mask snapd.seeded.service snapd.service snapd.socket 2>/dev/null || true
    fi

    for svc in s8-hardware.service s8-usb-gadget.service s8-buttons.service s8-typec.service s8-bluetooth.service s8-led.service s8-time-sync.service; do
        systemctl enable "$svc" 2>/dev/null || true
    done
    for svc in s8-vnc.service s8-desktop.service s8-novnc-ws.service s8-dp-bridge.service s8-input-bridge.service; do
        systemctl enable "$svc" 2>/dev/null || true
    done

    if systemctl is-active --quiet s8-seed-usb.service 2>/dev/null; then
        systemctl disable --now s8-seed-usb.service 2>/dev/null || true
    fi

    systemctl restart s8-hardware.service 2>/dev/null || true
    systemctl restart wpa_supplicant.service 2>/dev/null || true
    systemctl restart NetworkManager.service 2>/dev/null || true
    systemctl restart s8-usb-gadget.service 2>/dev/null || true
    systemctl restart s8-buttons.service 2>/dev/null || true
    systemctl restart s8-typec.service 2>/dev/null || true
    systemctl restart s8-bluetooth.service 2>/dev/null || true
    systemctl restart s8-led.service 2>/dev/null || true
    systemctl start --no-block s8-time-sync.service 2>/dev/null || true
    systemctl restart s8-dp-bridge.service 2>/dev/null || true
    systemctl restart s8-input-bridge.service 2>/dev/null || true
elif [ -d /etc/systemd/system ]; then
    mkdir -p /etc/systemd/system/multi-user.target.wants /etc/systemd/system/graphical.target.wants
    for svc in s8-hardware.service s8-usb-gadget.service s8-buttons.service s8-typec.service s8-bluetooth.service s8-led.service s8-time-sync.service; do
        ln -sf "/etc/systemd/system/$svc" "/etc/systemd/system/multi-user.target.wants/$svc"
    done
    for svc in s8-vnc.service s8-desktop.service s8-novnc-ws.service s8-dp-bridge.service s8-input-bridge.service; do
        ln -sf "/etc/systemd/system/$svc" "/etc/systemd/system/graphical.target.wants/$svc"
    done
fi

# 2. OpenRC enablement (Alpine Linux)
if command -v rc-update >/dev/null 2>&1 && [ -x /etc/init.d/s8-hardware ]; then
    rc-update add s8-hardware default 2>/dev/null || true
    rc-service s8-hardware restart 2>/dev/null || true
fi
if [ -d /etc/local.d ]; then
    cat > /etc/local.d/s8-hardware.start <<'LOCALD'
#!/bin/sh
/usr/local/bin/s8-hardware-init.sh >/var/log/s8-hardware.log 2>&1 &
/usr/local/bin/s8-usb-gadget.sh >/var/log/s8-usb-gadget.log 2>&1 &
[ -x /usr/local/bin/s8_button_daemon ] && /usr/local/bin/s8_button_daemon >/var/log/s8-buttons.log 2>&1 &
LOCALD
    chmod 755 /etc/local.d/s8-hardware.start 2>/dev/null || true
fi

# 3. OpenWrt procd / rc.local enablement
if [ -f /etc/openwrt_release ] || [ -d /etc/rc.d ]; then
    if [ -f /etc/rc.local ] && ! grep -q "s8-hardware-init.sh" /etc/rc.local 2>/dev/null; then
        sed -i '/^exit 0/d' /etc/rc.local 2>/dev/null || true
        cat >> /etc/rc.local <<'RCLOCAL'
/usr/local/bin/s8-hardware-init.sh >/var/log/s8-hardware.log 2>&1 &
/usr/local/bin/s8-usb-gadget.sh >/var/log/s8-usb-gadget.log 2>&1 &
[ -x /usr/local/bin/s8_button_daemon ] && /usr/local/bin/s8_button_daemon >/var/log/s8-buttons.log 2>&1 &
exit 0
RCLOCAL
        chmod 755 /etc/rc.local 2>/dev/null || true
    fi
fi

echo "[galaxy-s8-hw] Galaxy S8 Hardware Pack v1.0.3 installed and active."
exit 0
