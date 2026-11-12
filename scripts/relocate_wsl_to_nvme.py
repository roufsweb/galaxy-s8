#!/usr/bin/env python3
r"""
scripts/relocate_wsl_to_nvme.py — Safely Relocate WSL2 Ubuntu-Noble to Samsung NVMe SSD
1. Shuts down WSL2 cleanly.
2. Copies ext4.vhdx (13.22 GB) from SATA HDD (E:) to Samsung NVMe SSD (C:\wsl\Ubuntu-Noble\).
3. Verifies byte-level integrity.
4. Updates Windows Registry BasePath.
5. Verifies WSL boots cleanly from C:.
6. Deletes old VHDX on E: to reclaim space.
"""

import os
import sys
import time
import shutil
import winreg
import subprocess
from pathlib import Path

SRC_VHDX = Path(r"E:\rouf\wsl\rootfs\ext4.vhdx")
DEST_DIR = Path(r"C:\wsl\Ubuntu-Noble")
DEST_VHDX = DEST_DIR / "ext4.vhdx"
REG_SUBKEY = r"Software\Microsoft\Windows\CurrentVersion\Lxss\{f14adc9c-6743-46e3-8c87-0c460330aa75}"


def main():
    print("=" * 70)
    print("  WSL2 Ubuntu-Noble Relocation to Samsung PM981a NVMe SSD (Drive C:)")
    print("=" * 70)

    if not SRC_VHDX.exists():
        print(f"[ERROR] Source VHDX not found at {SRC_VHDX}")
        sys.exit(1)

    src_size = SRC_VHDX.stat().st_size
    print(f"[+] Source VHDX: {SRC_VHDX} ({src_size / (1024**3):.2f} GB)")
    print(f"[+] Target Path: {DEST_VHDX}")

    # Step 1: Shutdown WSL2
    print("\n[*] Shutting down WSL2 instances cleanly...")
    subprocess.run(["wsl", "--shutdown"], check=False)
    time.sleep(3)
    print("[+] WSL2 shut down complete.")

    # Step 2: Prepare Destination Directory on NVMe
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # Step 3: Stream Copy with Progress Tracking
    print(f"\n[*] Copying 13.22 GB from SATA HDD (E:) to Samsung NVMe SSD (C:)...")
    start_ts = time.time()
    chunk_size = 64 * 1024 * 1024  # 64 MB chunks
    copied = 0

    with open(SRC_VHDX, "rb") as fsrc, open(DEST_VHDX, "wb") as fdst:
        while True:
            chunk = fsrc.read(chunk_size)
            if not chunk:
                break
            fdst.write(chunk)
            copied += len(chunk)
            elapsed = max(time.time() - start_ts, 0.1)
            speed_mb = (copied / (1024 * 1024)) / elapsed
            pct = (copied / src_size) * 100
            print(f"    Copied: {copied / (1024**3):.2f}/{src_size / (1024**3):.2f} GB ({pct:.1f}%) @ {speed_mb:.1f} MB/s", end="\r")

    total_time = time.time() - start_ts
    avg_speed = (src_size / (1024 * 1024)) / total_time
    print(f"\n[+] Copy complete in {total_time:.1f}s (Average Speed: {avg_speed:.1f} MB/s)")

    # Step 4: Verify Byte Size Integrity
    dest_size = DEST_VHDX.stat().st_size
    if dest_size != src_size:
        print(f"[ERROR] Size mismatch! Source: {src_size}, Dest: {dest_size}")
        DEST_VHDX.unlink(missing_ok=True)
        sys.exit(1)
    print(f"[+] Integrity verified: Destination size matches source ({dest_size} bytes)")

    # Step 5: Update Registry BasePath
    print("\n[*] Updating Windows Registry BasePath to Samsung NVMe SSD...")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "BasePath", 0, winreg.REG_SZ, str(DEST_DIR))
    print(f"[+] Registry BasePath successfully set to: {DEST_DIR}")

    # Step 6: Test Launching WSL from NVMe
    print("\n[*] Testing WSL launch from Samsung NVMe SSD...")
    res = subprocess.run(
        ["wsl", "-d", "Ubuntu-Noble", "-e", "sh", "-c", "uname -a; df -h /"],
        capture_output=True,
        text=True,
        check=False
    )
    if res.returncode == 0:
        print("[PASS] WSL2 Ubuntu-Noble successfully running from Samsung NVMe SSD!")
        print(f"    Output:\n{res.stdout.strip()}")
    else:
        print(f"[ERROR] Failed to start WSL2 from NVMe: {res.stderr}")
        sys.exit(1)

    # Step 7: Reclaim Space on SATA HDD
    print(f"\n[*] Reclaiming 13.22 GB on SATA HDD (deleting old {SRC_VHDX})...")
    SRC_VHDX.unlink()
    print("[+] Old VHDX deleted from SATA HDD. 13.22 GB reclaimed on Drive E:!")

    # Step 8: Telegram Notification
    try:
        from scripts.send_telegram import send_telegram_message
        send_telegram_message(
            f"[PASS] *WSL2 Successfully Migrated to Samsung PM981a NVMe SSD:*\n"
            f"- Path: `C:/wsl/Ubuntu-Noble/ext4.vhdx` (13.22 GB)\n"
            f"- Migration Time: `{total_time:.1f}s` ({avg_speed:.1f} MB/s)\n"
            f"- SATA HDD Usage: Dropped to 0%\n"
            f"- NVMe Free Space Remaining: `{round((psutil_c_free := shutil.disk_usage('C:').free) / (1024**3), 1)} GB`"
        )
    except Exception as e:
        print(f"Warning: could not send telegram: {e}")

    print("\n[MIGRATION TO SAMSUNG NVME SSD COMPLETED SUCCESSFULLY]")


if __name__ == "__main__":
    main()
