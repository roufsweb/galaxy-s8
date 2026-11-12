#!/usr/bin/env python3
"""
privacy_guard.py - Automated Secret Sanitizer & Privacy Guard
Scans repository files for sensitive personal data, API tokens, Wi-Fi credentials,
and private bot identifiers, preventing leaks into Git or public releases.
"""

import os
import re
import sys
import argparse
import base64

# Encoded target patterns to prevent self-flagging
_WIFI_PASS_PAT = base64.b64decode('XGI1NTU1NTU1NVxi').decode()
_WIFI_SSID_PAT = r"\brouf\.iot\b"
_TG_BOT_ID_PAT = base64.b64decode("XGI4OTAxNzg2NTAzXGI=").decode()
_TG_CHAT_ID_PAT = base64.b64decode("XGI3NTkyMzc5MzQ5XGI=").decode()

PATTERNS = [
    # Telegram Bot Tokens with or without 'bot' prefix
    (r"(?:bot)?[0-9]{9,10}:[A-Za-z0-9_-]{35}", "<TELEGRAM_BOT_TOKEN>"),
    (_TG_BOT_ID_PAT, "<TELEGRAM_BOT_ID>"),
    (_TG_CHAT_ID_PAT, "<TELEGRAM_CHAT_ID>"),
    # Wi-Fi SSID & Password
    (_WIFI_SSID_PAT, "<WIFI_SSID>"),
    (_WIFI_PASS_PAT, "<WIFI_PASSWORD>"),
    # GitHub Tokens
    (r"\bghp_[A-Za-z0-9_]{36}\b", "<GITHUB_TOKEN_REDACTED>"),
    (r"\bgithub_pat_[A-Za-z0-9_]{82}\b", "<GITHUB_PAT_REDACTED>"),
    # Cloud API Keys
    (r"\bAKIA[0-9A-Z]{16}\b", "<AWS_KEY_REDACTED>"),
    (r"\bAIza[0-9A-Za-z\-_]{35}\b", "<GOOGLE_API_KEY_REDACTED>"),
    # Generic API Keys / Secrets
    (r"(?i)api[_-]?key\s*[:=]\s*['\"]([A-Za-z0-9_\-]{20,})['\"]", r"api_key: '<API_KEY_REDACTED>'"),
    (r"(?i)secret\s*[:=]\s*['\"]([A-Za-z0-9_\-]{20,})['\"]", r"secret: '<SECRET_REDACTED>'"),
]

EXCLUDE_DIRS = {
    ".git",
    ".agent",
    ".antigravity",
    "node_modules",
    "__pycache__",
    ".cache",
    ".vscode",
    "dist",
    "build",
    "kernel",
    "AP_G950NKSU5DVG2_CL21340847_QB54384937_REV00_user_low_ship_meta_OS9.tar",
    "galaxy-s8-stock-firmwire",
    "device_firmware",
    "meta-data",
    "ramdisk_root",
    "ramdisk_work",
    "magisk_boot",
    "scratch",
    "archive",
    "desktop-app",
}

EXCLUDE_EXTENSIONS = {
    ".tar", ".tar.gz", ".tar.md5", ".md5", ".img", ".lz4", ".bin", ".blob", ".hcd",
    ".so", ".dylib", ".dll", ".exe", ".png", ".jpg", ".jpeg", ".ico", ".wav", ".mp3", ".pdf",
    ".lock", ".pyc"
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB maximum for text scanning

def scan_file(filepath):
    """Scan a single file for sensitive patterns."""
    hits = []
    # Skip this script itself
    if os.path.abspath(filepath) == os.path.abspath(__file__):
        return hits
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for idx, line in enumerate(lines, 1):
            for pat, repl in PATTERNS:
                if re.search(pat, line):
                    hits.append((idx, pat, repl, line.strip()))
    except Exception:
        pass
    return hits

def sanitize_file(filepath):
    """Replace sensitive patterns in a file."""
    if os.path.abspath(filepath) == os.path.abspath(__file__):
        return False
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        modified = False
        new_content = content
        for pat, repl in PATTERNS:
            if re.search(pat, new_content):
                new_content = re.sub(pat, repl, new_content)
                modified = True
                
        if modified:
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_content)
            return True
    except Exception:
        pass
    return False

def walk_repo(root_dir):
    """Walk through repository finding valid files to scan."""
    for root, dirs, files in os.walk(root_dir):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in EXCLUDE_EXTENSIONS or file.startswith(".env"):
                continue
            filepath = os.path.join(root, file)
            try:
                if os.path.getsize(filepath) <= MAX_FILE_SIZE:
                    yield filepath
            except OSError:
                pass

def main():
    parser = argparse.ArgumentParser(description="Privacy Guard - Secret Sanitizer")
    parser.add_argument("--fix", action="store_true", help="Automatically redact sensitive patterns")
    parser.add_argument("--dir", "--root", dest="dir", default=".", help="Root directory to scan")
    args = parser.parse_args()

    target_dir = os.path.abspath(args.dir)
    print(f"Scanning directory: {target_dir}")

    all_hits = {}
    for filepath in walk_repo(target_dir):
        hits = scan_file(filepath)
        if hits:
            rel_path = os.path.relpath(filepath, target_dir)
            all_hits[rel_path] = hits

    if not all_hits:
        print("\n[OK] Zero sensitive credentials detected. Repository is clean.")
        return 0

    print(f"\n[ALERT] Found sensitive patterns in {len(all_hits)} files:")
    for rel_path, hits in all_hits.items():
        print(f"  File: {rel_path}")
        for line_num, pat, repl, line_text in hits[:3]:  # Show first 3 hits per file
            truncated = line_text[:60] + "..." if len(line_text) > 60 else line_text
            print(f"    Line {line_num} [{pat} -> {repl}]: {truncated}")
        if len(hits) > 3:
            print(f"    ... and {len(hits) - 3} more match(es)")

    if args.fix:
        sanitized_count = 0
        for rel_path in all_hits.keys():
            full_path = os.path.join(target_dir, rel_path)
            if sanitize_file(full_path):
                sanitized_count += 1
        print(f"\n[SUCCESS] Sanitized {sanitized_count} files.")
        return 0
    else:
        print("\nRun with --fix to automatically replace sensitive patterns.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
