# Galaxy S8 Developer Tools & Privacy Automation

This directory contains developer maintenance scripts, secret sanitizers, and repository automation tools.

---

## Tools Overview

| Tool | Purpose | Usage |
| :--- | :--- | :--- |
| `sanitize_repo.py` | Scans the codebase for sensitive credentials (Wi-Fi passwords, SSIDs, Telegram bot tokens, private keys) and automatically replaces them with public placeholders. | `python scripts/sanitize_repo.py --root . [--fix]` |
| `install_privacy_hook.py` | Installs an automated Git `pre-commit` hook that executes `sanitize_repo.py` before every commit, preventing accidental credential leaks. | `python scripts/install_privacy_hook.py` |
| `reorganize_repo.py` | Maintains structured repository organization, moving files into clean `boot/`, `src/`, `tests/`, `docs/`, and `releases/` directories. | `python scripts/reorganize_repo.py` |

