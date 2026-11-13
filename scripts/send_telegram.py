#!/usr/bin/env python3
"""
send_telegram.py — Autonomous Telegram Notification Dispatcher for Antigravity.
Reads credentials securely from .env and dispatches status updates, alerts,
and progress milestones directly to the authorized Telegram chat.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

def load_env():
    env_file = WORKSPACE / ".env"
    env_vars = {}
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
    return env_vars

def send_telegram_message(message: str, chat_id: str = None, parse_mode: str = "Markdown", reply_markup: dict = None) -> bool:
    env_vars = load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env_vars.get("TELEGRAM_BOT_TOKEN")
    default_chat = os.environ.get("TELEGRAM_ALLOWED_USER_IDS") or env_vars.get("TELEGRAM_ALLOWED_USER_IDS")
    
    target_chat = chat_id or default_chat
    if not token or not target_chat:
        print("[!] ERROR: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_ALLOWED_USER_IDS in .env", file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": message,
        "disable_web_page_preview": True
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                print(f"[+] Telegram message dispatched successfully to chat {target_chat}.")
                return True
            else:
                print(f"[!] HTTP {resp.status}: {resp.read().decode('utf-8')}", file=sys.stderr)
                return False
    except Exception as e:
        # Fallback to plain text if Markdown parsing fails
        if parse_mode:
            try:
                payload.pop("parse_mode", None)
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        print(f"[+] Telegram message dispatched (plain text fallback) to chat {target_chat}.")
                        return True
            except Exception as e2:
                print(f"[!] Telegram Dispatch Failed: {e2}", file=sys.stderr)
                return False
        print(f"[!] Telegram Dispatch Failed: {e}", file=sys.stderr)
        return False

_MEDIA_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
}


def _send_telegram_media(
    endpoint: str,
    field_name: str,
    media_path: str,
    default_mime: str,
    label: str,
    caption: str = "",
    chat_id: str = None,
) -> bool:
    """Upload a local media file to a Telegram Bot API endpoint via multipart/form-data."""
    env_vars = load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env_vars.get("TELEGRAM_BOT_TOKEN")
    default_chat = os.environ.get("TELEGRAM_ALLOWED_USER_IDS") or env_vars.get("TELEGRAM_ALLOWED_USER_IDS")

    target_chat = chat_id or default_chat
    if not token or not target_chat:
        print("[!] ERROR: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_ALLOWED_USER_IDS in .env", file=sys.stderr)
        return False

    p = Path(media_path)
    if not p.exists():
        print(f"[!] ERROR: {label.capitalize()} file not found: {media_path}", file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{token}/{endpoint}"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    mime_type = _MEDIA_MIME_TYPES.get(p.suffix.lower(), default_mime)

    with open(p, "rb") as f:
        file_bytes = f.read()

    body = bytearray()
    # chat_id field
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
    body.extend(f"{target_chat}\r\n".encode())

    # caption field
    if caption:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
        body.extend(f"{caption}\r\n".encode())

    # media file field
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{p.name}"\r\n'.encode())
    body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode())
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 200:
                print(f"[+] Telegram {label} dispatched successfully: {p.name}")
                return True
            else:
                print(f"[!] HTTP {resp.status}: {resp.read().decode('utf-8')}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"[!] Telegram {label.capitalize()} Dispatch Failed: {e}", file=sys.stderr)
        return False


def send_telegram_photo(photo_path: str, caption: str = "", chat_id: str = None) -> bool:
    """Dispatches an image file to Telegram via multipart/form-data."""
    return _send_telegram_media("sendPhoto", "photo", photo_path, "image/png", "photo", caption, chat_id)


def send_telegram_audio(audio_path: str, caption: str = "", chat_id: str = None) -> bool:
    """Dispatches an audio file to Telegram via multipart/form-data."""
    return _send_telegram_media("sendAudio", "audio", audio_path, "audio/wav", "audio", caption, chat_id)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--photo":
        photo = sys.argv[2]
        caption = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        success = send_telegram_photo(photo, caption)
    elif len(sys.argv) > 2 and sys.argv[1] == "--audio":
        audio = sys.argv[2]
        caption = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        success = send_telegram_audio(audio, caption)
    elif len(sys.argv) > 1 and sys.argv[1] in ("--photo", "--audio"):
        print(f"[!] ERROR: Missing file path for {sys.argv[1]}", file=sys.stderr)
        success = False
    elif len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
        success = send_telegram_message(msg)
    else:
        msg = "[INFO] *Antigravity Telegram Notifier Online*\nConnected to Samsung Galaxy S8 Native Linux Workspace."
        success = send_telegram_message(msg)
    sys.exit(0 if success else 1)

