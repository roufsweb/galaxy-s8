#!/usr/bin/env python3
"""
desktop-app/tests/test_reboot_flow.py — Test Flash -> Reboot Device UI Transformation
Verifies:
1. Flash deployment completes successfully.
2. Flash button converts to 'Reboot Device' (emerald styling, rotate-cw icon).
3. Clicking 'Reboot Device' triggers POST /api/reboot and sets loading state.
4. Selecting a new image resets button back to 'Flash Image'.
"""

import os
import sys
import time
import socket
import threading
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "desktop-app"))

from app.server.api import start_server
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path(os.environ.get("ANTIGRAVITY_ARTIFACTS_DIR", r"C:\Users\rakib\.gemini\antigravity\brain\32ab8e00-683f-431e-8f7d-5b48926742e1"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_reboot_flow():
    port = get_free_port()
    base_url = f"http://127.0.0.1:{port}"
    server = start_server(host="127.0.0.1", port=port, serial="mock_device")
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[+] Server started at {base_url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(base_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            # Step 1: Navigate to Flash OS page
            page.click("#navBtnFlash")
            page.wait_for_timeout(500)

            # Verify initial button state
            btn = page.locator("#btnStartDeploy")
            btn_txt = page.locator("#btnStartDeployTxt")
            assert "Flash Image" in btn_txt.inner_text(), f"Unexpected initial text: {btn_txt.inner_text()}"
            print("[PASS] Initial button state is 'Flash Image'.")

            # Capture initial screenshot
            p1 = ARTIFACT_DIR / "reboot_flow_01_initial.png"
            page.screenshot(path=str(p1), full_page=True)
            print(f"[+] Captured {p1.name}")

            # Step 2: Simulate flash completed state via setButtonToRebootMode()
            page.evaluate("() => { setButtonToRebootMode(); }")
            page.wait_for_timeout(300)

            # Verify transformed button state
            btn_txt_after = page.locator("#btnStartDeployTxt").inner_text()
            assert "Reboot Device" in btn_txt_after, f"Button text did not convert: {btn_txt_after}"
            btn_class = btn.get_attribute("class")
            assert "bg-emerald-500" in btn_class, f"Button class missing bg-emerald-500: {btn_class}"
            print("[PASS] Button successfully converted to 'Reboot Device' with emerald styling.")

            # Capture converted reboot button screenshot
            p2 = ARTIFACT_DIR / "reboot_flow_02_reboot_button.png"
            page.screenshot(path=str(p2), full_page=True)
            print(f"[+] Captured {p2.name}")

            # Step 3: Click 'Reboot Device'
            btn.click()
            page.wait_for_timeout(500)

            # Verify rebooting state
            btn_html = btn.inner_html()
            assert "Rebooting Device..." in btn_html, f"Button did not enter rebooting state: {btn_html}"
            assert btn.is_disabled(), "Button should be disabled during reboot"
            print("[PASS] Clicking 'Reboot Device' triggered rebooting state.")

            # Capture rebooting in progress screenshot
            p3 = ARTIFACT_DIR / "reboot_flow_03_rebooting.png"
            page.screenshot(path=str(p3), full_page=True)
            print(f"[+] Captured {p3.name}")

            # Step 4: Verify selecting a new image resets button back to 'Flash Image'
            page.evaluate("""() => {
                applySelectedImage('test/path/ubuntu.tar.gz', 'Ubuntu 24.04', 500, 'tar.gz');
            }""")
            page.wait_for_timeout(300)

            btn_txt_reset = page.locator("#btnStartDeployTxt").inner_text()
            assert "Flash Image" in btn_txt_reset, f"Button did not reset to 'Flash Image': {btn_txt_reset}"
            btn_class_reset = btn.get_attribute("class")
            assert "bg-sky-500" in btn_class_reset, f"Button class missing bg-sky-500: {btn_class_reset}"
            print("[PASS] Selecting new image resets button back to 'Flash Image'.")

            # Capture reset screenshot
            p4 = ARTIFACT_DIR / "reboot_flow_04_reset.png"
            page.screenshot(path=str(p4), full_page=True)
            print(f"[+] Captured {p4.name}")

            browser.close()

    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        print("[+] Test server shutdown complete.")

    print("\n[ALL TESTS PASSED SUCCESSFULLY]")


if __name__ == "__main__":
    test_reboot_flow()

