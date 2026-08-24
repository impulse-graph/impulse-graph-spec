#!/usr/bin/env python3
import os
import struct

SPEC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_VECTORS_DIR = os.path.join(SPEC_DIR, "test-vectors")

def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def align_buffer(buf: bytearray, align: int):
    rem = len(buf) % align
    if rem != 0:
        buf.extend(b'\x00' * (align - rem))

def build_null_snapshot():
    dir_name = "tc37_nullable_padded_bitmap"
    folder = os.path.join(TEST_VECTORS_DIR, dir_name)
    os.makedirs(folder, exist_ok=True)

    hdr = bytearray(4096)
    struct.pack_into("<I", hdr, 0, 0x494D5053)
    struct.pack_into("<H", hdr, 4, 9)
    struct.pack_into("<I", hdr, 6, 4096)
    struct.pack_into("<H", hdr, 10, 1)
    struct.pack_into("<H", hdr, 12, 1) # 1 relation
    struct.pack_into("<Q", hdr, 14, 1700000000000)
    struct.pack_into("<Q", hdr, 22, 1)

    dir_table = bytearray()
    
    string_pool = b"\x00Bus\x00voltage\x00"
    str_bytes_len = len(string_pool)
    dir_table.extend(struct.pack("<I", str_bytes_len))
    dir_table.extend(string_pool)
    align_buffer(dir_table, 128)
    
    dom_entry = struct.pack("<HBBIQ", 0, 3, 0, 1, 1354)
    dir_table.extend(dom_entry)
    align_buffer(dir_table, 128)
    
    rel_entry = bytearray(128)
    struct.pack_into("<H", rel_entry, 0, 0) # rel_id
    struct.pack_into("<H", rel_entry, 2, 0) # src
    struct.pack_into("<H", rel_entry, 4, 0) # tgt
    struct.pack_into("<B", rel_entry, 6, 0) # enc
    struct.pack_into("<B", rel_entry, 7, 4) # node_w
    struct.pack_into("<B", rel_entry, 8, 4) # edge_w
    struct.pack_into("<I", rel_entry, 12, 1) # name
    struct.pack_into("<Q", rel_entry, 16, 1354) # node_c
    struct.pack_into("<Q", rel_entry, 24, 5000) # edge_c
    struct.pack_into("<H", rel_entry, 104, 1) # attr_count
    dir_table.extend(rel_entry)
    
    # 44 byte AttributeDescriptor
    attr = bytearray(44)
    struct.pack_into("<I", attr, 0, 5) # name_off
    struct.pack_into("<B", attr, 4, 0x86) # type_code
    struct.pack_into("<I", attr, 8, 1) # dimension
    struct.pack_into("<Q", attr, 12, 8192) # data_off
    # data_bytes = 5000 floats * 4 = 20000 bytes
    struct.pack_into("<Q", attr, 20, 20000) # data_bytes
    dir_table.extend(attr)
    align_buffer(dir_table, 128)
    
    struct.pack_into("<Q", hdr, 0x1E, 4096)
    struct.pack_into("<Q", hdr, 0x26, len(dir_table))

    checksum = crc16(hdr[0:0x3E])
    struct.pack_into("<H", hdr, 0x3E, checksum)

    data_section = bytearray()
    
    # edgeCount = 5000. 5000 bits = 625 bytes. Padded to 128 = 768 bytes.
    validity = bytearray(768)
    struct.pack_into("<Q", validity, 0, 0xFFFFFFFFFFFFFFFF)
    data_section.extend(validity)
    
    for i in range(5000):
        data_section.extend(struct.pack("<f", 1.0))
    align_buffer(data_section, 4096)

    full_snapshot = bytearray()
    full_snapshot.extend(hdr)
    full_snapshot.extend(dir_table)
    align_buffer(full_snapshot, 8192)
    full_snapshot.extend(data_section)

    with open(os.path.join(folder, "snapshot.imps"), "wb") as f:
        f.write(full_snapshot)
        
    print("Regenerated snapshot.imps!")

if __name__ == "__main__":
    build_null_snapshot()
