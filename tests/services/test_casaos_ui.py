from playwright.sync_api import sync_playwright
import time
import os
import sys

ARTIFACT_DIR = r"C:\Users\rakib\.gemini\antigravity\brain\856563d1-ce89-44fd-8c75-5b4b5db94bbc"

def main():
    print("Launching Playwright browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()

        print("Navigating to CasaOS at http://localhost:8080/...")
        try:
            page.goto("http://localhost:8080/", timeout=30000, wait_until="networkidle")
        except Exception as e:
            print("Navigation wait warning:", e)
        
        time.sleep(3)
        
        # Capture initial screenshot
        shot1 = os.path.join(ARTIFACT_DIR, "casaos_screen_1_initial.png")
        page.screenshot(path=shot1, full_page=True)
        print(f"Saved initial screen to {shot1}")

        # Check page title and content
        title = page.title()
        print(f"Page Title: {title}")
        
        # Check if first-run setup or login is needed
        # CasaOS setup form typically has inputs for username/password
        inputs = page.query_selector_all("input")
        print(f"Found {len(inputs)} input fields on page.")
        for inp in inputs:
            itype = inp.get_attribute("type")
            iname = inp.get_attribute("name") or inp.get_attribute("placeholder") or ""
            print(f" - Input type={itype}, name/placeholder={iname}")

        # Check for any error messages or alerts visible on screen
        text_content = page.inner_text("body")
        print("\n--- Visible Body Text Preview (first 500 chars) ---")
        print(text_content[:500])
        print("--------------------------------------------------\n")

        # Check specifically for 'fail', 'error', 'failed to load'
        errors_found = []
        for line in text_content.splitlines():
            if any(w in line.lower() for w in ["fail", "error", "unable", "crash"]):
                errors_found.append(line.strip())
        
        if errors_found:
            print("WARNING: Found potential error strings on screen:")
            for err in errors_found:
                print("  *", err)
        else:
            print("No error strings detected in page text.")

        # Try to find and click 'App Store' button/icon
        # Common selectors: text="App Store", [title="App Store"], .appstore-icon
        appstore_btn = None
        for sel in ["text='App Store'", "text='AppStore'", "[aria-label='App Store']", "a:has-text('App Store')"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    appstore_btn = el
                    print(f"Found App Store button using selector: {sel}")
                    break
            except Exception:
                pass

        if appstore_btn:
            print("Clicking App Store button...")
            appstore_btn.click()
            time.sleep(4)
            shot2 = os.path.join(ARTIFACT_DIR, "casaos_screen_2_appstore.png")
            page.screenshot(path=shot2, full_page=True)
            print(f"Saved App Store screen to {shot2}")
        else:
            print("App Store button not immediately found with text search. Searching for icons/buttons...")
            buttons = page.query_selector_all("button, a, div[role='button']")
            for b in buttons:
                txt = b.inner_text().strip()
                if "app" in txt.lower():
                    print(f"Potential app button: '{txt}'")

        browser.close()

if __name__ == "__main__":
    main()

