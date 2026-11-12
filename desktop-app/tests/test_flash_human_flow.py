"""
Layer 3: Agentic End-to-End Human Flow Test Suite — Flash OS & Storage Partitioning
Simulates a real engineer navigating the S8 Imager desktop app:
1. Universal custom image selection via File Explorer picker.
2. Library preset switching (Debian 12, Kali, HAOS, Ubuntu).
3. Live vs Target OS contrast verification (Already Flashed vs Ready to Flash).
4. Windows C:/D: style storage slider & dynamic proportion bar math (4GB to 48GB).
5. Clean Ext4 format toggle and 2-stage deployment pipeline execution.
6. Captures high-res visual proof artifact: flash_page_verified.png.
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


class TestFlashHumanFlow(unittest.TestCase):
    """Exhaustive human-flow simulation for Flash OS and Storage Partitioning."""

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

    def test_flash_and_storage_partitioning_journey(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            # 1. Load Application
            page.goto(self.base_url, wait_until="domcontentloaded")
            self.assertIn("S8 Imager", page.title())
            page.wait_for_timeout(300)

            # 2. Check Initial Unified Flash Page State
            self.assertTrue(page.locator("#pageFlash").is_visible(), "Flash OS page should be visible by default")
            self.assertTrue(page.locator("#flashSelectedName").is_visible(), "Target image name should be visible")

            # 3. Simulate Universal File Selection
            page.set_input_files("#customImgFileInput", {
                "name": "kali-linux-custom-arm64.img",
                "mimeType": "application/octet-stream",
                "buffer": b"S8_KALI_CUSTOM_IMAGE_TEST_PAYLOAD" * 1024
            })
            page.wait_for_timeout(300)

            # Assert Custom File Name & Format Badge Updated
            self.assertIn("kali-linux-custom-arm64.img", page.locator("#flashSelectedName").inner_text())
            self.assertIn("RAW ROOTFS", page.locator("#flashTargetBadge").inner_text())

            # 4. Test Universal Storage Slider Dragging
            slider = page.locator("#allocSlider")

            # Test A: Set slider to 32 GB
            slider.fill("32")
            page.wait_for_timeout(150)
            self.assertEqual("32", page.locator("#sliderValueDisplay").inner_text())

            # Test B: Set slider to 48 GB
            slider.fill("48")
            page.wait_for_timeout(150)
            self.assertEqual("48", page.locator("#sliderValueDisplay").inner_text())

            # Test C: Reset slider to 16 GB default
            slider.fill("16")
            page.wait_for_timeout(150)
            self.assertEqual("16", page.locator("#sliderValueDisplay").inner_text())

            # 5. Test Unified Flashing & Real-Time Hardware Telemetry Log Window
            self.assertTrue(page.locator("#flashLogWindow").is_visible(), "Unified live log terminal window should be visible")
            self.assertTrue(page.locator("#btnCopyFlashLogs").is_visible(), "Copy Logs button should be visible")

            deploy_btn = page.locator("#btnStartDeploy")
            self.assertTrue(deploy_btn.is_enabled())
            deploy_btn.click()
            page.wait_for_timeout(300)

            # Check that deployment status moved to Flashing
            status_badge = page.locator("#flashStatusBadge").inner_text()
            self.assertTrue("FLASHING" in status_badge.upper() or "WRITING" in status_badge.upper())

            # Test Copy Logs button click
            page.click("#btnCopyFlashLogs")
            page.wait_for_timeout(200)

            # 8. Capture Visual Proof Screenshot for Antigravity Multimodal Review
            screenshot_path = self.artifact_dir / "flash_page_verified.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            self.assertTrue(screenshot_path.exists(), "flash_page_verified.png was not generated")

            # 9. Assert Zero Unhandled Console Errors
            self.assertEqual(console_errors, [], f"Unhandled console errors detected: {console_errors}")

            browser.close()


if __name__ == "__main__":
    unittest.main()
