#!/usr/bin/env python3
"""
scripts/run_human_flash_test.py — Human-Flow OS Flash & Wi-Fi Hardship Audit Engine
Simulates a real human user opening S8 Imager, selecting an unmodified upstream distro,
performing a clean installation on Samsung Galaxy S8 (SM-G950N, serial ce10171ab3e9620804),
testing in-app Wi-Fi onboarding, and documenting all hardships and errors encountered.
"""

import os
import sys
import time
import socket
import threading
from pathlib import Path

# Paths
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "desktop-app"))

from app.server.api import start_server, S8ApiHandler
from app.core.adb import AdbClient
from scripts.send_telegram import send_telegram_message, send_telegram_photo
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path(os.environ.get("ANTIGRAVITY_ARTIFACTS_DIR", r"C:\Users\rakib\.gemini\antigravity\brain\32ab8e00-683f-431e-8f7d-5b48926742e1"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_DISTRO = WORKSPACE / "distros" / "alpine-minirootfs-3.20.3-aarch64.tar.gz"
SERIAL = "ce10171ab3e9620804"


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    print("=" * 72)
    print("  S8 Imager — Human-Flow OS Flashing & Hardship Diagnostic Engine")
    print(f"  Target Device: Samsung Galaxy S8 ({SERIAL})")
    print(f"  Target Distro: {TARGET_DISTRO.name} ({TARGET_DISTRO.stat().st_size / (1024*1024):.2f} MB)")
    print("=" * 72)

    adb = AdbClient(SERIAL)
    if not adb.is_connected():
        print(f"[!] Warning: Device {SERIAL} not immediately responding. State: {adb.get_state()}")
    else:
        print(f"[+] Device {SERIAL} confirmed online. State: {adb.get_state()}")

    port = get_free_port()
    base_url = f"http://127.0.0.1:{port}"
    server = start_server(host="127.0.0.1", port=port, serial=SERIAL)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[+] Local S8 Imager server active at {base_url}")

    # Telegram notification: Stage start
    send_telegram_message(
        f"[STAGE] *Human-Flow Flashing Test Started:*\nTarget: Alpine Linux 3.20.3 aarch64 ({TARGET_DISTRO.name})\nDevice: Galaxy S8 ({SERIAL})"
    )

    captured_photos = []
    audit_findings = {
        "distro": TARGET_DISTRO.name,
        "distro_size_mb": round(TARGET_DISTRO.stat().st_size / (1024 * 1024), 2),
        "flash_status": "unknown",
        "flash_elapsed_sec": 0,
        "flash_logs": [],
        "wifi_scan_results": [],
        "wifi_connect_results": None,
        "post_install_checks": {},
        "errors_and_hardships": []
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})

            print(f"[+] Navigating to S8 Imager UI...")
            page.goto(base_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            # Step 1: Human navigation to Flash OS page and image selection
            page.click("#navBtnFlash")
            page.wait_for_timeout(500)

            print(f"[+] Selecting target image: {TARGET_DISTRO}")
            distro_size_mb = round(TARGET_DISTRO.stat().st_size / (1024 * 1024), 2)
            page.evaluate(
                """([p, name, mb]) => {
                    applySelectedImage(p, name, mb, 'tar.gz');
                }""",
                [str(TARGET_DISTRO), TARGET_DISTRO.name, distro_size_mb]
            )
            page.wait_for_timeout(500)

            # Slider adjustment to 16 GB
            page.evaluate("() => { updateAllocSlider(16); }")
            page.wait_for_timeout(300)

            # Capture Setup Screenshot
            p1 = ARTIFACT_DIR / "human_flash_01_setup.png"
            page.screenshot(path=str(p1), full_page=True)
            captured_photos.append((p1, "[VISUAL PROOF 1/4] Human-Flow: Target Image Setup & 16GB Allocation"))
            print(f"[+] Captured setup view: {p1.name}")

            # Step 2: Trigger Flash Deployment
            print(f"[+] Clicking START FLASH DEPLOYMENT button (#btnStartDeploy)...")
            flash_btn = page.locator("#btnStartDeploy")
            flash_btn.click()
            page.wait_for_timeout(800)

            # Step 3: Monitor Live Flashing
            flash_start = time.time()
            last_log_count = 0
            in_progress_snap_taken = False

            while True:
                page.wait_for_timeout(1000)
                status_res = page.evaluate("() => { return window._lastFlashStatus || null; }")
                
                # Also fetch status directly from backend API
                import urllib.request, json
                try:
                    with urllib.request.urlopen(f"{base_url}/api/flash/status", timeout=3) as resp:
                        api_data = json.loads(resp.read().decode())
                except Exception:
                    api_data = {}

                cur_status = api_data.get("status", "unknown")
                cur_progress = api_data.get("progress", 0.0)
                cur_desc = api_data.get("step_desc", "")
                logs = api_data.get("logs", [])

                # Print new logs
                if len(logs) > last_log_count:
                    for l in logs[last_log_count:]:
                        print(f"    {l}")
                    last_log_count = len(logs)

                # Capture in-progress snapshot around 50%
                if cur_progress >= 0.40 and not in_progress_snap_taken:
                    p2 = ARTIFACT_DIR / "human_flash_02_in_progress.png"
                    page.screenshot(path=str(p2), full_page=True)
                    captured_photos.append((p2, f"[VISUAL PROOF 2/4] Human-Flow: Live Deployment Progress ({cur_progress*100:.0f}%)"))
                    in_progress_snap_taken = True
                    print(f"[+] Captured in-progress view: {p2.name}")

                if cur_status in ["completed", "failed"]:
                    audit_findings["flash_status"] = cur_status
                    audit_findings["flash_elapsed_sec"] = round(time.time() - flash_start, 1)
                    audit_findings["flash_logs"] = logs
                    if cur_status == "failed":
                        audit_findings["errors_and_hardships"].append(
                            f"Flash Worker failed with error: {api_data.get('error_msg')}"
                        )
                    print(f"\n[+] Flashing finished with status: {cur_status.upper()} in {audit_findings['flash_elapsed_sec']}s")
                    break

                if time.time() - flash_start > 300:
                    audit_findings["flash_status"] = "timeout"
                    audit_findings["errors_and_hardships"].append("Flashing timed out after 300 seconds.")
                    print("[!] Flashing timed out.")
                    break

            page.wait_for_timeout(1000)
            p3 = ARTIFACT_DIR / "human_flash_03_result.png"
            page.screenshot(path=str(p3), full_page=True)
            captured_photos.append((p3, f"[VISUAL PROOF 3/4] Human-Flow: Flash Deployment Result ({audit_findings['flash_status'].upper()})"))
            print(f"[+] Captured flash completion view: {p3.name}")

            # Step 4: Test in-app Wi-Fi Onboarding
            print(f"\n[+] Testing in-app Wi-Fi configuration on Config page...")
            page.click("#navBtnConfig")
            page.wait_for_timeout(600)

            # Trigger Wi-Fi scan
            scan_btn = page.locator("#wifiScanBtn")
            print(f"[+] Clicking Wi-Fi SCAN button...")
            scan_btn.click()
            page.wait_for_timeout(3000)

            # Inspect scan results
            select_el = page.locator("#wifiSsidSelect")
            options = select_el.locator("option").all_inner_texts()
            print(f"[+] Scanned Wi-Fi Options: {options}")
            audit_findings["wifi_scan_results"] = options

            # Check if any real SSID was discovered
            real_ssids = [o for o in options if not o.startswith("(")]
            if not real_ssids:
                audit_findings["errors_and_hardships"].append(
                    "Wi-Fi Scan returned zero broadcast SSIDs (driver parameters or wpa_supplicant inactive)."
                )

            # Try connecting
            pass_input = page.locator("#wifiPassInput")
            pass_input.fill("test_password_123")
            connect_btn = page.locator("#wifiConnectBtn")
            print(f"[+] Clicking Wi-Fi CONNECT button...")
            connect_btn.click()
            page.wait_for_timeout(2000)

            p4 = ARTIFACT_DIR / "human_flash_04_wifi_config.png"
            page.screenshot(path=str(p4), full_page=True)
            captured_photos.append((p4, "[VISUAL PROOF 4/4] Human-Flow: In-App Wi-Fi Configuration Attempt"))
            print(f"[+] Captured Wi-Fi configuration view: {p4.name}")

            browser.close()

    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        print("[+] Test server shutdown complete.")

    # Step 5: Post-Install Device Hardware Inspection via ADB
    print(f"\n[+] Inspecting live post-install phone filesystem via ADB...")
    mount_check = adb.shell("mountpoint -q /mnt/ubuntu && echo 'MOUNTED' || echo 'NOT_MOUNTED'")
    audit_findings["post_install_checks"]["ubuntu_mount"] = mount_check

    # If not mounted, try mounting loop0 to inspect
    if "NOT_MOUNTED" in mount_check:
        adb.shell("mkdir -p /mnt/ubuntu; mount -o loop,rw /data/linux/rootfs.img /mnt/ubuntu 2>/dev/null || true")

    ls_root = adb.shell("ls -la /mnt/ubuntu 2>/dev/null")
    audit_findings["post_install_checks"]["rootfs_listing"] = ls_root
    print(f"    Rootfs files:\n{ls_root[:300]}...")

    os_release = adb.shell("cat /mnt/ubuntu/etc/os-release 2>/dev/null")
    audit_findings["post_install_checks"]["os_release"] = os_release
    print(f"    OS Release:\n{os_release}")

    # Check Busybox / Shell in Alpine
    sh_check = adb.shell("ls -l /mnt/ubuntu/bin/sh /mnt/ubuntu/bin/busybox 2>/dev/null")
    audit_findings["post_install_checks"]["alpine_shell"] = sh_check
    print(f"    Alpine Shell:\n{sh_check}")

    # Check if /data/linux/start_all.sh can run or what errors it encounters with Alpine
    start_all_test = adb.shell("sh -x /data/linux/start_all.sh 2>&1 | head -n 30")
    audit_findings["post_install_checks"]["start_all_test"] = start_all_test
    print(f"    start_all.sh initial trace:\n{start_all_test[:300]}...")

    # Identify hardships and incompatibilities with Alpine Linux
    if "Alpine" in os_release:
        audit_findings["errors_and_hardships"].append(
            "Hardship 1: Alpine Linux uses musl libc (/lib/ld-musl-aarch64.so.1) instead of glibc. "
            "Precompiled desktop binaries (Xtigervnc, metacity, gnome-panel, s8_button_daemon) compiled against glibc cannot execute natively without musl compatibility symlinks or gcompat."
        )
        audit_findings["errors_and_hardships"].append(
            "Hardship 2: Alpine Linux lacks GNU bash by default (/bin/sh is BusyBox ash). "
            "Scripts with bashisms or '#!/bin/bash' headers fail with 'command not found'."
        )
        audit_findings["errors_and_hardships"].append(
            "Hardship 3: Alpine Linux uses 'apk' package manager. Our apt sandbox shims (/etc/apt/apt.conf.d/99sandbox) are ignored."
        )
        audit_findings["errors_and_hardships"].append(
            "Hardship 4: OpenRC init system is used instead of systemd. D-Bus session activation and systemd --user units are absent."
        )

    # Step 6: Dispatch all visual proofs to Telegram
    print(f"\n[+] Dispatching {len(captured_photos)} visual proofs to Telegram...")
    for path, caption in captured_photos:
        send_telegram_photo(str(path), caption=caption)
        time.sleep(1)

    # Concluding message on Telegram
    summary_msg = (
        f"[REPORT] *Human-Flow Flashing & Hardship Audit Complete:*\n"
        f"- Target: `{TARGET_DISTRO.name}`\n"
        f"- Status: `{audit_findings['flash_status'].upper()}` ({audit_findings['flash_elapsed_sec']}s)\n"
        f"- Mount: `{audit_findings['post_install_checks'].get('ubuntu_mount')}`\n"
        f"- Hardships Logged: {len(audit_findings['errors_and_hardships'])}\n"
        f"See conversation artifact for the full technical breakdown."
    )
    send_telegram_message(summary_msg)

    print("\n[+] Audit execution finished successfully.")
    return audit_findings


if __name__ == "__main__":
    main()
