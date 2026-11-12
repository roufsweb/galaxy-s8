"""
Capture multiple DOM screenshots of the S8 Imager OS Flash section
across different viewports and user interaction states.
"""
import threading
import socket
import time
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent / "desktop-app"
sys.path.insert(0, str(BASE_DIR))

from app.server.api import start_server
from playwright.sync_api import sync_playwright

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def main():
    port = get_free_port()
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"
    artifact_dir = Path(r"C:\Users\rakib\.gemini\antigravity\brain\856563d1-ce89-44fd-8c75-5b4b5db94bbc")

    server = start_server(host=host, port=port, serial="ce10171ab3e9620804")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Shot 1: Standard Desktop Viewport (1280x800) - Default Idle State
        ctx1 = browser.new_context(viewport={"width": 1280, "height": 800})
        page1 = ctx1.new_page()
        page1.goto(base_url, wait_until="networkidle")
        page1.wait_for_timeout(500)
        shot1 = artifact_dir / "flash_dom_1280_default.png"
        page1.screenshot(path=str(shot1), full_page=True)
        print(f"[+] Saved Shot 1: {shot1}")

        # Shot 2: Widescreen Viewport (1600x900) - Responsive Expansion
        ctx2 = browser.new_context(viewport={"width": 1600, "height": 900})
        page2 = ctx2.new_page()
        page2.goto(base_url, wait_until="networkidle")
        page2.wait_for_timeout(500)
        shot2 = artifact_dir / "flash_dom_1600_wide.png"
        page2.screenshot(path=str(shot2), full_page=True)
        print(f"[+] Saved Shot 2: {shot2}")

        # Shot 3: Distro Library Modal Open
        page1.click("button:has-text('Browse Library')")
        page1.wait_for_timeout(400)
        shot3 = artifact_dir / "flash_dom_modal_library.png"
        page1.screenshot(path=str(shot3), full_page=True)
        print(f"[+] Saved Shot 3: {shot3}")

        # Shot 4: Custom Image Selected (Simulated via Explorer file input)
        page1.evaluate("closeDistroModal()")
        page1.wait_for_timeout(200)
        page1.set_input_files("#customImgFileInput", {
            "name": "kali-linux-2024.3-exynos8895.img",
            "mimeType": "application/octet-stream",
            "buffer": b"KALI_LINUX_S8_CUSTOM_PAYLOAD" * 2048
        })
        page1.wait_for_timeout(300)
        shot4 = artifact_dir / "flash_dom_custom_selected.png"
        page1.screenshot(path=str(shot4), full_page=True)
        print(f"[+] Saved Shot 4: {shot4}")

        # Shot 5: Flashing Pipeline Active State
        page1.click("#btnStartDeploy")
        page1.wait_for_timeout(600)
        shot5 = artifact_dir / "flash_dom_flashing_active.png"
        page1.screenshot(path=str(shot5), full_page=True)
        print(f"[+] Saved Shot 5: {shot5}")

        browser.close()

    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    print("[+] All DOM screenshots captured successfully.")

if __name__ == "__main__":
    main()
