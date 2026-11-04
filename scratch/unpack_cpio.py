import os
import shutil
import struct

def unpack_cpio(cpio_file, target_dir):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    with open(cpio_file, 'rb') as f:
        data = f.read()

    pos = 0
    total = len(data)
    count = 0
    while pos + 110 <= total:
        magic = data[pos:pos+6]
        if magic != b'070701':
            break
        
        mode = int(data[pos+14:pos+22], 16)
        filesize = int(data[pos+54:pos+62], 16)
        namesize = int(data[pos+94:pos+102], 16)

        pos += 110
        filename = data[pos:pos+namesize-1].decode('utf-8', errors='ignore')
        pos += namesize
        if pos % 4 != 0:
            pos += 4 - (pos % 4)

        if filename == 'TRAILER!!!':
            break

        filedata = data[pos:pos+filesize]
        pos += filesize
        if pos % 4 != 0:
            pos += 4 - (pos % 4)

        full_path = os.path.join(target_dir, filename.replace('/', os.sep))
        file_type = mode & 0o170000

        if file_type == 0o040000: # Directory
            os.makedirs(full_path, exist_ok=True)
        elif file_type == 0o120000: # Symlink
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            link_target = filedata.decode('utf-8', errors='ignore')
            # On windows we can write a text pointer or save symlink dict
            with open(full_path + '.symlink', 'w') as lf:
                lf.write(link_target)
        else: # Regular file
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as out_f:
                out_f.write(filedata)
        count += 1
    print(f'Extracted {count} entries into {target_dir}.')

if __name__ == '__main__':
    unpack_cpio('e:/rouf/galaxy-s8/scratch/switchroot_old.cpio', 'e:/rouf/galaxy-s8/scratch/ramdisk_work')

