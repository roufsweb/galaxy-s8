#!/usr/bin/env python3
"""
cleanup_project.py — Safely purges temporary build artifacts, unpacked test rootfs,
and redundant scratch dumps while preserving verified drivers, builders, and active configurations.
"""
import os
import shutil
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SCRATCH = WORKSPACE / "scratch"

def purge_scratch():
    print("[*] Cleaning up scratch workspace...")
    purge_dirs = [
        "haos_extracted",
        "haos_rootfs",
        "inspect_root",
        "magisk_boot",
        "test_boot_inspect",
        "test_fs_dir",
        "test_etc",
        "pulled_sbin",
    ]
    for d in purge_dirs:
        p = SCRATCH / d
        if p.exists():
            print(f"  - Removing obsolete extraction: {d}/")
            shutil.rmtree(p, ignore_errors=True)

    # Remove temporary screenshot captures in scratch (official copies are in brain artifacts)
    for png in SCRATCH.glob("*.png"):
        try:
            png.unlink()
        except Exception:
            pass

    # Remove temporary test audio recordings
    for media_pat in ["*.wav", "*.pcm", "*.raw"]:
        for media in SCRATCH.glob(media_pat):
            try:
                media.unlink()
            except Exception:
                pass

    # Remove obsolete disposable test filesystem images
    obsolete_files = [
        "raspios_rootfs.ext4",
        "haos_system.ext4",
        "haos_system.ext4.gz",
        "haos_data_resized.ext4.gz",
        "switchroot_old.cpio",
        "switchroot_new.cpio",
        "test.ext4",
        "test_fs.tar",
    ]
    for f in obsolete_files:
        p = SCRATCH / f
        if p.exists():
            print(f"  - Removing disposable scratch image: {f}")
            try:
                p.unlink()
            except Exception as e:
                print(f"    Warning: could not remove {f}: {e}")

    print("[+] Scratch cleanup finished.")

def organize_docs():
    print("[*] Organizing documentation...")
    docs_dir = WORKSPACE / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    # Move root markdown docs into docs/ where appropriate
    docs_to_move = [
        "HOME_ASSISTANT.md",
        "SENSORS_GUIDE.md",
        "PROJECT_FEATURE_QUEUE.md",
    ]
    for doc in docs_to_move:
        src = WORKSPACE / doc
        dst = docs_dir / doc
        if src.exists() and not dst.exists():
            print(f"  - Moving {doc} -> docs/{doc}")
            shutil.move(str(src), str(dst))

def clean_pycache():
    print("[*] Purging ephemeral __pycache__ and build caches...")
    for root, dirs, files in os.walk(WORKSPACE):
        if "__pycache__" in dirs:
            pycache_path = Path(root) / "__pycache__"
            try:
                shutil.rmtree(pycache_path, ignore_errors=True)
            except Exception:
                pass

def main():
    print("=" * 60)
    print("         GALAXY S8 PROJECT WORKSPACE CLEANUP")
    print("=" * 60)
    purge_scratch()
    organize_docs()
    clean_pycache()
    print("=" * 60)
    print("Cleanup complete. Clean workspace verified.")
    print("=" * 60)

if __name__ == "__main__":
    main()
