from playwright.sync_api import sync_playwright
import time
import os

ARTIFACT_DIR = r"C:\Users\rakib\.gemini\antigravity\brain\856563d1-ce89-44fd-8c75-5b4b5db94bbc"

def run_human_interaction():
    print("=== CasaOS Human-Like Web UI Interactive Verification ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use realistic desktop viewport
        context = browser.new_context(viewport={'width': 1600, 'height': 900})
        page = context.new_page()

        print("\n[Step 1] Navigating to http://localhost:8080/...")
        page.goto("http://localhost:8080/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # 1. Fill login form
        print("\n[Step 2] Logging in as user 'ubuntu'...")
        user_input = page.wait_for_selector("input[type='text'], input[placeholder*='ser']", timeout=10000)
        pass_input = page.wait_for_selector("input[type='password']", timeout=10000)
        
        user_input.fill("ubuntu")
        time.sleep(0.5)
        pass_input.fill("ubuntu")
        time.sleep(0.5)

        # Click login button
        login_btn = page.wait_for_selector("button:has-text('Login'), button[type='submit']", timeout=5000)
        login_btn.click()
        print("Submitted login. Waiting for dashboard...")
        time.sleep(5)

        # 2. Capture Dashboard
        dash_shot = os.path.join(ARTIFACT_DIR, "casaos_dashboard_verified.png")
        page.screenshot(path=dash_shot, full_page=True)
        print(f"Captured dashboard screenshot: {dash_shot}")

        # Check for error toasts / messages
        body_text = page.inner_text("body")
        print("\n--- Dashboard Content Check ---")
        errors = [line for line in body_text.splitlines() if any(w in line.lower() for w in ["fail", "error", "unable", "fatal"])]
        if errors:
            print("ALERT: Detected errors on dashboard:")
            for e in errors:
                print("  ->", e)
        else:
            print("SUCCESS: Zero error banners or toasts detected on dashboard!")

        # 3. Find App Store button
        print("\n[Step 3] Locating App Store in UI...")
        # CasaOS usually has an App Store card/icon or top-bar button
        appstore_el = None
        selectors = [
            "text='App Store'",
            ".app-card:has-text('App Store')",
            "[aria-label='App Store']",
            "div:has-text('App Store')",
            "span:has-text('App Store')"
        ]
        for sel in selectors:
            try:
                el = page.wait_for_selector(sel, timeout=3000)
                if el and el.is_visible():
                    appstore_el = el
                    print(f"Found App Store element with selector: {sel}")
                    break
            except Exception:
                pass

        if appstore_el:
            print("Clicking App Store...")
            appstore_el.click()
            print("Waiting for App Store modal and app catalog to load...")
            time.sleep(6)

            # Capture App Store screenshot
            store_shot = os.path.join(ARTIFACT_DIR, "casaos_appstore_verified.png")
            page.screenshot(path=store_shot, full_page=True)
            print(f"Captured App Store screenshot: {store_shot}")

            store_text = page.inner_text("body")
            store_errors = [line for line in store_text.splitlines() if any(w in line.lower() for w in ["fail to load", "error loading", "failed to fetch"])]
            if store_errors:
                print("ALERT: App Store displays errors:")
                for e in store_errors:
                    print("  ->", e)
            else:
                print("SUCCESS: App Store loaded cleanly without 'fail to load apps'!")

            # Check some visible apps
            print("\nSampling visible app titles in store:")
            app_titles = page.query_selector_all(".app-title, .title, h4, h3, .name")
            count = 0
            for t in app_titles:
                txt = t.inner_text().strip()
                if txt and len(txt) < 30 and txt not in ["CasaOS", "App Store", "Custom Install", "Categories"]:
                    print(f"  - App: {txt}")
                    count += 1
                    if count >= 8:
                        break
        else:
            print("Could not find App Store selector. Dumping visible elements...")
            for btn in page.query_selector_all("button, a"):
                t = btn.inner_text().strip()
                if t:
                    print("Button/Link:", t)

        browser.close()
        print("\n=== Playwright Verification Completed ===")

if __name__ == "__main__":
    run_human_interaction()

