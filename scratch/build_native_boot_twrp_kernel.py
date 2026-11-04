import os
import struct
import gzip
import tarfile

def pad(data, page_size=2048):
    rem = len(data) % page_size
    if rem != 0:
        return data + b'\x00' * (page_size - rem)
    return data

def update_cpio_init(in_cpio, new_init_path, out_cpio):
    with open(new_init_path, 'rb') as f:
        new_init_data = f.read()
    new_init_data = new_init_data.replace(b'\r\n', b'\n')

    with open(in_cpio, 'rb') as f:
        data = f.read()

    pos = 0
    total = len(data)
    out_chunks = []
    
    while pos + 110 <= total:
        magic = data[pos:pos+6]
        if magic != b'070701':
            break
        
        hdr = bytearray(data[pos:pos+110])
        namesize = int(hdr[94:102], 16)
        filesize = int(hdr[54:62], 16)
        
        pos += 110
        filename = data[pos:pos+namesize-1].decode('ascii', errors='ignore')
        name_block = data[pos:pos+namesize]
        pos += namesize
        if pos % 4 != 0:
            pos += 4 - (pos % 4)

        filedata = data[pos:pos+filesize]
        pos += filesize
        if pos % 4 != 0:
            pos += 4 - (pos % 4)

        if filename == 'init':
            print(f'Replacing init ({len(filedata)} bytes -> {len(new_init_data)} bytes)')
            hdr[54:62] = f'{len(new_init_data):08x}'.encode('ascii')
            hdr[14:22] = f'{0o100755:08x}'.encode('ascii')
            filedata = new_init_data

        chunk = bytes(hdr) + name_block
        if len(chunk) % 4 != 0:
            chunk += b'\x00' * (4 - (len(chunk) % 4))
        chunk += filedata
        if len(chunk) % 4 != 0:
            chunk += b'\x00' * (4 - (len(chunk) % 4))
        out_chunks.append(chunk)

        if filename == 'TRAILER!!!':
            break

    full_cpio = b''.join(out_chunks)
    with open(out_cpio, 'wb') as f:
        f.write(full_cpio)
    print(f'Wrote updated cpio: {len(full_cpio)} bytes.')
    return full_cpio

def main():
    # 1. Update init in switchroot cpio
    in_cpio = 'e:/rouf/galaxy-s8/scratch/switchroot_old.cpio'
    init_path = 'e:/rouf/galaxy-s8/scratch/switchroot_init.sh'
    out_cpio = 'e:/rouf/galaxy-s8/scratch/switchroot_new.cpio'
    cpio_data = update_cpio_init(in_cpio, init_path, out_cpio)

    # 2. GZIP compress (mtime=0)
    comp_ramdisk = gzip.compress(cpio_data, compresslevel=9, mtime=0)
    print(f'Gzip ramdisk size: {len(comp_ramdisk)} bytes ({len(comp_ramdisk)/1024:.1f} KB).')

    # 3. Extract TWRP kernel and DTB from recovery_restore.tar
    with tarfile.open('e:/rouf/galaxy-s8/recovery_restore.tar', 'r') as tf:
        rec_data = tf.extractfile('recovery.img').read()

    rec_hdr = rec_data[:2048]
    magic, k_sz, k_addr, r_sz, r_addr, s_sz, s_addr, t_addr, p_sz, dt_sz = struct.unpack('<8s9I', rec_hdr[:44])
    print(f'TWRP Kernel size: {k_sz}, DT size: {dt_sz}')

    k_pages = (k_sz + p_sz - 1) // p_sz
    r_pages = (r_sz + p_sz - 1) // p_sz
    s_pages = (s_sz + p_sz - 1) // p_sz

    k_off = p_sz
    r_off = k_off + k_pages * p_sz
    s_off = r_off + r_pages * p_sz
    dt_off = s_off + s_pages * p_sz

    kernel_data = rec_data[k_off : k_off + k_sz]
    dtb_data = rec_data[dt_off : dt_off + dt_sz]
    assert dtb_data[:4] == b'DTBH', f'Invalid DTB magic: {dtb_data[:4]}'

    # 4. Read official stock Samsung boot header (Finding 11: clones SRPPK29D005KU, dtb_addr 0x12000154)
    with tarfile.open('e:/rouf/galaxy-s8/boot_stock.tar', 'r') as tf:
        stock_boot = tf.extractfile('boot.img').read(2048)
    boot_hdr = bytearray(stock_boot)

    # Update kernel size, ramdisk size, and dtb size in the stock header
    struct.pack_into('<I', boot_hdr, 8, len(kernel_data))
    struct.pack_into('<I', boot_hdr, 16, len(comp_ramdisk))
    struct.pack_into('<I', boot_hdr, 40, len(dtb_data))

    print(f'Stock header cloned with Samsung vendor signatures:')
    print(f'  name: {boot_hdr[48:64]}')
    print(f'  dtb_addr: {hex(struct.unpack("<I", boot_hdr[44:48])[0])}')
    print(f'  second_addr: {hex(struct.unpack("<I", boot_hdr[28:32])[0])}')

    # Assemble boot image
    boot_img = (
        boot_hdr +
        pad(kernel_data, p_sz) +
        pad(comp_ramdisk, p_sz) +
        pad(dtb_data, p_sz)
    )

    print(f'Generated boot.img size: {len(boot_img)} bytes ({len(boot_img)/(1024*1024):.2f} MB).')
    max_boot_size = 41943040 # 40 MB
    assert len(boot_img) <= max_boot_size, f'Overflow! {len(boot_img)} > {max_boot_size}'

    # Save boot image
    out_boot_img = 'e:/rouf/galaxy-s8/scratch/boot_native_ubuntu.img'
    with open(out_boot_img, 'wb') as f:
        f.write(boot_img)

    # 5. Package into Odin USTAR tar
    out_tar = 'e:/rouf/galaxy-s8/boot_native_ubuntu.tar'
    with tarfile.open(out_tar, 'w', format=tarfile.USTAR_FORMAT) as tf:
        tf.add(out_boot_img, arcname='boot.img')

    print(f'Successfully built {out_tar}: {os.path.getsize(out_tar)} bytes!')

if __name__ == '__main__':
    main()
