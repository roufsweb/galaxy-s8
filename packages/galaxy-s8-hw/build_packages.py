#!/usr/bin/env python3
"""
build_packages.py -- Builds Galaxy S8 Hardware Pack (.deb + universal .tar.gz)
from tracked source modules (src/) and packages/galaxy-s8-hw/ definitions.

Usage (WSL / Linux with dpkg-deb and aarch64-linux-gnu-gcc):
    python3 packages/galaxy-s8-hw/build_packages.py
"""

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

PKG_NAME = "galaxy-s8-hw"
PKG_VERSION = "1.0.0"
PKG_ARCH = "arm64"

PKG_DIR = Path(__file__).resolve().parent
REPO_ROOT = PKG_DIR.parent.parent
DIST_DIR = REPO_ROOT / "packages" / "dist"


def write_lf_file(src: Path, dst: Path, mode: int):
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes().replace(b"\r\n", b"\n")
    dst.write_bytes(data)
    os.chmod(dst, mode)


def write_lf_bytes(dst: Path, text: str, mode: int):
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
    os.chmod(dst, mode)


def copy_bin(src: Path, dst: Path, mode: int = 0o755):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    os.chmod(dst, mode)


def compile_static_button_daemon(out_bin: Path):
    src_c = REPO_ROOT / "src" / "drivers" / "s8_button_daemon.c"
    compiler = shutil.which("aarch64-linux-gnu-gcc") or (
        shutil.which("gcc") if os.uname().machine == "aarch64" else None
    )
    if not compiler:
        raise RuntimeError("aarch64-linux-gnu-gcc not found; run inside WSL2 or ARM64 Linux.")
    out_bin.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [compiler, "-O2", "-Wall", "-static", str(src_c), "-o", str(out_bin)],
        check=True,
    )
    strip_tool = shutil.which("aarch64-linux-gnu-strip") or shutil.which("strip")
    if strip_tool:
        subprocess.run([strip_tool, str(out_bin)], check=False)
    os.chmod(out_bin, 0o755)
    print(f"[build] Compiled static s8_button_daemon ({out_bin.stat().st_size:,} B)")


def stage_rootfs(root: Path):
    usr_bin = root / "usr" / "local" / "bin"
    libexec = root / "usr" / "local" / "libexec"
    udev_dir = root / "etc" / "udev" / "rules.d"
    sysd_dir = root / "etc" / "systemd" / "system"
    logind_dir = root / "etc" / "systemd" / "logind.conf.d"
    initd_dir = root / "etc" / "init.d"

    # 1. Static ARM64 binaries
    compile_static_button_daemon(usr_bin / "s8_button_daemon")

    dp_prebuilt = PKG_DIR / "prebuilt" / "exynos_dp_bridge"
    if dp_prebuilt.is_file():
        copy_bin(dp_prebuilt, usr_bin / "exynos_dp_bridge", 0o755)
        print(f"[build] Staged exynos_dp_bridge ({dp_prebuilt.stat().st_size:,} B)")
    else:
        print("[warn] prebuilt/exynos_dp_bridge not found; skipping optional HDMI bridge ELF.")

    # 2. Tracked control/network/audio/driver scripts
    script_map = [
        (REPO_ROOT / "src" / "control" / "s8ctl.py", usr_bin / "s8ctl"),
        (REPO_ROOT / "src" / "control" / "s8_led_supervisor.py", usr_bin / "s8_led_supervisor.py"),
        (REPO_ROOT / "src" / "network" / "s8_wifi.py", usr_bin / "s8_wifi.py"),
        (REPO_ROOT / "src" / "network" / "start_bluetooth.sh", usr_bin / "start_bluetooth.sh"),
        (REPO_ROOT / "src" / "audio" / "init_audio.sh", usr_bin / "init_audio.sh"),
        (REPO_ROOT / "src" / "drivers" / "s8-dp", usr_bin / "s8-dp"),
        (REPO_ROOT / "src" / "drivers" / "s8_typec_daemon.py", usr_bin / "s8_typec_daemon.py"),
        (PKG_DIR / "scripts" / "s8-hardware-init.sh", usr_bin / "s8-hardware-init.sh"),
        (PKG_DIR / "scripts" / "s8-usb-gadget.sh", usr_bin / "s8-usb-gadget.sh"),
        (PKG_DIR / "scripts" / "s8-time-sync.py", usr_bin / "s8-time-sync.py"),
        (PKG_DIR / "scripts" / "s8-dp-bridge.sh", usr_bin / "s8-dp-bridge.sh"),
        (PKG_DIR / "scripts" / "s8-vnc-setup.sh", usr_bin / "s8-vnc-setup.sh"),
        (PKG_DIR / "scripts" / "galaxy-s8-hw-setup.sh", libexec / "galaxy-s8-hw-setup.sh"),
    ]
    for src, dst in script_map:
        write_lf_file(src, dst, 0o755)

    # 3. ALSA, udev rules, logind, systemd units, OpenRC fallback
    write_lf_file(REPO_ROOT / "src" / "audio" / "asound.conf", root / "etc" / "asound.conf", 0o644)

    for rule in (PKG_DIR / "udev").glob("*.rules"):
        write_lf_file(rule, udev_dir / rule.name, 0o644)

    write_lf_file(PKG_DIR / "systemd" / "99-s8-power.conf", logind_dir / "99-s8-power.conf", 0o644)
    for unit in (PKG_DIR / "systemd").glob("*.service"):
        write_lf_file(unit, sysd_dir / unit.name, 0o644)

    write_lf_file(PKG_DIR / "init.d" / "s8-hardware", initd_dir / "s8-hardware", 0o755)


def build_deb(stage_dir: Path) -> Path:
    deb_root = stage_dir / "deb_pkg"
    shutil.rmtree(deb_root, ignore_errors=True)
    stage_rootfs(deb_root)

    debian_dir = deb_root / "DEBIAN"
    debian_dir.mkdir(parents=True, exist_ok=True)

    control_txt = (
        f"Package: {PKG_NAME}\n"
        f"Version: {PKG_VERSION}\n"
        f"Section: admin\n"
        f"Priority: optional\n"
        f"Architecture: {PKG_ARCH}\n"
        f"Maintainer: Galaxy S8 Native Linux Project <rouf@localhost>\n"
        f"Recommends: python3, dnsmasq, alsa-utils, bluez, rfkill, libx11-6, libxfixes3, openssh-server, tigervnc-standalone-server, novnc, websockify\n"
        f"Description: Samsung Galaxy S8 (SM-G950N Exynos 8895) Hardware Pack\n"
        f" Adds native MAX77865 1500mA PMIC fast charge, V4L2 FIMC-IS2 panic guard,\n"
        f" ConfigFS USB RNDIS gadget, chassis button daemon (long-press poweroff),\n"
        f" Broadcom BCM4361 Wi-Fi/BT init, Calliope ABOX ALSA audio, ZRAM, MicroSD,\n"
        f" RGB LED supervisor, Type-C role manager, USB-C DisplayPort bridge, and s8ctl.\n"
    )
    write_lf_bytes(debian_dir / "control", control_txt, 0o644)

    postinst_txt = (
        "#!/bin/bash\n"
        "set -e\n"
        "if [ \"$1\" = \"configure\" ] || [ \"$1\" = \"triggered\" ]; then\n"
        "    /usr/local/libexec/galaxy-s8-hw-setup.sh\n"
        "fi\n"
        "exit 0\n"
    )
    write_lf_bytes(debian_dir / "postinst", postinst_txt, 0o755)

    prerm_txt = (
        "#!/bin/bash\n"
        "set -e\n"
        "if [ \"$1\" = \"remove\" ] && [ -d /run/systemd/system ] && command -v systemctl >/dev/null 2>&1; then\n"
        "    for svc in s8-dp-bridge.service s8-novnc-ws.service s8-vnc.service s8-buttons.service s8-typec.service s8-led.service s8-time-sync.service s8-bluetooth.service s8-usb-gadget.service s8-hardware.service; do\n"
        "        systemctl disable --now \"$svc\" 2>/dev/null || true\n"
        "    done\n"
        "fi\n"
        "exit 0\n"
    )
    write_lf_bytes(debian_dir / "prerm", prerm_txt, 0o755)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    deb_path = DIST_DIR / f"{PKG_NAME}_{PKG_VERSION}_{PKG_ARCH}.deb"
    dpkg_deb = shutil.which("dpkg-deb")
    if not dpkg_deb:
        raise RuntimeError("dpkg-deb not found; run inside WSL2 or Debian/Ubuntu.")
    subprocess.run([dpkg_deb, "--root-owner-group", "--build", str(deb_root), str(deb_path)], check=True)
    print(f"[build] Built {deb_path} ({deb_path.stat().st_size:,} B)")
    return deb_path


def build_tarball(stage_dir: Path) -> Path:
    tar_stage = stage_dir / f"{PKG_NAME}-{PKG_VERSION}-{PKG_ARCH}"
    shutil.rmtree(tar_stage, ignore_errors=True)
    stage_rootfs(tar_stage / "rootfs")
    write_lf_file(PKG_DIR / "install.sh", tar_stage / "install.sh", 0o755)
    write_lf_file(PKG_DIR / "uninstall.sh", tar_stage / "uninstall.sh", 0o755)

    tar_path = DIST_DIR / f"{PKG_NAME}-{PKG_VERSION}-{PKG_ARCH}.tar.gz"

    def normalize_tarinfo(ti: tarfile.TarInfo) -> tarfile.TarInfo:
        ti.uid = 0
        ti.gid = 0
        ti.uname = "root"
        ti.gname = "root"
        return ti

    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(tar_stage, arcname=tar_stage.name, filter=normalize_tarinfo)
    print(f"[build] Built {tar_path} ({tar_path.stat().st_size:,} B)")
    return tar_path


def main():
    stage_dir = Path("/tmp/s8_hw_stage") if os.name == "posix" else (DIST_DIR / "_stage")
    shutil.rmtree(stage_dir, ignore_errors=True)
    stage_dir.mkdir(parents=True, exist_ok=True)

    deb_path = build_deb(stage_dir)
    tar_path = build_tarball(stage_dir)

    sums = []
    for artifact in (deb_path, tar_path):
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        sums.append(f"{digest}  {artifact.name}")
    (DIST_DIR / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    shutil.rmtree(stage_dir, ignore_errors=True)
    print("[build] SHA256SUMS written cleanly.")


if __name__ == "__main__":
    main()

