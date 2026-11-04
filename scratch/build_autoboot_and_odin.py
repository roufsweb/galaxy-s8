#!/usr/bin/env python3
"""
build_autoboot_and_odin.py — Builds the Auto-Booting Galaxy S8 boot.img (for /dev/block/sda7)
and the 1-Click Odin Flashable Package (Ubuntu_24.04_GalaxyS8_Full_Odin.tar).

How it works:
  1. Extracts boot.img from boot_twrp_exact.tar (38.64 MB, DEFEX-free 4.4.111 kernel).
  2. Parses the ANDROID! header (page_size=2048, SRPPK29D005KU, dt_size, cmdline).
  3. Decompresses the LZMA ramdisk CPIO archive (newc format).
  4. Appends an 'ubuntu_boot' service to init.recovery.samsungexynos8895.rc triggered
     automatically on 'property:sys.usb.ffs.ready=1' (after USB gadget + adbd are live)
     so /data/linux/start_all.sh runs automatically on every boot with zero manual steps.
  5. Repacks the LZMA ramdisk + ANDROID! boot.img + SEANDROIDENFORCE footer.
  6. Creates Ubuntu_24.04_GalaxyS8_Full_Odin.tar (USTAR format for Odin AP slot).
"""
import io
import lzma
import os
import struct
import tarfile

WORKSPACE = r"e:\rouf\galaxy-s8"
SRC_TAR = os.path.join(WORKSPACE, "boot_twrp_exact.tar")
REC_TAR = os.path.join(WORKSPACE, "recovery_restore.tar")
OUT_BOOT = os.path.join(WORKSPACE, "scratch", "boot_ubuntu_autoboot.img")
OUT_ODIN_TAR = os.path.join(WORKSPACE, "Ubuntu_24.04_GalaxyS8_Full_Odin.tar")

AUTOBOOT_RC_SNIPPET = b"""

# --- Native Ubuntu 24.04.5 LTS + GNOME macOS Sonoma Auto-Boot ---
on property:sys.usb.ffs.ready=1
    start ubuntu_boot

service ubuntu_boot /sbin/sh /data/linux/start_all.sh
    user root
    group root
    disabled
    oneshot
    seclabel u:r:recovery:s0
"""


def align_up(val: int, align: int) -> int:
    return (val + align - 1) & ~(align - 1)


def patch_cpio_newc(cpio_bytes: bytes, target_name: bytes, append_bytes: bytes) -> bytes:
    """Finds target_name inside an SVR4 newc CPIO archive and appends append_bytes to its content."""
    out = bytearray()
    pos = 0
    n = len(cpio_bytes)
    patched = False

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

        if name_raw == target_name or name_raw == b"./" + target_name:
            orig_data = cpio_bytes[data_start:data_end]
            if b"service ubuntu_boot" not in orig_data:
                new_data = orig_data + append_bytes
            else:
                new_data = orig_data
            new_filesize_hex = f"{len(new_data):08X}".encode("ascii")
            new_header = header[:54] + new_filesize_hex + header[62:]

            out.extend(new_header)
            out.extend(cpio_bytes[name_start:name_aligned])
            out.extend(new_data)
            pad_len = align_up(len(out), 4) - len(out)
            out.extend(b"\x00" * pad_len)
            patched = True
        else:
            out.extend(cpio_bytes[pos:data_aligned])

        pos = data_aligned
        if name_raw == b"TRAILER!!!":
            break

    if not patched:
        raise RuntimeError(f"Could not find {target_name!r} in ramdisk CPIO archive")
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

    kernel_blob = boot_bytes[k_off:k_off + k_size]
    ramdisk_blob = boot_bytes[r_off:r_off + r_size]
    second_blob = boot_bytes[s_off:s_off + s_size]
    dt_blob = boot_bytes[dt_off:dt_off + dt_size]

    print(f"[*] Original boot.img: kernel={k_size}B, ramdisk={r_size}B, dt={dt_size}B, page_size={page_size}")

    cpio_raw = lzma.decompress(ramdisk_blob)
    print(f"[*] Decompressed ramdisk CPIO: {len(cpio_raw)} bytes")

    patched_cpio = patch_cpio_newc(cpio_raw, b"init.rc", AUTOBOOT_RC_SNIPPET)
    print(f"[*] Patched init.rc: {len(patched_cpio)} bytes")

    # Compress back to legacy LZMA (.lzma format with EOS marker so kernel decompress_unlzma handles it cleanly)
    new_ramdisk = lzma.compress(
        patched_cpio,
        format=lzma.FORMAT_ALONE,
        filters=[{"id": lzma.FILTER_LZMA1, " preset": 6, "dict_size": 8 * 1024 * 1024}]
        if False else [{"id": lzma.FILTER_LZMA1, "preset": 6}],
    )
    print(f"[*] Recompressed LZMA ramdisk: {len(new_ramdisk)} bytes (orig {r_size} bytes)")

    # Rebuild header with updated r_size
    new_header = bytearray(boot_bytes[:page_size])
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
    assert len(out) <= 41943040, f"Image too large for sda7: {len(out)}"

    with open(OUT_BOOT, "wb") as f:
        f.write(out)
    print(f"[+] Wrote auto-booting {OUT_BOOT} ({len(out)} bytes <= 41,943,040 B sda7 limit)")

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

