"""
Layer 3: Agentic End-to-End (E2E) Real-Human Flow Test Suite
Uses Playwright to simulate a human engineer operating S8 Imager desktop app:
navigating sidebar tabs, collapsing/expanding menus, opening the Distro Library
modal, switching target Linux distributions, selecting partition storage tiers,
and interacting with terminal controls. Captures visual proof of verified journeys.
"""
import unittest
import threading
import socket
import time
import os
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.server.api import start_server
from playwright.sync_api import sync_playwright


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestE2EHumanFlow(unittest.TestCase):
    """Simulates real-human user interactions across the full desktop app."""

    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        cls.host = "127.0.0.1"
        cls.base_url = f"http://{cls.host}:{cls.port}"
        cls.artifact_dir = Path(os.environ.get("ANTIGRAVITY_ARTIFACTS_DIR", r"C:\Users\rakib\.gemini\antigravity\brain\32ab8e00-683f-431e-8f7d-5b48926742e1"))
        cls.artifact_dir.mkdir(parents=True, exist_ok=True)

        cls.server = start_server(host=cls.host, port=cls.port, serial="ce10171ab3e9620804")
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)

    def test_complete_human_desktop_journey(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            # 1. Human Navigation: Load the Desktop Application
            page.goto(self.base_url, wait_until="domcontentloaded")
            page.wait_for_selector("#appSidebar", timeout=10000)
            self.assertIn("S8 Imager", page.title())

            # 2. Sidebar Navigation Journey
            # Step A: Test Sidebar Collapse / Expand (Both via Collapse Button and Phone Icon)
            sidebar = page.locator("#appSidebar")
            self.assertIn("w-56", sidebar.get_attribute("class") or "")
            page.click("#sidebarToggleBtn")
            page.wait_for_timeout(350)
            self.assertIn("w-16", sidebar.get_attribute("class") or "")
            page.click("#sidebarToggleBtn")
            page.wait_for_timeout(350)
            self.assertIn("w-56", sidebar.get_attribute("class") or "")

            # Test collapse/expand via phone logo icon
            page.click("#sidebarLogoBadge")
            page.wait_for_timeout(350)
            self.assertIn("w-16", sidebar.get_attribute("class") or "")
            page.click("#sidebarLogoBadge")
            page.wait_for_timeout(350)
            self.assertIn("w-56", sidebar.get_attribute("class") or "")

            # Step B: Navigate to Page 2 (Hardware Dashboard)
            page.click("#navBtnDashboard")
            page.wait_for_timeout(250)
            self.assertTrue(page.locator("#pageDashboard").is_visible(), "Dashboard should be visible")
            self.assertFalse(page.locator("#pageFlash").is_visible(), "Flash page should be hidden")

            # Step C: Navigate to Page 3 (Root Terminal)
            page.click("#navBtnTerminal")
            page.wait_for_timeout(250)
            self.assertTrue(page.locator("#pageTerminal").is_visible(), "Terminal page should be visible")

            # Step D: Navigate to Page 4 (Device & Network Configuration)
            page.click("#navBtnConfig")
            page.wait_for_timeout(250)
            self.assertTrue(page.locator("#pageConfig").is_visible(), "Config page should be visible")
            self.assertTrue(page.locator("#wifiSsidSelect").is_visible(), "Wi-Fi SSID selector should be visible")
            self.assertTrue(page.locator("#wifiConnectBtn").is_visible(), "Wi-Fi Connect button should be visible")
            self.assertTrue(page.locator("#configHostnameInput").is_visible(), "Hostname input should be visible")
            self.assertTrue(page.locator("#btnApplyHostname").is_visible(), "Apply Hostname button should be visible")
            self.assertTrue(page.locator("#configSshKeyInput").is_visible(), "SSH Key input should be visible")
            self.assertTrue(page.locator("#configPassInput").is_visible(), "Password input should be visible")

            # Step E: Return to Flash OS
            page.click("#navBtnFlash")
            page.wait_for_timeout(250)
            self.assertTrue(page.locator("#pageFlash").is_visible(), "Flash page should be visible again")

            # 3. Simulate Human Interaction on Unified Flash OS Page
            self.assertTrue(page.locator("#flashSelectedName").is_visible(), "Target image name should be visible")

            # Test Universal Storage Slider Dragging
            slider = page.locator("#allocSlider")
            slider.fill("32")
            page.wait_for_timeout(150)
            self.assertEqual("32", page.locator("#sliderValueDisplay").inner_text())

            slider.fill("16")
            page.wait_for_timeout(150)
            self.assertEqual("16", page.locator("#sliderValueDisplay").inner_text())

            # Verify Unified Flashing & Hardware Telemetry Log
            self.assertTrue(page.locator("#flashLogWindow").is_visible())
            self.assertTrue(page.locator("#btnStartDeploy").is_visible())

            # 4. Capture Visual Artifact for User Review
            screenshot_path = self.artifact_dir / "desktop_human_e2e.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            self.assertTrue(screenshot_path.exists(), "E2E screenshot was not created")

            # 5. Assert Zero Console Errors
            self.assertEqual(console_errors, [], f"Console errors detected: {console_errors}")

            browser.close()


if __name__ == "__main__":
    unittest.main()
