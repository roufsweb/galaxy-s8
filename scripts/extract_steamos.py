#!/usr/bin/env python3
"""
extract_steamos.py — Multi-volume 7z SteamOS ARM64 extractor with zero-token Telegram
progress heartbeats and GPT/filesystem inspection (512B & 4096B sector aware).
"""

import os
import sys
import json
import time
import struct
import threading
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

import multivolumefile
import py7zr
from scripts.send_telegram import send_telegram_message
from scripts.telegram_listener import register_active_task, clear_active_task

TASK_ID = "steamos-extract"
TASK_NAME = "SteamOS 18.15 GiB Archive Extract & GPT Audit"
ARCHIVE_PREFIX = WORKSPACE / "distros" / "steamos" / "steamos-arm-port-sm8550-v1.4.7z"
OUT_DIR = WORKSPACE / "distros" / "steamos" / "extracted"
EXPECTED_IMG_NAME = "steamos-arm-port-sm8550-v1.4.img"
EXPECTED_SIZE = 19493027840
AUDIT_OUT = WORKSPACE / "scratch" / "steamos_gpt_audit.json"


def detect_fs(f, start_byte: int, size_bytes: int) -> str:
    """Identify partition filesystem magic without mounting."""
    try:
        if size_bytes >= 0x440:
            f.seek(start_byte + 0x438)
            if f.read(2) == b"\x53\xef":
                return "ext2/3/4"
        if size_bytes >= 0x10048:
            f.seek(start_byte + 0x10040)
            if f.read(8) == b"_BHRfS_M":
                return "btrfs"
        if size_bytes >= 0x404:
            f.seek(start_byte + 0x400)
            if f.read(4) == b"\xe2\xe1\xf5\xe0":
                return "erofs"
        if size_bytes >= 512:
            f.seek(start_byte)
            head = f.read(512)
            if head.startswith(b"hsqs"):
                return "squashfs"
            if head.startswith(b"ANDROID!"):
                return "android_boot"
            if b"FAT32" in head[0x50:0x5A] or b"FAT16" in head[0x34:0x40] or b"MSDOS" in head[0:16]:
                return "vfat"
    except Exception:
        pass
    return "raw/unknown"


def inspect_gpt(img_path: Path) -> dict:
    """Parse GPT header at 512B or 4096B LBA1 and return partition metadata."""
    file_size = img_path.stat().st_size
    with open(img_path, "rb") as f:
        sector_size = None
        hdr = None
        for sec in (512, 4096):
            f.seek(sec)
            cand = f.read(92)
            if cand[:8] == b"EFI PART":
                sector_size = sec
                hdr = cand
                break

        if not hdr:
            return {"file_size": file_size, "gpt_found": False, "partitions": []}

        part_lba = struct.unpack("<Q", hdr[72:80])[0]
        num_parts = struct.unpack("<I", hdr[80:84])[0]
        entry_size = struct.unpack("<I", hdr[84:88])[0]

        partitions = []
        f.seek(part_lba * sector_size)
        raw_entries = f.read(num_parts * entry_size)
        for i in range(num_parts):
            ent = raw_entries[i * entry_size : (i + 1) * entry_size]
            if len(ent) < 128 or ent[:16] == b"\x00" * 16:
                continue
            first_lba, last_lba = struct.unpack("<QQ", ent[32:48])
            name_raw = ent[56:128]
            name = name_raw.decode("utf-16-le", errors="ignore").rstrip("\x00")
            start_byte = first_lba * sector_size
            size_bytes = (last_lba - first_lba + 1) * sector_size
            fs = detect_fs(f, start_byte, size_bytes)
            partitions.append({
                "index": i + 1,
                "name": name,
                "first_lba": first_lba,
                "last_lba": last_lba,
                "start_byte": start_byte,
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "filesystem": fs,
            })

        return {
            "file_size": file_size,
            "gpt_found": True,
            "sector_size": sector_size,
            "partitions": partitions,
        }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    img_path = OUT_DIR / EXPECTED_IMG_NAME

    register_active_task(TASK_ID, TASK_NAME)
    stop_event = threading.Event()
    start_ts = time.time()

    def heartbeat_loop():
        last_pct_bucket = -1
        last_notify_ts = start_ts
        while not stop_event.wait(15):
            if not img_path.exists():
                continue
            cur = img_path.stat().st_size
            pct = (cur / EXPECTED_SIZE) * 100.0
            elapsed = time.time() - start_ts
            speed_mb = (cur / (1024 * 1024)) / max(elapsed, 0.1)
            pct_bucket = int(pct // 20)
            now = time.time()
            if (pct_bucket > last_pct_bucket and pct >= 5.0) or (now - last_notify_ts >= 120):
                last_pct_bucket = max(last_pct_bucket, pct_bucket)
                last_notify_ts = now
                cur_gb = cur / (1024 ** 3)
                tot_gb = EXPECTED_SIZE / (1024 ** 3)
                msg = (
                    f"[PROGRESS] Extracting SteamOS Image\n"
                    f"- Progress: {cur_gb:.2f} / {tot_gb:.2f} GiB ({pct:.1f}%)\n"
                    f"- Throughput: {speed_mb:.1f} MB/s"
                )
                print(msg)
                sys.stdout.flush()
                send_telegram_message(msg, parse_mode=None)

    hb = threading.Thread(target=heartbeat_loop, daemon=True)
    hb.start()

    try:
        if img_path.exists() and img_path.stat().st_size == EXPECTED_SIZE:
            print(f"[OK] Image already extracted at {img_path} ({EXPECTED_SIZE} bytes).")
        else:
            print(f"[STAGE] Extracting {ARCHIVE_PREFIX}.001..003 to {OUT_DIR}...")
            sys.stdout.flush()
            with multivolumefile.open(str(ARCHIVE_PREFIX), mode="rb") as mv:
                with py7zr.SevenZipFile(mv, mode="r") as archive:
                    archive.extractall(path=OUT_DIR)
            print(f"[OK] Extraction completed in {time.time() - start_ts:.1f}s.")

        audit = inspect_gpt(img_path)
        AUDIT_OUT.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        print(f"[OK] GPT audit written to {AUDIT_OUT}")
        print(json.dumps(audit, indent=2))

        part_lines = [
            f"p{p['index']} {p['name']}: {p['size_mb']:.0f} MB ({p['filesystem']})"
            for p in audit.get("partitions", [])
        ]
        summary = (
            f"[PASS] SteamOS Extraction & GPT Audit Complete ({time.time() - start_ts:.0f}s)\n"
            f"- Image: {img_path.name} ({audit['file_size'] / (1024**3):.2f} GiB)\n"
            f"- Sector Size: {audit.get('sector_size', 'N/A')} B\n"
            f"- Partitions:\n  " + ("\n  ".join(part_lines) if part_lines else "None found")
        )
        send_telegram_message(summary, parse_mode=None)
    except Exception as exc:
        err_msg = f"[FAIL] SteamOS extraction error: {exc}"
        print(err_msg, file=sys.stderr)
        send_telegram_message(err_msg, parse_mode=None)
        sys.exit(1)
    finally:
        stop_event.set()
        hb.join(timeout=2)
        clear_active_task(TASK_ID)


if __name__ == "__main__":
    main()

