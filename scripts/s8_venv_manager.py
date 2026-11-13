#!/usr/bin/env python3
"""
scripts/s8_venv_manager.py — Universal Multi-OS Virtual Environment Manager & Tester
Creates, provisions, isolates, and tests official ARM64 Linux distributions in
non-destructive virtual environments without wiping the host Galaxy S8 OS:

  1. Backend `wsl-qemu`  : WSL2 Linux namespaces + binfmt_misc qemu-aarch64-static
  2. Backend `s8-device` : Live Exynos 8895 (4.4.111-s8-universal-v3) Linux namespaces
                           (ip netns + veth virtual NIC + private /dev + PID/MNT/UTS/IPC)
"""

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_APP_DIR = REPO_ROOT / "desktop-app"
DISTROS_DIR = REPO_ROOT / "distros"
HW_PACK_TAR = REPO_ROOT / "packages" / "dist" / "galaxy-s8-hw-universal-arm64.tar.gz"
LOGS_DIR = REPO_ROOT / "logs"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(DESKTOP_APP_DIR))

from app.core.adb import AdbClient  # noqa: E402
from app.core.distros import UPSTREAM_DISTROS  # noqa: E402
from app.core.flasher import extract_ext4_partition, is_disk_image_file  # noqa: E402

WSL_DISTRO = "Ubuntu-Noble"
WSL_VENV_ROOT = "/var/lib/s8-venvs"
S8_VENV_ROOT = "/mnt/android_data/venvs"
S8_RUNNER_PATH = f"{S8_VENV_ROOT}/_bin/s8venv_run.sh"

QEMU_AARCH64_BINFMT = (
    r":qemu-aarch64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    r"\x02\x00\xb7\x00:\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff"
    r"\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-aarch64-static:OCPF"
)

# Canonical device-side namespace isolation runner with veth virtual Ethernet + hardware passthrough
S8_RUNNER_SCRIPT = r"""#!/bin/sh
set -e
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

VENV_ID="$1"
ROOTFS="$2"
NET_IDX="$3"
CMD_SCRIPT="$4"

if [ -z "$VENV_ID" ] || [ -z "$ROOTFS" ] || [ -z "$NET_IDX" ] || [ -z "$CMD_SCRIPT" ]; then
    echo "Usage: s8venv_run.sh <id> <rootfs> <net_idx> <cmd_script>" >&2
    exit 2
fi
if [ ! -d "$ROOTFS" ]; then
    echo "[ERR] Rootfs not found: $ROOTFS" >&2
    exit 3
fi
if [ ! -f "$CMD_SCRIPT" ]; then
    echo "[ERR] Command script not found: $CMD_SCRIPT" >&2
    exit 4
fi

NS_NAME="s8v_${NET_IDX}_${VENV_ID}"
NS_NAME="$(echo "$NS_NAME" | tr -cd 'A-Za-z0-9_' | cut -c1-24)"
VETH_HOST="s8vh${NET_IDX}"
VETH_GUEST="s8vg${NET_IDX}"
HOST_IP="10.88.${NET_IDX}.1"
GUEST_IP="10.88.${NET_IDX}.2"
GUEST_HOSTNAME="s8-venv-${VENV_ID}"

cleanup() {
    ip netns del "$NS_NAME" 2>/dev/null || true
    ip link del "$VETH_HOST" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
cleanup

ip netns add "$NS_NAME"
ip link add "$VETH_HOST" type veth peer name "$VETH_GUEST"
ip addr add "${HOST_IP}/30" dev "$VETH_HOST"
ip link set "$VETH_HOST" up
ip link set "$VETH_GUEST" netns "$NS_NAME" name eth0
ip -n "$NS_NAME" link set lo up
ip -n "$NS_NAME" addr add "${GUEST_IP}/30" dev eth0
ip -n "$NS_NAME" link set eth0 up
ip -n "$NS_NAME" route add default via "$HOST_IP"

mkdir -p "$ROOTFS/proc" "$ROOTFS/sys" "$ROOTFS/dev" "$ROOTFS/tmp" "$ROOTFS/run" "$ROOTFS/etc"
if [ ! -f "$ROOTFS/etc/resolv.conf" ] || [ -L "$ROOTFS/etc/resolv.conf" ]; then
    rm -f "$ROOTFS/etc/resolv.conf" 2>/dev/null || true
    printf "nameserver 8.8.8.8\nnameserver 1.1.1.1\n" > "$ROOTFS/etc/resolv.conf"
fi

cp -f "$CMD_SCRIPT" "$ROOTFS/tmp/.s8venv_cmd.sh"
chmod 755 "$ROOTFS/tmp/.s8venv_cmd.sh"

export S8_VENV_ID="$VENV_ID"
export S8_VENV_HOST_IP="$HOST_IP"
export S8_VENV_GUEST_IP="$GUEST_IP"
export S8_VENV_HOSTNAME="$GUEST_HOSTNAME"
export S8_VENV_ROOTFS="$ROOTFS"

RC=0
ip netns exec "$NS_NAME" unshare --mount --pid --uts --ipc --fork /bin/sh -c '
    set -e
    R="$S8_VENV_ROOTFS"
    hostname "$S8_VENV_HOSTNAME"
    mount --make-rprivate / 2>/dev/null || true

    mount -t tmpfs -o mode=755 tmpfs "$R/dev"
    mkdir -p "$R/dev/pts" "$R/dev/shm" "$R/dev/net" "$R/dev/snd" "$R/dev/graphics"
    mknod -m 666 "$R/dev/null" c 1 3
    mknod -m 666 "$R/dev/zero" c 1 5
    mknod -m 666 "$R/dev/full" c 1 7
    mknod -m 666 "$R/dev/random" c 1 8
    mknod -m 666 "$R/dev/urandom" c 1 9
    mknod -m 666 "$R/dev/tty" c 5 0
    mount -t devpts -o newinstance,ptmxmode=0666 devpts "$R/dev/pts" 2>/dev/null || true
    ln -sf /dev/pts/ptmx "$R/dev/ptmx"
    ln -sf /proc/self/fd "$R/dev/fd"
    ln -sf /proc/self/fd/0 "$R/dev/stdin"
    ln -sf /proc/self/fd/1 "$R/dev/stdout"
    ln -sf /proc/self/fd/2 "$R/dev/stderr"

    for node in /dev/mali0 /dev/net/tun /dev/ion /dev/graphics/fb2; do
        if [ -e "$node" ]; then
            touch "$R$node"
            mount --bind "$node" "$R$node" 2>/dev/null || true
        fi
    done
    if [ -d /dev/snd ]; then
        mount --bind /dev/snd "$R/dev/snd" 2>/dev/null || true
    fi

    mount -t proc proc "$R/proc"
    mount -t tmpfs -o mode=1777 tmpfs "$R/run"
    if [ -d /sys ]; then
        mount --bind /sys "$R/sys" 2>/dev/null || true
        mount -o remount,ro,bind "$R/sys" 2>/dev/null || true
    fi

    mkdir -p "$R/tmp"
    chmod 1777 "$R/tmp"

    exec chroot "$R" /bin/sh -c "
        export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        export HOME=/root
        export TERM=xterm-256color
        exec /bin/sh /tmp/.s8venv_cmd.sh
    "
' || RC=$?
exit $RC
"""


@dataclass
class DistroProfile:
    id: str
    name: str
    filename: str
    pkg_mgr: str
    init_hint: str
    net_idx: int
    heavy: bool = False
    extra_probes: List[str] = field(default_factory=list)


def get_distro_profiles() -> List[DistroProfile]:
    """Return ordered list of all full ARM64 rootfs/disk distros supported for virtual environments."""
    by_filename = {d["filename"]: d for d in UPSTREAM_DISTROS}
    ordered_specs = [
        ("kali-nethunter", "Kali Linux ARM64 Minimal", "kali-nethunter-rootfs-minimal-arm64.tar.xz", "apt", "systemd", 11, False),
        ("openwrt-23.05", "OpenWrt 23.05.5 ARMv8 Router OS", "openwrt-23.05.5-armsr-armv8-rootfs.tar.gz", "opkg", "procd", 12, False),
        ("alpine-3.20", "Alpine Linux 3.20.3 Minirootfs", "alpine-minirootfs-3.20.3-aarch64.tar.gz", "apk", "openrc", 13, False),
        ("ubuntu-base-24.04", "Ubuntu 24.04.5 Minimal Base", "ubuntu-base-24.04.5-base-arm64.tar.gz", "apt", "systemd", 14, False),
        ("debian-12", "Debian 12 Bookworm Generic", "debian-12-generic-arm64.tar.xz", "apt", "systemd", 15, False),
        ("ubuntu-server-24.04", "Ubuntu 24.04 Server Rootfs", "ubuntu-24.04-server-rootfs-arm64.tar.xz", "apt", "systemd", 16, False),
        ("haos-18.4", "Home Assistant OS 18.4 ARM64", "haos_generic-aarch64-18.4.img.xz", "haos", "systemd", 17, False),
        ("arch-arm64", "Arch Linux ARM (aarch64)", "ArchLinuxARM-aarch64-latest.tar.gz", "pacman", "systemd", 18, False),
        ("raspios-bookworm", "Raspberry Pi OS Bookworm ARM64", "raspios-bookworm-arm64-desktop.img.xz", "apt", "systemd", 19, True),
        ("steamos-3.6", "SteamOS 3.6 Holo ARM64", "steamos-holo-1.4-arm64.tar.gz", "pacman", "systemd", 20, True),
        ("ubuntu-desktop-24.04", "Ubuntu 24.04.5 LTS Desktop", "ubuntu-24.04.5-preinstalled-desktop-arm64.img.xz", "apt", "systemd", 21, True),
    ]
    profiles = []
    for did, name, fname, pkg_mgr, init_hint, net_idx, heavy in ordered_specs:
        meta = by_filename.get(fname, {})
        profiles.append(
            DistroProfile(
                id=did,
                name=meta.get("name", name),
                filename=fname,
                pkg_mgr=pkg_mgr,
                init_hint=init_hint,
                net_idx=net_idx,
                heavy=heavy,
            )
        )
    return profiles


def win_to_wsl(p: Path) -> str:
    s = str(p.resolve()).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/mnt/{s[0].lower()}{s[2:]}"
    return s


def run_wsl(bash_script: str, timeout: int = 600, check: bool = True) -> subprocess.CompletedProcess:
    """Execute a multi-line bash script inside WSL2 Ubuntu-Noble as root cleanly via raw LF stdin."""
    payload = bash_script.replace("\r\n", "\n").encode("utf-8")
    proc = subprocess.run(
        ["wsl", "-d", WSL_DISTRO, "-u", "root", "--", "bash", "-s"],
        input=payload,
        capture_output=True,
        timeout=timeout,
    )
    proc = subprocess.CompletedProcess(
        args=proc.args,
        returncode=proc.returncode,
        stdout=proc.stdout.decode("utf-8", errors="replace"),
        stderr=proc.stderr.decode("utf-8", errors="replace"),
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"WSL command failed (rc={proc.returncode}):\nSTDOUT:\n{proc.stdout[-1500:]}\nSTDERR:\n{proc.stderr[-1500:]}"
        )
    return proc


def ensure_wsl_binfmt() -> None:
    """Register qemu-aarch64-static via binfmt_misc in WSL2 if not yet enabled."""
    script = f"""set -e
if [ ! -x /usr/bin/qemu-aarch64-static ]; then
    echo "[ERR] /usr/bin/qemu-aarch64-static missing in WSL" >&2
    exit 1
fi
if [ ! -e /proc/sys/fs/binfmt_misc/qemu-aarch64 ]; then
    printf '%s\\n' '{QEMU_AARCH64_BINFMT}' > /proc/sys/fs/binfmt_misc/register
fi
grep -q '^enabled' /proc/sys/fs/binfmt_misc/qemu-aarch64
echo "WSL_BINFMT_READY"
"""
    res = run_wsl(script, timeout=30)
    if "WSL_BINFMT_READY" not in res.stdout:
        raise RuntimeError(f"Failed to verify binfmt_misc: {res.stdout} {res.stderr}")


def _build_in_guest_test_script(profile: DistroProfile, is_device: bool) -> str:
    """Return POSIX /bin/sh validation commands tailored uniformly for every distro."""
    common = f"""#!/bin/sh
echo "=== VENV IDENTITY ==="
echo "ENV_ID={profile.id}"
echo "UNAME=$(uname -a)"
echo "ARCH=$(uname -m)"
echo "HOST=$(uname -n)"
echo "PID=$$"
if [ -f /etc/os-release ]; then
    grep -E '^(PRETTY_NAME|NAME|ID|VERSION_ID)=' /etc/os-release | head -n 5
elif [ -f /etc/openwrt_release ]; then
    cat /etc/openwrt_release
fi

echo "=== HARDWARE PACK & PERMISSIONS ==="
which s8ctl 2>/dev/null || ls -la /usr/local/bin/s8ctl /usr/bin/s8ctl 2>/dev/null || true
s8ctl --version 2>&1 || true
grep -E '^(aid_inet|aid_net_raw|aid_net_admin|aid_graphics):' /etc/group || echo "WARN_NO_AID_GROUPS"
ls -la /etc/asound.conf /etc/apt/apt.conf.d/99-s8-sandbox 2>/dev/null || true

echo "=== PACKAGE MANAGER & PYTHON VENV ==="
"""
    if profile.pkg_mgr == "apt":
        common += r"""
which apt-get dpkg || true
apt-get --version 2>&1 | head -n 1 || true
dpkg --version 2>&1 | head -n 1 || true
dpkg -l 2>/dev/null | wc -l | awk '{print "DPKG_PKGS=" $1}'
"""
    elif profile.pkg_mgr == "opkg":
        common += r"""
which opkg uci procd ubus ubusd dnsmasq iptables 2>/dev/null || true
opkg --version 2>&1 || true
opkg list-installed 2>/dev/null | head -n 8 || true
uci show dropbear 2>&1 | head -n 6 || uci show firewall 2>&1 | head -n 6 || true
mkdir -p /etc/config /tmp/uci_test
uci -c /tmp/uci_test set network.s8venv=interface 2>/dev/null || true
uci -c /tmp/uci_test set network.s8venv.proto=static 2>/dev/null || true
uci -c /tmp/uci_test show network 2>/dev/null | grep -q s8venv && echo "OPENWRT_UCI_RW_OK" || true
rm -rf /tmp/uci_test
"""
    elif profile.pkg_mgr == "apk":
        common += r"""
which apk rc-service busybox || true
apk --version 2>&1 || true
apk info 2>/dev/null | wc -l | awk '{print "APK_PKGS=" $1}'
"""
    elif profile.pkg_mgr == "pacman":
        common += r"""
which pacman systemctl || true
pacman --version 2>&1 | head -n 2 || true
pacman -Q 2>/dev/null | wc -l | awk '{print "PACMAN_PKGS=" $1}'
"""
    elif profile.pkg_mgr == "haos":
        common += r"""
ls -la /usr/sbin/hassos-supervisor /usr/bin/docker /usr/bin/os-agent /lib/systemd/systemd 2>/dev/null || true
which systemctl docker apk 2>/dev/null || true
"""

    common += r"""
if command -v python3 >/dev/null 2>&1; then
    echo "PYTHON3=$(python3 --version 2>&1)"
    rm -rf /tmp/s8_pyvenv_chk
    if python3 -m venv /tmp/s8_pyvenv_chk >/dev/null 2>&1; then
        /tmp/s8_pyvenv_chk/bin/python -c "import sys, socket; print('PY_VENV_OK prefix=' + sys.prefix)"
        rm -rf /tmp/s8_pyvenv_chk
    else
        echo "PY_VENV_SKIP_MINIMAL (python3-venv/ensurepip not preinstalled)"
    fi
else
    echo "PYTHON3_ABSENT (minimal upstream rootfs)"
fi
"""

    if is_device:
        common += f"""
echo "=== S8 ISOLATED NAMESPACE & HARDWARE ==="
grep -q "10.88.{profile.net_idx}.2" /proc/net/fib_trie 2>/dev/null && echo "KERNEL_VETH_IP_OK=10.88.{profile.net_idx}.2" || true
ip addr show eth0 2>/dev/null | head -n 6 || /sbin/ip addr show eth0 2>/dev/null | head -n 6 || ifconfig eth0 2>/dev/null || true
if command -v ping >/dev/null 2>&1; then
    ping -c 2 -W 1 10.88.{profile.net_idx}.1 2>&1 | tail -n 3
else
    echo "PING_BIN_ABSENT"
fi
ls -la /dev/mali0 /dev/net/tun /dev/snd /dev/graphics/fb2 2>/dev/null || true
ls /dev/video100 2>/dev/null && echo "FAIL_V4L2_LEAK" || echo "V4L2_GUARD_OK"
s8ctl status 2>&1 | head -n 14 || true
"""
        if profile.id == "kali-nethunter":
            common += r"""
echo "=== KALI SECURITY & RAW SOCKET PROBE ==="
if command -v python3 >/dev/null 2>&1; then
    python3 -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP); s.close(); print('KALI_RAW_SOCKET_OK')"
fi
[ -c /dev/net/tun ] && echo "KALI_DEV_NET_TUN_OK"
"""
        elif profile.id == "openwrt-23.05":
            common += r"""
echo "=== OPENWRT VIRTUAL ROUTER & UCI PROBE ==="
if command -v ip >/dev/null 2>&1 || [ -x /sbin/ip ]; then
    ip link add br-lan type bridge 2>&1 && ip addr add 192.168.88.1/24 dev br-lan && ip link set br-lan up && echo "OPENWRT_BRLAN_BRIDGE_OK" || echo "OPENWRT_BRIDGE_FALLBACK"
    ip link del br-lan 2>/dev/null || true
fi
/sbin/procd -h 2>&1 | head -n 2 || ls -l /sbin/procd
"""
        elif profile.id == "steamos-3.6":
            common += r"""
echo "=== STEAMOS GAMING RUNTIME PROBE ==="
ls -la /usr/lib/libGL.so* /usr/lib/libvulkan* 2>/dev/null | head -n 6 || true
which glxgears gamescope steam 2>/dev/null || true
"""
    return common + "\necho 'ALL_VENV_CHECKS_DONE'\n"


class S8VenvManager:
    """Creates and validates isolated PC (WSL QEMU) and on-device Exynos 8895 virtual environments."""

    def __init__(self, adb: Optional[AdbClient] = None):
        self.adb = adb or AdbClient()
        self.profiles = {p.id: p for p in get_distro_profiles()}

    def get_profile(self, distro_id: str) -> DistroProfile:
        if distro_id not in self.profiles:
            raise KeyError(f"Unknown distro id '{distro_id}'. Available: {', '.join(self.profiles)}")
        return self.profiles[distro_id]

    # ---------------- WSL2 QEMU ARM64 VIRTUAL ENVIRONMENTS ----------------
    def prepare_wsl_venv(self, distro_id: str, force: bool = False) -> Path:
        """Unpack official upstream image into WSL2 /var/lib/s8-venvs/<id>/rootfs and inject galaxy-s8-hw."""
        profile = self.get_profile(distro_id)
        src = DISTROS_DIR / profile.filename
        if not src.is_file():
            raise FileNotFoundError(f"Upstream distro archive missing: {src}")
        if not HW_PACK_TAR.is_file():
            raise FileNotFoundError(f"Hardware package missing: {HW_PACK_TAR}")

        ensure_wsl_binfmt()
        venv_dir = f"{WSL_VENV_ROOT}/{profile.id}"
        rootfs_dir = f"{venv_dir}/rootfs"
        meta_file = f"{venv_dir}/.s8_venv_meta.json"

        chk = run_wsl(f"test -f '{meta_file}' && echo READY || echo MISSING", check=False)
        if not force and "READY" in chk.stdout:
            return Path(rootfs_dir)

        wsl_src = win_to_wsl(src)
        wsl_hw = win_to_wsl(HW_PACK_TAR)

        temp_img_dir: Optional[tempfile.TemporaryDirectory] = None
        wsl_img_path = ""

        try:
            if is_disk_image_file(src):
                temp_img_dir = tempfile.TemporaryDirectory(prefix=f"s8_venv_{profile.id}_")
                out_raw = Path(temp_img_dir.name) / "rootfs.img"
                print(f"[wsl-qemu] Extracting ext4 partition from {src.name}...")
                extracted = extract_ext4_partition(
                    src,
                    out_raw,
                    log_callback=lambda m: print(f"    {m}"),
                )
                wsl_img_path = win_to_wsl(extracted)
                extract_cmd = f"""
rm -rf '{rootfs_dir}' /tmp/s8_vmnt_{profile.id}
mkdir -p '{rootfs_dir}' /tmp/s8_vmnt_{profile.id}
cp -f '{wsl_img_path}' /tmp/s8_vimg_{profile.id}.img
e2fsck -p /tmp/s8_vimg_{profile.id}.img >/dev/null 2>&1 || true
mount -o ro,loop /tmp/s8_vimg_{profile.id}.img /tmp/s8_vmnt_{profile.id}
tar -C /tmp/s8_vmnt_{profile.id} --numeric-owner -cf - . | tar -C '{rootfs_dir}' --numeric-owner -xf -
umount /tmp/s8_vmnt_{profile.id}
rm -rf /tmp/s8_vmnt_{profile.id} /tmp/s8_vimg_{profile.id}.img
"""
            else:
                tar_flag = "-xJf" if profile.filename.endswith(".xz") else "-xzf"
                extract_cmd = f"""
rm -rf '{rootfs_dir}'
mkdir -p '{rootfs_dir}'
tar -C '{rootfs_dir}' --numeric-owner {tar_flag} '{wsl_src}'
# Flatten single wrapper folder if present (e.g. kali-nethunter -> kali-arm64/)
shopt -s dotglob nullglob
if [ -d '{rootfs_dir}/kali-arm64/bin' ] || [ -d '{rootfs_dir}/kali-arm64/usr' ]; then
    mv '{rootfs_dir}/kali-arm64/'* '{rootfs_dir}/' 2>/dev/null || true
    rmdir '{rootfs_dir}/kali-arm64' 2>/dev/null || true
fi
shopt -u dotglob nullglob
"""

            provision_script = f"""set -e
if [ ! -e /proc/sys/fs/binfmt_misc/qemu-aarch64 ]; then
    printf '%s\\n' '{QEMU_AARCH64_BINFMT}' > /proc/sys/fs/binfmt_misc/register
fi
mkdir -p '{WSL_VENV_ROOT}' '{venv_dir}'
{extract_cmd}
mkdir -p '{rootfs_dir}/tmp' '{rootfs_dir}/proc' '{rootfs_dir}/dev' '{rootfs_dir}/sys' '{rootfs_dir}/etc'
chmod 1777 '{rootfs_dir}/tmp'
rm -f '{rootfs_dir}/etc/resolv.conf'
printf "nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n" > '{rootfs_dir}/etc/resolv.conf'

# Inject universal galaxy-s8-hw Stage 2 suite cleanly using POSIX sh
rm -rf '{rootfs_dir}/tmp/s8hw'
mkdir -p '{rootfs_dir}/tmp/s8hw'
tar -C '{rootfs_dir}/tmp/s8hw' -xzf '{wsl_hw}'
PKG_DIR="$(find '{rootfs_dir}/tmp/s8hw' -maxdepth 1 -mindepth 1 -type d | head -n 1)"
REL_PKG="${{PKG_DIR#'{rootfs_dir}'}}"
chroot '{rootfs_dir}' /bin/sh -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; /bin/sh '$REL_PKG/install.sh' --profile=core"
rm -rf '{rootfs_dir}/tmp/s8hw'

cat > '{meta_file}' <<'JSONEOF'
{{"id": "{profile.id}", "filename": "{profile.filename}", "hw_pack": "1.0.3", "prepared_at": "{time.strftime('%Y-%m-%dT%H:%M:%S')}"}}
JSONEOF
du -sh '{rootfs_dir}'
"""
            print(f"[wsl-qemu] Preparing & injecting galaxy-s8-hw into {profile.id}...")
            res = run_wsl(provision_script, timeout=900)
            print(f"    Rootfs staged: {res.stdout.strip().splitlines()[-1]}")
        finally:
            if temp_img_dir is not None:
                temp_img_dir.cleanup()

        return Path(rootfs_dir)

    def exec_wsl_venv(self, distro_id: str, shell_cmd: str, timeout: int = 180) -> Tuple[int, str]:
        """Run a shell command inside isolated WSL2 ARM64 QEMU virtual environment namespaces."""
        profile = self.get_profile(distro_id)
        rootfs_dir = f"{WSL_VENV_ROOT}/{profile.id}/rootfs"
        ensure_wsl_binfmt()

        script = f"""set -e
if [ ! -e /proc/sys/fs/binfmt_misc/qemu-aarch64 ]; then
    printf '%s\\n' '{QEMU_AARCH64_BINFMT}' > /proc/sys/fs/binfmt_misc/register
fi
R='{rootfs_dir}'
if [ ! -d "$R/etc" ]; then
    echo "[ERR] WSL venv rootfs missing for {profile.id}" >&2
    exit 3
fi
cat > "$R/tmp/.s8wsl_cmd.sh" <<'INNERCMDEOF'
{shell_cmd}
INNERCMDEOF
chmod 755 "$R/tmp/.s8wsl_cmd.sh"

export S8_WSL_R="$R"
export S8_WSL_HOST="s8-wsl-{profile.id}"

unshare --mount --pid --uts --ipc --fork /bin/sh -c '
    set -e
    R="$S8_WSL_R"
    hostname "$S8_WSL_HOST"
    mount --make-rprivate /
    mount -t tmpfs -o mode=755 tmpfs "$R/dev"
    mknod -m 666 "$R/dev/null" c 1 3
    mknod -m 666 "$R/dev/zero" c 1 5
    mknod -m 666 "$R/dev/urandom" c 1 9
    mkdir -p "$R/dev/pts" "$R/proc" "$R/tmp"
    chmod 1777 "$R/tmp"
    mount -t proc proc "$R/proc" 2>/dev/null || true
    exec chroot "$R" /bin/sh -c "
        export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        export HOME=/root
        exec /bin/sh /tmp/.s8wsl_cmd.sh
    "
'
"""
        proc = run_wsl(script, timeout=timeout, check=False)
        out = (proc.stdout or "") + ("\n[STDERR]\n" + proc.stderr if proc.stderr else "")
        return proc.returncode, out.strip()

    def test_wsl_venv(self, distro_id: str) -> Dict:
        profile = self.get_profile(distro_id)
        t0 = time.time()
        self.prepare_wsl_venv(distro_id)
        rc, out = self.exec_wsl_venv(distro_id, _build_in_guest_test_script(profile, is_device=False))
        elapsed = round(time.time() - t0, 2)
        passed = (
            rc == 0
            and "ARCH=aarch64" in out
            and "s8ctl v1.0.3" in out
            and "ALL_VENV_CHECKS_DONE" in out
        )
        return {
            "backend": "wsl-qemu",
            "id": profile.id,
            "name": profile.name,
            "passed": passed,
            "returncode": rc,
            "elapsed_sec": elapsed,
            "output": out,
        }

    # ---------------- GALAXY S8 ON-DEVICE VIRTUAL ENVIRONMENTS ----------------
    def ensure_s8_runner(self) -> None:
        """Install canonical isolated namespace runner script on live Galaxy S8 via HTTP push."""
        with tempfile.TemporaryDirectory(prefix="s8runner_") as tmpd:
            local_sh = Path(tmpd) / "s8venv_run.sh"
            local_sh.write_bytes(S8_RUNNER_SCRIPT.replace("\r\n", "\n").encode("utf-8"))
            ok, err = self.adb.push_rwp_http(str(local_sh), S8_RUNNER_PATH, timeout=60)
            if not ok:
                raise RuntimeError(f"Failed to push on-device venv runner: {err}")
        out = self.adb.exec_os(f"chmod 755 '{S8_RUNNER_PATH}' && test -x '{S8_RUNNER_PATH}' && echo S8_RUNNER_OK", timeout=20)
        if "S8_RUNNER_OK" not in out:
            raise RuntimeError(f"Failed to verify on-device venv runner: {out}")

    def _get_s8_free_gb(self) -> float:
        out = self.adb.exec_os("df -k /mnt/android_data | tail -n 1", timeout=15)
        parts = out.strip().split()
        if len(parts) >= 4 and parts[3].isdigit():
            return round(int(parts[3]) / (1024 * 1024), 2)
        return 0.0

    def create_s8_venv(self, distro_id: str, force: bool = False, min_free_gb: float = 4.0) -> str:
        """Provision isolated virtual environment rootfs on Galaxy S8 (/mnt/android_data/venvs/<id>)."""
        profile = self.get_profile(distro_id)
        self.ensure_s8_runner()
        remote_dir = f"{S8_VENV_ROOT}/{profile.id}"
        remote_rootfs = f"{remote_dir}/rootfs"
        remote_meta = f"{remote_dir}/.s8_venv_meta.json"

        chk = self.adb.exec_os(f"test -f '{remote_meta}' && echo S8_VENV_READY || echo MISSING", timeout=15)
        if not force and "S8_VENV_READY" in chk:
            return remote_rootfs

        free_gb = self._get_s8_free_gb()
        if free_gb < min_free_gb:
            raise RuntimeError(f"Insufficient free space on /mnt/android_data ({free_gb} GB < {min_free_gb} GB)")

        self.prepare_wsl_venv(distro_id)

        temp_bundle_dir = tempfile.TemporaryDirectory(prefix=f"s8_push_{profile.id}_")
        try:
            bundle_win = Path(temp_bundle_dir.name) / f"{profile.id}_rootfs.tar.gz"
            bundle_wsl = win_to_wsl(bundle_win)
            src_rootfs = f"{WSL_VENV_ROOT}/{profile.id}/rootfs"
            print(f"[s8-device] Packing normalized rootfs bundle for {profile.id}...")
            run_wsl(
                f"tar -C '{src_rootfs}' --exclude='./proc/*' --exclude='./sys/*' --exclude='./dev/*' "
                f"--numeric-owner -cf - . | gzip -1 > '{bundle_wsl}'",
                timeout=900,
            )
            size_mb = round(bundle_win.stat().st_size / (1024 * 1024), 2)
            print(f"[s8-device] Pushing {size_mb} MB over USB RNDIS HTTP to {remote_dir}...")
            remote_tar = f"{remote_dir}/rootfs.tar.gz"
            ok, err = self.adb.push_rwp_http(str(bundle_win), remote_tar, timeout=1800)
            if not ok:
                raise RuntimeError(f"push_rwp_http failed for {profile.id}: {err}")

            log_tar = f"/tmp/s8_untar_{profile.id}.log"
            unpack_cmd = (
                f"rm -rf '{remote_rootfs}' && mkdir -p '{remote_rootfs}' && "
                f"tar -C '{remote_rootfs}' --numeric-owner -m -xzf '{remote_tar}' > '{log_tar}' 2>&1; RC=$?; "
                f"rm -f '{remote_tar}'; "
                f"if [ $RC -eq 0 ]; then "
                f"printf '{{\"id\":\"{profile.id}\",\"hw_pack\":\"1.0.3\"}}\\n' > '{remote_meta}'; "
                f"echo S8_VENV_UNPACKED; "
                f"else tail -n 30 '{log_tar}'; fi; rm -f '{log_tar}'"
            )
            unpack_out = self.adb.exec_os(unpack_cmd, timeout=1800)
            if "S8_VENV_UNPACKED" not in unpack_out:
                raise RuntimeError(f"On-device rootfs unpack failed: {unpack_out}")
        finally:
            temp_bundle_dir.cleanup()

        return remote_rootfs

    def exec_s8_venv(self, distro_id: str, shell_cmd: str, timeout: int = 120) -> Tuple[int, str]:
        """Run a shell command inside isolated Exynos 8895 namespaces + veth network on the Galaxy S8."""
        profile = self.get_profile(distro_id)
        remote_rootfs = f"{S8_VENV_ROOT}/{profile.id}/rootfs"
        remote_cmd_path = f"{S8_VENV_ROOT}/_bin/cmd_{profile.id}.sh"
        with tempfile.TemporaryDirectory(prefix="s8cmd_") as tmpd:
            local_cmd = Path(tmpd) / "cmd.sh"
            local_cmd.write_bytes(shell_cmd.replace("\r\n", "\n").encode("utf-8"))
            ok, err = self.adb.push_rwp_http(str(local_cmd), remote_cmd_path, timeout=60)
            if not ok:
                return 1, f"Failed to push guest command script: {err}"
        run_cmd = (
            f"sh '{S8_RUNNER_PATH}' '{profile.id}' '{remote_rootfs}' '{profile.net_idx}' '{remote_cmd_path}'; "
            f"echo __S8VENV_RC=$?"
        )
        out = self.adb.exec_os(run_cmd, timeout=timeout)
        rc = 1
        lines = out.splitlines()
        cleaned = []
        for ln in lines:
            if ln.startswith("__S8VENV_RC="):
                try:
                    rc = int(ln.split("=", 1)[1].strip())
                except ValueError:
                    pass
            else:
                cleaned.append(ln)
        return rc, "\n".join(cleaned).strip()

    def test_s8_venv(self, distro_id: str, prune_after: bool = False) -> Dict:
        profile = self.get_profile(distro_id)
        t0 = time.time()
        self.create_s8_venv(distro_id)
        rc, out = self.exec_s8_venv(distro_id, _build_in_guest_test_script(profile, is_device=True))
        if prune_after:
            self.remove_s8_venv(distro_id)
        elapsed = round(time.time() - t0, 2)

        veth_ok = (
            ("2 packets transmitted, 2 received" in out)
            or ("0% packet loss" in out)
            or (
                "PING_BIN_ABSENT" in out
                and (
                    f"10.88.{profile.net_idx}.2" in out
                    or f"KERNEL_VETH_IP_OK=10.88.{profile.net_idx}.2" in out
                )
            )
        )

        passed = (
            rc == 0
            and "ARCH=aarch64" in out
            and f"HOST=s8-venv-{profile.id}" in out
            and "s8ctl v1.0.3" in out
            and "V4L2_GUARD_OK" in out
            and veth_ok
            and "ALL_VENV_CHECKS_DONE" in out
        )
        return {
            "backend": "s8-device",
            "id": profile.id,
            "name": profile.name,
            "passed": passed,
            "pruned_heavy": prune_after,
            "returncode": rc,
            "elapsed_sec": elapsed,
            "output": out,
        }

    def remove_s8_venv(self, distro_id: str) -> None:
        profile = self.get_profile(distro_id)
        self.adb.exec_os(f"rm -rf '{S8_VENV_ROOT}/{profile.id}'", timeout=60)

    def remove_wsl_venv(self, distro_id: str) -> None:
        profile = self.get_profile(distro_id)
        run_wsl(f"rm -rf '{WSL_VENV_ROOT}/{profile.id}'", timeout=60)

    def list_venvs(self) -> Dict:
        wsl_res = run_wsl(
            f"for d in '{WSL_VENV_ROOT}'/*; do [ -f \"$d/.s8_venv_meta.json\" ] && du -sh \"$d\"; done || true",
            check=False,
        )
        s8_out = self.adb.exec_os(
            f"for d in '{S8_VENV_ROOT}'/*; do [ -f \"$d/.s8_venv_meta.json\" ] && du -sh \"$d\"; done || true",
            timeout=30,
        )
        return {
            "wsl_qemu": wsl_res.stdout.strip(),
            "s8_device": s8_out.strip(),
            "s8_free_gb": self._get_s8_free_gb(),
        }


def main():
    parser = argparse.ArgumentParser(description="Galaxy S8 Universal Multi-OS Virtual Environment Manager")
    parser.add_argument(
        "action",
        choices=["list", "create", "exec", "test", "test-all", "rm"],
        help="Operation to perform",
    )
    parser.add_argument("--distro", default="kali-nethunter", help="Distro id (e.g., kali-nethunter, openwrt-23.05, all)")
    parser.add_argument(
        "--backend",
        choices=["wsl-qemu", "s8-device", "both"],
        default="both",
        help="Virtual environment backend",
    )
    parser.add_argument("--cmd", default="uname -a && s8ctl status", help="Shell command for exec")
    parser.add_argument("--force", action="store_true", help="Rebuild virtual environment even if cached")
    parser.add_argument("--prune-heavy", action="store_true", help="Prune >2.5 GB device venv rootfs after pass")
    parser.add_argument("--report", default=str(LOGS_DIR / "venv_matrix_report.json"), help="JSON output report path")
    args = parser.parse_args()

    mgr = S8VenvManager()

    if args.action == "list":
        info = mgr.list_venvs()
        print("=== S8 VENV INVENTORY ===")
        print(f"S8 /mnt/android_data Free: {info['s8_free_gb']} GB")
        print("--- WSL2 QEMU Environments ---")
        print(info["wsl_qemu"] or "(none)")
        print("--- Galaxy S8 Device Environments ---")
        print(info["s8_device"] or "(none)")
        print("--- Supported Catalog ---")
        for p in get_distro_profiles():
            print(f"  {p.id:20s} | pkg={p.pkg_mgr:6s} | init={p.init_hint:7s} | heavy={p.heavy}")
        return

    if args.action == "create":
        if args.backend in ("wsl-qemu", "both"):
            p = mgr.prepare_wsl_venv(args.distro, force=args.force)
            print(f"[OK] WSL QEMU venv ready: {p}")
        if args.backend in ("s8-device", "both"):
            p = mgr.create_s8_venv(args.distro, force=args.force)
            print(f"[OK] Galaxy S8 device venv ready: {p}")
        return

    if args.action == "exec":
        if args.backend in ("wsl-qemu", "both"):
            rc, out = mgr.exec_wsl_venv(args.distro, args.cmd)
            print(f"[wsl-qemu rc={rc}]\n{out}")
        if args.backend in ("s8-device", "both"):
            rc, out = mgr.exec_s8_venv(args.distro, args.cmd)
            print(f"[s8-device rc={rc}]\n{out}")
        return

    if args.action == "rm":
        if args.backend in ("wsl-qemu", "both"):
            mgr.remove_wsl_venv(args.distro)
            print(f"[OK] Removed WSL venv {args.distro}")
        if args.backend in ("s8-device", "both"):
            mgr.remove_s8_venv(args.distro)
            print(f"[OK] Removed S8 venv {args.distro}")
        return

    targets = get_distro_profiles() if args.action == "test-all" or args.distro == "all" else [mgr.get_profile(args.distro)]
    results = []
    for prof in targets:
        print("=" * 72)
        print(f"[VENV TEST] {prof.id} ({prof.name})")
        print("=" * 72)
        if args.backend in ("wsl-qemu", "both"):
            r_wsl = mgr.test_wsl_venv(prof.id)
            results.append(r_wsl)
            print(f"  -> wsl-qemu  : {'PASS' if r_wsl['passed'] else 'FAIL'} ({r_wsl['elapsed_sec']}s)")
            if not r_wsl["passed"]:
                print(r_wsl["output"][-1000:])
        if args.backend in ("s8-device", "both"):
            prune = args.prune_heavy and prof.heavy
            r_s8 = mgr.test_s8_venv(prof.id, prune_after=prune)
            results.append(r_s8)
            print(f"  -> s8-device : {'PASS' if r_s8['passed'] else 'FAIL'} ({r_s8['elapsed_sec']}s)")
            if not r_s8["passed"]:
                print(r_s8["output"][-1200:])

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report)
    report_path.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    passed_cnt = sum(1 for r in results if r["passed"])
    print("=" * 72)
    print(f"[SUMMARY] Virtual Environment Matrix: {passed_cnt}/{len(results)} Passed | Report: {report_path}")
    if passed_cnt != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
