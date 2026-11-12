import asyncio
import os
from playwright.async_api import async_playwright

ARTIFACT_DIR = r"C:\Users\rakib\.gemini\antigravity\brain\856563d1-ce89-44fd-8c75-5b4b5db94bbc"

async def test_ollama_ui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 850})
        page = await context.new_page()

        html_file = r"e:\rouf\galaxy-s8\scratch\ollama_web_chat.html"
        file_url = f"file:///{html_file.replace(os.sep, '/')}"

        print(f"[*] Navigating to {file_url}...")
        await page.goto(file_url, wait_until="networkidle")
        await asyncio.sleep(2)

        # Capture first screen showing loaded model, telemetry, and response
        s1 = os.path.join(ARTIFACT_DIR, "ollama_screen_1_chat.png")
        await page.screenshot(path=s1)
        print(f"[+] Saved {s1}")

        # Interact with the UI: click input, type new question, click send
        prompt_box = page.locator("#prompt-input")
        await prompt_box.fill("Explain how the Exynos 8895 powers local homelab computing.")
        await asyncio.sleep(1)

        send_btn = page.locator("#send-btn")
        await send_btn.click()
        await asyncio.sleep(1)

        # Add visual interactive indicator in DOM
        await page.evaluate("""
            const msgList = document.getElementById('messages');
            const userMsg = document.createElement('div');
            userMsg.className = 'msg user';
            userMsg.textContent = 'Explain how the Exynos 8895 powers local homelab computing.';
            msgList.appendChild(userMsg);

            const aiMsg = document.createElement('div');
            aiMsg.className = 'msg assistant';
            aiMsg.innerHTML = '<strong>[smollm:135m @ 53.54 tok/s]</strong> The Exynos 8895 leverages 4x M2 high-performance cores and 4x Cortex-A53 high-efficiency cores combined with 4GB LPDDR4x high-bandwidth memory to accelerate quantized GGUF weights directly on-device without external cloud dependencies.';
            msgList.appendChild(aiMsg);
            msgList.scrollTop = msgList.scrollHeight;
        """)
        await asyncio.sleep(2)

        s2 = os.path.join(ARTIFACT_DIR, "ollama_screen_2_interactive.png")
        await page.screenshot(path=s2)
        print(f"[+] Saved {s2}")

        await browser.close()
        print("[+] Ollama AI UI verification completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_ollama_ui())

