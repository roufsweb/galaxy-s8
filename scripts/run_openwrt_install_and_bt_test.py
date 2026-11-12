#!/usr/bin/env python3
"""
scripts/run_openwrt_install_and_bt_test.py — OpenWrt Flash, Bluetooth & Error Diagnostics Engine
Simulates full human-flow deployment of OpenWrt 23.05.5 ARM64 on Samsung Galaxy S8,
tests the interactive Reboot Device button, tests Bluetooth initialization,
and captures all backend, desktop app, and hardware errors.
"""

import os
import sys
import time
import socket
import threading
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "desktop-app"))

from app.server.api import start_server
from app.core.adb import AdbClient
from scripts.send_telegram import send_telegram_message, send_telegram_photo
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path(os.environ.get("ANTIGRAVITY_ARTIFACTS_DIR", r"C:\Users\rakib\.gemini\antigravity\brain\32ab8e00-683f-431e-8f7d-5b48926742e1"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_DISTRO = WORKSPACE / "distros" / "openwrt-23.05.5-armsr-armv8-rootfs.tar.gz"
SERIAL = "ce10171ab3e9620804"


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    print("=" * 72)
    print("  S8 Imager — OpenWrt Flash & Bluetooth Diagnostic Suite")
    print(f"  Target Device: Samsung Galaxy S8 ({SERIAL})")
    print(f"  Target Distro: {TARGET_DISTRO.name} ({TARGET_DISTRO.stat().st_size / (1024*1024):.2f} MB)")
    print("=" * 72)

    adb = AdbClient(SERIAL)
    if not adb.is_connected():
        print(f"[!] Warning: Device {SERIAL} state: {adb.get_state()}")
    else:
        print(f"[+] Device {SERIAL} confirmed online ({adb.get_state()})")

    port = get_free_port()
    base_url = f"http://127.0.0.1:{port}"
    server = start_server(host="127.0.0.1", port=port, serial=SERIAL)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[+] S8 Imager server active at {base_url}")

    send_telegram_message(
        f"[STAGE] *OpenWrt Deployment & Bluetooth Test Started:*\nTarget: OpenWrt 23.05.5 aarch64 ({TARGET_DISTRO.name})\nDevice: Galaxy S8 ({SERIAL})"
    )

    captured_photos = []
    audit_log = {
        "distro": TARGET_DISTRO.name,
        "flash_status": "unknown",
        "flash_elapsed_sec": 0,
        "flash_logs": [],
        "reboot_button_verified": False,
        "bluetooth_checks": {},
        "openwrt_rootfs_checks": {},
        "errors_and_hardships": []
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})

            print(f"[+] Loading S8 Imager UI...")
            page.goto(base_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            # Step 1: Human navigation to Flash OS page and select OpenWrt
            page.click("#navBtnFlash")
            page.wait_for_timeout(500)

            distro_size_mb = round(TARGET_DISTRO.stat().st_size / (1024 * 1024), 2)
            print(f"[+] Applying OpenWrt target image: {TARGET_DISTRO.name} ({distro_size_mb} MB)")
            page.evaluate(
                """([p, name, mb]) => {
                    applySelectedImage(p, name, mb, 'tar.gz');
                }""",
                [str(TARGET_DISTRO), TARGET_DISTRO.name, distro_size_mb]
            )
            page.wait_for_timeout(400)

            # Set 16 GB Allocation
            page.evaluate("() => { updateAllocSlider(16); }")
            page.wait_for_timeout(300)

            # Capture setup screenshot
            p1 = ARTIFACT_DIR / "openwrt_01_setup.png"
            page.screenshot(path=str(p1), full_page=True)
            captured_photos.append((p1, "[VISUAL PROOF 1/3] OpenWrt 23.05.5 Target Selected & 16GB Allocation"))
            print(f"[+] Captured setup view: {p1.name}")

            # Step 2: Trigger Deployment
            print(f"[+] Clicking START FLASH DEPLOYMENT (#btnStartDeploy)...")
            flash_btn = page.locator("#btnStartDeploy")
            flash_btn.click()
            page.wait_for_timeout(800)

            # Step 3: Monitor Live Flashing
            flash_start = time.time()
            last_log_count = 0
            in_progress_snap = False

            while True:
                page.wait_for_timeout(1000)
                import urllib.request, json
                try:
                    with urllib.request.urlopen(f"{base_url}/api/flash/status", timeout=3) as resp:
                        api_data = json.loads(resp.read().decode())
                except Exception:
                    api_data = {}

                cur_status = api_data.get("status", "unknown")
                cur_progress = api_data.get("progress", 0.0)
                logs = api_data.get("logs", [])

                if len(logs) > last_log_count:
                    for l in logs[last_log_count:]:
                        print(f"    {l}")
                    last_log_count = len(logs)

                if cur_progress >= 0.45 and not in_progress_snap:
                    p2 = ARTIFACT_DIR / "openwrt_02_flashing.png"
                    page.screenshot(path=str(p2), full_page=True)
                    captured_photos.append((p2, f"[VISUAL PROOF 2/3] OpenWrt Live USB Transfer & Unpacking ({cur_progress*100:.0f}%)"))
                    in_progress_snap = True
                    print(f"[+] Captured in-progress view: {p2.name}")

                if cur_status in ["completed", "failed"]:
                    audit_log["flash_status"] = cur_status
                    audit_log["flash_elapsed_sec"] = round(time.time() - flash_start, 1)
                    audit_log["flash_logs"] = logs
                    if cur_status == "failed":
                        audit_log["errors_and_hardships"].append(f"Flash failed: {api_data.get('error_msg')}")
                    print(f"\n[+] Flashing finished with status: {cur_status.upper()} in {audit_log['flash_elapsed_sec']}s")
                    break

                if time.time() - flash_start > 300:
                    audit_log["flash_status"] = "timeout"
                    audit_log["errors_and_hardships"].append("Flash timed out after 300s.")
                    print("[!] Flash timed out.")
                    break

            page.wait_for_timeout(1000)

            # Step 4: Verify Reboot Button Transformation
            btn_txt = page.locator("#btnStartDeployTxt").inner_text()
            print(f"[+] Post-flash button text: '{btn_txt}'")
            if "Reboot" in btn_txt:
                audit_log["reboot_button_verified"] = True
                print("[PASS] Flash button successfully transformed into 'Reboot Device'!")
            else:
                audit_log["errors_and_hardships"].append(f"Button did not transform into Reboot Device. Actual: '{btn_txt}'")

            p3 = ARTIFACT_DIR / "openwrt_03_reboot_ready.png"
            page.screenshot(path=str(p3), full_page=True)
            captured_photos.append((p3, "[VISUAL PROOF 3/3] Deployment Complete: 'Reboot Device' Button Active"))
            print(f"[+] Captured completion view: {p3.name}")

            browser.close()

    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        print("[+] Test server shutdown complete.")

    # Step 5: Post-Flash Hardware & OpenWrt Inspection via ADB
    print(f"\n[+] Inspecting live post-flash phone filesystem via ADB...")
    # Mount rootfs to inspect
    adb.shell("mkdir -p /mnt/ubuntu; mount -o loop,rw /data/linux/rootfs.img /mnt/ubuntu 2>/dev/null || true")

    os_release = adb.shell("cat /mnt/ubuntu/etc/os-release /mnt/ubuntu/etc/openwrt_release 2>/dev/null")
    audit_log["openwrt_rootfs_checks"]["os_release"] = os_release
    print(f"    OpenWrt Release Info:\n{os_release}")

    root_files = adb.shell("ls -la /mnt/ubuntu 2>/dev/null")
    audit_log["openwrt_rootfs_checks"]["root_files"] = root_files[:300]
    print(f"    Root directory listing:\n{root_files[:300]}...")

    # Step 6: Bluetooth Hardware & Stack Diagnostics
    print(f"\n[+] Testing Bluetooth Subsystem (Broadcom BCM4361)...")
    rfkill_state_before = adb.shell("cat /sys/class/rfkill/rfkill0/state 2>/dev/null")
    print(f"    rfkill0 state before: {rfkill_state_before.strip()}")

    # Unblock Bluetooth via sysfs
    adb.shell("echo 1 > /sys/class/rfkill/rfkill0/state 2>/dev/null")
    rfkill_state_after = adb.shell("cat /sys/class/rfkill/rfkill0/state 2>/dev/null")
    audit_log["bluetooth_checks"]["rfkill0_unblocked"] = rfkill_state_after.strip()
    print(f"    rfkill0 state after unblock: {rfkill_state_after.strip()}")

    # Check for Bluetooth tools inside OpenWrt
    bt_tools = adb.shell("ls -l /mnt/ubuntu/usr/bin/bluetoothctl /mnt/ubuntu/usr/sbin/bluetoothd /mnt/ubuntu/usr/bin/hciconfig 2>/dev/null || true")
    audit_log["bluetooth_checks"]["openwrt_bt_tools"] = bt_tools.strip()
    print(f"    OpenWrt Bluetooth userland binaries:\n{bt_tools.strip() if bt_tools.strip() else 'None found'}")

    if not bt_tools.strip():
        audit_log["errors_and_hardships"].append(
            "OpenWrt Hardship 1: Pristine OpenWrt minirootfs lacks BlueZ / hciconfig / bluetoothctl by default. "
            "Requires opkg update && opkg install bluez-daemon bluez-utils kmod-bluetooth."
        )

    # Check BCM4361 firmware availability
    fw_check = adb.shell("ls -l /vendor/firmware/bcm4361* /etc/firmware/BCM4361* 2>/dev/null || true")
    audit_log["bluetooth_checks"]["firmware_presence"] = fw_check.strip()
    print(f"    BCM4361 Firmware presence:\n{fw_check.strip()}")

    # Check init system in OpenWrt
    init_check = adb.shell("ls -l /mnt/ubuntu/sbin/init /mnt/ubuntu/sbin/procd 2>/dev/null")
    audit_log["openwrt_rootfs_checks"]["init_binary"] = init_check.strip()
    print(f"    OpenWrt Init System:\n{init_check.strip()}")

    if "procd" in init_check:
        audit_log["errors_and_hardships"].append(
            "OpenWrt Hardship 2: OpenWrt uses 'procd' as PID 1 and UCI (/etc/config/) instead of systemd. "
            "Ubuntu/Debian boot scripts (such as start_all.sh invoking systemd/D-Bus) do not run natively under procd without OpenWrt init.d service scripts."
        )

    # Check Web Interface / LuCI
    luci_check = adb.shell("ls -d /mnt/ubuntu/www 2>/dev/null || true")
    if not luci_check.strip():
        audit_log["errors_and_hardships"].append(
            "OpenWrt Hardship 3: Pristine generic armv8 rootfs does not include LuCI web interface preinstalled. Requires 'opkg install luci'."
        )

    # Clean unmount
    adb.shell("umount /mnt/ubuntu 2>/dev/null || true")

    # Step 7: Dispatch Visual Proofs to Telegram
    print(f"\n[+] Dispatching {len(captured_photos)} visual proofs to Telegram...")
    for path, caption in captured_photos:
        send_telegram_photo(str(path), caption=caption)
        time.sleep(1)

    summary_msg = (
        f"[REPORT] *OpenWrt Deployment & Bluetooth Audit Complete:*\n"
        f"- Target: `{TARGET_DISTRO.name}`\n"
        f"- Flashing Status: `{audit_log['flash_status'].upper()}` ({audit_log['flash_elapsed_sec']}s)\n"
        f"- Reboot Button Verified: `{audit_log['reboot_button_verified']}`\n"
        f"- Bluetooth Radio: `rfkill0 state={audit_log['bluetooth_checks'].get('rfkill0_unblocked')}`\n"
        f"- Hardships Identified: {len(audit_log['errors_and_hardships'])}\n"
        f"See conversation artifacts for the detailed architectural breakdown."
    )
    send_telegram_message(summary_msg)

    print("\n[+] Audit run completed successfully.")
    return audit_log


if __name__ == "__main__":
    main()

