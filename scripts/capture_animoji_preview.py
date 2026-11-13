#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

html_path = Path(r"C:\Users\rakib\.gemini\antigravity\brain\32ab8e00-683f-431e-8f7d-5b48926742e1\s8_animoji_avatar.html")
out_path = Path("docs/assets/screenshots/s8_animoji_speaking_proof.png")
out_path.parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.goto(html_path.as_uri())
    page.wait_for_timeout(1000)
    page.evaluate("setAssistantState('SPEAKING', '\"Yes Rouf! I can animate my talking face with live lip-sync, blinking eyes, and audio waveforms!\"')")
    page.wait_for_timeout(600)
    page.screenshot(path=str(out_path))
    browser.close()

print(f"[OK] Captured: {out_path} ({out_path.stat().st_size} bytes)")

