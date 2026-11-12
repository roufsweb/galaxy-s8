from playwright.sync_api import sync_playwright
import time
import os

ARTIFACT_DIR = r"C:\Users\rakib\.gemini\antigravity\brain\856563d1-ce89-44fd-8c75-5b4b5db94bbc"

def capture_docker_containers():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 900})
        page = context.new_page()

        print("Navigating to Portainer home...")
        page.goto("http://localhost:9000/#!/home")
        time.sleep(3)

        # Check if login is needed
        if page.query_selector("input[type='password']"):
            print("Logging in to Portainer as admin...")
            page.fill("input[name='Username'], #username, input[type='text']", "admin")
            page.fill("input[name='Password'], #password, input[type='password']", "admin12345678")
            page.click("button:has-text('Login'), button[type='submit']")
            time.sleep(4)

        # Click on 'local' environment item
        print("Looking for 'local' environment card...")
        local_card = page.wait_for_selector("a[href*='/1/docker/'], .blocklist-item:has-text('local'), div:has-text('local') >> nth=-1", timeout=10000)
        local_card.click()
        print("Clicked 'local' environment. Waiting for Docker Dashboard...")
        time.sleep(4)

        # Capture Docker Environment Dashboard
        shot = os.path.join(ARTIFACT_DIR, "portainer_screen_4_docker_dashboard.png")
        page.screenshot(path=shot, full_page=True)
        print(f"Captured Portainer Docker Dashboard: {shot}")

        # Navigate to Containers list
        containers_btn = page.wait_for_selector("a[href*='containers'], span:has-text('Containers')", timeout=5000)
        containers_btn.click()
        print("Clicked 'Containers'. Waiting for containers table...")
        time.sleep(4)

        # Capture Containers List
        shot_list = os.path.join(ARTIFACT_DIR, "portainer_screen_5_containers_list.png")
        page.screenshot(path=shot_list, full_page=True)
        print(f"Captured Portainer Containers List: {shot_list}")

        # Print container names
        body = page.inner_text("body")
        print("\n--- Portainer Containers Detected ---")
        for line in body.splitlines():
            if any(c in line.lower() for c in ["adguard", "portainer", "running"]):
                print("  Container:", line.strip())

        browser.close()

if __name__ == "__main__":
    capture_docker_containers()

