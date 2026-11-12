#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
project_index.py — Samsung Galaxy S8 Native Linux Autonomous Repository Indexer
Scans the entire repository, maps all critical assets (kernels, boot images, flashers,
drivers, control scripts, firmware archives, desktop app, and documentation), and generates a
standardized PROJECT_INDEX.md catalog with CLI query, graph inspection, and verification capabilities.
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Paths to ignore during indexing
EXCLUDE_DIRS = {
    ".git", ".system_generated", "node_modules", "obj", "__pycache__",
    ".idea", ".vscode", "tmp", "temp", "build", "dist"
}

# Key categories and their path patterns
CATEGORY_RULES = [
    ("Skills & Operational Runbooks", lambda p: ".agent/skills" in p or ".agent\\skills" in p),
    ("Master Rulebooks & Core Guides", lambda p: p.endswith(("GEMINI.md", "FINDINGS.md", "HISTORY.md", "SUMMARY.md", "PROJECT_INDEX.md", "README.md", "AP_AND_KERNEL_BUILD_GUIDE.md"))),
    ("S8 Imager Desktop Application", lambda p: "desktop-app" in p),
    ("Production Flashers & Release Packages", lambda p: "releases" in p or p.endswith(("_Flasher.exe", "_Odin.tar", ".img.gz", "Launch_S8_Imager.bat"))),
    ("Hardware Drivers & Daemons (C Source)", lambda p: p.endswith((".c", ".h")) and ("scratch" in p or "src" in p)),
    ("System Supervisors & Bring-up Scripts", lambda p: p.endswith((".sh", ".py", ".ps1")) and ("scratch" in p or "tools" in p or "scripts" in p or "boot" in p)),
    ("Kernel Source Tree & Configs", lambda p: ("kernel" in p or "galaxy-s8-kvm-kernel" in p) and p.endswith((".config", "Makefile", "Kconfig"))),
    ("Firmware Dumps & Base Archives", lambda p: "archive" in p or "firmware" in p or "dumps" in p),
    ("Technical Documentation & Specifications", lambda p: p.startswith("docs") or p.endswith((".html", ".txt", ".md"))),
]

DEPENDENCY_GRAPH = [
    {
        "element": "#connStatusDot / #connStatusText",
        "page": "Global Header",
        "route": "GET /api/status",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/device.py:DeviceManager.get_telemetry()",
        "target": "USB State, Wi-Fi 192.168.0.227:6080 probe, Battery /sys/class/power_supply/battery"
    },
    {
        "element": "#btnTorchToggle",
        "page": "Global Header",
        "route": "GET /api/torch?state=1|0",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/device.py:DeviceManager.set_torch()",
        "target": "Rear LED Torch /sys/class/leds/torch-sec1/brightness (0 or 10)"
    },
    {
        "element": "#btnHapticTest",
        "page": "Global Header",
        "route": "GET /api/haptic?ms=150",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/device.py:DeviceManager.pulse_haptic()",
        "target": "Chassis Vibrator /sys/class/timed_output/vibrator/enable"
    },
    {
        "element": "#btnOpenScreen",
        "page": "Global Header",
        "route": "GET /api/screen",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/adb.py:AdbClient.forward()",
        "target": "ADB forward 6080, 5901, 2222 -> launches http://localhost:6080/vnc_lite.html"
    },
    {
        "element": "#rebootSelect",
        "page": "Global Header",
        "route": "GET /api/reboot?mode=...",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/adb.py:AdbClient.reboot()",
        "target": "S-Boot Bootloader: adb reboot / reboot download (PID_685D) / reboot recovery"
    },
    {
        "element": "#btnBrowseImage",
        "page": "#pageFlash",
        "route": "GET /api/browse/image",
        "handler": "desktop-app/app/server/api.py:pick_native_image_file()",
        "core": "Windows Native File Dialog (PowerShell OpenFileDialog)",
        "target": "Selects local .tar.xz, .img.gz, .tar, .img distribution image"
    },
    {
        "element": "#storageSlider",
        "page": "#pageFlash",
        "route": "GET /api/storage/info?alloc=<gb>",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/flasher.py:FlasherEngine.calculate_storage()",
        "target": "/dev/block/sda15 (USERDATA 53.7 GB total), validates 4-48 GB rootfs allocation"
    },
    {
        "element": "#btnStartFlash",
        "page": "#pageFlash",
        "route": "POST /api/flash/start",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/flasher.py:FlasherEngine.start_flash()",
        "target": "MAX77865 PMIC registers -> clean Ext4 format -> unpacks rootfs -> start_all.sh"
    },
    {
        "element": "#flashLogStream",
        "page": "#pageFlash",
        "route": "GET /api/flash/status",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/flasher.py:FlasherEngine.status/logs",
        "target": "Streams live progress % (0-100) and line-by-line deployment logs"
    },
    {
        "element": "#cpuFreqM2 / #cpuFreqA53",
        "page": "#pageDashboard",
        "route": "GET /api/status",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/device.py:DeviceManager.get_telemetry()",
        "target": "/sys/devices/system/cpu/cpu[0-7]/cpufreq/scaling_cur_freq"
    },
    {
        "element": "#dpStateBadge",
        "page": "#pageDashboard",
        "route": "GET /api/status",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/device.py:DeviceManager.get_telemetry()",
        "target": "Type-C DisplayPort DECON2 /sys/class/switch/hdmi/state (0=Off, 1=Active 1080p60)"
    },
    {
        "element": "#termNativeInput",
        "page": "#pageTerminal",
        "route": "GET /api/exec?cmd=...&env=os|ap",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/adb.py:AdbClient.shell() / exec_os()",
        "target": "Dual-Shell: AP root /sbin/sh vs Linux OS chroot /mnt/ubuntu /bin/bash -c"
    },
    {
        "element": "#btnWifiScan",
        "page": "#pageWifi",
        "route": "GET /api/wifi/scan",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/device.py:DeviceManager.scan_wifi()",
        "target": "Broadcom BCM4361 Wi-Fi scan results (s8ctl wifi scan / wpa_cli)"
    },
    {
        "element": "#btnWifiConnect",
        "page": "#pageWifi",
        "route": "GET /api/wifi/connect?ssid=...&pass=...",
        "handler": "desktop-app/app/server/api.py:S8ApiHandler",
        "core": "desktop-app/app/core/adb.py:AdbClient.shell()",
        "target": "Writes credentials to /data/linux/connect_wifi.sh and executes in background"
    }
]

def get_file_size_fmt(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:,.1f} {unit}" if unit in ['MB', 'GB'] else f"{size_bytes:,} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def categorize_file(rel_path):
    rel_norm = rel_path.replace("\\", "/")
    for cat_name, rule_fn in CATEGORY_RULES:
        if rule_fn(rel_norm):
            return cat_name
    return "Miscellaneous Assets"

def scan_repository(repo_root):
    catalog = {}
    total_files = 0
    total_bytes = 0

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        rel_root = os.path.relpath(root, repo_root).replace("\\", "/")

        # Prune deep vendor trees and kernel source trees so we don't index tens of thousands of internal files
        if rel_root != ".":
            if "galaxy-s8-kvm-kernel" in rel_root or "kernel" in rel_root:
                dirs[:] = []
            elif "archive" in rel_root:
                dirs[:] = []
            elif "tests" in rel_root and "ui_verification" in rel_root:
                dirs[:] = []

        for file in files:
            full_path = os.path.join(root, file)
            try:
                stat = os.stat(full_path)
            except OSError:
                continue

            rel_path = os.path.relpath(full_path, repo_root).replace("\\", "/")
            cat = categorize_file(rel_path)
            
            if cat not in catalog:
                catalog[cat] = []

            catalog[cat].append({
                "path": rel_path,
                "abs_path": str(Path(full_path).resolve()),
                "size_bytes": stat.st_size,
                "size_fmt": get_file_size_fmt(stat.st_size),
                "mtime": stat.st_mtime
            })
            total_files += 1
            total_bytes += stat.st_size

    for cat in catalog:
        catalog[cat].sort(key=lambda x: x["path"].lower())

    return catalog, total_files, total_bytes

def generate_markdown(catalog, repo_root, total_files, total_bytes):
    lines = [
        "# Samsung Galaxy S8 Native Linux — Master Project Asset & File Index (`PROJECT_INDEX.md`)",
        "",
        "> [!IMPORTANT]",
        "> **AUTONOMOUS REPOSITORY INDEX:**",
        f"> Automatically generated by [`scripts/project_index.py`](file:///{repo_root.replace('\\', '/')}/scripts/project_index.py).",
        f"> Total Tracked Assets: **{total_files}** files | Total Size: **{get_file_size_fmt(total_bytes)}**.",
        "",
        "---",
        "",
        "## S8 Imager: Vertex-to-Back Application Dependency Graph",
        "",
        "| Frontend Element | UI Page / Container | API Route | Backend Handler | Target Subsystem / Hardware Node |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]

    for g in DEPENDENCY_GRAPH:
        lines.append(f"| `{g['element']}` | {g['page']} | `{g['route']}` | [`{g['handler']}`](file:///{repo_root.replace('\\', '/')}/{g['handler'].split(':')[0]}) | {g['target']} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    for cat_name, items in sorted(catalog.items()):
        if not items:
            continue
        lines.append(f"## {cat_name} ({len(items)} items)")
        lines.append("")
        lines.append("| Asset / File Path | Size | Description & Role |")
        lines.append("| :--- | :--- | :--- |")

        for item in items:
            p = item["path"]
            abs_p = item["abs_path"].replace("\\", "/")
            size = item["size_fmt"]
            
            # Auto-describe known files
            desc = describe_known_asset(p)
            lines.append(f"| [`{p}`](file:///{abs_p}) | {size} | {desc} |")
        lines.append("")

    return "\n".join(lines)

def describe_known_asset(path):
    p = path.lower()
    if "ap_and_kernel_build_guide.md" in p:
        return "Authoritative master guide for kernel compilation and Odin AP package assembly."
    elif "gemini.md" in p:
        return "Master operational rulebook and verified anti-hallucination hardware constraints."
    elif "findings.md" in p:
        return "Empirical hardware, kernel, power management, and userland findings ledger."
    elif "history.md" in p:
        return "Chronological task execution history, test proofs, and verified procedure logs."
    elif "summary.md" in p:
        return "High-level architectural overview, current milestone statuses, and subsystem table."
    elif "project_index.md" in p:
        return "Autonomous comprehensive index of all project assets, tools, and scripts."
    elif "readme.md" in p:
        return "Repository master README and project setup documentation."
    elif "launch_s8_imager.bat" in p:
        return "1-Click Windows batch launcher for the S8 Imager desktop application."
    elif "desktop-app/ui/index.html" in p:
        return "High-density Bento grid HTML/JS user interface for S8 Imager desktop app."
    elif "desktop-app/app/server/api.py" in p:
        return "Core REST API & WebSocket handler for hardware telemetry, flasher, and terminal."
    elif "desktop-app/app/core/flasher.py" in p:
        return "Autonomous 2-stage multi-ROM deployment engine with pre-flash hardware guards."
    elif "desktop-app/app/core/device.py" in p:
        return "Hardware state poller, telemetry collector, and battery/thermal supervisor."
    elif "desktop-app/app/core/adb.py" in p:
        return "Thread-safe ADB client with bundled binary auto-fallback and subprocess runner."
    elif "build_rocksolid_boot.py" in p:
        return "Production-grade automated boot.img and Odin AP package builder with Calliope DSP audio."
    elif "build_custom_boot.py" in p:
        return "Custom kernel & DTB boot.img packaging tool with verified LZMA ramdisk."
    elif "ubuntu_24.04_galaxys8_full_standalone_odin.tar" in p:
        return "1-Click complete standalone Odin OS package (boot + recovery + full userdata OS rootfs, 3.37 GB)."
    elif "ubuntu_24.04_galaxys8_full_odin.tar" in p or "galaxy_s8_linux_ap.tar" in p:
        return "Dual-partition fail-safe Odin AP package (auto-booting boot.img + recovery.img, ~78 MB)."
    elif "boot_golden.img" in p or "boot_ubuntu_autoboot.img" in p:
        return "Auto-booting kernel + ramdisk image with Calliope DSP audio, universal sys.usb.ffs.ready trigger."
    elif "exynos_dp_bridge.c" in p:
        return "Native Exynos 8895 DECON2 USB-C DisplayPort 1080p60 framebuffer bridge daemon."
    elif "s8_typec_daemon.py" in p:
        return "Type-C CCIC role supervisor enforcing DFP mode and 1500mA fast-charging registers."
    elif "s8_input_bridge.c" in p:
        return "Hotplug USB mouse and keyboard input forwarder to X11 (:1) with anti-phantom filter."
    elif "s8_button_daemon.c" in p:
        return "Physical chassis buttons daemon (Power DPMS, Volume haptics/ALSA, Bixby screenshot)."
    elif "s8ctl.py" in p:
        return "Unified hardware CLI suite (CPU/GPU boost, Wi-Fi, torch, haptics, battery, dock)."
    elif "start_all.sh" in p:
        return "Master boot supervisor (V4L2 guard, 1500mA fast charge, Wi-Fi, GNOME 46 desktop, daemons)."
    elif "connect_wifi.sh" in p:
        return "Broadcom BCM4361 Wi-Fi connection script with fallback SoftAP portal."
    elif "init_audio.sh" in p:
        return "ALSA hardware routing for Maxim MAX98506 speaker and CS47L92 DMIC1 microphone."
    elif "sanitize_repo.py" in p:
        return "Automated secret scanner and sanitizer enforcing zero credential leakage."
    elif "cleanup_project.py" in p:
        return "Automated workspace cleanup tool purging temporary artifacts and scratch images."
    elif "ci_cd_validator.py" in p:
        return "Automated 4-layer CI/CD quality gate & test runner for S8 Imager."
    elif "project_index.py" in p:
        return "Autonomous repository crawler, indexer, and integrity validator tool."
    elif "galaxy-s8-ap-kernel-builder" in p:
        return "Operational runbook for compiling Exynos 8895 Linux kernel and packaging Odin AP tarballs."
    elif "galaxy-s8-native-linux" in p:
        return "Master operational runbook for live S8 Linux, GNOME 46 macOS desktop, and DisplayPort."
    elif "galaxy-s8-universal-installer" in p:
        return "Architecture and runbook for 2-stage drag-and-drop autonomous multi-ROM OS installer."
    elif "production-grade-vibe-coding" in p:
        return "Engineering standard enforcing automated verification and 4-layer testing pyramid."
    elif "production-ui-design-guard" in p:
        return "Restrained production UI design standards, token architecture, and Bento grid specs."
    elif "skill.md" in p:
        return "Operational runbook and behavioral instructions for agent skill."
    return "Project asset."

def main():
    parser = argparse.ArgumentParser(description="Galaxy S8 Project Index Manager")
    parser.add_argument("--root", default=".", help="Root path of the repository")
    parser.add_argument("--build", action="store_true", help="Build or update PROJECT_INDEX.md")
    parser.add_argument("--verify", action="store_true", help="Verify integrity of all catalogued assets")
    parser.add_argument("--query", help="Search the index for a keyword or file path")
    parser.add_argument("--graph", help="Query the Vertex-to-Back application dependency graph")
    args = parser.parse_args()

    repo_root = os.path.abspath(args.root)

    if args.graph:
        kw = args.graph.lower()
        print(f"=== S8 Imager Vertex-to-Back Dependency Graph for '{args.graph}' ===")
        matches = [g for g in DEPENDENCY_GRAPH if kw in g["element"].lower() or kw in g["route"].lower() or kw in g["target"].lower() or kw in g["page"].lower() or kw in g["core"].lower()]
        if not matches:
            print("No matching component found in dependency graph.")
            return
        for m in matches:
            print(f"\n[Element]: {m['element']} ({m['page']})")
            print(f"  * Route:   {m['route']}")
            print(f"  * Handler: {m['handler']}")
            print(f"  * Core:    {m['core']}")
            print(f"  * Target:  {m['target']}")
        print(f"\nTotal matches: {len(matches)}")
        return

    catalog, total_files, total_bytes = scan_repository(repo_root)

    if args.query:
        kw = args.query.lower()
        print(f"=== Project Asset Query Results for '{args.query}' ===")
        matches = 0
        for cat, items in catalog.items():
            cat_matches = [i for i in items if kw in i["path"].lower() or kw in describe_known_asset(i["path"]).lower()]
            if cat_matches:
                print(f"\n--- {cat} ---")
                for m in cat_matches:
                    print(f"  * {m['path']} ({m['size_fmt']})")
                    print(f"    Role: {describe_known_asset(m['path'])}")
                    matches += 1
        print(f"\nTotal matches found: {matches}")
        return

    if args.verify:
        print("=== Verifying Repository Asset Integrity ===")
        missing = 0
        checked = 0
        for cat, items in catalog.items():
            for m in items:
                checked += 1
                if not os.path.exists(m["abs_path"]):
                    print(f"[!] MISSING: {m['path']}")
                    missing += 1
        if missing == 0:
            print(f"[OK] All {checked} indexed assets verified present on disk.")
        else:
            print(f"[FAIL] {missing} assets were indexed but missing on disk.")
            sys.exit(1)
        return

    # Default action: Build PROJECT_INDEX.md
    md_content = generate_markdown(catalog, repo_root, total_files, total_bytes)
    output_path = os.path.join(repo_root, "PROJECT_INDEX.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[OK] Master Project Index successfully generated at: {output_path}")
    print(f"     Indexed: {total_files} files ({get_file_size_fmt(total_bytes)}) across {len(catalog)} categories.")

if __name__ == "__main__":
    main()
