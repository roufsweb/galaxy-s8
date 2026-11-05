import asyncio
import os
import sys
from playwright.async_api import async_playwright

ARTIFACT_DIR = r"C:\Users\rakib\.gemini\antigravity\brain\856563d1-ce89-44fd-8c75-5b4b5db94bbc"

async def test_codeserver():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 900})
        page = await context.new_page()

        print("[*] Navigating to Code-Server at http://localhost:8443...")
        try:
            await page.goto("http://localhost:8443", wait_until="networkidle", timeout=25000)
        except Exception as e:
            print(f"[*] Navigation note: {e}")

        # Capture login screen
        login_img = os.path.join(ARTIFACT_DIR, "codeserver_screen_1_login.png")
        await page.screenshot(path=login_img)
        print(f"[+] Saved {login_img}")

        # Check for password input
        pwd_input = page.locator('input[type="password"]')
        if await pwd_input.count() > 0:
            print("[*] Entering password...")
            await pwd_input.fill("admin12345678")
            submit_btn = page.locator('input[type="submit"], button[type="submit"]')
            if await submit_btn.count() > 0:
                await submit_btn.click()
            else:
                await pwd_input.press("Enter")

            print("[*] Waiting for Monaco workbench to initialize...")
            await page.wait_for_selector(".monaco-workbench, .part.workbench", timeout=30000)
            await asyncio.sleep(5)  # Allow UI elements to settle

        # Capture main workbench
        dash_img = os.path.join(ARTIFACT_DIR, "codeserver_screen_2_workbench.png")
        await page.screenshot(path=dash_img)
        print(f"[+] Saved {dash_img}")

        # Check if terminal or editor is visible
        title = await page.title()
        print(f"[+] Code-Server Page Title: {title}")

        await browser.close()
        print("[+] Code-Server UI test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_codeserver())

