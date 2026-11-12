#!/usr/bin/env python3
"""
S8 Imager - Production-Grade Vibe Coding CI/CD Validator (Root Launcher)
"""
import sys
from pathlib import Path
import subprocess

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DESKTOP_SCRIPT = REPO_ROOT / "desktop-app" / "scripts" / "ci_cd_validator.py"

if __name__ == "__main__":
    res = subprocess.run([sys.executable, str(DESKTOP_SCRIPT)], cwd=str(REPO_ROOT))
    sys.exit(res.returncode)

