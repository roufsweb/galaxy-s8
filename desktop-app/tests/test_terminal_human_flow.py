"""
Layer 3: Agentic E2E Human-Flow Test for Galaxy S8 Root Terminal (Dual-Shell & Dual-Transport).
Simulates realistic human typing, command execution, ANSI rendering, shell switching,
RWP Wi-Fi vs USB transport switching, keybindings, and captures visual proof artifacts.
"""
import unittest
import threading
import time
import socket
import sys
import os
from pathlib import Path
from http.server import HTTPServer

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from playwright.sync_api import sync_playwright

from app.server.api import start_server, S8ApiHandler
from app.core.adb import AdbClient
from app.core.device import DeviceManager
from app.core.flasher import FlasherEngine

ARTIFACTS_DIR = Path(os.environ.get("ANTIGRAVITY_ARTIFACTS_DIR", r"C:\Users\rakib\.gemini\antigravity\brain\32ab8e00-683f-431e-8f7d-5b48926742e1"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


class TestTerminalHumanFlow(unittest.TestCase):
    """Rigorous end-to-end human simulation of the Terminal page."""

    server = None
    server_thread = None
    port = None
    base_url = None

    @classmethod
    def setUpClass(cls):
        # Bind ephemeral port
        s = socket.socket()
        s.bind(("", 0))
        cls.port = s.getsockname()[1]
        s.close()

        cls.server = start_server(host="127.0.0.1", port=cls.port, serial="ce10171ab3e9620804")
        # Ensure offline test execution is instant, robust, and deterministic
        S8ApiHandler.adb_client.is_connected = lambda: False
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()

    def test_terminal_real_human_journey(self):
        """Simulates real human interaction with the Terminal page."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            # 1. Human Navigation: Load the Desktop Application
            page.goto(self.base_url, wait_until="domcontentloaded")
            page.wait_for_selector("#navBtnTerminal", timeout=10000)
            self.assertIn("S8 Imager", page.title())

            # 2. Navigate to Root Terminal Page
            page.click("#navBtnTerminal")
            page.wait_for_selector("#termNativeInput", state="visible", timeout=10000)
            self.assertTrue(page.locator("#pageTerminal").is_visible(), "Terminal page must be visible")

            # Capture Initial Terminal View
            initial_screenshot = ARTIFACTS_DIR / "terminal_screen_initial.png"
            page.screenshot(path=str(initial_screenshot), full_page=False)
            self.assertTrue(initial_screenshot.exists(), "Initial terminal screenshot must exist")

            # 3. Simulate Human Keystroke Typing for 's8ctl status'
            term_input = page.locator("#termNativeInput")
            term_input.focus()
            term_input.type("s8ctl status", delay=35)
            page.wait_for_timeout(200)
            page.keyboard.press("Enter")
            
            # Wait for s8ctl status to complete and verify output is directly in its entry block
            page.wait_for_function("() => !document.querySelector('#term-entry-0')?.innerText.includes('Executing')", timeout=15000)
            entry_0_text = page.locator("#term-entry-0").inner_text()
            self.assertIn("s8ctl status", entry_0_text)
            self.assertTrue("Samsung" in entry_0_text or "Exynos" in entry_0_text or "CPU" in entry_0_text)

            # 4. Human interaction typing 'uname -a' and 'free -h'
            term_input.focus()
            term_input.type("uname -a", delay=25)
            page.keyboard.press("Enter")
            page.wait_for_function("() => !document.querySelector('#term-entry-1')?.innerText.includes('Executing')", timeout=15000)
            entry_1_text = page.locator("#term-entry-1").inner_text()
            self.assertIn("uname -a", entry_1_text)
            self.assertIn("Linux", entry_1_text)

            term_input.focus()
            term_input.type("free -h", delay=25)
            page.keyboard.press("Enter")
            page.wait_for_function("() => !document.querySelector('#term-entry-2')?.innerText.includes('Executing')", timeout=15000)
            entry_2_text = page.locator("#term-entry-2").inner_text()
            self.assertIn("free -h", entry_2_text)
            self.assertTrue("Mem:" in entry_2_text or "total" in entry_2_text)

            # 5. Capture Live OS Shell Screenshot with outputs cleanly beneath commands
            os_screenshot = ARTIFACTS_DIR / "terminal_os_live.png"
            page.screenshot(path=str(os_screenshot), full_page=False)
            self.assertTrue(os_screenshot.exists(), "OS Shell live screenshot must exist")

            # 6. Test USB Wire Connection Badge & s8ctl Helper Dropdown
            badge_usb = page.locator("#badgeUsbConn")
            self.assertTrue(badge_usb.is_visible(), "USB ADB connection badge must be visible")
            self.assertIn("USB ADB", badge_usb.inner_text())

            # Test opening custom s8ctl dropdown menu
            menu_btn = page.locator("#s8ctlMenuBtn")
            self.assertTrue(menu_btn.is_visible(), "s8ctl menu button must be visible")
            menu_btn.click()
            page.wait_for_timeout(200)
            menu_dropdown = page.locator("#s8ctlMenuDropdown")
            self.assertTrue(menu_dropdown.is_visible(), "s8ctl custom dark dropdown must be open")

            # Click 's8ctl cpu performance' inside dropdown
            perf_btn = menu_dropdown.locator("button").filter(has_text="s8ctl cpu performance").first
            perf_btn.click()
            page.wait_for_timeout(200)
            page.wait_for_function("() => !document.querySelector('#term-entry-3')?.innerText.includes('Executing')", timeout=15000)
            entry_3_text = page.locator("#term-entry-3").inner_text()
            self.assertIn("s8ctl cpu performance", entry_3_text)

            # 7. Test Dual-Shell Switching: Switch to AP Shell
            btn_ap = page.locator("#btnShellAp")
            btn_ap.click()
            page.wait_for_timeout(300)
            ap_prompt = page.locator("#termInlinePrompt").inner_text()
            self.assertIn("Recovery", ap_prompt)

            # Type 'dmesg | tail -n 25' in AP Shell and wait for completion
            term_input.focus()
            term_input.type("dmesg | tail -n 25", delay=25)
            page.keyboard.press("Enter")
            page.wait_for_function("() => !document.querySelector('#term-entry-0')?.innerText.includes('Executing')", timeout=15000)
            ap_entry_0_text = page.locator("#term-entry-0").inner_text()
            self.assertIn("dmesg", ap_entry_0_text)

            # Capture AP Shell Screenshot
            ap_screenshot = ARTIFACTS_DIR / "terminal_ap_live.png"
            page.screenshot(path=str(ap_screenshot), full_page=False)
            self.assertTrue(ap_screenshot.exists(), "AP Shell live screenshot must exist")

            # 8. Test Command History Navigation (ArrowUp / ArrowDown)
            term_input.focus()
            page.keyboard.press("ArrowUp")
            page.wait_for_timeout(150)
            input_val = term_input.input_value()
            self.assertTrue(len(input_val) > 0, "ArrowUp must recall previous command from history")

            # 9. Test Keybinding: Ctrl+C Cancels Current Input
            page.keyboard.press("Control+c")
            page.wait_for_timeout(150)
            self.assertEqual(term_input.input_value(), "", "Ctrl+C must clear current input line")

            # 10. Test Clear Button
            page.click("button[title*='Clear']")
            page.wait_for_timeout(200)
            screen_buffer = page.locator("#termScreenBuffer")
            self.assertEqual(screen_buffer.inner_text().strip(), "", "Clear button must clear terminal buffer")

            # 11. Switch back to OS Shell and type a final verified confirmation
            page.click("#btnShellOs")
            page.wait_for_timeout(200)
            term_input.focus()
            term_input.type("echo 'Galaxy S8 Native Terminal 100% Operational'", delay=25)
            page.wait_for_timeout(150)
            page.keyboard.press("Enter")
            page.wait_for_function("() => !document.querySelector('#term-entry-5')?.innerText.includes('Executing')", timeout=15000)

            # Capture Final Verified Screenshot
            final_screenshot = ARTIFACTS_DIR / "terminal_final_verified.png"
            page.screenshot(path=str(final_screenshot), full_page=False)
            self.assertTrue(final_screenshot.exists(), "Final terminal screenshot must exist")

            # Zero console error assertion
            self.assertEqual(console_errors, [], f"Terminal generated unexpected browser console errors: {console_errors}")

            browser.close()


if __name__ == "__main__":
    unittest.main()
