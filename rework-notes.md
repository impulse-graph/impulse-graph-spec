# Architectural Rework Notes: Impulse Graph C-ABI Binary Snapshot Specification (v2.6 Proposal)

* **Document Status**: Proposal / Architectural Rework Reference
* **Target Spec Version**: 2.6.0
* **Date**: 2026-08-03
* **Primary Scope**: Single-Pass Ingestion, Physical Section/Block Layout, SoA Attribute Storage, Alignment Standards, and Cryptographic Signing Location.

---

## 1. Executive Summary & Design Goals

Following technical discussions regarding snapshot layout optimizations (drawing inspiration from Parquet while preserving Impulse Graph's core sub-microsecond zero-copy `mmap` traversal performance), this document outlines proposed structural refinements for **v2.6 of the Impulse Graph C-ABI Binary Snapshot Specification**.

### Primary Objectives:
1. **Single-Pass Streaming Ingestion**: Enable streaming snapshot writers (e.g. S3 multi-part uploads, pipeline stdout streams) to calculate cryptographic signatures and checksums without back-patching Header Page 0.
2. **Unified Key-Value Metadata**: Replace the dual 2KB header metadata cap and Section 7 catalog with a single, unlimited, length-prefixed UTF-8 Key/Value stream supporting repeated keys.
3. **Per-Relation Block Contiguity**: Group each relation's CSR/CSC topology and edge attributes into contiguous, 4KB page-aligned blocks to enable independent, single-VMA `mmap` calls per relation.
4. **Structure of Arrays (SoA) & Parquet-style Variable Blobs**: Standardize node and edge attribute storage on SIMD-friendly SoA for fixed-length primitives, and Arrow/Parquet-style Offset + Data Blobs for variable-length payload attributes.
5. **Strict Hardware Alignment**: Enforce 128-byte alignment across all internal matrix and attribute sub-arrays for AVX-512 vector units and GPU warp coalescing (NVIDIA GPUDirect Storage `cuFile`), anchored by 4KB OS page boundaries for block headers.

---

## 2. Structural & Layout Changes

### 2.1 Cryptographic Signing Relocation to Footer (EOF)
* **Old (v2.5)**: `SignatureBlock` (1024 bytes) and SHA-256 digest embedded in Section 1 (Header Page 0). Required writer to seek back (`pwrite`) to Header Page 0 after writing all payload data to patch signatures.
* **New (v2.6 Proposal)**: `SignatureBlock` and `SHA256` payload digest are relocated to the **Footer Block at EOF**.
  - **Writer Advantage**: Enables true single-pass streaming ingestion. Payload digest and Ed25519 signatures are computed incrementally and written cleanly at EOF.
  - **Reader Verification**: Readers verify integrity by seeking to `EOF - FooterBlockBytes`.

### 2.2 Unified UTF-8 Key-Value Metadata Stream
* **Old (v2.5)**: Metadata split between `HeaderCustomMetadata` (2KB hard cap inside Page 0) and Section 7 (`Custom Metadata Catalog`).
* **New (v2.6 Proposal)**: Single, unified **Metadata Stream** residing in the Footer Block (or optional 4KB aligned Metadata Block).
  - Format: Sequence of length-prefixed UTF-8 Key/Value records:
    ```text
    [KeyLen: uint16_t][KeyBytes: UTF-8][ValueLen: uint32_t][ValueBytes: UTF-8]
    ```
  - **Unlimited Capacity & Multi-Map Semantics**: Keys and values have unlimited byte capacity and allow duplicate keys (e.g., repeated `tag=production`, `tag=us-east-1` entries) for rich lineage tracing.

### 2.3 Complete Removal of LSN / Write-Ahead Log Data
* **Deprecations**: `KafkaOffset` (8B) in Section 1 Header, `DeltaLogOffset`/`DeltaLogBytes` in Section 2 Relation Directory, and Section 6 (`Delta Log Section`) are **completely removed**.
* **Design Principle**: Snapshot files are strictly immutable, deterministic binary artifacts. Live Write-Ahead Log (WAL) ingestion and real-time edge mutations belong exclusively to external server frameworks (`impulse-platform` WAL / RocksDB overlay), keeping the snapshot core engine ultra-lean and zero-dependency.

### 2.4 Simplified Topology Encodings & Identifier Type Widths
* **Elimination of Mandatory Adaptive Encoding Complexity**: Complex adaptive matrix compression modes (`Delta-VByte`, `SIMDComp`, `Sliced ELLPACK`, `TPU Blocked COO`, `Roaring Bitmaps`, `Hybrid 16/32`) are **retired from the core engine baseline**. This eliminates decoder branching, SIMD dispatch overhead, and complex parser fallbacks.
* **Standardized Topology**: Topology is **always standard CSR** (`csrRowOffsets` + `csrColumnIndices`) with direct primitive array indexing (`uint16_t`, `uint32_t`, or `uint64_t`).
* **Optional CSC Index**: An incoming transpose index (`cscRowOffsets` + `cscColumnIndices`) may be optionally included within a Relation Block for high-speed bidirectional graph traversals.
* **Explicit Reverse Relations**: Reverse relations (e.g. `MEMBER_OF_REVERSE`) are explicitly represented as first-class entries in the relation catalog (`relation_id`) rather than implicitly computed or dynamically decoded.
* **Identifier Type Widths**:
  - `relation_id`: Fixed `uint16_t` (`INT16`, up to 65,536 distinct relation types per snapshot).
  - `node_type` (`domain_id`): Fixed `uint16_t` (`INT16`, up to 65,536 distinct node domains per snapshot).
  - **Node ID Width**: Selected per node domain / relation based on cardinality:
    - `uint16_t` ($N \le 65,535$ nodes)
    - `uint32_t` ($N \le 4,294,967,295$ nodes)
    - `uint64_t` ($N > 4.29\text{B}$ trillion-scale nodes)
  - **Edge Index / Offset Width**: `uint32_t` or `uint64_t` for `csrRowOffsets` / `csrColumnIndices` per relation based on edge count ($E$) and node count ($N$).

### 2.5 Parquet/Arrow-Style Registered & Custom Encoding Space
To support specialized domain extensions (e.g. GPU accelerators, SIMD PFOR codecs, domain-specific graph compression) without polluting the core kernel with mandatory dependencies, Section 2 defines an **8-bit `EncodingID`** field per relation:

* **Core Encodings (`0x00` .. `0x7F`)**:
  - `0x00` (`ENCODING_RAW`): **Mandatory Core Default**. Direct uncompressed primitive array (`uint16_t[]`, `uint32_t[]`, `uint64_t[]`). Guarantees 100% zero-copy `mmap` pointer casting (`const uint32_t* cols = (const uint32_t*)(mmap_ptr + offset)`).
  - `0x01` (`ENCODING_ZSTD_FRAME`): Entire section RFC 8878 Zstd frame compressed.
  - `0x02` .. `0x7F`: Reserved for future core spec standard encodings.
* **Registered Vendor / Custom Encodings (`0x80` .. `0xFF`)**:
  - Dedicated ID space for custom vendor plugins (e.g. `0x85` for custom GPU Sliced ELLPACK or domain-specific vector codecs).
  - **Plugin Registration**: Readers match custom `EncodingID` against registered plugin codecs (`impulse_register_codec(0x85, custom_decoder_fn)`). Unregistered custom codecs fail fast with `IMPULSE_ERR_UNSUPPORTED_ENCODING`.
  - **Metadata Mapping**: Custom encoding URIs are optionally declared in the UTF-8 Metadata Stream (e.g. `relation.1.encoding = "com.nvidia.cugraph.ellpack"`).

### 2.6 Dual-Directory & S3 Streaming Upload Architecture
To support **zero-disk-staging S3 Multi-part Uploads** (where S3 parts are write-once and in-place `pwrite` back-patching is impossible), the spec enforces a **Dual-Directory Pattern**:

* **S3 Direct Streaming Ingestion Workflow**:
  1. Writer uploads Part 1 (Page 0 Header, setting flag `GLOBAL_FEAT_FOOTER_DIRECTORY = 1`).
  2. Writer streams Relation Blocks direct to S3 parts, maintaining running tallies (`NodeCount`, `EdgeCount`, offsets) in RAM memory.
  3. Writer uploads Final S3 Part containing the **Footer Block** (with finalized Catalog Directory Table, Metadata Stream, Crypto Signature, and 16-Byte Trailer).
* **Dual Discovery for Readers**:
  - **Local `mmap` Reader**: Reads Page 1 Directory Table directly or jumps to `FooterDirectoryOffset`. (For local files, builder back-patches Page 1 in $< 1\mu\text{s}$).
  - **S3 / Cloud Reader**: Issues **1 HTTP Range GET** for the last 16 bytes (`EOF - 16`), fetches `footer_length`, issues **1 HTTP Range GET** for the Footer Block, and acquires the complete Catalog & Relation Directory Table (`NodeCount`, `EdgeCount`, offsets) with zero full-file downloads!

### 2.7 Proposed Section 1: Header Page Layout (4KB Page 0 Baseline)
By relocating crypto signatures, LSN data, and custom metadata to the Footer Block, the **v2.6 Snapshot Header** becomes an ultra-compact, 64-byte active baseline within a fixed 4KB page:

| Byte Offset | Field Name | C-ABI Type | Size | Default / Constant | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x0000` – `0x0003` | `Magic` | `uint32_t` | 4 Bytes | `0x494D5053` (`"IMPS"`) | Magic constant identifying Impulse-Graph binary snapshot file. |
| `0x0004` – `0x0005` | `Version` | `uint16_t` | 2 Bytes | `0x0206` (`518`) | Protocol specification version (Packed `0x0206` for v2.6.0). |
| `0x0006` – `0x0009` | `DataOffset` | `uint32_t` | 4 Bytes | `4096` (`0x00001000`) | Fixed constant (`4096`). Section 2 always starts immediately at byte 4096 (Page 1). |
| `0x000A` – `0x000B` | `DomainCount` | `uint16_t` | 2 Bytes | Variable | Total number of node domains in the catalog (up to 65,536). |
| `0x000C` – `0x000D` | `RelationCount` | `uint16_t` | 2 Bytes | Variable | Total number of relations in the matrix (up to 65,536). |
| `0x000E` – `0x0015` | `TimestampMs` | `uint64_t` | 8 Bytes | Epoch Milliseconds | Unix epoch timestamp (milliseconds) when snapshot was generated. |
| `0x0016` – `0x001D` | `GlobalRequiredFeatures` | `uint64_t` | 8 Bytes | Bitmask | **Global Feature-in-Use Bitmask** (64-bit feature flags). |
| `0x001E` – `0x0025` | `FooterDirectoryOffset` | `uint64_t` | 8 Bytes | Absolute File Offset | File offset to Footer Directory Table (`0` if Page 1 directory is used). |
| `0x0026` – `0x002D` | `FooterDirectoryBytes` | `uint64_t` | 8 Bytes | Byte Size | Byte size of Footer Directory Table (`0` if omitted). |
| `0x002E` – `0x003D` | `SnapshotUUID` | `uint8_t[16]` | 16 Bytes | Random Binary UUID | Unique 128-bit Binary UUID for this snapshot build artifact. |
| `0x003E` – `0x003F` | `HeaderChecksum` | `uint16_t` | 2 Bytes | CRC-16-CCITT | Fast CRC-16 checksum calculated over bytes `0x0000..0x003D`. |
| `0x0040` – `0x0FFF` | `ReservedPadding` | `uint8_t[4032]` | 4032 Bytes | `0x00 ...` | **Reserved Header Expansion Padding** (Aligns Header to 4KB boundary). |

---

## 3. Physical Section & Block Design

To maximize OS page cache locality and allow microservices to memory-map specific relations independently, the file is organized into **4KB page-aligned physical blocks**:

```text
┌───────────────────────────────────────────────────────────────────────────────────┐
│ SECTION 1: Snapshot Header (4KB Page 0, Offset 0x0000)                             │
│   ├── Magic ("IMPS"), Version (0x0206), DataOffset (4096)                          │
│   └── GlobalRequiredFeatures Bitmask                                              │
├───────────────────────────────────────────────────────────────────────────────────┤
│ SECTION 2: Catalog & Directory Directory Table (4KB Page 1, Offset 0x1000)        │
│   ├── Domain Catalog (Node Types)                                                      │
│   └── Relation Directory Table (Absolute File Offsets & Section Bitmasks)           │
├───────────────────────────────────────────────────────────────────────────────────┤
│ RELATION BLOCK 1 [e.g. User-MEMBER_OF-Group] (MANDATORY, 4KB Aligned)             │
│   ├── csrRowOffsets Array (128B Aligned)                                          │
│   ├── csrColumnIndices Stream (128B Aligned)                                      │
│   ├── cscRowOffsets Array (OPTIONAL Transpose, 128B Aligned)                      │
│   ├── cscColumnIndices Array (OPTIONAL Transpose, 128B Aligned)                   │
│   ├── Edge Fixed-width SoA Attribute Arrays (128B Aligned)                        │
│   └── Edge Var-length Attribute Offsets & Data Blobs (128B Aligned)               │
├───────────────────────────────────────────────────────────────────────────────────┤
│ RELATION BLOCK 2 [e.g. User-FOLLOWS-User] (MANDATORY, 4KB Aligned)                │
│   └── (Same internal 128B aligned array sequence)                                 │
├───────────────────────────────────────────────────────────────────────────────────┤
│ NODE DOMAIN BLOCK 1 [e.g. User Nodes] (OPTIONAL, 4KB Aligned)                     │
│   ├── Node Fixed-width SoA Attribute Arrays (128B Aligned)                        │
│   └── Node Var-length Attribute Offsets & Data Blobs (128B Aligned)               │
├───────────────────────────────────────────────────────────────────────────────────┤
│ FOOTER BLOCK (EOF, 4KB Aligned)                                                   │
│   ├── Unified UTF-8 Key/Value Custom Metadata Stream                              │
│   ├── Final Catalog & Relation Directory Table (S3 Stream Copy)                   │
│   ├── SHA-256 Payload Checksum (32 Bytes)                                         │
│   ├── Cryptographic Signature Block (Ed25519 / RSA)                               │
│   └── 16-Byte Footer Trailer (footer_length [u64] + version [u32] + "IMPS" [u32]) │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Rationale for "Relations Before Nodes":
1. **Topology Read Ergonomics**: Pure topology readers (e.g. reachability, ReBAC query pods) read the first contiguous physical bytes (Header $\rightarrow$ Catalog $\rightarrow$ CSR Topology) and fetch 100% of graph structure without seeking past optional node attribute payloads.
2. **Optional Node Attributes**: Omitting node attributes leaves no byte gaps—the file cleanly transitions directly from Relation Blocks to the Footer Block.

---

## 4. Node & Edge Attribute Storage Architecture

Attributes are partitioned into fixed-length primitives and variable-length payloads to optimize for hardware vectorization and $O(1)$ memory mapping.

### 4.1 Fixed-Length & Variable Attributes: Structure of Arrays (SoA)

#### Bitwise Nullability Flag & Base Type Mask
Attribute data types are encoded in an 8-bit field (`uint8_t type_code`) using a bitwise flag model:

```c
#define IMPULSE_TYPE_MASK     0x7F  // Bits 0..6: Base Primitive Type (Up to 128 base types)
#define IMPULSE_NULLABLE_FLAG 0x80  // Bit 7: Nullability Flag (1 = Nullable with Validity Bitmap, 0 = Non-Null)

// Bitwise evaluation in C-ABI parsers
uint8_t base_type   = descriptor->type_code & IMPULSE_TYPE_MASK;
bool    is_nullable = (descriptor->type_code & IMPULSE_NULLABLE_FLAG) != 0;
```

* **Non-Nullable (`is_nullable == false`, Bit 7 = 0)**: Zero validity bitmap overhead. 100% of memory is allocated strictly to contiguous data values.
* **Nullable (`is_nullable == true`, Bit 7 = 1)**: A 128-byte aligned **Validity Bitmap** (`uint64_t validity_bitmap[(N + 63) / 64]`) is placed immediately before the data array (or offsets array) inside the attribute section ($1\text{ bit per entity}$, Bit $i=1 \rightarrow$ valid, Bit $i=0 \rightarrow$ null). Enables AVX-512 masked vector operations (`_mm512_mask_loadu_ps`).

#### Base Data Type Table (`0x00` .. `0x7F` Base Codes):
| Base Code (`0x7F`) | Base Type Name | Non-Null Code | Nullable Code (`0x80`) | Dimension (`dim`) | Stride / Memory Layout |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x01` | `INT8` | `0x01` | `0x81` | $\ge 1$ | $1 \times \text{dim}$ Bytes (int8_t/uint8_t) |
| `0x02` | `INT16` | `0x02` | `0x82` | $\ge 1$ | $2 \times \text{dim}$ Bytes (int16_t/uint16_t) |
| `0x03` | `INT32` | `0x03` | `0x83` | $\ge 1$ | $4 \times \text{dim}$ Bytes (int32_t/uint32_t) |
| `0x04` | `INT64` | `0x04` | `0x84` | $\ge 1$ | $8 \times \text{dim}$ Bytes (int64_t/uint64_t) |
| `0x05` | `FLOAT16` | `0x05` | `0x85` | $\ge 1$ | $2 \times \text{dim}$ Bytes (bfloat16/fp16) |
| `0x06` | `FLOAT32` | `0x06` | `0x86` | $\ge 1$ | $4 \times \text{dim}$ Bytes (IEEE 754 float, **edge weights**) |
| `0x07` | `FLOAT64` | `0x07` | `0x87` | $\ge 1$ | $8 \times \text{dim}$ Bytes (IEEE 754 double, high precision) |
| `0x08` | `TIMESTAMP_MS` | `0x08` | `0x88` | $\ge 1$ | $8 \times \text{dim}$ Bytes (uint64 epoch ms) |
| `0x09` | `TIMESTAMP_NS` | `0x09` | `0x89` | $\ge 1$ | $8 \times \text{dim}$ Bytes (uint64 epoch ns) |
| `0x0A` | `FIXED_BYTES` | `0x0A` | `0x8A` | $\ge 1$ | $\text{dim}$ Bytes (dim=16 for UUID, dim=32 for SHA-256) |
| `0x0B` | `VAR_STRING` | `0x0B` | `0x8B` | Ignored (`0`) | Variable UTF-8 (`uint32_t offsets[]` + Data Blob) |
| `0x0C` | `VAR_BYTES` | `0x0C` | `0x8C` | Ignored (`0`) | Variable Binary (`uint32_t offsets[]` + Data Blob) |

* **Format**: Each primitive numerical column is stored as a standalone, contiguous 128-byte aligned physical array.
* **Vector Attributes**: Setting `dimension > 1` (e.g. `FLOAT32` with `dimension = 128`) maps directly to PyTorch / NumPy 2D Tensors (`shape = [N, 128]`) in zero-copy `mmap` mode.
* **Edge Attributes Mapping**: Common edge properties—such as **edge weights** (`FLOAT32` / `FLOAT64`), **temporal timestamps** (`TIMESTAMP_MS`), **edge status/type flags** (`INT32`), and **capacity/flow**—turn directly into fixed-width SoA arrays stored 1:1 alongside edge indices in the Relation Block ($1 \text{ entry per edge}$, indexed at `edge_idx = 0 .. EdgeCount - 1`).
* **Access**: Node/Edge $i$'s attribute is indexed directly via zero-copy offset calculation: `attr_ptr[i * dimension]`.
* **SIMD Advantage**: Eliminates Array of Structures (AoS) striding overhead; enables AVX-512 / ARM NEON vector units to process 16x 32-bit values per instruction cycle (e.g. SIMD filtering on edge weights or temporal timestamp windows).

### 4.2 Variable-Length Attributes: Arrow/Parquet-Style Blobs
For high-cardinality strings, JSON payloads, or dynamic byte vectors, attributes use a dual-array layout:
1. **Offsets Array**: `uint32_t offsets[N + 1]` (or `uint64_t offsets[N + 1]` for $> 4\text{GB}$ blobs).
2. **Contiguous Data Blob**: Raw UTF-8 bytes or serialized payloads.
* **Access**: Node $i$'s payload spans bytes `data_blob[offsets[i] .. offsets[i+1]]`.

### 4.3 Low-Cardinality Strings: Dictionary-Encoded SoA
* **Format**: Unique strings stored in a Dictionary Catalog; nodes store a fixed-width SoA index array (`uint8_t` or `uint16_t` per node).
* **Advantage**: Compresses string attributes down to 1B or 2B per node, enabling instant SIMD integer mask scanning for string predicate filters (e.g. `WHERE status == 'ACTIVE'`).

---

## 5. Hardware Alignment Specification

| Boundary Level | Alignment Constraint | Target Hardware / System Benefit |
| :--- | :--- | :--- |
| **Major Block Headers** (Header, Catalog, Relation Blocks, Node Blocks, Footer) | **4096 Bytes (4KB OS Page)** | Enables independent, single-VMA `mmap` calls per section without cross-page memory contamination. |
| **Internal Matrix & Array Boundaries** (`csrRowOffsets`, `csrColumnIndices`, `cscRowOffsets`, `cscColumnIndices`, SoA arrays) | **128 Bytes** (`(len + 127) & ~127`) | Guarantees alignment for AVX-512 aligned vector loads (`_mm512_load_si512`), GPU warp memory coalescing, and NVIDIA GPUDirect Storage (`cuFile`) DMA transfers. |

---

## 6. Writer Implementation Guide (C-ABI Alignment Macros)

```c
// Internal Array 128-Byte SIMD/GPU Alignment Macro
#define IMPULSE_ALIGN_128(offset) (((offset) + 127ULL) & ~127ULL)

// Block-level 4KB OS Page Alignment Macro
#define IMPULSE_ALIGN_4K(offset)  (((offset) + 4095ULL) & ~4095ULL)

// Example calculation when positioning CsrColumnIndices
uint64_t row_off_end = rel_start_offset + csr_row_off_bytes;
uint64_t csr_col_idx_offset = IMPULSE_ALIGN_128(row_off_end);
uint64_t internal_padding = csr_col_idx_offset - row_off_end;
```
