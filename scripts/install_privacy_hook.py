#!/usr/bin/env python3
"""
install_privacy_hook.py - Installs Git Pre-Commit Hook for Secret Sanitization
"""

import os
import sys

HOOK_CONTENT = """#!/bin/sh
# Git Pre-Commit Hook: Automated Secret Sanitizer & Privacy Guard
echo "[*] Running Privacy Guard secret scan..."
python scripts/sanitize_repo.py --root .
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "[!] COMMIT ABORTED: Sensitive patterns detected."
    echo "    Run 'python scripts/sanitize_repo.py --root . --fix' to sanitize files before committing."
    exit 1
fi

echo "[+] Privacy Guard check passed. No secrets detected."
exit 0
"""

def install_hook():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_dir = os.path.join(repo_root, ".git")
    hooks_dir = os.path.join(git_dir, "hooks")
    
    if not os.path.isdir(git_dir):
        print(f"[!] .git directory not found at {git_dir}. Is this a git repository?")
        return False
        
    os.makedirs(hooks_dir, exist_ok=True)
    hook_path = os.path.join(hooks_dir, "pre-commit")
    
    with open(hook_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HOOK_CONTENT)
        
    try:
        # Make executable on Unix/WSL/Git-Bash
        os.chmod(hook_path, 0o755)
    except Exception:
        pass
        
    print(f"[+] Successfully installed pre-commit privacy hook to {hook_path}")
    return True

if __name__ == "__main__":
    if install_hook():
        sys.exit(0)
    else:
        sys.exit(1)

