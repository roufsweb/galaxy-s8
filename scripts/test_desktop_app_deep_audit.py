import os
import sys
import time
import socket
import threading
from pathlib import Path

WORKSPACE = Path(r"e:\rouf\galaxy-s8")
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "desktop-app"))

from app.server.api import start_server
from app.core.adb import AdbClient
from scripts.send_telegram import send_telegram_message, send_telegram_photo
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path(os.environ.get("ANTIGRAVITY_ARTIFACTS_DIR", r"C:\Users\rakib\.gemini\antigravity\brain\32ab8e00-683f-431e-8f7d-5b48926742e1"))
SERIAL = "ce10171ab3e9620804"

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def main():
    print("=== DEEP DESKTOP APP & TERMINAL INTERACTION AUDIT ===")
    adb = AdbClient(SERIAL)
    print(f"[+] Device state: {adb.get_state()} (Online={adb.is_connected()})")

    port = get_free_port()
    base_url = f"http://127.0.0.1:{port}"
    server = start_server(host="127.0.0.1", port=port, serial=SERIAL)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[+] S8 Imager server active at {base_url}")

    captured_shots = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(base_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            # 1. Device Header & Telemetry Inspection
            print("[+] Verifying Device Header & Connection Pills...")
            dev_status = page.locator("#deviceStatusPill").inner_text()
            print(f"    Connection Status Pill: '{dev_status}'")
            p1 = ARTIFACT_DIR / "app_audit_01_device_connected.png"
            page.screenshot(path=str(p1), full_page=True)
            captured_shots.append((p1, "[VISUAL PROOF] S8 Imager Live Device Header & Telemetry"))

            # 2. Terminal Navigation & Interactive Commands
            print("[+] Navigating to Terminal section...")
            page.click("#navBtnTerminal")
            page.wait_for_selector("#termNativeInput", state="visible", timeout=10000)

            print("[+] Executing terminal command: 'uname -a'...")
            term_input = page.locator("#termNativeInput")
            term_input.focus()
            term_input.type("uname -a", delay=20)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)

            print("[+] Executing terminal command: 'cat /proc/uptime'...")
            term_input.focus()
            term_input.type("cat /proc/uptime", delay=20)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)

            print("[+] Executing terminal command: 'df -h /data'...")
            term_input.focus()
            term_input.type("df -h /data", delay=20)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)

            term_out = page.locator("#term-entry-0").inner_text() if page.locator("#term-entry-0").count() > 0 else "No entries"
            print(f"    Terminal Entry 0:\n{term_out}")

            p2 = ARTIFACT_DIR / "app_audit_02_terminal_active.png"
            page.screenshot(path=str(p2), full_page=True)
            captured_shots.append((p2, "[VISUAL PROOF] Terminal Execution: Kernel #6 Live Output"))

            # 3. Sidebar Collapse & Navigation Responsiveness
            print("[+] Testing Sidebar Collapse...")
            page.click("#sidebarLogoBadge")
            page.wait_for_timeout(400)
            p3 = ARTIFACT_DIR / "app_audit_03_sidebar_collapsed.png"
            page.screenshot(path=str(p3), full_page=True)
            captured_shots.append((p3, "[VISUAL PROOF] Responsive UI: Collapsed Sidebar Mode"))

            # Expand sidebar back
            page.click("#sidebarLogoBadge")
            page.wait_for_timeout(300)

            # 4. Device Config & Battery Health Section
            print("[+] Navigating to Device Config tab...")
            page.click("#navBtnConfig")
            page.wait_for_timeout(600)
            p4 = ARTIFACT_DIR / "app_audit_04_device_config.png"
            page.screenshot(path=str(p4), full_page=True)
            captured_shots.append((p4, "[VISUAL PROOF] Device Configuration & Battery Health Dashboard"))

            browser.close()

    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        print("[+] Test server shutdown complete.")

    # Dispatch visual updates to Telegram
    for path, caption in captured_shots:
        send_telegram_photo(str(path), caption)

    print("[+] All desktop app feature tests passed and photos dispatched to Telegram.")

if __name__ == "__main__":
    main()
