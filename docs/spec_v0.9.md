# Normative Binary Specification: Impulse Graph Format (0.9.0)

This document is automatically generated from the normative specification schema `v0.9.yaml`.

---

## 1. Executive Summary & Header Baseline

- **Magic Constant**: `0x494D5053` (`IMPS`)
- **Protocol Version**: `0.9.0` (`0x0009`)
- **Header Offset Baseline**: `4096` bytes (Page 0)

---

## 2. Enumeration Types

### `impulse_status_t`
*C-ABI Status and Error Return Codes (v0.9.0)*

| Name | Value |
| :--- | :--- |
| `IMPULSE_OK` | `0` |
| `IMPULSE_ERR_INVALID_MAGIC` | `1` |
| `IMPULSE_ERR_UNSUPPORTED_VERSION` | `2` |
| `IMPULSE_ERR_UNSUPPORTED_GLOBAL_FEATURE` | `3` |
| `IMPULSE_ERR_UNSUPPORTED_SECTION_FEATURE` | `4` |
| `IMPULSE_ERR_CORRUPT_CHECKSUM` | `5` |
| `IMPULSE_ERR_IO_FAILURE` | `6` |
| `IMPULSE_ERR_INVALID_ARGUMENT` | `7` |
| `IMPULSE_ERR_SIGNATURE_MISMATCH` | `8` |
| `IMPULSE_ERR_BUFFER_OVERFLOW` | `9` |

### `impulse_key_type_t`
*Domain Catalog Key Type Enums (v0.9.0)*

| Name | Value |
| :--- | :--- |
| `IMPULSE_KEY_TYPE_INT8` | `1` |
| `IMPULSE_KEY_TYPE_INT16` | `2` |
| `IMPULSE_KEY_TYPE_INT32` | `3` |
| `IMPULSE_KEY_TYPE_INT64` | `4` |
| `IMPULSE_KEY_TYPE_UINT8` | `5` |
| `IMPULSE_KEY_TYPE_UINT16` | `6` |
| `IMPULSE_KEY_TYPE_UINT32` | `7` |
| `IMPULSE_KEY_TYPE_UINT64` | `8` |
| `IMPULSE_KEY_TYPE_FLOAT32` | `9` |
| `IMPULSE_KEY_TYPE_FLOAT64` | `10` |
| `IMPULSE_KEY_TYPE_VAR_STRING` | `11` |
| `IMPULSE_KEY_TYPE_UUID128` | `12` |

### `impulse_encoding_type_t`
*Primary Topology CSR Encoding Enums (v0.9.0)*

| Name | Value |
| :--- | :--- |
| `IMPULSE_ENC_RAW_UINT32` | `0` |
| `IMPULSE_ENC_DELTA_VBYTE` | `1` |
| `IMPULSE_ENC_RAW_UINT16` | `2` |
| `IMPULSE_ENC_HYBRID_16_32` | `3` |
| `IMPULSE_ENC_SIMDCOMP` | `4` |
| `IMPULSE_ENC_SLICED_ELLPACK` | `5` |
| `IMPULSE_ENC_TPU_BCOO` | `6` |
| `IMPULSE_ENC_RAW_UINT64` | `7` |
| `IMPULSE_ENC_ROARING_BITMAP` | `8` |

---

## 3. Binary Layout Structs

### `impulse_snapshot_header_v0_9_t`
*Section 1 Fixed 4KB Baseline Snapshot Header (Spec v0.9.0)* (Expected Size: 4096 bytes)

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `magic` | `uint32` | Magic constant (0x494D5053 = 'IMPS') |
| `version` | `uint16` | Protocol version number (0x0009) |
| `data_offset` | `uint32` | Byte offset where Section 2 payload begins (4096) |
| `domain_count` | `uint16` | Total number of domains in catalog |
| `relation_count` | `uint16` | Total number of relations in matrix |
| `timestamp_ms` | `uint64` | Unix epoch timestamp (milliseconds) |
| `required_features` | `uint64` | Global feature flags bitmask |
| `footer_directory_offset` | `uint64` | Absolute file offset to Footer Directory Table |
| `footer_directory_bytes` | `uint64` | Byte size of Footer Directory Table |
| `snapshot_uuid` | `uint8[16]` | 128-bit Binary UUID |
| `header_checksum` | `uint16` | CRC-16-CCITT checksum over bytes 0x00..0x3D |
| `header_padding` | `uint8[4032]` | Reserved header expansion padding |

### `impulse_domain_catalog_entry_v0_9_t`
*Section 2 Domain Catalog Entry (16 Bytes)* (Expected Size: 16 bytes)

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `domain_id` | `uint16` | Zero-indexed domain identifier |
| `key_type` | `uint8` | Domain key primitive type enum |
| `reserved` | `uint8` | Alignment padding |
| `name_offset` | `uint32` | Offset into Shared String Table |
| `node_count` | `uint64` | Total node count in domain |

### `impulse_relation_directory_entry_v0_9_t`
*Section 2 Relation Directory Entry (128 Bytes)* (Expected Size: 128 bytes)

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `relation_id` | `uint16` | Zero-indexed relation identifier |
| `src_domain_id` | `uint16` | Source domain ID |
| `tgt_domain_id` | `uint16` | Target domain ID |
| `encoding_id` | `uint8` | Topology encoding type enum |
| `node_id_width` | `uint8` | Node index width (bits) |
| `edge_index_width` | `uint8` | Edge index width (bits) |
| `reserved1` | `uint8[3]` | Reserved alignment |
| `name_offset` | `uint32` | Offset into Shared String Table |
| `node_count` | `uint64` | Source node count |
| `edge_count` | `uint64` | Edge count |
| `section_features` | `uint64` | Section feature bitmask |
| `csr_row_off_offset` | `uint64` | CSR row offsets file offset |
| `csr_row_off_bytes` | `uint64` | CSR row offsets byte size |
| `csr_col_idx_offset` | `uint64` | CSR col indices file offset |
| `csr_col_idx_bytes` | `uint64` | CSR col indices byte size |
| `csc_row_off_offset` | `uint64` | CSC row offsets file offset |
| `csc_row_off_bytes` | `uint64` | CSC row offsets byte size |
| `csc_col_idx_offset` | `uint64` | CSC col indices file offset |
| `csc_col_idx_bytes` | `uint64` | CSC col indices byte size |
| `attr_count` | `uint16` | Number of edge attribute descriptors |
| `reserved2` | `uint8[22]` | Directory entry expansion padding |

### `impulse_attribute_descriptor_v0_9_t`
*Section 2 Edge Attribute Descriptor Entry (44 Bytes)* (Expected Size: 44 bytes)

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `name_offset` | `uint32` | Offset into Shared String Table |
| `type_code` | `uint8` | Attribute primitive type enum |
| `reserved1` | `uint8` | Alignment padding |
| `reserved2` | `uint16` | Alignment padding |
| `dimension` | `uint32` | Vector dimension (1 for scalar) |
| `data_offset` | `uint64` | Absolute file offset to attribute payload |
| `data_bytes` | `uint64` | Byte size of attribute payload |
| `offsets_offset` | `uint64` | Absolute file offset to var-string offsets array |
| `offsets_bytes` | `uint64` | Byte size of var-string offsets array |

### `impulse_footer_trailer_v0_9_t`
*16-Byte Footer Trailer at EOF* (Expected Size: 16 bytes)

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `footer_length` | `uint64` | Byte size of Footer Block |
| `spec_version` | `uint32` | Spec version (0x0009) |
| `footer_magic` | `uint32` | Footer magic (0x494D5053 = 'IMPS') |
