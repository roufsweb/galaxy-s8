import struct
import gzip
import os
import tarfile

def main():
    # 1. Read PC's ADB public key
    pubkey_path = os.path.expanduser('~/.android/adbkey.pub')
    with open(pubkey_path, 'rb') as f:
        pubkey_data = f.read().strip() + b'\n'
    print(f'Read PC adb public key ({len(pubkey_data)} bytes): {pubkey_data.split()[-1].decode()}')

    # 2. Read official Magisk CPIO
    with open('e:/rouf/galaxy-s8/scratch/magisk_official.cpio', 'rb') as f:
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

    # Modify default.prop
    for e in entries:
        if e['name'] == 'default.prop':
            text = e['content'].decode('latin1')
            text = text.replace('ro.secure=1', 'ro.secure=0')
            text = text.replace('ro.adb.secure=1', 'ro.adb.secure=0')
            text = text.replace('ro.debuggable=0', 'ro.debuggable=1')
            text = text.replace('persist.sys.usb.config=mtp', 'persist.sys.usb.config=mtp,adb')
            e['content'] = text.encode('latin1')

    # Add /adb_keys containing PC public key into ramdisk
    entries.append({
        'name': 'adb_keys',
        'mode': 0o100644,
        'uid': 0,
        'gid': 0,
        'nlink': 1,
        'mtime': 0,
        'content': pubkey_data
    })
    print('Injected /adb_keys into ramdisk root.')

    # Add overlay.d/init.headless.rc
    headless_rc = (
        "on early-init\n"
        "    setprop ro.secure 0\n"
        "    setprop ro.adb.secure 0\n"
        "    setprop ro.debuggable 1\n"
        "\n"
        "on post-fs-data\n"
        "    mkdir /data/misc/adb 02750 system shell\n"
        "    copy /adb_keys /data/misc/adb/adb_keys\n"
        "    chown system shell /data/misc/adb/adb_keys\n"
        "    chmod 0640 /data/misc/adb/adb_keys\n"
        "    setprop persist.sys.usb.config mtp,adb\n"
        "    setprop sys.usb.config mtp,adb\n"
        "\n"
        "on boot\n"
        "    setprop persist.sys.usb.config mtp,adb\n"
        "    setprop sys.usb.config mtp,adb\n"
        "    start adbd\n"
        "\n"
        "on property:sys.boot_completed=1\n"
        "    copy /adb_keys /data/misc/adb/adb_keys\n"
        "    chown system shell /data/misc/adb/adb_keys\n"
        "    chmod 0640 /data/misc/adb/adb_keys\n"
        "    setprop persist.sys.usb.config mtp,adb\n"
        "    setprop sys.usb.config mtp,adb\n"
        "    start adbd\n"
        "    exec u:r:magisk:s0 -- /system/bin/locksettings set-disabled true\n"
        "    exec u:r:magisk:s0 -- /system/bin/settings put global setup_wizard_has_run 1\n"
        "    exec u:r:magisk:s0 -- /system/bin/settings put secure user_setup_complete 1\n"
        "    exec u:r:magisk:s0 -- /system/bin/wm dismiss-keyguard\n"
    ).encode('latin1')

    entries.append({
        'name': 'overlay.d/init.headless.rc',
        'mode': 0o100644,
        'uid': 0,
        'gid': 0,
        'nlink': 1,
        'mtime': 0,
        'content': headless_rc
    })

    # Build CPIO
    out_cpio = bytearray()
    ino = 1
    for e in entries:
        name_b = e['name'].encode('latin1') + b'\0'
        content = e['content']
        mode_val = e['mode']
        uid_val = e['uid']
        gid_val = e['gid']
        nlink_val = e['nlink']
        mtime_val = e['mtime']
        hdr = (
            f"070701{ino:08X}{mode_val:08X}{uid_val:08X}{gid_val:08X}"
            f"{nlink_val:08X}{mtime_val:08X}{len(content):08X}"
            f"00000000000000000000000000000000{len(name_b):08X}00000000"
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

    comp_ramdisk = gzip.compress(bytes(out_cpio), compresslevel=9, mtime=0)
    print(f'Gzip ramdisk size: {len(comp_ramdisk)} bytes.')

    with tarfile.open('e:/rouf/galaxy-s8/boot_stock.tar', 'r') as tf:
        stock_boot = tf.extractfile('boot.img').read()

    stock_hdr = bytearray(stock_boot[:2048])
    k_len, _, _, _, _, _, _, page_size = struct.unpack('<8I', stock_hdr[8:40])
    dtb_len = struct.unpack('<I', stock_hdr[40:44])[0]
    kernel_data = stock_boot[page_size : page_size + k_len]
    r_len_old = struct.unpack('<I', stock_hdr[16:20])[0]
    r_off = page_size + ((k_len + page_size - 1) // page_size) * page_size
    dtb_off = r_off + ((r_len_old + page_size - 1) // page_size) * page_size
    dtb_data = stock_boot[dtb_off : dtb_off + dtb_len]

    struct.pack_into('<I', stock_hdr, 16, len(comp_ramdisk))

    def pad(d, sz):
        rem = len(d) % sz
        if rem != 0:
            return d + b'\0' * (sz - rem)
        return d

    boot_img = (
        stock_hdr +
        pad(kernel_data, page_size) +
        pad(comp_ramdisk, page_size) +
        pad(dtb_data, page_size)
    )

    print(f'Total boot.img size: {len(boot_img)} bytes ({len(boot_img)/(1024*1024):.2f} MB).')

    temp_boot = 'e:/rouf/galaxy-s8/scratch/magisk_headless_boot.img'
    with open(temp_boot, 'wb') as f:
        f.write(boot_img)

    out_tar = 'e:/rouf/galaxy-s8/magisk_headless_adb.tar'
    with tarfile.open(out_tar, 'w', format=tarfile.USTAR_FORMAT) as tf:
        tf.add(temp_boot, arcname='boot.img')

    print(f'Successfully built {out_tar}: {os.path.getsize(out_tar)} bytes!')

if __name__ == '__main__':
    main()
