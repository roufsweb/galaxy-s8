from playwright.sync_api import sync_playwright
import time
import os

ARTIFACT_DIR = r"C:\Users\rakib\.gemini\antigravity\brain\856563d1-ce89-44fd-8c75-5b4b5db94bbc"
EXACT_TOKEN = "524b869054a8bed7891dbaa27e439f58e044fe6368b156f2286ce749d747aece"

def run_portainer_flow():
    print(f"Using Exact Portainer Setup Token: {EXACT_TOKEN}")
    print("=== Portainer CE Human-Like Web UI Interactive Setup ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 900})
        page = context.new_page()

        print("[Step 1] Navigating to http://localhost:9000/...")
        page.goto("http://localhost:9000/")
        
        # Wait for form to mount
        print("Waiting for password input to mount...")
        page.wait_for_selector("#password", timeout=25000)
        time.sleep(1)

        # 1. Capture Initial Setup Screen
        shot1 = os.path.join(ARTIFACT_DIR, "portainer_screen_1_setup.png")
        page.screenshot(path=shot1, full_page=True)
        print(f"Captured Portainer setup screen: {shot1}")

        # Fill fields with keystroke typing
        print("Typing credentials and token...")
        page.fill("#username", "")
        page.type("#username", "admin", delay=20)
        
        page.fill("#password", "")
        page.type("#password", "admin12345678", delay=20)

        page.fill("#confirm_password", "")
        page.type("#confirm_password", "admin12345678", delay=20)

        page.fill("#setup_token", "")
        page.type("#setup_token", EXACT_TOKEN, delay=10)

        time.sleep(1)

        # Check button state
        btn_create = page.wait_for_selector("button:has-text('Create user')", timeout=5000)
        is_disabled = btn_create.is_disabled()
        print(f"Create user button disabled: {is_disabled}")

        if not is_disabled:
            btn_create.click()
            print("Clicked 'Create user'. Waiting for environment page...")
            time.sleep(6)

            # 2. Select Local Environment / Get Started
            shot_env = os.path.join(ARTIFACT_DIR, "portainer_screen_2_environments.png")
            page.screenshot(path=shot_env, full_page=True)
            print(f"Captured environments screen: {shot_env}")

            # Click Get Started or environment item
            for sel in ["button:has-text('Get Started')", "div:has-text('Get Started')", ".blocklist-item", "a[href*='local']", "tr:has-text('local')", "div:has-text('local')"]:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.click()
                        print(f"Clicked environment element: {sel}")
                        time.sleep(4)
                        break
                except Exception:
                    pass

            time.sleep(4)

            # 3. Capture Live Portainer Dashboard
            shot_dash = os.path.join(ARTIFACT_DIR, "portainer_screen_3_dashboard_live.png")
            page.screenshot(path=shot_dash, full_page=True)
            print(f"Captured live Portainer Dashboard: {shot_dash}")

            # Extract dashboard text
            body = page.inner_text("body")
            print("\n--- Portainer Dashboard Metrics ---")
            for line in body.splitlines():
                if any(k in line.lower() for k in ["container", "image", "volume", "stack", "portainer", "adguard", "docker", "local", "dashboard"]):
                    print("  Metric:", line.strip())

        browser.close()
        print("Portainer CE verification finished!")

if __name__ == "__main__":
    run_portainer_flow()
