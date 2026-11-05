#!/usr/bin/env python3
"""
reorganize_repo.py - Restructures the Galaxy S8 repository into clean production directories:
src/, boot/, tests/, docs/, releases/, archive/.
"""

import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DIRS_TO_CREATE = [
    "boot",
    "src/drivers",
    "src/desktop",
    "src/audio",
    "src/control",
    "src/network",
    "src/services",
    "tests/benchmarks",
    "tests/hardware",
    "tests/ui_verification",
    "releases",
    "docs/css",
    "archive",
]

COPIES = [
    # Boot
    ("scratch/build_autoboot_and_odin.py", "boot/build_autoboot_and_odin.py"),
    ("scratch/start_all.sh", "boot/start_all.sh"),
    
    # Drivers
    ("scratch/exynos_dp_bridge.c", "src/drivers/exynos_dp_bridge.c"),
    ("scratch/s8_button_daemon.c", "src/drivers/s8_button_daemon.c"),
    ("scratch/s8_input_bridge.c", "src/drivers/s8_input_bridge.c"),

    # Desktop
    ("scratch/start_gnome_macos.sh", "src/desktop/start_gnome_macos.sh"),
    ("scratch/polish_gnome_macos.sh", "src/desktop/polish_gnome_macos.sh"),
    ("scratch/nginx_novnc.conf", "src/desktop/nginx_novnc.conf"),
    ("scratch/apply_panel_layout.py", "src/desktop/apply_panel_layout.py"),

    # Audio
    ("scratch/asound.conf", "src/audio/asound.conf"),
    ("scratch/init_audio.sh", "src/audio/init_audio.sh"),
    ("scratch/mixer_paths.xml", "src/audio/mixer_paths.xml"),
    ("scratch/mixer_gains.xml", "src/audio/mixer_gains.xml"),

    # Control
    ("scratch/s8ctl.py", "src/control/s8ctl.py"),
    ("scratch/s8_control_center.py", "src/control/s8_control_center.py"),

    # Network
    ("scratch/connect_wifi.sh", "src/network/connect_wifi.sh"),
    ("scratch/setup_wifi.sh", "src/network/setup_wifi.sh"),
    ("scratch/start_bluetooth.sh", "src/network/start_bluetooth.sh"),
    ("scratch/adb_forward_daemon.py", "src/network/adb_forward_daemon.py"),

    # Services
    ("scratch/start-docker", "src/services/start_docker.sh"),
    ("scratch/start_casaos.sh", "src/services/start_casaos.sh"),
    ("scratch/start_homeassistant.sh", "src/services/start_homeassistant.sh"),
    ("scratch/start_uptime_kuma.sh", "src/services/start_uptime_kuma.sh"),
    ("scratch/start_codeserver.sh", "src/services/start_codeserver.sh"),

    # Tests Benchmarks
    ("scratch/benchmark_suite.py", "tests/benchmarks/benchmark_suite.py"),
    ("scratch/test_perf.c", "tests/benchmarks/test_perf.c"),

    # Tests Hardware
    ("scratch/test_dp_colors.c", "tests/hardware/test_dp_colors.c"),
    ("scratch/test_dp_ion_pattern.c", "tests/hardware/test_dp_ion_pattern.c"),
    ("scratch/test_audio_devs.py", "tests/hardware/test_audio_devs.py"),
    ("scratch/test_vsync.c", "tests/hardware/test_vsync.c"),

    # Tests UI Verification
    ("scratch/test_casaos_ui.py", "tests/ui_verification/test_casaos_ui.py"),
    ("scratch/test_casaos_human_flow.py", "tests/ui_verification/test_casaos_human_flow.py"),
    ("scratch/test_portainer_ui.py", "tests/ui_verification/test_portainer_ui.py"),
    ("scratch/test_portainer_containers.py", "tests/ui_verification/test_portainer_containers.py"),
    ("scratch/test_uptimekuma_ui.py", "tests/ui_verification/test_uptimekuma_ui.py"),
    ("scratch/test_filebrowser_ui.py", "tests/ui_verification/test_filebrowser_ui.py"),
    ("scratch/test_sdcard_filebrowser.py", "tests/ui_verification/test_sdcard_filebrowser.py"),
    ("scratch/verify_ollama_ui.py", "tests/ui_verification/verify_ollama_ui.py"),
    ("scratch/test_codeserver_ui.py", "tests/ui_verification/test_codeserver_ui.py"),
    ("scratch/test_codeserver_editor.py", "tests/ui_verification/test_codeserver_editor.py"),
]

# Move legacy clutter from workspace root to archive/
ROOT_ARCHIVE_FILES = [
    "echo",
    "echo_arm64",
    "strace",
    "ld-2.31.so",
    "libc-2.31.so",
    "boot_stock.tar",
    "boot_stock_magisk.img",
    "boot_stock_magisk.tar",
    "boot_twrp_autoboot_exact.tar",
    "boot_twrp_exact.tar",
    "magisk_headless_adb.tar",
    "magisk_patched-30700_DAZdX.tar",
    "boot_and_recovery_headless.tar",
    "recovery_restore.tar",
    "boot_kvm_fixed.tar",
    "boot_linux_switchroot.img",
    "boot_native_ubuntu.tar",
    "boot.img",
    "boot.img.lz4",
    "twrp_as_boot.tar",
    "alpine-test.tar.gz",
    "ubuntu-base-18.04.5-base-arm64.tar.gz",
    "ubuntu-base-20.04.5-base-arm64.tar.gz",
    "ubuntu-base-22.04.4-base-arm64.tar.gz",
    "last_kmsg_switchroot_test.log",
]

def main():
    print("[*] Creating structured directories...")
    for d in DIRS_TO_CREATE:
        dp = os.path.join(ROOT, d)
        os.makedirs(dp, exist_ok=True)
        print(f"  Created: {d}")

    print("\n[*] Populating organized files...")
    for src_rel, dst_rel in COPIES:
        src = os.path.join(ROOT, src_rel)
        dst = os.path.join(ROOT, dst_rel)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  Copied: {src_rel} -> {dst_rel}")
        else:
            print(f"  [MISSING]: {src_rel}")

    print("\n[*] Moving root archives to archive/...")
    archive_dir = os.path.join(ROOT, "archive")
    for f in ROOT_ARCHIVE_FILES:
        fp = os.path.join(ROOT, f)
        if os.path.exists(fp):
            dst = os.path.join(archive_dir, f)
            shutil.move(fp, dst)
            print(f"  Archived: {f} -> archive/{f}")

    print("\n[+] Reorganization completed successfully.")

if __name__ == "__main__":
    main()

