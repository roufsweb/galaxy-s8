import os
import struct
import gzip
import tarfile

def main():
    # 1. Read switchroot cpio
    cpio_path = 'e:/rouf/galaxy-s8/scratch/switchroot_old.cpio'
    with open(cpio_path, 'rb') as f:
        cpio_data = f.read()

    print(f'Read switchroot cpio: {len(cpio_data)} bytes.')

    # 2. Compress with standard GZIP (mtime=0)
    comp_ramdisk = gzip.compress(cpio_data, compresslevel=9, mtime=0)
    print(f'Gzip switchroot ramdisk size: {len(comp_ramdisk)} bytes.')

    # 3. Read official stock Samsung boot
    stock_tar = 'e:/rouf/galaxy-s8/boot_stock.tar'
    with tarfile.open(stock_tar, 'r') as tf:
        stock_boot = tf.extractfile('boot.img').read()

    # Exact factory header
    stock_hdr = bytearray(stock_boot[:2048])
    k_len, _, _, _, _, _, _, page_size = struct.unpack('<8I', stock_hdr[8:40])
    dtb_len = struct.unpack('<I', stock_hdr[40:44])[0]
    kernel_data = stock_boot[page_size : page_size + k_len]
    r_len_old = struct.unpack('<I', stock_hdr[16:20])[0]
    r_off = page_size + ((k_len + page_size - 1) // page_size) * page_size
    dtb_off = r_off + ((r_len_old + page_size - 1) // page_size) * page_size
    dtb_data = stock_boot[dtb_off : dtb_off + dtb_len]

    # Update ramdisk size in stock header
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

    print(f'Generated boot.img: {len(boot_img)} bytes ({len(boot_img)/(1024*1024):.2f} MB).')
    assert len(boot_img) <= 41943040, f'Overflow! {len(boot_img)} > 41943040'

    # Save boot image
    temp_boot = 'e:/rouf/galaxy-s8/scratch/boot_native_ubuntu.img'
    with open(temp_boot, 'wb') as f:
        f.write(boot_img)

    # Package into Odin USTAR tar
    out_tar = 'e:/rouf/galaxy-s8/boot_native_ubuntu.tar'
    with tarfile.open(out_tar, 'w', format=tarfile.USTAR_FORMAT) as tf:
        tf.add(temp_boot, arcname='boot.img')

    print(f'Successfully built {out_tar}: {os.path.getsize(out_tar)} bytes!')

if __name__ == '__main__':
    main()

