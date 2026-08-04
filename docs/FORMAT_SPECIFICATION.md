# Formal Specification: Impulse-Graph C-ABI Binary Snapshot Format

* **Specification Version**: 0.9.0 (SemVer, pre-1.0 stabilization release)
* **Document Status**: Standard Reference Specification
* **Byte Order**: Little-Endian (`LE`, IEEE 754 & x86-64 / ARM64 Native)
* **Memory Alignment**: 128-Byte SIMD / GPU Boundary (`(len + 127) & ~127`) & 4KB OS Page Boundary (`(offset + 4095) & ~4095`)
* **Integrity Validation**: SHA-256 Checksum (32 Bytes, calculated over payload) & Ed25519 Cryptographic Signature Block

---

## 1. Specification Overview & Modular Design Principles

This document defines the formal binary protocol specification for the **Impulse-Graph C-ABI Binary Snapshot Format (Version 0.9.0)**.

The format is organized into **4KB OS page-aligned physical blocks**, structured to support **single-pass S3/cloud streaming uploads**, **$O(1)$ zero-copy `mmap` range loading**, and **AVX-512 / GPU SIMD vectorization**.

### Physical File Layout Overview

```text
┌───────────────────────────────────────────────────────────────────────────────────┐
│ SECTION 1: Snapshot Header (4KB Page 0, Offset 0x0000)                             │
│   ├── Magic ("IMPS"), Version (0x0009), DataOffset (4096)                          │
│   └── GlobalRequiredFeatures, SnapshotUUID, HeaderChecksum                        │
├───────────────────────────────────────────────────────────────────────────────────┤
│ SECTION 2: Catalog & Relation Directory Table (4KB Page 1, Offset 0x1000)         │
│   ├── Domain Catalog (Node Types)                                                      │
│   └── Sorted Relation Directory Table (Sorted by SrcDomainID, TgtDomainID)          │
├───────────────────────────────────────────────────────────────────────────────────┤
│ RELATION BLOCK 1 [MANDATORY, 4KB Aligned]                                         │
│   ├── csrRowOffsets Array (128B Aligned, uint32/uint64)                           │
│   ├── csrColumnIndices Stream (128B Aligned, RAW 0x00 Encoding)                   │
│   ├── cscRowOffsets / cscColumnIndices Arrays (Optional Transpose, 128B Aligned)  │
│   ├── Edge Fixed-width SoA Attribute Arrays (128B Aligned: weights, timestamps...)│
│   └── Edge Var-length Attribute Offsets & Data Blobs (128B Aligned)               │
├───────────────────────────────────────────────────────────────────────────────────┤
│ RELATION BLOCK 2 [MANDATORY, 4KB Aligned]                                         │
│   └── (Contiguous 128B aligned topology & attribute array sequence)               │
├───────────────────────────────────────────────────────────────────────────────────┤
│ NODE DOMAIN BLOCK 1 [OPTIONAL, 4KB Aligned]                                       │
│   ├── Node Fixed-width SoA Attribute Arrays (128B Aligned)                        │
│   └── Node Var-length Attribute Offsets & Data Blobs (128B Aligned)               │
├───────────────────────────────────────────────────────────────────────────────────┤
│ FOOTER BLOCK [EOF, 4KB Aligned]                                                   │
│   ├── Unified UTF-8 Key/Value Custom Metadata Stream (Unlimited multi-map)         │
│   ├── Final Catalog & Relation Directory Table Copy (S3 Cloud Range Reader Copy)  │
│   ├── SHA-256 Payload Checksum & Ed25519 Cryptographic Signature Block            │
│   └── 16-Byte Footer Trailer (footer_length [u64] + version [u32] + "IMPS" [u32]) │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Section 1: Snapshot Header Layout (Fixed 4KB Page 0 Baseline)

The snapshot header occupies byte offset `0x00000000` (Page 0). It contains a **64-byte active baseline** aligned to a single CPU cache line, inside a fixed 4096-byte page (`DataOffset = 4096`).

### Header Byte Offset Table

| Byte Offset | Field Name | C-ABI Type | Size | Default / Constant | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x0000` – `0x0003` | `Magic` | `uint32_t` | 4 Bytes | `0x494D5053` (`"IMPS"`) | Magic constant identifying Impulse-Graph binary snapshot file. |
| `0x0004` – `0x0005` | `Version` | `uint16_t` | 2 Bytes | `0x0009` (`9`) | Protocol specification version number (v0.9.0 packed `0x0009`). |
| `0x0006` – `0x0009` | `DataOffset` | `uint32_t` | 4 Bytes | `4096` (`0x00001000`) | Fixed constant (`4096`). Section 2 always starts at byte 4096 (Page 1). |
| `0x000A` – `0x000B` | `DomainCount` | `uint16_t` | 2 Bytes | Variable | Total number of node domains in the catalog (up to 65,536). |
| `0x000C` – `0x000D` | `RelationCount` | `uint16_t` | 2 Bytes | Variable | Total number of relations in the matrix (up to 65,536). |
| `0x000E` – `0x0015` | `TimestampMs` | `uint64_t` | 8 Bytes | Epoch Milliseconds | Unix epoch timestamp (milliseconds) when snapshot was created. |
| `0x0016` – `0x001D` | `GlobalRequiredFeatures` | `uint64_t` | 8 Bytes | Bitmask | **Global Feature-in-Use Bitmask** (64-bit feature flags). |
| `0x001E` – `0x0025` | `FooterDirectoryOffset` | `uint64_t` | 8 Bytes | Absolute File Offset | File offset to Footer Directory Table (`0` if Page 1 directory is used). |
| `0x0026` – `0x002D` | `FooterDirectoryBytes` | `uint64_t` | 8 Bytes | Byte Size | Byte size of Footer Directory Table (`0` if omitted). |
| `0x002E` – `0x003D` | `SnapshotUUID` | `uint8_t[16]` | 16 Bytes | Random Binary UUID | Unique 128-bit Binary UUID for this snapshot build artifact. |
| `0x003E` – `0x003F` | `HeaderChecksum` | `uint16_t` | 2 Bytes | CRC-16-CCITT | Fast CRC-16 checksum calculated over bytes `0x0000..0x003D`. |
| `0x0040` – `0x0FFF` | `ReservedPadding` | `uint8_t[4032]` | 4032 Bytes | `0x00 ...` | **Reserved Header Expansion Padding** (Aligns Header to 4KB boundary). |

---

## 3. Section 2: Catalog & Directory Directory Table

Begins at byte offset `DataOffset` (byte 4096). Contains node domain definitions and the **Relation Directory Table**.

### 3.1 Domain Catalog (Node Types)
Contains `DomainCount` sequential domain records:
* `DomainID` (`uint16_t`, 2B): Zero-indexed domain identifier (`0`..`DomainCount - 1`).
* `NameLen` (`uint16_t`, 2B): Length of domain name string.
* `Name` (`byte[NameLen]`): UTF-8 string (e.g. `"User"`, `"Group"`).

### 3.2 Relation Directory Table (Matrix Descriptors)
Contains `RelationCount` relation descriptors, **sorted primary by `SrcDomainID` and secondary by `TgtDomainID`** to enable $O(\log R)$ binary search lookups:

| Field Name | Type | Size | Description |
| :--- | :--- | :--- | :--- |
| `RelationID` | `uint16_t` | 2B | Zero-indexed relation identifier (`0`..`RelationCount - 1`). |
| `SrcDomainID` | `uint16_t` | 2B | Domain ID of source nodes. |
| `TgtDomainID` | `uint16_t` | 2B | Domain ID of target nodes. |
| `EncodingID` | `uint8_t` | 1B | Topology encoding enum (`0x00` = `ENCODING_RAW` uncompressed, `0x01` = `ZSTD`, `0x80`..`0xFF` = Registered plugins). |
| `NodeIDWidth` | `uint8_t` | 1B | Byte width of target node IDs (`0x02` = `uint16_t`, `0x04` = `uint32_t`, `0x08` = `uint64_t`). |
| `EdgeIndexWidth` | `uint8_t` | 1B | Byte width of CSR row offsets (`0x04` = `uint32_t`, `0x08` = `uint64_t`). |
| `NodeCount` | `uint64_t` | 8B | Number of source nodes ($N$) in relation matrix (up to $1.84 \times 10^{19}$). |
| `EdgeCount` | `uint64_t` | 8B | Total number of directed edges ($E$) in relation matrix. |
| `SectionFeatures` | `uint64_t` | 8B | Per-relation feature bitmask (e.g., bit 0 = CSC present, bit 1 = weighted edges). |
| `CsrRowOffOffset` | `uint64_t` | 8B | Absolute file offset to `csrRowOffsets` array (128B aligned). |
| `CsrRowOffBytes` | `uint64_t` | 8B | Byte size of `csrRowOffsets` array ($= (N + 1) \times \text{EdgeIndexWidth}$). |
| `CsrColIdxOffset` | `uint64_t` | 8B | Absolute file offset to `csrColumnIndices` array (128B aligned). |
| `CsrColIdxBytes` | `uint64_t` | 8B | Byte size of `csrColumnIndices` array ($= E \times \text{NodeIDWidth}$). |
| `CscRowOffOffset` | `uint64_t` | 8B | Absolute file offset to optional `cscRowOffsets` array (`0` if omitted). |
| `CscRowOffBytes` | `uint64_t` | 8B | Byte size of `cscRowOffsets` array (`0` if omitted). |
| `CscColIdxOffset` | `uint64_t` | 8B | Absolute file offset to optional `cscColumnIndices` array (`0` if omitted). |
| `CscColIdxBytes` | `uint64_t` | 8B | Byte size of `cscColumnIndices` array (`0` if omitted). |

---

## 4. Topology & Attribute Specification

### 4.1 Topology Mechanics (Always CSR, Optional CSC)
* **Standard CSR**: Topology is **always standard CSR** (`csrRowOffsets` + `csrColumnIndices`).
* **Direct Array Indexing**: Targets are indexed directly via uncompressed arrays (`ENCODING_RAW = 0x00`). `columnIndices` for node $i$'s $k$-th neighbor is read at `csrColumnIndices[csrRowOffsets[i] + k]`.
* **Optional CSC Transpose**: An incoming transpose index (`cscRowOffsets` + `cscColumnIndices`) may be included for bidirectional traversals.
* **Explicit Reverse Relations**: Reverse relations (e.g. `MEMBER_OF_REVERSE`) are represented explicitly as first-class catalog relations.

### 4.2 Attribute Storage Architecture (Structure of Arrays)

Attributes are partitioned into fixed-length primitives and variable-length payloads stored in **Structure of Arrays (SoA)** layout.

#### Bitwise Nullability Flag & Base Type Mask
Attribute data types are encoded in an 8-bit field (`uint8_t type_code`):

```c
#define IMPULSE_TYPE_MASK     0x7F  // Bits 0..6: Base Primitive Type (Up to 128 base types)
#define IMPULSE_NULLABLE_FLAG 0x80  // Bit 7: Nullability Flag (1 = Nullable with Validity Bitmap, 0 = Non-Null)

// Bitwise evaluation in C-ABI parsers
uint8_t base_type   = descriptor->type_code & IMPULSE_TYPE_MASK;
bool    is_nullable = (descriptor->type_code & IMPULSE_NULLABLE_FLAG) != 0;
```

* **Non-Nullable (`is_nullable == false`, Bit 7 = 0)**: Zero validity bitmap overhead. 100% of memory is allocated to contiguous data values.
* **Nullable (`is_nullable == true`, Bit 7 = 1)**: A 128-byte aligned **Validity Bitmap** (`uint64_t validity_bitmap[(N + 63) / 64]`) is placed immediately before the data array ($1\text{ bit per entity}$, Bit $i=1 \rightarrow$ valid, Bit $i=0 \rightarrow$ null).

#### Base Data Type Table (`0x00` .. `0x7F` Base Codes):
| Base Code (`0x7F`) | Base Type Name | Non-Null Code | Nullable Code (`0x80`) | Dimension (`dim`) | Memory Layout |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x01` | `INT8` | `0x01` | `0x81` | $\ge 1$ | $1 \times \text{dim}$ Bytes (`int8_t` / `uint8_t`) |
| `0x02` | `INT16` | `0x02` | `0x82` | $\ge 1$ | $2 \times \text{dim}$ Bytes (`int16_t` / `uint16_t`) |
| `0x03` | `INT32` | `0x03` | `0x83` | $\ge 1$ | $4 \times \text{dim}$ Bytes (`int32_t` / `uint32_t`) |
| `0x04` | `INT64` | `0x04` | `0x84` | $\ge 1$ | $8 \times \text{dim}$ Bytes (`int64_t` / `uint64_t`) |
| `0x05` | `FLOAT16` | `0x05` | `0x85` | $\ge 1$ | $2 \times \text{dim}$ Bytes (bfloat16 / fp16) |
| `0x06` | `FLOAT32` | `0x06` | `0x86` | $\ge 1$ | $4 \times \text{dim}$ Bytes (IEEE 754 float, **edge weights**) |
| `0x07` | `FLOAT64` | `0x07` | `0x87` | $\ge 1$ | $8 \times \text{dim}$ Bytes (IEEE 754 double, high precision) |
| `0x08` | `TIMESTAMP_MS` | `0x08` | `0x88` | $\ge 1$ | $8 \times \text{dim}$ Bytes (uint64 epoch ms) |
| `0x09` | `TIMESTAMP_NS` | `0x09` | `0x89` | $\ge 1$ | $8 \times \text{dim}$ Bytes (uint64 epoch ns) |
| `0x0A` | `FIXED_BYTES` | `0x0A` | `0x8A` | $\ge 1$ | $\text{dim}$ Bytes (dim=16 for UUID, dim=32 for SHA-256) |
| `0x0B` | `VAR_STRING` | `0x0B` | `0x8B` | Ignored (`0`) | Variable UTF-8 (`uint32_t offsets[]` + Data Blob) |
| `0x0C` | `VAR_BYTES` | `0x0C` | `0x8C` | Ignored (`0`) | Variable Binary (`uint32_t offsets[]` + Data Blob) |

---

## 5. Footer Block & S3 Streaming Upload Specification

### 5.1 Single-Pass S3 Ingestion
For unseekable S3 multi-part uploads, signatures, SHA-256 digests, and catalog directories are serialized into the **Footer Block at EOF**:

1. Part 1: Upload Page 0 Header (`GLOBAL_FEAT_FOOTER_DIRECTORY = 1`).
2. Parts 2..N: Stream Relation and Node Blocks, tracking running counts in RAM.
3. Final Part: Upload Footer Block containing:
   - Unified UTF-8 Key/Value Metadata Stream.
   - Final Catalog & Relation Directory Table Copy.
   - SHA-256 Payload Digest & Ed25519 Signature Block.
   - **16-Byte Footer Trailer** (at `EOF - 16`).

### 5.2 16-Byte Footer Trailer Specification
Every compliant v0.9.0 snapshot MUST terminate with exactly 16 bytes at EOF:

```c
typedef struct impulse_footer_trailer {
    uint64_t footer_length;    // 8 Bytes: Byte size of Footer Block
    uint32_t spec_version;     // 4 Bytes: Protocol version (0x0009)
    uint32_t footer_magic;     // 4 Bytes: "IMPS" (0x494D5053)
} impulse_footer_trailer_t;     // Exactly 16 Bytes at EOF
```

---

## 6. Hardware Alignment & C-ABI Macros

* **128-Byte Array Alignment**: All sub-arrays (`csrRowOffsets`, `csrColumnIndices`, `cscRowOffsets`, `cscColumnIndices`, SoA arrays) MUST be aligned to 128-byte boundaries.
* **4KB Page Block Alignment**: Every Relation Block, Node Domain Block, and Footer Block MUST begin on a 4096-byte OS page boundary.

```c
// 128-Byte Alignment for AVX-512 SIMD & GPU Warp Coalescing
#define IMPULSE_ALIGN_128(offset) (((offset) + 127ULL) & ~127ULL)

// 4KB Page Alignment for OS Virtual Memory Area (VMA) Isolation
#define IMPULSE_ALIGN_4K(offset)  (((offset) + 4095ULL) & ~4095ULL)
```
