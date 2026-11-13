"""
Minimal First-Boot Connectivity Seed Injector for Untouched Upstream Distros (Rule 27).
Only adds USB RNDIS IP (192.168.7.2), SSH access + host key, V4L2 panic guard,
invalid /boot/firmware fstab repair, and optional user credentials/OEM bypass.
Never forks or bloats the upstream OS; hardware drivers belong in galaxy-s8-hw.
"""

import shlex
from pathlib import Path
from typing import Callable, Optional

from app.config import RESOURCES_BIN_DIR
from app.core.adb import AdbClient


class HardwareInjector:
    """Seeds untouched OS images with minimal USB RNDIS SSH connectivity & safety guards."""

    def __init__(self, adb: Optional[AdbClient] = None):
        self.adb = adb or AdbClient()

    @staticmethod
    def _build_seed_shell(
        target_root: str = "/mnt/ubuntu",
        username: str = "ubuntu",
        password: str = "ubuntu",
        hostname: str = "galaxy-s8",
        pub_key: str = "",
        wifi_ssid: str = "",
        wifi_password: str = "",
        has_static_dropbear: bool = False,
    ) -> str:
        safe_user = "".join(c for c in (username or "ubuntu") if c.isalnum() or c in "-_") or "ubuntu"
        safe_host = "".join(c for c in (hostname or "galaxy-s8") if c.isalnum() or c in "-.") or "galaxy-s8"
        q_pw = shlex.quote(password or "ubuntu")
        q_key = shlex.quote(pub_key.strip())
        q_ssid = shlex.quote(wifi_ssid.strip())
        q_wpw = shlex.quote(wifi_password)

        return f"""#!/bin/sh
set -e
R="{target_root}"
mkdir -p "$R/opt/s8-seed" "$R/etc/udev/rules.d" "$R/etc/systemd/system" "$R/etc/systemd/system/multi-user.target.wants" "$R/etc/init.d"

# 1. Exynos 8895 FIMC-IS2 V4L2 panic guard (Rule 2)
cat > "$R/etc/udev/rules.d/60-persistent-v4l.rules" <<'EOF'
ACTION=="remove", GOTO="persistent_v4l_end"
SUBSYSTEM!="video4linux", GOTO="persistent_v4l_end"
ENV{{MAJOR}}=="", GOTO="persistent_v4l_end"
KERNEL=="video[1-9][0-9]*|v4l-subdev*", OPTIONS+="ignore_device", GOTO="persistent_v4l_end"
IMPORT{{program}}="v4l_id $devnode"
SUBSYSTEMS=="usb", IMPORT{{builtin}}="usb_id"
KERNEL=="video*", ENV{{ID_SERIAL}}=="?*", SYMLINK+="v4l/by-id/$env{{ID_BUS}}-$env{{ID_SERIAL}}-video-index$attr{{index}}"
LABEL="persistent_v4l_end"
EOF
cat > "$R/etc/udev/rules.d/99-s8-no-fimc.rules" <<'EOF'
SUBSYSTEM=="video4linux", KERNEL=="video[1-9][0-9]*", OPTIONS+="ignore_device", RUN+="/bin/rm -f /dev/%k"
SUBSYSTEM=="video4linux", KERNEL=="v4l-subdev*", OPTIONS+="ignore_device", RUN+="/bin/rm -f /dev/%k"
EOF

# 2. Prevent 90s systemd boot stall on non-existent Raspberry Pi / EFI / SteamOS partitions
if [ -f "$R/etc/fstab" ]; then
    sed -i -E '/(LABEL=system-boot|LABEL=BOOT|\\/boot\\/firmware|\\/boot\\/efi|[[:space:]]\\/boot[[:space:]]|[[:space:]]\\/home[[:space:]]|[[:space:]]\\/esp[[:space:]])/s/^([^#])/# s8-disabled: \\1/' "$R/etc/fstab"
fi

# 3. Hostname
echo {shlex.quote(safe_host)} > "$R/etc/hostname"
if [ -f "$R/etc/hosts" ] && ! grep -q {shlex.quote(safe_host)} "$R/etc/hosts"; then
    echo "127.0.1.1 {safe_host}" >> "$R/etc/hosts"
fi

# 4. Android PARANOID_NETWORK aid_inet group so SSH/apt/NetworkManager sockets work cleanly
for grp in "aid_inet:x:3003:" "aid_net_raw:x:3004:" "aid_net_admin:x:3005:"; do
    gname=$(echo "$grp" | cut -d: -f1)
    grep -q "^${{gname}}:" "$R/etc/group" 2>/dev/null || echo "$grp" >> "$R/etc/group"
done
for u in root _apt systemd-network systemd-resolve messagebus; do
    if grep -q "^${{u}}:" "$R/etc/passwd" 2>/dev/null; then
        for aidg in aid_inet aid_net_raw; do
            grep -qE "^${{aidg}}:.*[:,]${{u}}(,|$)" "$R/etc/group" 2>/dev/null || \
                sed -i -E "s/^(${{aidg}}:[^:]*:[^:]*:)(.*)/\\1\\2,${{u}}/; s/:,/:/g" "$R/etc/group" 2>/dev/null || true
        done
    fi
done

# 5. Minimal ConfigFS USB RNDIS 192.168.7.2 bootstrap
cat > "$R/opt/s8-seed/s8-seed-usb.sh" <<'EOF'
#!/bin/sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null || true
mkdir -p /sys/kernel/config
mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config 2>/dev/null || true
G=/sys/kernel/config/usb_gadget/g1
if [ -d "$G/functions/ffs.adb" ] && [ -d "$G/functions/rndis.usb0" ] && [ "$(cat "$G/UDC" 2>/dev/null)" = "10c00000.dwc3" ]; then
    :
elif [ ! -d "$G/functions/rndis.usb0" ] || [ "$(cat "$G/UDC" 2>/dev/null)" != "10c00000.dwc3" ]; then
    echo 0 > /sys/class/android_usb/android0/enable 2>/dev/null || true
    echo "" > "$G/UDC" 2>/dev/null || true
    mkdir -p "$G/strings/0x409" "$G/configs/c.1/strings/0x409" "$G/functions/rndis.usb0"
    echo 0x04E8 > "$G/idVendor"; echo 0x6863 > "$G/idProduct"
    echo 0xE0 > "$G/bDeviceClass"; echo 0x01 > "$G/bDeviceSubClass" 2>/dev/null || true; echo 0x03 > "$G/bDeviceProtocol" 2>/dev/null || true
    echo "ce10171ab3e9620804" > "$G/strings/0x409/serialnumber"
    echo "Samsung" > "$G/strings/0x409/manufacturer"
    echo "Galaxy S8 Linux" > "$G/strings/0x409/product"
    echo "RNDIS" > "$G/configs/c.1/strings/0x409/configuration"
    ln -sf "$G/functions/rndis.usb0" "$G/configs/c.1/rndis.usb0" 2>/dev/null || true
    echo rndis > /sys/class/android_usb/android0/functions 2>/dev/null || true
    echo "10c00000.dwc3" > "$G/UDC" 2>/dev/null || true
    echo 1 > /sys/class/android_usb/android0/enable 2>/dev/null || true
fi
for i in 1 2 3 4 5 6 7 8 9 10; do
    ip link show rndis0 >/dev/null 2>&1 && break
    sleep 0.3
done
if ip link show rndis0 >/dev/null 2>&1; then
    ip addr replace 192.168.7.2/24 dev rndis0
    ip link set rndis0 up
    command -v nmcli >/dev/null 2>&1 && nmcli dev set rndis0 managed no >/dev/null 2>&1 || true
    if command -v dnsmasq >/dev/null 2>&1; then
        dnsmasq --keep-in-foreground --no-daemon --interface=rndis0 --bind-interfaces --port=0 --dhcp-range=192.168.7.10,192.168.7.50,12h --dhcp-option=3 --dhcp-option=6 --dhcp-leasefile=/run/dnsmasq-rndis.leases --pid-file=/run/dnsmasq-rndis.pid </dev/null >/dev/null 2>&1 &
    elif command -v busybox >/dev/null 2>&1 && busybox udhcpd --help >/dev/null 2>&1; then
        printf "start 192.168.7.10\nend 192.168.7.50\ninterface rndis0\nopt subnet 255.255.255.0\nopt lease 43200\n" > /run/s8-udhcpd.conf
        busybox udhcpd -f /run/s8-udhcpd.conf </dev/null >/dev/null 2>&1 &
    fi
fi
while true; do
    if ! (/run/s8/busybox ip -4 addr show dev rndis0 2>/dev/null || ip -4 addr show dev rndis0 2>/dev/null) | grep -q "192.168.7.2"; then
        /run/s8/busybox ip addr replace 192.168.7.2/24 dev rndis0 2>/dev/null || ip addr replace 192.168.7.2/24 dev rndis0 2>/dev/null || true
        /run/s8/busybox ip link set rndis0 up 2>/dev/null || ip link set rndis0 up 2>/dev/null || true
    fi
    /run/s8/busybox sleep 3 2>/dev/null || sleep 3
done
EOF
chmod +x "$R/opt/s8-seed/s8-seed-usb.sh"
if [ -d "$R/etc/NetworkManager" ]; then
    mkdir -p "$R/etc/NetworkManager/conf.d"
    printf "[keyfile]\nunmanaged-devices=interface-name:rndis0;interface-name:usb0\n" > "$R/etc/NetworkManager/conf.d/99-s8-rndis-unmanaged.conf"
fi

cat > "$R/etc/systemd/system/s8-seed-usb.service" <<'EOF'
[Unit]
Description=Galaxy S8 First-Boot USB RNDIS Connectivity Seed
DefaultDependencies=no
After=systemd-udevd.service local-fs.target sys-kernel-config.mount
Wants=sys-kernel-config.mount
Before=network-pre.target

[Service]
Type=simple
SupplementaryGroups=aid_inet aid_net_raw aid_net_admin
ExecStart=/opt/s8-seed/s8-seed-usb.sh
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
chmod 644 "$R/etc/systemd/system/s8-seed-usb.service"
ln -sf /etc/systemd/system/s8-seed-usb.service "$R/etc/systemd/system/multi-user.target.wants/s8-seed-usb.service"

# 6. First-Boot User & SSH Key Seed
PUBKEY={q_key}
mkdir -p "$R/root/.ssh" && chmod 700 "$R/root/.ssh"
if [ -n "$PUBKEY" ]; then
    grep -qxF "$PUBKEY" "$R/root/.ssh/authorized_keys" 2>/dev/null || echo "$PUBKEY" >> "$R/root/.ssh/authorized_keys"
    chmod 600 "$R/root/.ssh/authorized_keys"
fi

# Seed user account & bypass tty1-dependent oem-config.target on headless desktop images
if [ -x "$R/usr/sbin/useradd" ] || [ -x "$R/bin/chpasswd" ] || [ -x "$R/usr/sbin/chpasswd" ] || [ -x "$R/usr/sbin/adduser" ]; then
    if command -v chroot >/dev/null 2>&1 && ( [ "$(uname -m)" = "aarch64" ] || [ -x "$R/usr/bin/qemu-aarch64-static" ] || [ -x /usr/bin/qemu-aarch64-static ] ); then
        TMP_QEMU=0
        if [ "$(uname -m)" != "aarch64" ] && [ -x /usr/bin/qemu-aarch64-static ] && [ ! -e "$R/usr/bin/qemu-aarch64-static" ]; then
            cp /usr/bin/qemu-aarch64-static "$R/usr/bin/"
            TMP_QEMU=1
        fi
        mkdir -p "$R/dev" "$R/proc" "$R/tmp"
        mount --bind /dev "$R/dev" 2>/dev/null || true
        mount --bind /proc "$R/proc" 2>/dev/null || true
        cat > "$R/tmp/.s8_user_setup.sh" <<'EOF'
#!/bin/sh
U="$1"
PW="$2"
id -u "$U" >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo,adm,aid_inet,aid_net_raw,aid_net_admin "$U" 2>/dev/null || adduser -D -s /bin/sh "$U" 2>/dev/null || useradd -m -s /bin/sh "$U" 2>/dev/null || true
if command -v chpasswd >/dev/null 2>&1; then
    printf '%s:%s\n' "$U" "$PW" | chpasswd 2>/dev/null || true
    printf '%s:%s\n' "root" "$PW" | chpasswd 2>/dev/null || true
fi
mkdir -p "/home/$U/.ssh" && chmod 700 "/home/$U/.ssh"
[ -f /root/.ssh/authorized_keys ] && cp -f /root/.ssh/authorized_keys "/home/$U/.ssh/authorized_keys"
chown -R "$U:$U" "/home/$U/.ssh" 2>/dev/null || true
EOF
        chmod +x "$R/tmp/.s8_user_setup.sh"
        env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root TERM=linux chroot "$R" /bin/sh /tmp/.s8_user_setup.sh {shlex.quote(safe_user)} {q_pw} || true
        rm -f "$R/tmp/.s8_user_setup.sh"
        umount "$R/proc" 2>/dev/null || umount -l "$R/proc" 2>/dev/null || true
        umount "$R/dev" 2>/dev/null || umount -l "$R/dev" 2>/dev/null || true
        [ "$TMP_QEMU" -eq 1 ] && rm -f "$R/usr/bin/qemu-aarch64-static"
    fi
fi

# Switch Canonical oem-config.target (which conflicts with multi-user & fails without /dev/tty1) -> graphical.target
if [ -L "$R/etc/systemd/system/default.target" ]; then
    TARGET_LINK=$(readlink "$R/etc/systemd/system/default.target" || true)
    case "$TARGET_LINK" in
        *oem-config*)
            ln -sf /usr/lib/systemd/system/graphical.target "$R/etc/systemd/system/default.target"
            ln -sf /dev/null "$R/etc/systemd/system/oem-config.service"
            ln -sf /dev/null "$R/etc/systemd/system/oem-config.target"
            ln -sf /dev/null "$R/etc/systemd/system/ubiquity.service"
            ;;
    esac
fi

# 7. SSH Bootstrap Daemon: enable OpenSSH if present, else static s8-dropbear
if [ -x "$R/usr/sbin/sshd" ]; then
    sed -i 's/^#\\?PermitRootLogin .*/PermitRootLogin yes/' "$R/etc/ssh/sshd_config" 2>/dev/null || true
    sed -i 's/^#\\?PasswordAuthentication .*/PasswordAuthentication yes/' "$R/etc/ssh/sshd_config" 2>/dev/null || true
    mkdir -p "$R/etc/systemd/system/ssh.service.d"
    ln -sf /lib/systemd/system/ssh.service "$R/etc/systemd/system/multi-user.target.wants/ssh.service" 2>/dev/null || ln -sf /usr/lib/systemd/system/ssh.service "$R/etc/systemd/system/multi-user.target.wants/ssh.service" 2>/dev/null || true
elif [ {1 if has_static_dropbear else 0} -eq 1 ] && [ -x "$R/opt/s8-seed/s8-dropbear" ]; then
    ln -sf s8-dropbear "$R/opt/s8-seed/dropbear"
    ln -sf s8-dropbear "$R/opt/s8-seed/dropbearkey"
    ln -sf s8-dropbear "$R/opt/s8-seed/scp"
    cat > "$R/opt/s8-seed/s8-seed-ssh.sh" <<'EOF'
#!/bin/sh
export PATH=/opt/s8-seed:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
mkdir -p /etc/dropbear /var/run
if [ ! -f /etc/dropbear/dropbear_ed25519_host_key ]; then
    /opt/s8-seed/s8-dropbear dropbearkey -t ed25519 -f /etc/dropbear/dropbear_ed25519_host_key >/dev/null 2>&1 || true
fi
if [ ! -f /etc/dropbear/dropbear_rsa_host_key ]; then
    /opt/s8-seed/s8-dropbear dropbearkey -t rsa -f /etc/dropbear/dropbear_rsa_host_key >/dev/null 2>&1 || true
fi
if [ -f /etc/dropbear/dropbear_ed25519_host_key ] && [ -f /etc/dropbear/dropbear_rsa_host_key ]; then
    exec /opt/s8-seed/s8-dropbear dropbear -F -p 22 -r /etc/dropbear/dropbear_ed25519_host_key -r /etc/dropbear/dropbear_rsa_host_key
else
    exec /opt/s8-seed/s8-dropbear dropbear -R -F -p 22
fi
EOF
    chmod +x "$R/opt/s8-seed/s8-seed-ssh.sh"
    cat > "$R/etc/systemd/system/s8-seed-ssh.service" <<'EOF'
[Unit]
Description=Galaxy S8 First-Boot Minimal Dropbear SSH Seed
DefaultDependencies=no
After=s8-seed-usb.service local-fs.target
ConditionPathExists=!/usr/sbin/sshd

[Service]
Type=simple
SupplementaryGroups=aid_inet aid_net_raw aid_net_admin
ExecStart=/opt/s8-seed/s8-seed-ssh.sh
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
    chmod 644 "$R/etc/systemd/system/s8-seed-ssh.service"
    ln -sf /etc/systemd/system/s8-seed-ssh.service "$R/etc/systemd/system/multi-user.target.wants/s8-seed-ssh.service"
fi

# 8. Optional user-supplied pre-boot Wi-Fi Netplan (never hardcoded)
SSID={q_ssid}
WPW={q_wpw}
if [ -n "$SSID" ]; then
    mkdir -p "$R/etc/netplan"
    cat > "$R/etc/netplan/90-s8-wifi.yaml" <<EOF
network:
  version: 2
  wifis:
    wlan0:
      optional: true
      dhcp4: true
      access-points:
        "$SSID":
          password: "$WPW"
EOF
    chmod 600 "$R/etc/netplan/90-s8-wifi.yaml"
fi

# 9. Universal systemd >= 256 cgroup v1 PID 1 wrapper (Kali, HAOS 18.4, SteamOS 3.6)
if [ -x "$R/usr/lib/systemd/systemd" ] || [ -x "$R/lib/systemd/systemd" ]; then
    cat > "$R/opt/s8-seed/s8-init-wrapper.sh" <<'EOF'
#!/bin/sh
rm -f /dev/watchdog /dev/watchdog0 /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null || true
if ! grep -q "SYSTEMD_CGROUP_ENABLE_LEGACY_FORCE=1" /proc/cmdline 2>/dev/null; then
    echo "$(cat /proc/cmdline) SYSTEMD_CGROUP_ENABLE_LEGACY_FORCE=1 systemd.unified_cgroup_hierarchy=0 systemd.legacy_systemd_cgroup_controller=1" > /run/s8/cmdline
    /run/s8/busybox mount -o bind /run/s8/cmdline /proc/cmdline 2>/dev/null || mount -o bind /run/s8/cmdline /proc/cmdline 2>/dev/null || true
fi
[ -x /opt/s8-seed/s8-seed-usb.sh ] && /opt/s8-seed/s8-seed-usb.sh </dev/null >/dev/null 2>&1 &
export SYSTEMD_CGROUP_ENABLE_LEGACY_FORCE=1
if [ -x /usr/lib/systemd/systemd ]; then
    exec /usr/lib/systemd/systemd "$@"
fi
exec /lib/systemd/systemd "$@"
EOF
    chmod 755 "$R/opt/s8-seed/s8-init-wrapper.sh"
    ln -sf /opt/s8-seed/s8-init-wrapper.sh "$R/sbin/init"
fi

# 10. OpenRC / BusyBox /sbin/init fallback for Alpine Linux
if [ -f "$R/etc/alpine-release" ]; then
    if [ -f "$R/etc/inittab" ]; then
        sed -i -E 's/^(tty[0-9]|ttyS0)/# s8-disabled: \1/' "$R/etc/inittab" 2>/dev/null || true
    fi
    cat > "$R/opt/s8-seed/s8-alpine-boot.sh" <<'EOF'
#!/bin/sh
export PATH=/run/s8:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
rm -f /dev/watchdog /dev/watchdog0 /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null || true
mountpoint -q /proc || mount -t proc proc /proc 2>/dev/null || true
mountpoint -q /sys || mount -t sysfs sysfs /sys 2>/dev/null || true
mount -o remount,rw / 2>/dev/null || true
[ -f /etc/hostname ] && hostname -F /etc/hostname 2>/dev/null || true
ip link set lo up 2>/dev/null || true
[ -x /usr/local/bin/s8-hardware-init.sh ] && /usr/local/bin/s8-hardware-init.sh </dev/null >/var/log/s8-hardware.log 2>&1 &
[ -x /opt/s8-seed/s8-seed-usb.sh ] && /opt/s8-seed/s8-seed-usb.sh </dev/null >/var/log/s8-seed-usb.log 2>&1 &
[ -x /opt/s8-seed/s8-seed-ssh.sh ] && /opt/s8-seed/s8-seed-ssh.sh </dev/null >/var/log/s8-seed-ssh.log 2>&1 &
[ -x /usr/local/bin/s8_button_daemon ] && /usr/local/bin/s8_button_daemon </dev/null >/var/log/s8-buttons.log 2>&1 &
exit 0
EOF
    chmod 755 "$R/opt/s8-seed/s8-alpine-boot.sh"
    if [ ! -x "$R/sbin/openrc" ] && [ -f "$R/etc/inittab" ]; then
        sed -i 's|^::sysinit:/sbin/openrc sysinit|::sysinit:/opt/s8-seed/s8-alpine-boot.sh|' "$R/etc/inittab"
        sed -i '/\\/sbin\\/openrc/s/^/# s8-disabled: /' "$R/etc/inittab"
    fi
fi

if [ -f "$R/sbin/openrc" ] && [ ! -L "$R/sbin/init" -o "$(readlink "$R/sbin/init")" != "/opt/s8-seed/s8-init-wrapper.sh" ]; then
    cat > "$R/etc/init.d/s8-seed" <<'EOF'
#!/sbin/openrc-run
depend() {{ need localmount; before net; }}
start() {{
    /opt/s8-seed/s8-seed-usb.sh &
    [ -x /opt/s8-seed/s8-seed-ssh.sh ] && /opt/s8-seed/s8-seed-ssh.sh &
}}
EOF
    chmod +x "$R/etc/init.d/s8-seed"
    mkdir -p "$R/etc/runlevels/default"
    ln -sf /etc/init.d/s8-seed "$R/etc/runlevels/default/s8-seed"
fi

# 11. OpenWrt procd / preinit / rc.local setup
if [ -f "$R/etc/openwrt_release" ]; then
    touch "$R/.dockerenv"
    rm -f "$R/init" "$R/etc/rc.d/S19firewall" "$R/etc/rc.d/S19dnsmasq" "$R/etc/rc.d/S35odhcpd" 2>/dev/null || true
    mkdir -p "$R/etc/config"
    cat > "$R/etc/config/network" <<'EOF'
config interface 'loopback'
	option device 'lo'
	option proto 'static'
	option ipaddr '127.0.0.1'
	option netmask '255.0.0.0'
EOF
    cat > "$R/etc/config/system" <<'EOF'
config system
	option hostname 'galaxy-s8'
	option timezone 'UTC'
	option ttylogin '0'
	option log_size '64'
	option urandom_seed '0'
EOF
    if [ -f "$R/sbin/init" ] && [ ! -L "$R/sbin/init" ] && [ ! -f "$R/sbin/init.openwrt.real" ]; then
        mv "$R/sbin/init" "$R/sbin/init.openwrt.real"
    fi
    cat > "$R/opt/s8-seed/s8-openwrt-init.sh" <<'EOF'
#!/bin/sh
export container=s8-native
rm -f /dev/watchdog /dev/watchdog0 /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null || true
[ -x /opt/s8-seed/s8-seed-usb.sh ] && /opt/s8-seed/s8-seed-usb.sh </dev/null >/dev/null 2>&1 &
exec /sbin/init.openwrt.real "$@"
EOF
    chmod 755 "$R/opt/s8-seed/s8-openwrt-init.sh"
    ln -sf /opt/s8-seed/s8-openwrt-init.sh "$R/sbin/init"
    if [ -f "$R/lib/preinit/00_preinit.conf" ]; then
        grep -q "INITRAMFS=1" "$R/lib/preinit/00_preinit.conf" 2>/dev/null || cat >> "$R/lib/preinit/00_preinit.conf" <<'EOF'
INITRAMFS=1
export INITRAMFS=1
pi_preinit_no_failsafe="y"
fs_failsafe_wait_timeout=0
EOF
    fi
    if [ -f "$R/lib/preinit/80_mount_root" ]; then
        sed -i 's/^[[:space:]]*mount_root/	: # s8-root-already-mounted/' "$R/lib/preinit/80_mount_root" 2>/dev/null || true
    fi
    if [ -f "$R/etc/inittab" ]; then
        sed -i '/::askfirst:/s/^/# /' "$R/etc/inittab" 2>/dev/null || true
    fi
fi

if [ -f "$R/etc/openwrt_release" ] || [ -f "$R/etc/rc.local" ]; then
    touch "$R/etc/rc.local"
    sed -i '/s8-seed-usb.sh/d; /^exit 0/d' "$R/etc/rc.local" 2>/dev/null || true
    cat >> "$R/etc/rc.local" <<'EOF'
/opt/s8-seed/s8-seed-usb.sh >/var/log/s8-seed-usb.log 2>&1 &
[ -x /opt/s8-seed/s8-seed-ssh.sh ] && /opt/s8-seed/s8-seed-ssh.sh >/var/log/s8-seed-ssh.log 2>&1 &
exit 0
EOF
    chmod 755 "$R/etc/rc.local"
fi

# 12. Home Assistant OS 18.4 (HAOS) single-ext4 & Kernel 4.4.111 Docker setup
if [ -f "$R/usr/sbin/haos-supervisor" ] || [ -f "$R/usr/lib/systemd/system/haos-agent.service" ]; then
    mkdir -p "$R/mnt/data/supervisor" "$R/mnt/data/docker" "$R/mnt/boot" "$R/mnt/overlay" "$R/var/lib/docker" "$R/var/log/journal" "$R/etc/docker"
    rm -f "$R/etc/systemd/system/local-fs.target.wants/mnt-boot.mount" \
          "$R/etc/systemd/system/local-fs.target.wants/mnt-data.mount" \
          "$R/etc/systemd/system/local-fs.target.wants/mnt-overlay.mount" \
          "$R/etc/systemd/system/local-fs.target.wants/var.mount" \
          "$R/etc/systemd/system/local-fs.target.wants/haos-expand.service" \
          "$R/etc/systemd/system/local-fs.target.wants/haos-data.service" \
          "$R/etc/systemd/system/local-fs.target.wants/haos-data-disk-detach.service" \
          "$R/etc/systemd/system/local-fs.target.wants/haos-overlay.service" \
          "$R/etc/systemd/system/swap.target.wants/haos-swapfile.service" \
          "$R/etc/systemd/system/swap.target.wants/mnt-data-swapfile.swap" \
          "$R/etc/systemd/system/multi-user.target.wants/haos-bind.target" \
          "$R/etc/systemd/system/multi-user.target.wants/rauc.service" \
          "$R/etc/systemd/system/multi-user.target.wants/raucdb-update.service" \
          "$R/etc/systemd/system/multi-user.target.wants/haos-persists.service" \
          "$R/etc/systemd/system/multi-user.target.wants/vmtoolsd.service" \
          "$R/etc/systemd/system/multi-user.target.wants/qemu-guest.service" \
          "$R/etc/systemd/system/sysinit.target.wants/haos-wipe.service" \
          "$R/etc/systemd/system/haos-bind.target.wants/"* \
          "$R/etc/systemd/system/haos-zram.target.wants/"* 2>/dev/null || true
    for u in mnt-boot.mount mnt-data.mount mnt-overlay.mount mnt-config.mount var.mount var-lib-docker.mount haos-expand.service haos-data.service haos-data-disk-detach.service haos-overlay.service haos-swapfile.service mnt-data-swapfile.swap haos-bind.target rauc.service raucdb-update.service haos-apparmor.service haos-wipe.service; do
        ln -sf /dev/null "$R/etc/systemd/system/$u"
    done
    rm -f "$R/usr/lib/systemd/system/docker.service.d/failure.conf" 2>/dev/null || true
    mkdir -p "$R/usr/lib/systemd/system/docker.service.d"
    cat > "$R/usr/lib/systemd/system/docker.service.d/haos.conf" <<'EOF'
[Service]
EnvironmentFile=-/run/dockerd.env
ExecStart=
ExecStart=/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock
OOMScoreAdjust=-400
EOF
    cat > "$R/etc/docker/daemon.json" <<'EOF'
{{
    "storage-driver": "overlay2",
    "data-root": "/mnt/data/docker",
    "bip": "172.30.232.1/23",
    "ipv6": false
}}
EOF
    if [ -x "$R/usr/sbin/xtables-legacy-multi" ]; then
        ln -sf xtables-legacy-multi "$R/usr/sbin/iptables"
        ln -sf xtables-legacy-multi "$R/usr/sbin/ip6tables"
        ln -sf xtables-legacy-multi "$R/sbin/iptables" 2>/dev/null || true
        ln -sf xtables-legacy-multi "$R/sbin/ip6tables" 2>/dev/null || true
    fi
fi

# 13. SteamOS 3.6 ARM64 (Holo) single-ext4 & Exynos 8895 USB RNDIS preservation
if grep -q "ID=steamos" "$R/etc/os-release" 2>/dev/null; then
    mkdir -p "$R/home/deck" "$R/var/lib/steamos-sm8550"
    touch "$R/var/lib/steamos-sm8550/home-expanded"
    rm -f "$R/etc/systemd/system/usb-gadget.target.wants/"* \
          "$R/etc/systemd/system/steamos-offload.target.wants/"* \
          "$R/etc/systemd/system/local-fs.target.wants/steamos-sm8550-expand-home.service" \
          "$R/etc/systemd/system/multi-user.target.wants/steamos-sm8550-expand-home.service" \
          "$R/etc/systemd/system/multi-user.target.wants/sm8550-"* \
          "$R/etc/systemd/system/multi-user.target.wants/deckard-"* \
          "$R/etc/systemd/system/multi-user.target.wants/odin3-thor-autoinstall.service" \
          "$R/etc/systemd/system/multi-user.target.wants/konkrd.service" \
          "$R/etc/systemd/system/NetworkManager.service.wants/sm8550-wifi-backend.service" \
          "$R/etc/systemd/system/bluetooth.target.wants/sm8550-bluetooth-setup.service" \
          "$R/etc/systemd/system/sound.target.wants/sm8550-audio-setup.service" \
          "$R/etc/systemd/system/basic.target.wants/deckard-"* \
          "$R/etc/systemd/system/default.target.wants/deckard-"* \
          "$R/etc/systemd/system/graphical.target.wants/steamos-boot.service" 2>/dev/null || true
    for u in usb-gadget.service adbd.service adbd-pre.service adbd-post.service steamos-sm8550-expand-home.service steamos-boot.service; do
        ln -sf /dev/null "$R/etc/systemd/system/$u"
    done
    ln -sf /usr/lib/systemd/system/multi-user.target "$R/etc/systemd/system/default.target" 2>/dev/null || true
fi
echo "[SEED] Minimal connectivity & V4L2 safety seed complete."
"""

    def seed_mounted_adb(
        self,
        target_mount: str = "/mnt/ubuntu",
        username: str = "ubuntu",
        password: str = "ubuntu",
        hostname: str = "galaxy-s8",
        wifi_ssid: str = "",
        wifi_password: str = "",
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Apply minimal first-boot connectivity seed via TWRP ADB while rootfs is mounted."""
        def log(msg: str):
            if log_callback:
                log_callback(msg)

        _, pub_path = self.adb.ensure_ssh_keypair()
        pub_key = pub_path.read_text(encoding="utf-8").strip() if pub_path and pub_path.is_file() else ""

        dropbear_bin = RESOURCES_BIN_DIR / "s8-dropbear-arm64"
        has_db = dropbear_bin.is_file()
        if has_db:
            log("[SEED] Staging tiny static SSH bootstrap binary into /opt/s8-seed/...")
            self.adb.root_shell(f"mkdir -p {target_mount}/opt/s8-seed")
            self.adb.push(str(dropbear_bin), f"{target_mount}/opt/s8-seed/s8-dropbear", timeout=30)
            self.adb.root_shell(f"chmod 755 {target_mount}/opt/s8-seed/s8-dropbear")

        script = self._build_seed_shell(
            target_root=target_mount,
            username=username,
            password=password,
            hostname=hostname,
            pub_key=pub_key,
            wifi_ssid=wifi_ssid,
            wifi_password=wifi_password,
            has_static_dropbear=has_db,
        )
        local_tmp = Path.home() / ".s8_imager_seed.sh"
        local_tmp.write_bytes(script.replace("\r\n", "\n").encode("utf-8"))
        try:
            self.adb.push(str(local_tmp), "/tmp/s8_seed_apply.sh", timeout=20)
            out = self.adb.root_shell("sh /tmp/s8_seed_apply.sh 2>&1; RC=$?; rm -f /tmp/s8_seed_apply.sh; echo EXIT=$RC", timeout=90)
            log(out or "[SEED] Applied minimal seed.")
            return ("EXIT=0" in out) and ("[SEED]" in out or "complete" in out.lower())
        finally:
            local_tmp.unlink(missing_ok=True)

    def seed_mounted_rwp(
        self,
        target_mount: str = "/mnt/s8_stage",
        username: str = "ubuntu",
        password: str = "ubuntu",
        hostname: str = "galaxy-s8",
        wifi_ssid: str = "",
        wifi_password: str = "",
        install_hw_pack: bool = True,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Apply connectivity seed & universal galaxy-s8-hw pack over RWP/SSH."""
        def log(msg: str):
            if log_callback:
                log_callback(msg)

        _, pub_path = self.adb.ensure_ssh_keypair()
        pub_key = pub_path.read_text(encoding="utf-8").strip() if pub_path and pub_path.is_file() else ""

        dropbear_bin = RESOURCES_BIN_DIR / "s8-dropbear-arm64"
        has_db = dropbear_bin.is_file()
        if has_db:
            self.adb.exec_env(
                f"/run/s8/busybox mkdir -p {target_mount}/opt/s8-seed && "
                f"/run/s8/busybox cp -f /run/s8/s8-dropbear-arm64 {target_mount}/opt/s8-seed/s8-dropbear 2>/dev/null && "
                f"/run/s8/busybox chmod 755 {target_mount}/opt/s8-seed/s8-dropbear 2>/dev/null || true",
                env="os",
            )

        script = self._build_seed_shell(
            target_root=target_mount,
            username=username,
            password=password,
            hostname=hostname,
            pub_key=pub_key,
            wifi_ssid=wifi_ssid,
            wifi_password=wifi_password,
            has_static_dropbear=has_db,
        )
        push_fn = getattr(self.adb, "push_rwp_http", self.adb.push_ssh)
        local_tmp = Path.home() / ".s8_imager_seed_rwp.sh"
        local_tmp.write_bytes(script.replace("\r\n", "\n").encode("utf-8"))
        try:
            pushed_seed, _ = push_fn(str(local_tmp), "/tmp/s8_seed_apply.sh", timeout=30)
            if not pushed_seed:
                import base64
                b64 = base64.b64encode(script.replace("\r\n", "\n").encode("utf-8")).decode("ascii")
                self.adb.exec_env(
                    f"echo '{b64}' | (/run/s8/busybox base64 -d 2>/dev/null || base64 -d) > /tmp/s8_seed_apply.sh",
                    env="os",
                    timeout=30,
                )
            out = self.adb.exec_env(
                "export PATH=/run/s8:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; "
                "sh /tmp/s8_seed_apply.sh 2>&1; RC=$?; rm -f /tmp/s8_seed_apply.sh; echo EXIT=$RC",
                env="os",
                timeout=90,
            )
        finally:
            local_tmp.unlink(missing_ok=True)
        log(out or "[SEED] Applied minimal seed over RWP.")
        ok = ("EXIT=0" in out) and ("[SEED]" in out or "complete" in out.lower())

        if ok and install_hw_pack:
            from app.config import REPO_ROOT
            tar_pkg = REPO_ROOT / "packages" / "dist" / "galaxy-s8-hw-universal-arm64.tar.gz"
            if tar_pkg.is_file():
                log("[HW-PACK] Pre-installing universal galaxy-s8-hw into target rootfs...")
                push_fn = getattr(self.adb, "push_rwp_http", self.adb.push_ssh)
                pushed, _ = push_fn(str(tar_pkg), "/tmp/s8_hw_univ.tar.gz", timeout=60)
                if pushed:
                    hw_out = self.adb.exec_env(
                        f"export PATH=/run/s8:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; "
                        f"mkdir -p /tmp/s8_hw_u && "
                        f"(/mnt/android_data/linux/tools/s8-tar -xzf /tmp/s8_hw_univ.tar.gz -C /tmp/s8_hw_u 2>/dev/null || "
                        f"/run/s8/busybox tar -xzf /tmp/s8_hw_univ.tar.gz -C /tmp/s8_hw_u) && "
                        f"cp -a /tmp/s8_hw_u/galaxy-s8-hw-*/rootfs/* '{target_mount}/' && "
                        f"chroot '{target_mount}' /bin/sh /usr/local/libexec/galaxy-s8-hw-setup.sh 2>&1; "
                        f"rm -rf /tmp/s8_hw_u /tmp/s8_hw_univ.tar.gz; echo HW_DONE",
                        env="os",
                        timeout=60,
                    )
                    log(hw_out or "[HW-PACK] Universal hardware pack installed.")
        return ok

    def inject(self, target_mount: str = "/mnt/ubuntu", log_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Backward-compatible entry point calling minimal connectivity seed (Rule 27)."""
        return self.seed_mounted_adb(target_mount=target_mount, log_callback=log_callback)
