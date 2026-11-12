#!/usr/bin/env python3
"""
cleanup_project.py — Comprehensive Workspace Hygiene and Space Reclaim Runbook.
Adheres strictly to .agent/skills/folder-and-file-management/SKILL.md.

Purges:
  1. Ephemeral __pycache__ and build caches across entire workspace.
  2. Temporary PyInstaller build directories (desktop-app/build/).
  3. Redundant multi-gigabyte uncompressed raw disk extractions in distros/ (retaining pristine upstream archives).
  4. Redundant large tarballs and obsolete intermediate test boot images in scratch/.
  5. Temporary test logs and disposable probe files.
Preserves:
  - All verified releases, builders, source trees, drivers, packages, and skills.
"""
import os
import shutil
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SCRATCH = WORKSPACE / "scratch"
DISTROS = WORKSPACE / "distros"
DESKTOP_APP = WORKSPACE / "desktop-app"
LOGS = WORKSPACE / "logs"

def clean_pycache():
    print("[*] Purging ephemeral __pycache__ and bytecode caches...")
    count = 0
    for root, dirs, files in os.walk(WORKSPACE):
        if "__pycache__" in dirs:
            pycache_path = Path(root) / "__pycache__"
            try:
                shutil.rmtree(pycache_path, ignore_errors=True)
                count += 1
            except Exception:
                pass
    print(f"[+] Purged {count} __pycache__ directories.")

def clean_desktop_app_build():
    print("[*] Purging PyInstaller temporary build artifacts...")
    build_dir = DESKTOP_APP / "build"
    if build_dir.exists():
        size = sum(f.stat().st_size for f in build_dir.rglob("*") if f.is_file())
        shutil.rmtree(build_dir, ignore_errors=True)
        print(f"[+] Removed desktop-app/build/ ({size / (1024*1024):.1f} MB freed).")

def clean_distros_raw_extractions():
    print("[*] Cleaning redundant uncompressed disk dumps in distros/...")
    # Keep upstream compressed archives: *.img.xz, *.tar.xz, *.tar.gz, *.sau
    disposable_patterns = [
        "*.raw",
        "haos_generic-aarch64-18.4.img",
        "ubuntu-24.04-server-cloudimg-arm64.img",
        "haos_data.ext4",
        "haos_system0.ext4",
        "haos_system0_rootfs.tar.gz",
        "*.log",
    ]
    freed_bytes = 0
    for pat in disposable_patterns:
        for f in DISTROS.glob(pat):
            try:
                size = f.stat().st_size
                f.unlink()
                freed_bytes += size
                print(f"  - Removed extracted image: {f.name} ({size / (1024*1024):.1f} MB)")
            except Exception as e:
                print(f"    Warning: Could not remove {f.name}: {e}")
    print(f"[+] Distros extractions cleaned: {freed_bytes / (1024*1024*1024):.2f} GB freed.")

def clean_scratch():
    print("[*] Cleaning obsolete test boot images and scratch archives...")
    if not SCRATCH.exists():
        return

    # 1. Obsolete huge archives in scratch
    scratch_disposable_files = [
        "kernel_source.tar.gz",
        "kernel_src.tar.gz",
        "ubuntu-base-24.04.5-base-arm64.tar.gz",
        # Intermediate test boot images superseded by releases/Galaxy_S8_Linux_AP.tar
        "boot.img",
        "boot_custom.img",
        "boot_from_tar.img",
        "boot_golden.img",
        "boot_native_linux.img",
        "boot_native_ubuntu.img",
        "boot_proven_autoboot.img",
        "boot_test_kernel.img",
        "boot_twrp_autoboot.img",
        "boot_twrp_exact.img",
        "boot_ubuntu_autoboot.img",
        "magisk_headless_boot.img",
        "recovery.img",
        "recovery_standalone_twrp.img",
        # Intermediate test kernels
        "Image_custom",
        "Image_k9",
        "Image_kernel3",
        "Image_native_docker",
    ]
    freed_bytes = 0
    for fname in scratch_disposable_files:
        p = SCRATCH / fname
        if p.exists():
            try:
                size = p.stat().st_size
                p.unlink()
                freed_bytes += size
                print(f"  - Removed scratch artifact: {fname} ({size / (1024*1024):.1f} MB)")
            except Exception as e:
                print(f"    Warning: Could not remove {fname}: {e}")

    # 2. Obsolete scratch directories
    purge_dirs = [
        "haos_extracted",
        "haos_rootfs",
        "inspect_root",
        "magisk_boot",
        "test_boot_inspect",
        "test_fs_dir",
        "test_etc",
        "pulled_sbin",
        "ramdisk_work",
        "kernel_out",
    ]
    for d in purge_dirs:
        p = SCRATCH / d
        if p.exists():
            try:
                shutil.rmtree(p, ignore_errors=True)
                print(f"  - Removed temporary folder: scratch/{d}/")
            except Exception:
                pass

    # 3. Disposable test screenshots & audio dumps in scratch
    for pat in ["*.png", "*.wav", "*.pcm", "*.raw"]:
        for media in SCRATCH.glob(pat):
            try:
                media.unlink()
            except Exception:
                pass

    print(f"[+] Scratch cleanup finished: {freed_bytes / (1024*1024):.1f} MB freed.")

def clean_logs():
    print("[*] Archiving obsolete diagnostic dumps in logs/...")
    archive_diag = WORKSPACE / "archive" / "diagnostic_dumps"
    archive_diag.mkdir(parents=True, exist_ok=True)
    for p in LOGS.iterdir():
        if p.is_dir() and p.name.startswith("crash_investigation_"):
            dst = archive_diag / p.name
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.move(str(p), str(dst))
            print(f"  - Moved {p.name} -> archive/diagnostic_dumps/")

def clean_kernel_intermediates():
    print("[*] Cleaning massive linker intermediates in kernel/ (preserving Image & .config)...")
    kdir = WORKSPACE / "kernel"
    if not kdir.exists():
        return
    freed = 0
    for name in (
        "vmlinux.o",
        "vmlinux",
        ".tmp_vmlinux1",
        ".tmp_vmlinux2",
        ".tmp_kallsyms1.o",
        ".tmp_kallsyms2.o",
        ".tmp_System.map",
        "System.map",
    ):
        p = kdir / name
        if p.is_file():
            try:
                sz = p.stat().st_size
                p.unlink()
                freed += sz
                print(f"  - Removed kernel/{name} ({sz / (1024*1024):.1f} MB)")
            except Exception:
                pass
    print(f"[+] Kernel linker intermediates cleaned: {freed / (1024*1024*1024):.2f} GB freed.")

def main():
    print("=" * 60)
    print("         GALAXY S8 PROJECT WORKSPACE CLEANUP")
    print("=" * 60)
    clean_pycache()
    clean_desktop_app_build()
    clean_distros_raw_extractions()
    clean_kernel_intermediates()
    clean_scratch()
    clean_logs()
    print("=" * 60)
    print("Workspace cleanup complete. Industry standards enforced.")
    print("=" * 60)

if __name__ == "__main__":
    main()
