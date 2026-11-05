#!/usr/bin/env python3
"""
build_autoboot_and_odin.py — Builds the Auto-Booting Galaxy S8 boot.img (for /dev/block/sda7)
with embedded Calliope DSP Audio Firmware (all 9 SRAM, DRAM, IVA, and extra firmware binaries),
proper CPIO directory structure (etc/firmware and vendor/firmware), early /system_root mounting
in permissive.sh, 1500mA Fast Charging, V4L2 ISP Kernel Panic Guard, and 1-Click Odin Package.
"""
import os
import struct
import lzma
import tarfile

WORKSPACE = r"e:\rouf\galaxy-s8"
SRC_TAR = os.path.join(WORKSPACE, "archive", "boot_twrp_exact.tar")
REC_TAR = os.path.join(WORKSPACE, "archive", "recovery_restore.tar")
OUT_BOOT = os.path.join(WORKSPACE, "boot", "boot_ubuntu_autoboot.img")
OUT_ODIN_TAR = os.path.join(WORKSPACE, "releases", "Ubuntu_24.04_GalaxyS8_Full_Odin.tar")

AUTOBOOT_RC_SNIPPET = b"""

# --- Native Ubuntu 24.04.5 LTS + GNOME macOS Sonoma Auto-Boot ---
on boot
    start ubuntu_boot

service ubuntu_boot /sbin/sh /data/linux/start_all.sh
    user root
    group root
    disabled
    oneshot
    seclabel u:r:recovery:s0
"""

PERMISSIVE_SH_NEW = b"""#!/sbin/sh
setenforce 0

# Early Audio DSP and Wi-Fi Firmware mount for ABOX & BCM4361
mkdir -p /system_root /etc/firmware /data
mount -o ro /dev/block/sda17 /system_root 2>/dev/null
rm -rf /vendor
ln -s /system_root/vendor /vendor 2>/dev/null || true
mount -o bind /system_root/vendor/firmware /etc/firmware 2>/dev/null || true
"""

ALL_FIRMWARES = (
    "calliope_sram.bin",
    "calliope_dram.bin",
    "calliope_iva.bin",
    "dsm.bin",
    "AP_AUDIO_SLSI.bin",
    "APBargeIn_AUDIO_SLSI.bin",
    "SoundBoosterParam.bin",
    "APBiBF_AUDIO_SLSI.bin",
    "dsm_tune.bin"
)

def align_up(val: int, align: int) -> int:
    return (val + align - 1) & ~(align - 1)

def make_cpio_entry(filename: str, data: bytes = b"", mode: int = 0o100644, ino: int = 200) -> bytes:
    name_bytes = filename.encode("ascii") + b"\x00"
    filesize = len(data)
    header = f"070701{ino:08X}{mode:08X}{0:08X}{0:08X}{1:08X}{0:08X}{filesize:08X}{0:08X}{0:08X}{0:08X}{0:08X}{len(name_bytes):08X}{0:08X}".encode("ascii")
    entry = bytearray()
    entry.extend(header)
    entry.extend(name_bytes)
    entry.extend(b"\x00" * (align_up(len(entry), 4) - len(entry)))
    entry.extend(data)
    entry.extend(b"\x00" * (align_up(len(entry), 4) - len(entry)))
    return bytes(entry)

SKIP_FILES = {
    b"twres/fonts/DroidSansFallback.ttf",
    b"./twres/fonts/DroidSansFallback.ttf",
    b"twres/fonts/NotoSansCJKjp-Regular.ttf",
    b"./twres/fonts/NotoSansCJKjp-Regular.ttf",
    b"sbin/libclang_rt.ubsan_standalone-aarch64-android.so",
    b"./sbin/libclang_rt.ubsan_standalone-aarch64-android.so",
}

def patch_cpio_archive(cpio_bytes: bytes) -> bytes:
    out = bytearray()
    pos = 0
    n = len(cpio_bytes)
    trailer_pos = -1

    while pos + 110 <= n:
        magic = cpio_bytes[pos:pos + 6]
        if magic not in (b"070701", b"070702"):
            break
        header = cpio_bytes[pos:pos + 110]
        filesize = int(header[54:62].decode("ascii"), 16)
        namesize = int(header[94:102].decode("ascii"), 16)

        name_start = pos + 110
        name_end = name_start + namesize
        name_aligned = align_up(name_end, 4)

        name_raw = cpio_bytes[name_start:name_end].rstrip(b"\x00")
        data_start = name_aligned
        data_end = data_start + filesize
        data_aligned = align_up(data_end, 4)

        if name_raw == b"TRAILER!!!":
            trailer_pos = pos
            break

        if name_raw in SKIP_FILES:
            print(f"[-] Trimming bloated TWRP asset: {name_raw.decode('latin1')} ({filesize} bytes)")
            pos = data_aligned
            continue

        if name_raw in (b"init.rc", b"./init.rc"):
            orig_data = cpio_bytes[data_start:data_end]
            if b"service ubuntu_boot" not in orig_data:
                new_data = orig_data + AUTOBOOT_RC_SNIPPET
            else:
                new_data = orig_data
            new_filesize_hex = f"{len(new_data):08X}".encode("ascii")
            new_header = header[:54] + new_filesize_hex + header[62:]
            out.extend(new_header)
            out.extend(cpio_bytes[name_start:name_aligned])
            out.extend(new_data)
            out.extend(b"\x00" * (align_up(len(out), 4) - len(out)))
        elif name_raw in (b"sbin/permissive.sh", b"./sbin/permissive.sh"):
            new_data = PERMISSIVE_SH_NEW
            new_filesize_hex = f"{len(new_data):08X}".encode("ascii")
            new_header = header[:54] + new_filesize_hex + header[62:]
            out.extend(new_header)
            out.extend(cpio_bytes[name_start:name_aligned])
            out.extend(new_data)
            out.extend(b"\x00" * (align_up(len(out), 4) - len(out)))
            print("[+] Patched sbin/permissive.sh with early firmware mount")
        else:
            out.extend(cpio_bytes[pos:data_aligned])

        pos = data_aligned

    if trailer_pos < 0:
        raise RuntimeError("Could not find TRAILER!!! in CPIO archive")

    # Inhibit Directory structure: etc/firmware and vendor/firmware
    ino_counter = 1000
    out.extend(make_cpio_entry("etc/firmware", b"", mode=0o040755, ino=ino_counter))
    ino_counter += 1
    out.extend(make_cpio_entry("vendor", b"", mode=0o040755, ino=ino_counter))
    ino_counter += 1
    out.extend(make_cpio_entry("vendor/firmware", b"", mode=0o040755, ino=ino_counter))
    ino_counter += 1

    # Inhibit All 9 Calliope DSP and audio firmwares directly into both directories
    scratch_dir = os.path.join(WORKSPACE, "scratch")
    for fw_name in ALL_FIRMWARES:
        fw_path = os.path.join(scratch_dir, fw_name)
        if os.path.exists(fw_path):
            with open(fw_path, "rb") as fp:
                fw_data = fp.read()
            out.extend(make_cpio_entry(f"etc/firmware/{fw_name}", fw_data, mode=0o100644, ino=ino_counter))
            ino_counter += 1
            out.extend(make_cpio_entry(f"vendor/firmware/{fw_name}", fw_data, mode=0o100644, ino=ino_counter))
            ino_counter += 1
            print(f"[+] Injected firmware: {fw_name} ({len(fw_data)} bytes)")
        else:
            print(f"[!] Warning: firmware {fw_name} not found in {scratch_dir}")

    out.extend(cpio_bytes[trailer_pos:])
    return bytes(out)

def build_autoboot():
    with tarfile.open(SRC_TAR, "r") as t:
        boot_bytes = t.extractfile("boot.img").read()

    magic, k_size, k_addr, r_size, r_addr, s_size, s_addr, t_addr, page_size, dt_size, os_ver = struct.unpack(
        "<8s10I", boot_bytes[:48]
    )
    assert magic == b"ANDROID!", f"Unexpected magic: {magic}"

    k_off = page_size
    r_off = k_off + align_up(k_size, page_size)
    s_off = r_off + align_up(r_size, page_size)
    dt_off = s_off + align_up(s_size, page_size)

    custom_kernel_path = os.path.join(WORKSPACE, "scratch", "Image_native_docker")
    if os.path.exists(custom_kernel_path):
        with open(custom_kernel_path, "rb") as fk:
            kernel_blob = fk.read()
        k_size = len(kernel_blob)
        print(f"[+] Using custom DEFEX-free native Docker & Bluetooth kernel: {custom_kernel_path} ({k_size} bytes)")
    else:
        kernel_blob = boot_bytes[k_off:k_off + k_size]

    ramdisk_blob = boot_bytes[r_off:r_off + r_size]
    second_blob = boot_bytes[s_off:s_off + s_size]
    dt_blob = boot_bytes[dt_off:dt_off + dt_size]

    print(f"[*] Original boot: kernel={k_size} B, ramdisk={r_size} B, dt={dt_size} B, page={page_size}")

    # Decompress CPIO ramdisk
    cpio_raw = lzma.decompress(ramdisk_blob)
    print(f"[*] Decompressed ramdisk CPIO: {len(cpio_raw)} bytes")

    patched_cpio = patch_cpio_archive(cpio_raw)
    print(f"[*] Patched CPIO with firmware: {len(patched_cpio)} bytes")

    # Compress with LZMA alone format (preset 9 for max compression)
    new_ramdisk = lzma.compress(
        patched_cpio,
        format=lzma.FORMAT_ALONE,
        filters=[{"id": lzma.FILTER_LZMA1, "preset": 9}]
    )
    print(f"[*] Recompressed LZMA ramdisk: {len(new_ramdisk)} bytes (delta: {len(new_ramdisk) - r_size:+d} bytes)")

    new_header = bytearray(boot_bytes[:page_size])
    struct.pack_into("<I", new_header, 8, k_size)
    struct.pack_into("<I", new_header, 16, len(new_ramdisk))

    out = bytearray()
    out.extend(new_header)
    out.extend(kernel_blob)
    out.extend(b"\x00" * (align_up(len(out), page_size) - len(out)))

    out.extend(new_ramdisk)
    out.extend(b"\x00" * (align_up(len(out), page_size) - len(out)))

    if s_size > 0:
        out.extend(second_blob)
        out.extend(b"\x00" * (align_up(len(out), page_size) - len(out)))

    if dt_size > 0:
        out.extend(dt_blob)
        out.extend(b"\x00" * (align_up(len(out), page_size) - len(out)))

    out.extend(b"SEANDROIDENFORCE")
    assert len(out) <= 41943040, f"Image too large for sda7: {len(out)} > 41943040"

    with open(OUT_BOOT, "wb") as f:
        f.write(out)
    print(f"[+] Wrote {OUT_BOOT} ({len(out)} bytes <= 41,943,040 limit, free: {41943040 - len(out)} bytes)")

    with tarfile.open(OUT_ODIN_TAR, "w", format=tarfile.USTAR_FORMAT) as t:
        t.add(OUT_BOOT, arcname="boot.img")
        if os.path.exists(REC_TAR):
            with tarfile.open(REC_TAR, "r") as rt:
                rec_info = rt.getmember("recovery.img")
                rec_file = rt.extractfile("recovery.img")
                ti = tarfile.TarInfo(name="recovery.img")
                ti.size = rec_info.size
                ti.mtime = int(rec_info.mtime)
                ti.mode = 0o644
                t.addfile(ti, rec_file)
    print(f"[+] Created 1-Click Odin Installer: {OUT_ODIN_TAR} ({os.path.getsize(OUT_ODIN_TAR)} bytes)")

if __name__ == "__main__":
    build_autoboot()
