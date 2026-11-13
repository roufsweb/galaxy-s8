#!/usr/bin/env python3
"""
capture_desktop_app_pages.py — Complete Visual Inspection & Page Screenshot Engine
Spins up the S8 Imager backend server, launches headless Chromium via Playwright,
navigates through every single page and modal, captures high-resolution screenshots,
saves them to docs/assets/screenshots/ and copies to the artifact directory.
"""

import os
import sys
import time
import socket
import threading
import shutil
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE / "desktop-app"))

from app.server.api import start_server
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path(os.environ.get("ANTIGRAVITY_ARTIFACTS_DIR", r"C:\Users\rakib\.gemini\antigravity\brain\32ab8e00-683f-431e-8f7d-5b48926742e1"))
OUT_DIR = WORKSPACE / "docs" / "assets" / "screenshots"

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def capture_all_pages():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    
    port = get_free_port()
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"
    
    print(f"[*] Starting S8 Imager server on {base_url}...")
    server = start_server(host=host, port=port, serial="ce10171ab3e9620804")
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    captured = {}
    
    try:
        with sync_playwright() as p:
            print("[*] Launching Chromium browser...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1366, "height": 820})
            page = context.new_page()
            
            # 1. Load Page 1: Flash OS
            print("[*] Capturing Page 1: Flash OS...")
            page.goto(base_url, wait_until="networkidle")
            page.wait_for_selector("#appSidebar", timeout=10000)
            page.wait_for_timeout(1000)
            
            p1_path = OUT_DIR / "s8_imager_page1_flash.png"
            page.screenshot(path=str(p1_path), full_page=False)
            captured["page1_flash"] = p1_path
            
            # 2. Open Official OS Catalog Modal
            print("[*] Capturing Modal: Official OS Catalog...")
            page.click("#btnOpenCatalog")
            page.wait_for_selector("#distroModal:not(.hidden)", timeout=5000)
            page.wait_for_timeout(500)
            
            p_cat_path = OUT_DIR / "s8_imager_modal_catalog.png"
            page.screenshot(path=str(p_cat_path), full_page=False)
            captured["modal_catalog"] = p_cat_path
            
            page.click("button[onclick='closeDistroModal()']")
            page.wait_for_timeout(300)
            
            # 3. Page 2: Hardware Dashboard
            print("[*] Capturing Page 2: Hardware Dashboard...")
            page.click("#navBtnDashboard")
            page.wait_for_selector("#pageDashboard:not(.hidden)", timeout=5000)
            page.wait_for_timeout(1000)
            
            p2_path = OUT_DIR / "s8_imager_page2_dashboard.png"
            page.screenshot(path=str(p2_path), full_page=False)
            captured["page2_dashboard"] = p2_path
            
            # 4. Page 3: Interactive Terminal
            print("[*] Capturing Page 3: Interactive Terminal...")
            page.click("#navBtnTerminal")
            page.wait_for_selector("#pageTerminal:not(.hidden)", timeout=5000)
            # Run a simulated fast command in terminal to show real terminal activity
            page.fill("#termNativeInput", "s8ctl status")
            page.keyboard.press("Enter")
            page.wait_for_timeout(1200)
            
            p3_path = OUT_DIR / "s8_imager_page3_terminal.png"
            page.screenshot(path=str(p3_path), full_page=False)
            captured["page3_terminal"] = p3_path
            
            # 5. Page 4: Config & Rollback
            print("[*] Capturing Page 4: Config & Rollback...")
            page.click("#navBtnConfig")
            page.wait_for_selector("#pageConfig:not(.hidden)", timeout=5000)
            page.wait_for_timeout(1000)
            
            p4_path = OUT_DIR / "s8_imager_page4_config.png"
            page.screenshot(path=str(p4_path), full_page=False)
            captured["page4_config"] = p4_path
            
            # 6. Modal: Buy Me a Coffee / Support Project
            print("[*] Capturing Modal: Buy Me a Coffee...")
            page.click("button[onclick='openDonateModal()']")
            page.wait_for_selector("#donateModal:not(.hidden)", timeout=5000)
            page.wait_for_timeout(500)
            
            p_don_path = OUT_DIR / "s8_imager_modal_donate.png"
            page.screenshot(path=str(p_don_path), full_page=False)
            captured["modal_donate"] = p_don_path
            
            browser.close()
            
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        
    print("\n[OK] All Page Screenshots Captured Successfully:")
    for k, p in captured.items():
        print(f"  - {k}: {p} ({p.stat().st_size} bytes)")
        dest = ARTIFACT_DIR / p.name
        shutil.copyfile(p, dest)
        
    return captured

if __name__ == "__main__":
    capture_all_pages()
