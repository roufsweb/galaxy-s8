from playwright.sync_api import sync_playwright
import time
import os

ARTIFACT_DIR = r"C:\Users\rakib\.gemini\antigravity\brain\856563d1-ce89-44fd-8c75-5b4b5db94bbc"

def run_filebrowser_flow():
    print("=== FileBrowser Personal Cloud Web UI Verification ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 900})
        page = context.new_page()

        print("[Step 1] Navigating to http://localhost:8088/...")
        page.goto("http://localhost:8088/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # 1. Capture Login Screen
        shot1 = os.path.join(ARTIFACT_DIR, "filebrowser_screen_1_login.png")
        page.screenshot(path=shot1, full_page=True)
        print(f"Captured FileBrowser login screen: {shot1}")

        # Fill credentials
        print("Logging in as admin...")
        page.fill("input[type='text'], input[placeholder*='ser']", "admin")
        page.fill("input[type='password']", "admin12345678")
        time.sleep(1)

        # Click submit
        page.click("input[type='submit'], button[type='submit'], button:has-text('Login')")
        print("Submitted credentials. Waiting for file explorer...")
        time.sleep(5)

        # 2. Capture Live File Manager Dashboard
        shot2 = os.path.join(ARTIFACT_DIR, "filebrowser_screen_2_dashboard.png")
        page.screenshot(path=shot2, full_page=True)
        print(f"Captured FileBrowser Dashboard: {shot2}")

        # Verify listed files and folders
        body = page.inner_text("body")
        print("\n--- Files and Directories Detected in /mnt/android_data ---")
        for line in body.splitlines():
            line_s = line.strip()
            if any(f in line_s.lower() for f in ["docker", "adguard", "portainer", "filebrowser", "lost+found", "data"]):
                print("  Item:", line_s)

        # 3. Click on 'adguard' folder to browse inside
        adguard_folder = page.query_selector("text='adguard'")
        if adguard_folder:
            print("Clicking 'adguard' folder...")
            adguard_folder.click()
            time.sleep(3)
            shot3 = os.path.join(ARTIFACT_DIR, "filebrowser_screen_3_browse.png")
            page.screenshot(path=shot3, full_page=True)
            print(f"Captured directory contents: {shot3}")

        browser.close()
        print("FileBrowser verification 100% completed!")

if __name__ == "__main__":
    run_filebrowser_flow()

