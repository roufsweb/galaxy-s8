import asyncio
import os
from playwright.async_api import async_playwright

ARTIFACT_DIR = r"C:\Users\rakib\.gemini\antigravity\brain\856563d1-ce89-44fd-8c75-5b4b5db94bbc"

async def test_uptimekuma():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 900})
        page = await context.new_page()

        print("[*] Navigating to Uptime Kuma at http://localhost:3001...")
        await page.goto("http://localhost:3001", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Capture initial setup or login screen
        s1 = os.path.join(ARTIFACT_DIR, "uptimekuma_screen_1_setup.png")
        await page.screenshot(path=s1)
        print(f"[+] Saved {s1}")

        # Check for admin setup form
        user_input = page.locator('input[type="text"], input[name="username"]')
        pwd_inputs = page.locator('input[type="password"]')
        if await user_input.count() > 0 and await pwd_inputs.count() >= 2:
            print("[*] Setting up Uptime Kuma admin account...")
            await user_input.first.fill("admin")
            await pwd_inputs.nth(0).fill("admin12345678")
            await pwd_inputs.nth(1).fill("admin12345678")
            submit_btn = page.locator('button[type="submit"]')
            await submit_btn.click()
            await page.wait_for_selector(".navbar, .btn-primary, .dashboard", timeout=25000)
            await asyncio.sleep(4)

        # Capture Dashboard
        s2 = os.path.join(ARTIFACT_DIR, "uptimekuma_screen_2_dashboard.png")
        await page.screenshot(path=s2)
        print(f"[+] Saved {s2}")

        # Click "Add New Monitor"
        add_btn = page.locator("text='Add New Monitor', text='Add new monitor'")
        if await add_btn.count() > 0:
            print("[*] Adding new monitor...")
            await add_btn.first.click()
            await asyncio.sleep(2)

            name_input = page.locator('#name, input[name="name"]')
            if await name_input.count() > 0:
                await name_input.fill("Galaxy S8 Native CasaOS")

            url_input = page.locator('#url, input[name="url"]')
            if await url_input.count() > 0:
                await url_input.fill("http://127.0.0.1:8080")

            save_btn = page.locator('button[type="submit"]:has-text("Save")')
            if await save_btn.count() > 0:
                await save_btn.click()
                print("[*] Monitor saved, awaiting first ping check...")
                await asyncio.sleep(6)

        # Capture active monitors screen
        s3 = os.path.join(ARTIFACT_DIR, "uptimekuma_screen_3_monitors_live.png")
        await page.screenshot(path=s3)
        print(f"[+] Saved {s3}")

        await browser.close()
        print("[+] Uptime Kuma verification completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_uptimekuma())

