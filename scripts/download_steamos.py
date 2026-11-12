#!/usr/bin/env python3
"""
download_steamos.py — Downloads SteamOS ARM64 release images from Zaviya / Valve.
"""

import os
import sys
import time
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
DISTROS_DIR = WORKSPACE / "distros" / "steamos"
DISTROS_DIR.mkdir(parents=True, exist_ok=True)

PARTS = [
    ("steamos-arm-port-sm8550-v1.4.7z.001", "https://github.com/hashtagbasit/Zaviya/releases/download/v1.4/steamos-arm-port-sm8550-v1.4.7z.001"),
    ("steamos-arm-port-sm8550-v1.4.7z.002", "https://github.com/hashtagbasit/Zaviya/releases/download/v1.4/steamos-arm-port-sm8550-v1.4.7z.002"),
    ("steamos-arm-port-sm8550-v1.4.7z.003", "https://github.com/hashtagbasit/Zaviya/releases/download/v1.4/steamos-arm-port-sm8550-v1.4.7z.003"),
]

def download_file(filename, url):
    dest = DISTROS_DIR / filename
    if dest.exists() and dest.stat().st_size > 100 * 1024 * 1024:
        print(f"[OK] {filename} already exists ({dest.stat().st_size / (1024**2):.1f} MB). Skipping.")
        return True

    print(f"\n[*] Starting download: {filename}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    start_time = time.time()
    last_print = 0
    last_tg_time = start_time
    last_tg_pct = 0
    try:
        from scripts.send_telegram import send_telegram_message
    except Exception:
        send_telegram_message = None

    try:
        with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            if send_telegram_message:
                send_telegram_message(f"[STAGE] Starting download: {filename} ({total/(1024**2):.1f} MB)")
            while True:
                chunk = resp.read(2 * 1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                now = time.time()
                pct = int((downloaded * 100 / total)) if total else 0
                speed = downloaded / (now - start_time) / (1024 * 1024)
                if now - last_print > 2:
                    last_print = now
                    print(f"[{filename}] {downloaded / (1024**2):.1f} / {total / (1024**2):.1f} MB ({pct}%) @ {speed:.2f} MB/s", flush=True)

                # Telegram progress heartbeat every 20% or every 180 seconds
                if send_telegram_message and (pct >= last_tg_pct + 20 or now - last_tg_time > 180):
                    last_tg_pct = pct
                    last_tg_time = now
                    send_telegram_message(f"[PROGRESS] {filename}: {downloaded/(1024**2):.1f}/{total/(1024**2):.1f} MB ({pct}%) @ {speed:.2f} MB/s")

        elapsed = time.time() - start_time
        msg = f"[PASS] Successfully downloaded {filename} ({downloaded / (1024**2):.1f} MB) in {elapsed:.1f}s."
        print(msg)
        if send_telegram_message:
            send_telegram_message(msg)
        return True
    except Exception as e:
        print(f"[ERR] Failed to download {filename}: {e}", file=sys.stderr)
        return False

def main():
    print("=== SteamOS ARM64 Image Downloader ===")
    print(f"Target Directory: {DISTROS_DIR}")
    for name, url in PARTS:
        success = download_file(name, url)
        if not success:
            print(f"[!] Warning: Download failed for {name}")

if __name__ == "__main__":
    main()

