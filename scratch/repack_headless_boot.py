import os
import struct
import lz4.block
import tarfile

def build():
    # 1. Read cpio data
    with open('e:/rouf/galaxy-s8/scratch/ramdisk.cpio', 'rb') as f:
        data = f.read()

    pos = 0
    entries = []
    while pos < len(data) - 110:
        magic = data[pos:pos+6]
        if magic not in (b'070701', b'070702'):
            break
        mode = int(data[pos+14:pos+22], 16)
        uid = int(data[pos+22:pos+30], 16)
        gid = int(data[pos+30:pos+38], 16)
        nlink = int(data[pos+38:pos+46], 16)
        mtime = int(data[pos+46:pos+54], 16)
        filesize = int(data[pos+54:pos+62], 16)
        namesize = int(data[pos+94:pos+102], 16)
        pos += 110
        name = data[pos:pos+namesize-1].decode('latin1', errors='ignore')
        pos += namesize
        rem = (110 + namesize) % 4
        if rem != 0:
            pos += (4 - rem)
        content = data[pos:pos+filesize]
        pos += filesize
        rem2 = filesize % 4
        if rem2 != 0:
            pos += (4 - rem2)
        if name != 'TRAILER!!!':
            entries.append({'name': name, 'mode': mode, 'uid': uid, 'gid': gid, 'nlink': nlink, 'mtime': mtime, 'content': content})

    print(f'Parsed {len(entries)} entries from cpio.')

    # 2. Modify default.prop
    for e in entries:
        if e['name'] == 'default.prop':
            text = e['content'].decode('latin1')
            text = text.replace('ro.secure=1', 'ro.secure=0')
            text = text.replace('ro.adb.secure=1', 'ro.adb.secure=0')
            text = text.replace('ro.debuggable=0', 'ro.debuggable=1')
            text = text.replace('persist.sys.usb.config=mtp', 'persist.sys.usb.config=mtp,adb')
            e['content'] = text.encode('latin1')
            print('Modified default.prop:')
            for line in text.splitlines():
                if any(k in line for k in ['secure', 'debuggable', 'usb.config']):
                    print('  ', line)

    # 3. Add overlay.d/headless_adb.rc
    headless_rc = (
        "on early-init\n"
        "    setprop ro.secure 0\n"
        "    setprop ro.adb.secure 0\n"
        "    setprop ro.debuggable 1\n"
        "\n"
        "on post-fs-data\n"
        "    setprop persist.sys.usb.config mtp,adb\n"
        "    setprop sys.usb.config mtp,adb\n"
        "\n"
        "on boot\n"
        "    setprop persist.sys.usb.config mtp,adb\n"
        "    setprop sys.usb.config mtp,adb\n"
        "    start adbd\n"
        "\n"
        "on property:sys.boot_completed=1\n"
        "    setprop persist.sys.usb.config mtp,adb\n"
        "    setprop sys.usb.config mtp,adb\n"
        "    start adbd\n"
        "    exec u:r:magisk:s0 -- /system/bin/settings put global setup_wizard_has_run 1\n"
        "    exec u:r:magisk:s0 -- /system/bin/settings put secure user_setup_complete 1\n"
        "    exec u:r:magisk:s0 -- /system/bin/locksettings set-disabled true\n"
        "    exec u:r:magisk:s0 -- /system/bin/wm dismiss-keyguard\n"
    ).encode('latin1')

    entries.append({
        'name': 'overlay.d/headless_adb.rc',
        'mode': 0o100644,
        'uid': 0,
        'gid': 0,
        'nlink': 1,
        'mtime': 0,
        'content': headless_rc
    })
    print('Added overlay.d/headless_adb.rc')

    # 4. Pack into CPIO
    out_cpio = bytearray()
    ino = 1
    for e in entries:
        name_b = e['name'].encode('latin1') + b'\0'
        name_len = len(name_b)
        content = e['content']
        hdr = (
            f"070701{ino:08X}{e['mode']:08X}{e['uid']:08X}{e['gid']:08X}"
            f"{e['nlink']:08X}{e['mtime']:08X}{len(content):08X}"
            f"00000000000000000000000000000000{name_len:08X}00000000"
        ).encode('ascii')
        out_cpio.extend(hdr)
        out_cpio.extend(name_b)
        rem = (len(hdr) + len(name_b)) % 4
        if rem != 0:
            out_cpio.extend(b'\0' * (4 - rem))
        out_cpio.extend(content)
        rem2 = len(content) % 4
        if rem2 != 0:
            out_cpio.extend(b'\0' * (4 - rem2))
        ino += 1

    trailer_name = b'TRAILER!!!\0'
    hdr = (
        f"07070100000000000000000000000000000000000000010000000000000000"
        f"00000000000000000000000000000000{len(trailer_name):08X}00000000"
    ).encode('ascii')
    out_cpio.extend(hdr)
    out_cpio.extend(trailer_name)
    rem = (len(hdr) + len(trailer_name)) % 4
    if rem != 0:
        out_cpio.extend(b'\0' * (4 - rem))
    total_rem = len(out_cpio) % 512
    if total_rem != 0:
        out_cpio.extend(b'\0' * (512 - total_rem))

    print(f'Repacked CPIO size: {len(out_cpio)} bytes.')

    # 5. Compress CPIO with LZ4 legacy format
    # S-Boot requires LZ4 legacy format (0x184C2102) with 8MB block sizes
    lz4_magic = b'\x02\x21\x4c\x18'
    block_size = 8 * 1024 * 1024 # 8MB
    compressed_ramdisk = bytearray(lz4_magic)

    pos = 0
    while pos < len(out_cpio):
        chunk = bytes(out_cpio[pos:pos+block_size])
        pos += len(chunk)
        comp_chunk = lz4.block.compress(chunk, mode='high_compression', store_size=False)
        compressed_ramdisk.extend(struct.pack('<I', len(comp_chunk)))
        compressed_ramdisk.extend(comp_chunk)

    print(f'Compressed ramdisk size: {len(compressed_ramdisk)} bytes.')

    # 6. Assemble boot.img
    # Use stock kernel (AP_G950NKSU5DVG2) and stock DTB with exact stock header
    with open('e:/rouf/galaxy-s8/boot_stock.tar', 'rb') as f:
        tf = tarfile.open(fileobj=f)
        stock_boot = tf.extractfile('boot.img').read()

    # Exact stock 2048-byte header from official Samsung firmware
    new_hdr = bytearray(stock_boot[:2048])
    hdr = stock_boot[:2048]
    k_len, _, _, _, _, _, _, page_size = struct.unpack('<8I', hdr[8:40])
    dtb_len = struct.unpack('<I', hdr[40:44])[0]
    kernel_data = stock_boot[page_size : page_size + k_len]
    
    # In stock boot, dtb is after ramdisk
    r_len_old = struct.unpack('<I', hdr[16:20])[0]
    r_off = page_size + ((k_len + page_size - 1) // page_size) * page_size
    dtb_off = r_off + ((r_len_old + page_size - 1) // page_size) * page_size
    dtb_data = stock_boot[dtb_off : dtb_off + dtb_len]

    def pad(d, sz):
        rem = len(d) % sz
        if rem != 0:
            return d + b'\0' * (sz - rem)
        return d

    # Only patch the ramdisk size in the original stock header
    # This preserves S-Boot board ID (SRPPK29D005KU), second_addr (0x10f00000), dtb_addr (0x12000154)
    struct.pack_into('<I', new_hdr, 16, len(compressed_ramdisk))

    boot_img_data = (
        new_hdr +
        pad(kernel_data, page_size) +
        pad(compressed_ramdisk, page_size) +
        pad(dtb_data, page_size)
    )

    out_boot_img = 'e:/rouf/galaxy-s8/scratch/boot.img'
    with open(out_boot_img, 'wb') as f:
        f.write(boot_img_data)
    print(f'Generated boot.img: {len(boot_img_data)} bytes ({len(boot_img_data)/(1024*1024):.2f} MB).')
    assert len(boot_img_data) <= 41943040, f'Overflow! {len(boot_img_data)} > 41943040'

    # 7. Extract recovery.img from recovery_restore.tar
    with tarfile.open('e:/rouf/galaxy-s8/recovery_restore.tar', 'r') as tf:
        rec_data = tf.extractfile('recovery.img').read()
    print(f'Loaded recovery.img: {len(rec_data)} bytes.')

    # 8. Package both into boot_and_recovery_headless.tar in pure USTAR format
    out_tar = 'e:/rouf/galaxy-s8/boot_and_recovery_headless.tar'
    with tarfile.open(out_tar, 'w', format=tarfile.USTAR_FORMAT) as tf:
        tf.add(out_boot_img, arcname='boot.img')
        # write temp recovery.img
        temp_rec = 'e:/rouf/galaxy-s8/scratch/recovery.img'
        with open(temp_rec, 'wb') as rf:
            rf.write(rec_data)
        tf.add(temp_rec, arcname='recovery.img')

    print(f'Successfully built {out_tar}: {os.path.getsize(out_tar)} bytes!')

if __name__ == '__main__':
    build()

