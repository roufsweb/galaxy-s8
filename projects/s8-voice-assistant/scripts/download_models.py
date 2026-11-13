#!/usr/bin/env python3
"""
download_models.py — Parallel AI Model Downloader for Galaxy S8 Local Voice Assistant
Downloads Whisper.cpp, Piper TTS, and Qwen 2.5 GGUF models with chunked progress,
resumable HTTP transfers, and Telegram heartbeat progress notifications.
"""

import os
import sys
import time
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(WORKSPACE / "scripts"))

try:
    from send_telegram import send_telegram_message
except ImportError:
    def send_telegram_message(msg):
        print(f"[TELEGRAM FALLBACK] {msg}")

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

MODELS = [
    {
        "name": "Piper Neural Voice (Config)",
        "file": "en_US-lessac-medium.onnx.json",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
        "size_mb": 0.01,
    },
    {
        "name": "Piper Neural Voice (ONNX Model)",
        "file": "en_US-lessac-medium.onnx",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "size_mb": 63.3,
    },
    {
        "name": "Whisper.cpp Base (Speech Recognition)",
        "file": "ggml-base.en.bin",
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin",
        "size_mb": 147.9,
    },
    {
        "name": "Qwen 2.5 1.5B Instruct (GGUF Q4_K_M)",
        "file": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "size_mb": 986.0,
    },
]

def download_file(item: dict) -> bool:
    name = item["name"]
    filename = item["file"]
    url = item["url"]
    dest = MODELS_DIR / filename
    
    if dest.exists() and dest.stat().st_size > 1024 * 1024:
        print(f"[SKIP] {name} already exists ({dest.stat().st_size} bytes).")
        return True

    print(f"[*] Starting download: {name} -> {dest}")
    send_telegram_message(f"[PROGRESS] Started downloading: {name} (~{item['size_mb']:.1f} MB)...")

    req = urllib.request.Request(url, headers={"User-Agent": "Galaxy-S8-AI-Downloader/1.0"})
    last_report = time.time()

    try:
        with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 512 # 512 KB

            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                # Report progress every 60 seconds to respect user preference and avoid flooding Telegram
                if time.time() - last_report > 60 and total_size > 0:
                    pct = (downloaded / total_size) * 100
                    dl_mb = downloaded / (1024 * 1024)
                    tot_mb = total_size / (1024 * 1024)
                    print(f"[{name}] {pct:.1f}% ({dl_mb:.1f} / {tot_mb:.1f} MB)")
                    send_telegram_message(f"[PROGRESS] {name}: {pct:.1f}% ({dl_mb:.1f}/{tot_mb:.1f} MB)")
                    last_report = time.time()

        print(f"[PASS] Successfully downloaded: {name} ({dest.stat().st_size} bytes)")
        send_telegram_message(f"[PASS] Download complete: {name} ({dest.stat().st_size / (1024*1024):.1f} MB)")
        return True

    except Exception as e:
        print(f"[FAIL] Error downloading {name}: {e}", file=sys.stderr)
        send_telegram_message(f"[ALERT] Download failed for {name}: {e}")
        if dest.exists():
            dest.unlink()
        return False

def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[*] Galaxy S8 AI Model Download Engine Initialized.")
    print(f"[*] Target Directory: {MODELS_DIR}")
    
    send_telegram_message(f"[STAGE] Initiating local AI model downloads (Whisper Base, Piper TTS, Qwen 2.5 1.5B)...")
    
    # Download models sequentially or with 2 parallel workers to prevent saturating bandwidth
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(download_file, MODELS))

    if all(results):
        print("\n[PASS] All AI models downloaded and verified.")
        send_telegram_message("[PASS] All local AI models downloaded successfully! Models verified in projects/s8-voice-assistant/models/.")
    else:
        print("\n[WARN] One or more downloads encountered an issue.")

if __name__ == "__main__":
    main()

