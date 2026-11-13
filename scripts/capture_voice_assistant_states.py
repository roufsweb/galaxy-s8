#!/usr/bin/env python3
"""
capture_voice_assistant_states.py — Captures all 4 visual interaction states
of the Galaxy S8 Voice Assistant Animoji Avatar for visual proof and Telegram dispatch.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

WORKSPACE = Path(__file__).resolve().parent.parent
HTML_PATH = WORKSPACE / "projects" / "s8-voice-assistant" / "ui" / "avatar.html"
ARTIFACT_DIR = Path(r"C:\Users\rakib\.gemini\antigravity\brain\32ab8e00-683f-431e-8f7d-5b48926742e1")
DOCS_IMG_DIR = WORKSPACE / "docs" / "assets" / "screenshots"
DOCS_IMG_DIR.mkdir(parents=True, exist_ok=True)

STATES = [
    ("IDLE", '"Standing by for your next question."', 0.0, "avatar_state_idle.png"),
    ("LISTENING", '"Listening to CS47L92 DMIC1 microphone (hw:0,9)..."', 0.45, "avatar_state_listening.png"),
    ("THINKING", '"Transcribing speech with Whisper Base & Qwen 2.5 thinking..."', 0.1, "avatar_state_thinking.png"),
    ("SPEAKING", '"I am running natively on Exynos 8895 with 4GB RAM under Ubuntu 24.04 LTS."', 0.85, "avatar_state_speaking.png"),
]

def main():
    print("[+] Rendering and capturing Galaxy S8 Voice Assistant interaction states...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1920}) # Portrait DisplayPort
        page.goto(HTML_PATH.as_uri())
        page.wait_for_timeout(1000)

        for state, text, amp, filename in STATES:
            # Set state
            js = f"setAssistantState('{state}', '{text}'); setAudioAmplitude({amp});"
            page.evaluate(js)
            page.wait_for_timeout(600)

            # Save to brain artifact directory
            art_file = ARTIFACT_DIR / filename
            page.screenshot(path=str(art_file))
            print(f"[OK] Saved artifact: {art_file} ({art_file.stat().st_size} bytes)")

            # Save to docs screenshots
            doc_file = DOCS_IMG_DIR / filename
            page.screenshot(path=str(doc_file))

        browser.close()
    print("[+] All 4 Voice Assistant visual states successfully rendered and captured.")

if __name__ == "__main__":
    main()
