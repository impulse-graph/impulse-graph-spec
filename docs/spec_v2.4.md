# Normative Binary Specification: Impulse Graph Format (v2.4.0)

* **Specification Version**: 2.4.0
* **Byte Order**: Little-Endian (`LE`, IEEE 754 & x86-64 / ARM64 Native)
* **Magic Constant**: `0x494D5053` (`"IMPS"`)
* **Baseline Header Offset**: 4096 Bytes (4KB OS Page Aligned)

---

## 1. Executive Summary & Layout

This document is automatically generated from the normative specification schema `v2.4.yaml`.

### Section 1: Snapshot Header Layout

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `magic` | `uint32` | Magic constant (0x494D5053 = 'IMPS') |
| `version` | `uint16` | Protocol major version number |
| `data_offset` | `uint32` | Byte offset where Section 2 payload begins |
| `domain_count` | `uint16` | Total number of domains in domain catalog |
| `relation_count` | `uint16` | Total number of relations in matrix |
| `kafka_offset` | `uint64` | Kafka Write-Ahead Log (WAL) offset |
| `timestamp_ms` | `uint64` | Unix epoch timestamp (milliseconds) |
| `sha256` | `uint8[32]` | Cryptographic SHA-256 checksum over data[data_offset..EOF] |
| `reserved` | `uint8[2]` | Reserved baseline alignment padding |
| `global_required_features` | `uint64` | Global Feature-in-Use Bitmask |

---

## 2. Enums & Feature Bitmaps

### Status Codes (`impulse_status_t`)

| Status Enum Name | Value | Description |
| :--- | :--- | :--- |
| `IMPULSE_OK` | `0` | Status code 0 |
| `IMPULSE_ERR_INVALID_MAGIC` | `1` | Status code 1 |
| `IMPULSE_ERR_UNSUPPORTED_VERSION` | `2` | Status code 2 |
| `IMPULSE_ERR_UNSUPPORTED_GLOBAL_FEATURE` | `3` | Status code 3 |
| `IMPULSE_ERR_UNSUPPORTED_SECTION_FEATURE` | `4` | Status code 4 |
| `IMPULSE_ERR_CORRUPT_CHECKSUM` | `5` | Status code 5 |
| `IMPULSE_ERR_IO_FAILURE` | `6` | Status code 6 |
| `IMPULSE_ERR_INVALID_ARGUMENT` | `7` | Status code 7 |
| `IMPULSE_ERR_SIGNATURE_MISMATCH` | `8` | Status code 8 |
| `IMPULSE_ERR_BUFFER_OVERFLOW` | `9` | Status code 9 |

### CSR Encoding Enums (`impulse_encoding_type_t`)

| Encoding Enum Name | Value | Description |
| :--- | :--- | :--- |
| `IMPULSE_ENC_RAW_UINT32` | `0` | Topology compression mode 0 |
| `IMPULSE_ENC_DELTA_VBYTE` | `1` | Topology compression mode 1 |
| `IMPULSE_ENC_RAW_UINT16` | `2` | Topology compression mode 2 |
| `IMPULSE_ENC_HYBRID_16_32` | `3` | Topology compression mode 3 |
| `IMPULSE_ENC_SIMDCOMP` | `4` | Topology compression mode 4 |
| `IMPULSE_ENC_SLICED_ELLPACK` | `5` | Topology compression mode 5 |
| `IMPULSE_ENC_TPU_BCOO` | `6` | Topology compression mode 6 |
| `IMPULSE_ENC_RAW_UINT64` | `7` | Topology compression mode 7 |
| `IMPULSE_ENC_ROARING_BITMAP` | `8` | Topology compression mode 8 |

---

## 3. Global & Section Feature Bitmaps

| Feature Flag | Bitmask Value | Category |
| :--- | :--- | :--- |
| `IMPULSE_GLOBAL_FEAT_4KB_PAGE_ALIGNED` | `0x0000000000000008` | Global Feature |
| `IMPULSE_GLOBAL_FEAT_ED25519_SIGNED` | `0x0000000000000010` | Global Feature |
| `IMPULSE_SECTION_FEAT_RAW_UINT32` | `0x0000000000000001` | Per-Section Feature |
| `IMPULSE_SECTION_FEAT_DELTA_VBYTE` | `0x0000000000000002` | Per-Section Feature |
| `IMPULSE_SECTION_FEAT_RAW_UINT16` | `0x0000000000000004` | Per-Section Feature |
| `IMPULSE_SECTION_FEAT_SIMDCOMP` | `0x0000000000000010` | Per-Section Feature |
| `IMPULSE_SECTION_FEAT_SLICED_ELLPACK` | `0x0000000000000020` | Per-Section Feature |