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

# Blacklisted strings / regex patterns to detect and protect
PATTERNS = [
    # Telegram Bot Tokens (e.g. 1234567890:AA...)
    (r"\b8901786503:[A-Za-z0-9_-]{35}\b", "<TELEGRAM_BOT_TOKEN>"),
    (r"\b8901786503\b", "<TELEGRAM_BOT_ID>"),
    # Telegram Chat ID
    (r"\b7592379349\b", "<TELEGRAM_CHAT_ID>"),
    # Wi-Fi SSID & Password
    (r"\brouf\.iot\b", "<WIFI_SSID>"),
    (r"\b<WIFI_PASSWORD>\b", "<WIFI_PASSWORD>"),
    # Generic API Keys / Secrets if any
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
    "galaxy-s8-kvm-kernel",
    "AP_G950NKSU5DVG2_CL21340847_QB54384937_REV00_user_low_ship_meta_OS9.tar",
    "galaxy-s8-stock-firmwire",
    "device_firmware",
    "meta-data",
    "ramdisk_root",
    "ramdisk_work",
    "magisk_boot",
}

EXCLUDE_EXTENSIONS = {
    ".tar", ".tar.gz", ".tar.md5", ".md5", ".img", ".lz4", ".bin", ".blob", ".hcd",
    ".so", ".png", ".jpg", ".jpeg", ".ico", ".wav", ".mp3", ".pdf",
    ".lock", ".pyc"
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB maximum for text scanning

def scan_file(filepath):
    """Scan a single file for sensitive patterns."""
    hits = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for idx, line in enumerate(lines, 1):
            for pat, repl in PATTERNS:
                if re.search(pat, line):
                    hits.append((idx, pat, repl, line.strip()))
    except Exception as e:
        pass
    return hits

def sanitize_file(filepath):
    """Replace sensitive patterns in a file."""
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
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True
    except Exception as e:
        print(f"Error sanitizing {filepath}: {e}")
    return False

def scan_repo(root_dir, fix=False):
    """Walk repo and check or sanitize files."""
    findings = []
    fixed_count = 0
    
    for root, dirs, files in os.walk(root_dir):
        # Filter directories in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in EXCLUDE_EXTENSIONS:
                continue
            
            filepath = os.path.join(root, file)
            try:
                if os.path.getsize(filepath) > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            hits = scan_file(filepath)
            if hits:
                findings.append((filepath, hits))
                if fix:
                    if sanitize_file(filepath):
                        fixed_count += 1
                        
    return findings, fixed_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Privacy Guard & Secret Sanitizer")
    parser.add_argument("--root", default=".", help="Root directory to scan")
    parser.add_argument("--fix", action="store_true", help="Automatically sanitize detected patterns")
    args = parser.parse_args()

    print(f"Scanning directory: {os.path.abspath(args.root)}")
    findings, fixed = scan_repo(args.root, fix=args.fix)
    
    if findings:
        print(f"\n[ALERT] Found sensitive patterns in {len(findings)} files:")
        for fp, hits in findings:
            rel = os.path.relpath(fp, args.root)
            print(f"  File: {rel}")
            for line_no, pat, repl, line in hits:
                print(f"    Line {line_no} [{pat} -> {repl}]: {line[:80]}")
        if args.fix:
            print(f"\n[SUCCESS] Sanitized {fixed} files.")
            sys.exit(0)
        else:
            print("\nRun with --fix to automatically replace sensitive patterns.")
            sys.exit(1)
    else:
        print("\n[OK] Zero sensitive credentials detected. Repository is clean.")
        sys.exit(0)
