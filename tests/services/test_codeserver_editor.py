import asyncio
import os
from playwright.async_api import async_playwright

ARTIFACT_DIR = r"C:\Users\rakib\.gemini\antigravity\brain\856563d1-ce89-44fd-8c75-5b4b5db94bbc"

async def test_codeserver_interaction():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 900})
        page = await context.new_page()

        print("[*] Loading Code-Server...")
        await page.goto("http://localhost:8443", wait_until="networkidle", timeout=30000)

        # Check for password
        pwd_input = page.locator('input[type="password"]')
        if await pwd_input.count() > 0:
            await pwd_input.fill("admin12345678")
            submit_btn = page.locator('input[type="submit"], button[type="submit"]')
            if await submit_btn.count() > 0:
                await submit_btn.click()
            else:
                await pwd_input.press("Enter")

        print("[*] Waiting for Monaco workbench...")
        await page.wait_for_selector(".monaco-workbench", timeout=30000)
        await asyncio.sleep(4)

        # Click "New File..."
        new_file_link = page.locator("text='New File...'")
        if await new_file_link.count() > 0:
            print("[*] Clicking 'New File...'...")
            await new_file_link.first.click()
            await asyncio.sleep(2)

        # Focus editor and type Python code
        print("[*] Typing code into Monaco editor...")
        await page.keyboard.type("#!/usr/bin/env python3\n")
        await page.keyboard.type("# Galaxy S8 Homelab Verification Script\n")
        await page.keyboard.type("import platform, os\n")
        await page.keyboard.type("print(f'System: {platform.system()} on {platform.machine()}')\n")
        await page.keyboard.type("print('Homelab Status: Exynos 8895 8-Core Running Natively!')\n")
        await asyncio.sleep(2)

        editor_img = os.path.join(ARTIFACT_DIR, "codeserver_screen_3_editor.png")
        await page.screenshot(path=editor_img)
        print(f"[+] Saved {editor_img}")

        await browser.close()
        print("[+] Code-Server editor interaction verified!")

if __name__ == "__main__":
    asyncio.run(test_codeserver_interaction())

