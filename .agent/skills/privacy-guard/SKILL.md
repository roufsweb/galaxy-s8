---
name: privacy-guard
description: Automated secret sanitizer and privacy enforcement runbook to ensure zero personal tokens, Wi-Fi credentials, private keys, or internal identifiers leak into git tracking, commit history, or public releases.
---

# Privacy Guard & Secret Sanitization Runbook

This skill establishes automated procedures and verification gates to guarantee that no private credentials, personal identifiers, or environment-specific secrets are committed to Git or exposed in public documentation.

---

## 1. Protected Patterns & Redaction Rules

| Secret Category | Detected Pattern | Safe Public Placeholder |
| :--- | :--- | :--- |
| **Wi-Fi SSID** | `<WIFI_SSID>`, user internal SSIDs | `<WIFI_SSID>` or `$WIFI_SSID` |
| **Wi-Fi Password / PSK** | User pre-shared keys, passwords | `<WIFI_PASSWORD>` or `$WIFI_PSK` |
| **Telegram Bot Token** | `[0-9]{8,10}:[A-Za-z0-9_-]{35}` | `<TELEGRAM_BOT_TOKEN>` or `$TELEGRAM_BOT_TOKEN` |
| **Telegram Chat ID** | User numerical chat ID | `<TELEGRAM_CHAT_ID>` or `$TELEGRAM_CHAT_ID` |
| **API Keys / Secrets** | `api_key = "..."`, `secret = "..."` | `<API_KEY_REDACTED>` |
| **Private SSH Keys** | `-----BEGIN OPENSSH PRIVATE KEY-----` | Must be quarantined and gitignored |
| **Device Serial Numbers** | Samsung ADB serials in public templates | `<DEVICE_SERIAL>` |

---

## 2. Automated Scanner & Sanitizer Tool

The project includes an automated scanner at `scripts/sanitize_repo.py`.

### Scan Repository for Secrets
```bash
python scripts/sanitize_repo.py --root .
```
Returns exit code `0` if clean; returns exit code `1` and lists offending lines if secrets are found.

### Automatically Sanitize Offending Files
```bash
python scripts/sanitize_repo.py --root . --fix
```
Replaces all detected sensitive patterns with their respective safe public placeholders in place.

---

## 3. Git Pre-Commit Hook Integration

To prevent accidental commits of sensitive data, install the pre-commit hook:

```bash
python scripts/install_privacy_hook.py
```

This installs `.git/hooks/pre-commit` which automatically executes `scripts/sanitize_repo.py --root .` before every commit. If any secret is detected, the commit is aborted immediately.

---

## 4. Gitignore Enforcement Policy

The following patterns must always remain in `.gitignore`:

```gitignore
# Credentials & secrets
.env*
*.token
*.key
*.pem
*.secret
auth*.json
credentials.json

# Test logs & crash dumps
*.log
last_kmsg*
/proc/
/sys/

# Large binaries & archives (handled via releases)
*.tar.md5
AP_*.tar
*.img.lz4
```

