#!/usr/bin/env python3
"""
generate_string_fuzz_vectors.py — Generates Spec v0.9.0 String Table Fuzz & Corruption Test Vectors
"""

import os
import json
import struct
import hashlib

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

def build_v09_snapshot(string_pool_bytes: bytes, domain_name_offsets: list, expected_status: str, dir_name: str, desc: str):
    folder = os.path.join(TEST_VECTORS_DIR, dir_name)
    os.makedirs(folder, exist_ok=True)

    # 1. Header (4096 bytes)
    hdr = bytearray(4096)
    struct.pack_into("<I", hdr, 0, 0x494D5053)  # magic "IMPS"
    struct.pack_into("<H", hdr, 4, 9)           # version 0.9.0 (9)
    struct.pack_into("<I", hdr, 6, 4096)        # data_offset 4096
    struct.pack_into("<H", hdr, 10, len(domain_name_offsets)) # domain_count
    struct.pack_into("<H", hdr, 12, 0)          # relation_count
    struct.pack_into("<Q", hdr, 14, 1700000000000) # timestamp_ms
    struct.pack_into("<Q", hdr, 22, 1)          # required_features (4KB_PAGE_ALIGNED)

    checksum = crc16(hdr[0:0x3E])
    struct.pack_into("<H", hdr, 0x3E, checksum)

    # 2. Section 2 Directory Table
    dir_table = bytearray()
    
    # String Table Header & Pool
    str_bytes_len = len(string_pool_bytes)
    dir_table.extend(struct.pack("<I", str_bytes_len))
    dir_table.extend(string_pool_bytes)

    align_buffer(dir_table, 128)

    # Domain Catalog Array (Fixed 16 Bytes per domain)
    for i, name_off in enumerate(domain_name_offsets):
        dom_bytes = struct.pack("<HBBII", i, 3, 0, name_off, 0) # domain_id, key_type, reserved, name_offset, node_count (packed)
        # Note: struct.pack("<HBBII", ...) is 2+1+1+4+4 = 12 bytes, add 4 bytes padding for uint64 node_count
        # Real format: domain_id (2), key_type (1), reserved (1), name_offset (4), node_count (8) = 16 bytes
        dom_entry = struct.pack("<HBBIQ", i, 3, 0, name_off, 0)
        dir_table.extend(dom_entry)

    align_buffer(dir_table, 4096)

    # Combine Header + Directory Table
    full_snapshot = bytearray()
    full_snapshot.extend(hdr)
    full_snapshot.extend(dir_table)

    sha256_hex = hashlib.sha256(full_snapshot).hexdigest()

    # Save snapshot.imps
    with open(os.path.join(folder, "snapshot.imps"), "wb") as f:
        f.write(full_snapshot)

    # Save manifest.json
    manifest = {
        "name": dir_name,
        "description": desc,
        "spec_version": "0.9.0",
        "domain_count": len(domain_name_offsets),
        "relation_count": 0,
        "total_nodes": 0,
        "total_edges": 0,
        "sha256": sha256_hex,
        "expected_status": expected_status
    }
    with open(os.path.join(folder, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[+] Created Test Vector: {dir_name} ({expected_status})")

def main():
    # tc32: String Offset Out of Bounds
    build_v09_snapshot(
        string_pool_bytes=b"\x00User\x00",
        domain_name_offsets=[0xFFFFFFFF], # Out of bounds offset
        expected_status="REJECT_STRING_OFFSET_OUT_OF_BOUNDS",
        dir_name="tc32_string_offset_out_of_bounds",
        desc="Corrupt snapshot with domain name_offset 0xFFFFFFFF pointing past string pool boundary"
    )

    # tc33: String Missing Null Terminator
    build_v09_snapshot(
        string_pool_bytes=b"UnterminatedStringWithoutNull",
        domain_name_offsets=[0], # Offset 0 has no null terminator in string_pool_bytes
        expected_status="REJECT_STRING_UNTERMINATED",
        dir_name="tc33_string_missing_null_terminator",
        desc="Corrupt string pool with missing null-terminator byte at EOF"
    )

    # tc34: String Table Bytes Overflow
    # Craft raw snapshot where string_table_bytes = 0xFFFFFFFF (4GB)
    hdr = bytearray(4096)
    struct.pack_into("<I", hdr, 0, 0x494D5053)
    struct.pack_into("<H", hdr, 4, 9)
    struct.pack_into("<I", hdr, 6, 4096)
    struct.pack_into("<H", hdr, 10, 1)
    struct.pack_into("<H", hdr, 12, 0)
    checksum = crc16(hdr[0:0x3E])
    struct.pack_into("<H", hdr, 0x3E, checksum)

    dir_table = bytearray()
    dir_table.extend(struct.pack("<I", 0xFFFFFFFF)) # Massive 4GB string pool
    dir_table.extend(b"\x00User\x00")
    align_buffer(dir_table, 4096)

    full = hdr + dir_table
    folder = os.path.join(TEST_VECTORS_DIR, "tc34_string_table_bytes_overflow")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "snapshot.imps"), "wb") as f:
        f.write(full)
    with open(os.path.join(folder, "manifest.json"), "w") as f:
        json.dump({
            "name": "tc34_string_table_bytes_overflow",
            "description": "Corrupt string_table_bytes set to 0xFFFFFFFF (4GB) exceeding file size",
            "spec_version": "0.9.0",
            "domain_count": 1,
            "relation_count": 0,
            "total_nodes": 0,
            "total_edges": 0,
            "sha256": hashlib.sha256(full).hexdigest(),
            "expected_status": "REJECT_STRING_TABLE_OVERFLOW"
        }, f, indent=2)
    print("[+] Created Test Vector: tc34_string_table_bytes_overflow (REJECT_STRING_TABLE_OVERFLOW)")

    # tc35: Invalid UTF-8 String Sequence
    build_v09_snapshot(
        string_pool_bytes=b"\x00\xFF\xFE\xFD\xFC\x00",
        domain_name_offsets=[1], # Points to invalid UTF-8 bytes
        expected_status="REJECT_INVALID_UTF8_STRING",
        dir_name="tc35_invalid_utf8_string",
        desc="Corrupt string pool containing invalid UTF-8 byte sequence (0xFF 0xFE 0xFD 0xFC)"
    )

    # tc36: Empty String Pool No Null Byte
    hdr = bytearray(4096)
    struct.pack_into("<I", hdr, 0, 0x494D5053)
    struct.pack_into("<H", hdr, 4, 9)
    struct.pack_into("<I", hdr, 6, 4096)
    struct.pack_into("<H", hdr, 10, 1)
    struct.pack_into("<H", hdr, 12, 0)
    checksum = crc16(hdr[0:0x3E])
    struct.pack_into("<H", hdr, 0x3E, checksum)

    dir_table = bytearray()
    dir_table.extend(struct.pack("<I", 0)) # string_table_bytes = 0 (empty, no \0 byte)
    align_buffer(dir_table, 128)
    dir_table.extend(struct.pack("<HBBIQ", 0, 3, 0, 0, 0)) # name_offset 0
    align_buffer(dir_table, 4096)

    full = hdr + dir_table
    folder = os.path.join(TEST_VECTORS_DIR, "tc36_empty_string_pool_no_null_byte")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "snapshot.imps"), "wb") as f:
        f.write(full)
    with open(os.path.join(folder, "manifest.json"), "w") as f:
        json.dump({
            "name": "tc36_empty_string_pool_no_null_byte",
            "description": "Corrupt string pool with 0 bytes missing mandatory leading null byte at offset 0",
            "spec_version": "0.9.0",
            "domain_count": 1,
            "relation_count": 0,
            "total_nodes": 0,
            "total_edges": 0,
            "sha256": hashlib.sha256(full).hexdigest(),
            "expected_status": "REJECT_EMPTY_STRING_POOL"
        }, f, indent=2)
    print("[+] Created Test Vector: tc36_empty_string_pool_no_null_byte (REJECT_EMPTY_STRING_POOL)")

if __name__ == "__main__":
    main()
