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
│ SECTION 2: Catalog & Directory Directory Table (4KB Page 1, Offset 0x1000)         │
│   ├── 1. String Table (Shared Null-Terminated UTF-8 String Pool Blob)              │
│   ├── 2. Domain Catalog Array (Fixed 16-Byte POD Structs)                         │
│   └── 3. Sorted Relation Directory Table (Fixed 128B Entries + 40B Attr Descriptors) │
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

## 3. Section 2: Catalog, String Table & Directory Table Layout

Begins at byte offset `DataOffset` (byte 4096). Contains the **Shared String Table**, node domain definitions, and the **Relation Directory Table**.

### 3.1 Shared String Table (String Pool Heap)
Begins at byte offset `DataOffset` (4096):
* `StringTableBytes` (`uint32_t`, 4B): Total byte size of string pool blob.
* `StringPool` (`byte[StringTableBytes]`): Contiguous null-terminated UTF-8 byte stream starting with `\0` at offset `0`.
  - String offset `0` corresponds to empty string `""`.
  - All domain names, relation names, and attribute names store a 32-bit `name_offset` pointing directly to their null-terminated UTF-8 byte stream in this pool.

### 3.2 Domain Catalog Array (Fixed 16 Bytes per Domain)
Begins immediately after String Table, aligned to a 128-byte boundary. Contains `DomainCount` fixed-size 16-byte records:

| Byte Offset | Field Name | C-ABI Type | Size | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0x0000` – `0x0001` | `DomainID` | `uint16_t` | 2 Bytes | Zero-indexed domain identifier (`0`..`DomainCount - 1`). |
| `0x0002` | `KeyType` | `uint8_t` | 1 Byte | Domain key primitive type enum (`0x01` = INT8..`0x0B` = VAR_STRING). |
| `0x0003` | `Reserved` | `uint8_t` | 1 Byte | `0x00` alignment padding. |
| `0x0004` – `0x0007` | `NameOffset` | `uint32_t` | 4 Bytes | 0-indexed byte offset into String Table (points to null-terminated string, e.g., `"User\0"`). |
| `0x0008` – `0x000F` | `NodeCount` | `uint64_t` | 8 Bytes | Total number of nodes $N$ in this domain. |

### 3.3 Relation Directory Table (Fixed 128 Bytes per Relation)
Begins immediately after Domain Catalog Array, aligned to a 128-byte boundary. Contains `RelationCount` relation descriptors, **sorted primary by `SrcDomainID` and secondary by `TgtDomainID`**:

| Byte Offset | Field Name | C-ABI Type | Size | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0x0000` – `0x0001` | `RelationID` | `uint16_t` | 2 Bytes | Zero-indexed relation identifier (`0`..`RelationCount - 1`). |
| `0x0002` – `0x0003` | `SrcDomainID` | `uint16_t` | 2 Bytes | Domain ID of source nodes. |
| `0x0004` – `0x0005` | `TgtDomainID` | `uint16_t` | 2 Bytes | Domain ID of target nodes. |
| `0x0006` | `EncodingID` | `uint8_t` | 1 Byte | Topology encoding enum (`0x00` = `ENCODING_RAW`, `0x01` = `ZSTD`). |
| `0x0007` | `NodeIDWidth` | `uint8_t` | 1 Byte | Byte width of target node IDs (`0x02` = `uint16_t`, `0x04` = `uint32_t`, `0x08` = `uint64_t`). |
| `0x0008` | `EdgeIndexWidth` | `uint8_t` | 1 Byte | Byte width of CSR row offsets (`0x04` = `uint32_t`, `0x08` = `uint64_t`). |
| `0x0009` – `0x000B` | `Reserved1` | `uint8_t[3]` | 3 Bytes | `0x00` alignment padding. |
| `0x000C` – `0x000F` | `NameOffset` | `uint32_t` | 4 Bytes | 0-indexed byte offset into String Table (points to null-terminated string, e.g., `"FOLLOWS\0"`). |
| `0x0010` – `0x0017` | `NodeCount` | `uint64_t` | 8 Bytes | Number of source nodes ($N$) in relation matrix. |
| `0x0018` – `0x001F` | `EdgeCount` | `uint64_t` | 8 Bytes | Total number of directed edges ($E$) in relation matrix. |
| `0x0020` – `0x0027` | `SectionFeatures` | `uint64_t` | 8 Bytes | Per-relation feature bitmask (bit 0 = CSC, bit 1 = weighted, bit 2 = virtual relation, bits 3..4 = multiplicity). |
| `0x0028` – `0x002F` | `CsrRowOffOffset` | `uint64_t` | 8 Bytes | Absolute file offset to `csrRowOffsets` array (128B aligned; `0` if Virtual or `M:1`/`1:1`). |
| `0x0030` – `0x0037` | `CsrRowOffBytes` | `uint64_t` | 8 Bytes | Byte size of `csrRowOffsets` array ($= (N + 1) \times \text{EdgeIndexWidth}$; `0` if Virtual or `M:1`/`1:1`). |
| `0x0038` – `0x003F` | `CsrColIdxOffset` | `uint64_t` | 8 Bytes | Absolute file offset to `csrColumnIndices` array (128B aligned; `0` if Virtual). |
| `0x0040` – `0x0047` | `CsrColIdxBytes` | `uint64_t` | 8 Bytes | Byte size of `csrColumnIndices` array ($= E \times \text{NodeIDWidth}$; `0` if Virtual). |
| `0x0048` – `0x004F` | `CscRowOffOffset` | `uint64_t` | 8 Bytes | Absolute file offset to optional `cscRowOffsets` array (`0` if omitted, Virtual, or `1:M`/`1:1`). |
| `0x0050` – `0x0057` | `CscRowOffBytes` | `uint64_t` | 8 Bytes | Byte size of `cscRowOffsets` array (`0` if omitted, Virtual, or `1:M`/`1:1`). |
| `0x0058` – `0x005F` | `CscColIdxOffset` | `uint64_t` | 8 Bytes | Absolute file offset to optional `cscColumnIndices` array (`0` if omitted or Virtual). |
| `0x0060` – `0x0067` | `CscColIdxBytes` | `uint64_t` | 8 Bytes | Byte size of `cscColumnIndices` array (`0` if omitted or Virtual). |
| `0x0068` – `0x0069` | `AttrCount` | `uint16_t` | 2 Bytes | Number of edge attributes defined for this relation (`0` if Virtual). |

#### 3.3.2 Virtual Super-Relation C-ABI Payload (`Reserved2` Overload & Overflow Rules)

When `IMP_REL_FEATURE_VIRTUAL` (`Bit 2`) is enabled in `SectionFeatures`:
* **Inline Fast Path ($1 \le \text{component\_count} \le 10$)**:
  Bytes `0x006A` – `0x007F` (22 bytes) in the `RelationDirectoryEntry` are overloaded to store the constituent relation payload directly inside the fixed 128-byte entry (zero extra file reads or memory allocations):

```c
struct ImpulseVirtualRelationPayload {
    uint16_t component_count;    // Number of constituent physical relation IDs (1 <= C <= 10)
    uint16_t component_ids[10];  // Inline array of constituent physical RelationIDs (padded with 0x0000)
};
```

* **Overflow Extended Path ($\text{component\_count} > 10$, up to 65,536)**:
  For large virtual relations composed of more than 10 physical relations:
  1. `component_ids[0]` is set to `0xFFFF` (Overflow Sentinel Flag).
  2. `CsrColIdxOffset` (8-byte `uint64_t`) stores a 128B-aligned absolute file offset to an off-heap array of `uint16_t component_ids[component_count]`.
  3. `CsrColIdxBytes` stores the byte size ($= \text{component\_count} \times 2$).
* **Maximum Theoretical Capacity**: Up to **65,536 physical relations** per virtual super-relation (matching the overall `.imps` relation limit).

---

#### 3.3.3 Per-Relation Feature Bitmask (`SectionFeatures` 64-bit Layout)

The `SectionFeatures` field defines C-ABI flags and structural contracts for topology storage:

```c
#define IMP_REL_FEATURE_CSC          (1ULL << 0) // Bit 0: CSC Transpose Index Present
#define IMP_REL_FEATURE_WEIGHTED     (1ULL << 1) // Bit 1: Edge Weights Present
#define IMP_REL_FEATURE_VIRTUAL      (1ULL << 2) // Bit 2: Virtual Super-Relation (No physical arrays on disk)

// Multiplicity Bitmask (Bits 3..4)
#define IMP_REL_CARDINALITY_MASK     (3ULL << 3) // Bitmask for relation multiplicity (Bits 3..4)
#define IMP_REL_CARDINALITY_M_N      (0ULL << 3) // Many-to-Many (Default full CSR/CSC layout)
#define IMP_REL_CARDINALITY_M_1      (1ULL << 3) // Many-to-One  (Flat target array, CsrRowOffBytes = 0)
#define IMP_REL_CARDINALITY_1_M      (2ULL << 3) // One-to-Many  (Forward CSR, reverse flat CSC array)
#define IMP_REL_CARDINALITY_1_1      (3ULL << 3) // One-to-One   (Flat bi-directional direct arrays)
```

---

### 3.4 Attribute Descriptor Structure (Fixed 44 Bytes)

Every node attribute and edge attribute is defined by a fixed 44-byte POD struct:

| Byte Offset | Field Name | C-ABI Type | Size | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0x0000` – `0x0003` | `NameOffset` | `uint32_t` | 4 Bytes | 0-indexed byte offset into String Table (points to null-terminated string, e.g., `"weight\0"`). |
| `0x0004` | `TypeCode` | `uint8_t` | 1 Byte | Base Primitive Type (`Bits 0..6`) + `0x80` Nullability Flag (`Bit 7`). |
| `0x0005` | `Reserved1` | `uint8_t` | 1 Byte | `0x00` alignment padding. |
| `0x0006` – `0x0007` | `Reserved2` | `uint16_t` | 2 Bytes | `0x00` alignment padding. |
| `0x0008` – `0x000B` | `Dimension` | `uint32_t` | 4 Bytes | Element dimension $D$ ($1$ for scalar, $D \ge 1$ for fixed vectors, $0$ for variable-length). |
| `0x000C` – `0x0013` | `DataOffset` | `uint64_t` | 8 Bytes | 128B-aligned absolute file offset to attribute data array / payload blob. |
| `0x0014` – `0x001B` | `DataBytes` | `uint64_t` | 8 Bytes | Total byte size of attribute data array / payload blob. |
| `0x001C` – `0x0023` | `OffsetsOffset` | `uint64_t` | 8 Bytes | 128B-aligned absolute file offset to `uint32_t offsets[]` array (`0` for fixed-width). |
| `0x0024` – `0x002B` | `OffsetsBytes` | `uint64_t` | 8 Bytes | Total byte size of `uint32_t offsets[]` array ($= (K + 1) \times 4$; `0` for fixed-width). |

---

## 4. Topology & Attribute Specification

### 4.1 Topology Mechanics & Multiplicity Optimizations

* **Many-to-Many (`IMP_REL_CARDINALITY_M_N`)**: Topology is standard CSR (`csrRowOffsets` + `csrColumnIndices`). Target $k$ of node $i$ is read at `csrColumnIndices[csrRowOffsets[i] + k]`.
* **Many-to-One (`IMP_REL_CARDINALITY_M_1`)**: Every source node has at most 1 target node. `csrRowOffsets` is omitted (`CsrRowOffBytes = 0`). `csrColumnIndices` becomes a flat direct array of length $N$. Target node ID for source node $i$ is read directly at `csrColumnIndices[i]` (where `MAX_UINT` indicates no edge).
* **One-to-Many (`IMP_REL_CARDINALITY_1_M`)**: Forward CSR is standard (`csrRowOffsets` + `csrColumnIndices`). Reverse CSC transpose omits `cscRowOffsets` (`CscRowOffBytes = 0`), storing a flat direct source node ID array in `cscColumnIndices`.
* **One-to-One (`IMP_REL_CARDINALITY_1_1`)**: Both `csrRowOffsets` and `cscRowOffsets` are omitted. Forward and reverse traversals use flat direct arrays in $O(1)$ single-hop dereferences.
* **Virtual Super-Relations (`IMP_REL_FEATURE_VIRTUAL`)**: Contains no physical topology arrays. `ImpulseVM` resolves the relation by expanding traversals over `component_ids[0 .. component_count - 1]` and unioning intermediate bitsets via `OP_SET_UNION` or `OP_CSC_WALK_MULTI`.
* **Optional CSC Transpose**: An incoming transpose index (`cscRowOffsets` + `cscColumnIndices`) may be included for bidirectional traversals.
* **Explicit Reverse Relations**: Reverse relations (e.g. `MEMBER_OF_REVERSE`) are represented explicitly as first-class catalog relations.

### 4.2 Attribute Storage Architecture (Structure of Arrays)

Attributes are partitioned into fixed-length primitives, fixed-width vectors, and variable-length payloads stored in **Structure of Arrays (SoA)** layout.

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
* **Nullable (`is_nullable == true`, Bit 7 = 1)**: A 128-byte aligned **Validity Bitmap** (`uint64_t validity_bitmap[(K + 63) / 64]`) is placed at `DataOffset` immediately preceding the data array ($1\text{ bit per entity}$, Bit $i=1 \rightarrow$ valid value, Bit $i=0 \rightarrow$ null).

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

### 4.4 Optional Snapshot Topology & Topology Inspection Opcodes (`0x19` .. `0x1C`)

In accordance with the Impulse Graph Engine physical snapshot format specification, **all structural topology representations (CSR, CSC, COO) and Key Catalogs are fully optional**:
* **CSR (Forward Out-Edges $u \to v$)**: Optional. Opcodes `OP_CSR_*` fail-fast with `IMPULSE_VM_ERR_NULL_SNAPSHOT` if absent.
* **CSC (Reverse In-Edges $v \leftarrow u$)**: Optional. Opcodes `OP_CSC_*` fail-fast with `IMPULSE_VM_ERR_NULL_SNAPSHOT` if absent.
* **COO (Coordinate Edge List $[E, 2]$)**: Optional. Opcodes `OP_COO_*` fail-fast with `IMPULSE_VM_ERR_NULL_SNAPSHOT` if absent.
* **Key Catalogs (Dense Node ID $\leftrightarrow$ String Key / UUID)**: Optional. Opcodes `OP_MAP_KEYS_TO_DENSE` fail-fast if absent.

To enable dynamic adaptive query execution without runtime exception traps, `ImpulseVM` provides 4 dedicated **Topology Inspection Opcodes**:

| Opcode ID | Instruction Signature | Description | Result & Flags |
| :--- | :--- | :--- | :--- |
| **`0x19`** | **`OP_HAS_CSR R_DST, REL_ID`** | Inspects if relation `REL_ID` has CSR forward offsets installed | `R_DST = 1` if present, `0` if absent.<br>Sets `ZF = 0` (present) or `ZF = 1` (absent). |
| **`0x1A`** | **`OP_HAS_CSC R_DST, REL_ID`** | Inspects if relation `REL_ID` has CSC reverse offsets installed | `R_DST = 1` if present, `0` if absent.<br>Sets `ZF = 0` (present) or `ZF = 1` (absent). |
| **`0x1B`** | **`OP_HAS_COO R_DST, REL_ID`** | Inspects if relation `REL_ID` has COO edge list installed | `R_DST = 1` if present, `0` if absent.<br>Sets `ZF = 0` (present) or `ZF = 1` (absent). |
| **`0x1C`** | **`OP_HAS_KEY_CATALOG R_DST, DOMAIN_ID`** | Inspects if domain `DOMAIN_ID` has String/UUID key catalog installed | `R_DST = 1` if present, `0` if absent.<br>Sets `ZF = 0` (present) or `ZF = 1` (absent). |

---

### 4.3 Detailed Physical Storage Rules for Attributes

Attribute storage layout depends on whether the attribute is fixed-width (scalar / vector) or variable-length.

#### 1. Fixed-Width Primitives & Vector Attributes ($D \ge 1$)
* **Location**: Edge attributes sit in the **Relation Block** immediately following topology arrays; Node attributes sit in **Node Domain Blocks**.
* **Offset & Alignment**: Data array begins at absolute file offset `DataOffset`, aligned to a 128-byte boundary.
* **Element Indexing**: Element $i$ ($0 \le i < K$, where $K = E$ for edges or $K = N$ for nodes) starts at byte offset:
  $$\text{ByteOffset}(i) = \text{DataOffset} + (i \times D \times \text{sizeof(BaseType)})$$

#### 2. Variable-Length String & Binary Attributes (`VAR_STRING` 0x0B, `VAR_BYTES` 0x0C)
* **Offsets Array**: Stored at 128B-aligned `OffsetsOffset` containing an array of $K + 1$ 32-bit unsigned integers (`uint32_t offsets[K + 1]`), where `offsets[0] = 0`.
* **Data Payload Blob**: Stored at 128B-aligned `DataOffset` containing the raw concatenated UTF-8 text or binary bytes.
* **Slice Extraction**: Payload bytes for element $i$ are extracted from `DataOffset + offsets[i]` with byte length `offsets[i + 1] - offsets[i]`.

---

## 5. Footer Block & S3 Streaming Upload Specification

### 5.1 Single-Pass S3 Ingestion
For unseekable S3 multi-part uploads, signatures, SHA-256 digests, and catalog directories are serialized into the **Footer Block at EOF**.

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

```c
// 128-Byte Alignment for AVX-512 SIMD & GPU Warp Coalescing
#define IMPULSE_ALIGN_128(offset) (((offset) + 127ULL) & ~127ULL)

// 4KB Page Alignment for OS Virtual Memory Area (VMA) Isolation
#define IMPULSE_ALIGN_4K(offset)  (((offset) + 4095ULL) & ~4095ULL)
```

---

## 7. Future Research & Architectural Explorations

### 7.1 Multi-Snapshot Query Execution & Cross-Snapshot Relation Namespacing

Future specification iterations explore allowing single queries (`ImpulseVM` execution pipelines) to bind and traverse across multiple `.imps` binary snapshots (e.g., Snapshot `A` containing relations `rel0..10`, and Snapshot `B` containing relations `rel11..13`).

#### Core Design & Research Directives:

1. **Relation Namespacing & Virtual Directory Table**:
   - **Syntax & Disambiguation**: Enforce namespace resolution (`SnapshotAlias::RelationName`, e.g., `A::userToGroup`) to prevent relation collisions across snapshots.
   - **Composite Relation Handles**: Expand 16-bit relation handles in `impOps` to 32-bit composite handles `(SnapshotID << 16) | LocalRelID` or construct a thread-safe `VirtualRelationDirectory` at query compilation time.

2. **Node ID Space Alignment & Key Compatibility**:
   - **Identity Verification**: Enforce snapshot bind-time verification comparing node domain names, entity counts, primary key schemas, and domain identity hashes.
   - **Zero-Copy Pass-Through**: For snapshots generated against identical baseline node ID catalogs (e.g., base snapshot + delta snapshots), preserve sub-microsecond direct $O(1)$ node indexing.
   - **Dense Translation Vectors (`OP_REMAP_ID_SPACE`)**: For mismatched node ID orderings across snapshots, construct or mmap dense remapping vectors (`map_A_to_B[node_id_A] -> node_id_B`) to translate frontier node bitsets between snapshot steps without allocation overhead.
   - **Bounds Safety**: Enforce domain count bounds checking ($N_A$ vs $N_B$) to prevent out-of-bounds memory access during CSR row offset lookups.

3. **Off-Heap String Table & Attribute Memory Isolation**:
   - **String Pool Base Pointer Isolation**: Scope variable-length UTF-8 string offsets (`VAR_STRING`) to their originating snapshot's string pool pointer (`string_table_base_A` vs `string_table_base_B`) to avoid cross-snapshot memory corruption in attribute filter opcodes (`OP_FILTER_ATTR_STR`).
   - **Attribute Schema Unification**: Standardize bitwise primitive types across snapshots to ensure vector operations (`OP_MXV`) run without runtime alignment or type-coercion overhead.

### 7.2 ImpulseVM Register Windowing & 64 KB Off-Heap Scratch Baseline

`ImpulseVM` query execution contexts (`VmQueryContext` / `impulse_vm_context_t`) establish a **64 KB (`65,536` bytes)** default baseline off-heap scratch memory allocation.

#### Specification Constraints & Directives:
1. **64 KB Default Off-Heap Scratch Baseline**:
   - Every `VmQueryContext` instance pre-allocates 64 KB of 64-byte aligned off-heap scratch memory upon initialization.
   - 64 KB is guaranteed to fit 100% inside CPU **L2 Data Cache** (~512 KB to 1 MB per core on x86-64 and ARM64 processors), eliminating DRAM latency during query execution.
2. **Register Windowing Stride**:
   - Subroutine calls (`OP_CALL`) shift register windows forward (increasing memory offsets) by a stride of 12 registers (96 bytes per frame step).
   - The 64 KB default scratch allocation supports up to **680 recursive call steps** out of the box with **zero off-heap dynamic memory allocations** during query execution.
3. **Upfront Capacity Assertion (`.scratch_bytes`)**:
   - Queries requiring deeper recursion (e.g. 10,000-step Depth-First Search or complex recursive graph traversals) declare their required capacity upfront in assembly headers via `.scratch_bytes 1048576` (1 MB) or using `OP_ALLOC_SCRATCH R_DST, BYTES` (`0x73`).

4. **Multi-Snapshot Lifecycle & Execution Safety**:
   - **Atomic Ref-Counting & Thread Safety**: Extend `VmQueryContext` to maintain atomic read-locks and reference counts across all participant snapshot `mmap` handles to prevent OS page faults (`SIGBUS`) during dynamic snapshot unmapping or hot-swapping.

### 7.2 Dynamic Delta Overlay for In-Memory Graph CRUD Operations (v0.9.2+ Feature Roadmap)

A major future research initiative slated for the **v0.9.2+ feature roadmap** focuses on evaluating dynamic in-memory **Delta Overlays** (`CsrDeltaLayer`) for handling real-time Graph CRUD operations (insertions/deletions of nodes and edges, and node/edge attribute mutations) directly on top of immutable `.imps` zero-copy snapshots.


#### Architectural Challenges & Empirical Verification Mandate:

1. **Traversal Performance Overhead Hypothesis**:
   - **Tombstone Bitset Evaluation**: Marking deleted nodes/edges via `RoaringBitmap` or dense bitset tombstones requires per-neighbor bitwise checking during `OP_CSR_WALK`, potentially disrupting AVX-512 SIMD vector loops.
   - **Dual-Path Adjacency Merging**: Traversing inserted edges requires merging static contiguous CSR array reads with dynamic in-memory adjacency lists, introducing pointer indirection, cache line misses, and branch mispredictions.
   - **Attribute Mutation Overlays**: Overriding fixed-width SoA attribute arrays or variable-length string blobs with dynamic Copy-on-Write (CoW) maps breaks contiguous off-heap array alignment.

2. **Empirical Benchmark Verification Requirement**:
   - In accordance with empirical verification standards, the engine design team hypothesizes that dynamic delta overlays will incur a measurable performance penalty compared to raw zero-copy `mmap` snapshots.
   - Rigorous empirical micro- and macro-benchmarks (measuring MTEPS throughput, QPS, L1/L3 cache misses, and branch misprediction rates via JMH and Google Benchmark) must be conducted to establish exact performance curves across varying delta scale ratios (0.1% to 10% mutation volume).

3. **Trade-Off Analysis & Valid Workload Scenarios**:
   - **Real-Time Read-After-Write (RAW) Consistency**: For Relationship-Based Access Control (ReBAC / Zanzibar), fraud detection, and transactional security, paying a modest traversal latency penalty ($0.2\mu\text{s} \to 1.5\mu\text{s}$) to guarantee instant sub-millisecond Read-After-Write freshness is a highly valid trade-off compared to serving stale access control reads while awaiting offline snapshot compaction.
   - **High Read-to-Write Ratios ($>99\%$ Read, $<1\%$ Mutation)**: For workloads where $99.9\%$ of edges are read zero-copy from disk `mmap` and only $0.1\%$ hit the delta layer, overall query latency degrades by only 5%–15%, avoiding the massive CPU and disk I/O cost of rebuilding multi-hundred-gigabyte snapshots for single mutations.
   - **Resource-Constrained Environments**: For edge nodes or cloud instances with strict I/O caps, delta overlays bound write amplification to $O(\Delta)$ memory footprint rather than $O(\text{Snapshot Size})$ disk writes.

4. **v1.0 Tolerable Overhead Guidance & Benchmark SLA ($\le 20\%$ Latency Degrade Target)**:
   - **v1.0 Performance SLA Standard**: A **$\le 20\%$ max latency overhead** ($\text{Latency}_{\text{delta}} \le 1.20 \times \text{Latency}_{\text{snapshot}}$ for low mutation volumes $\Delta \le 1\%$) is formally established as the target performance budget for v1.0 releases.
   - **Compaction Trigger Signal**: If empirical benchmark execution demonstrates traversal overhead exceeding 20%, `impulse-engine` runtime automatically triggers background **A/B Snapshot Compaction** to re-baseline the delta layer into a new `.imps` snapshot and restore sub-microsecond zero-copy speeds.
   - **SIMD Masking Mandate**: To satisfy the $\le 20\%$ target budget, tombstone bitset evaluation inside `impOps` must use vector bitwise masking (e.g. AVX-512 `vpandn` or Java Vector API bitwise masks) rather than scalar `if (isDeleted)` branches.




