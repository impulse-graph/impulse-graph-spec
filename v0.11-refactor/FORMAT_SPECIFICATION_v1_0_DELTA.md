# Impulse Binary Snapshot Format `.imps` v1.0 Delta Specification (v0.9.0 → v1.0)

> **Status**: Companion Format Delta (`feat/v0.11.0-ISA-Refactor`)
> Documents the minimal binary format extensions to `docs/FORMAT_SPECIFICATION.md` (`v0.9.0`, `0x0009`) required to cleanly support every ImpulseVM v0.11 / v1.0 ISA feature without breaking 128-byte alignment or zero-copy `mmap` invariants.

---

## 1. Optional CSC-to-CSR Edge Map (`cscEdgePerm[]`) for Weighted Pull-CSC

- **Problem**: Edge attributes in `.imps` v0.9.0 are stored strictly in CSR edge order (`0..E-1`), while `cscColumnIndices[e_csc]` stores only `src_u`. Weighted `0x34 OP_SPMV` and `0x6C OP_LANE_STATE_WALK` cannot execute lock-free deterministic CSC Pull over edge weights in $O(1)$ without an edge-index mapping.
- **Change (`RelationDirectoryEntry` §3.3)**:
  - Add feature flag in `SectionFeatures`:
    ```c
    #define IMP_REL_FEATURE_CSC_EDGE_PERM (1ULL << 5) // Bit 5: cscEdgePerm[] present immediately after cscColumnIndices
    ```
  - When Bit `5` is set, a 128-byte aligned `cscEdgePerm[EdgeCount]` array (`EdgeIndexWidth` bytes per entry, `uint32_t` or `uint64_t`) maps `e_csc -> e_csr`, stored via a companion `IndexType = 0x09` (`CscEdgePerm`) entry or extended relation header offset.
  - **Backward Compatibility**: Readers ignoring Bit `5` fall back cleanly to Push-CSR on weighted relations.

---

## 2. Explicit `SrcNodeIDWidth` in `RelationDirectoryEntry` (§3.3)

- **Problem**: Byte `0x0007` (`NodeIDWidth`) only encodes target node ID width (`csrColumnIndices`), leaving mixed-width cross-domain relations (e.g., `SrcDomain = uint16_t`, `TgtDomain = uint32_t`) implicit in CSC.
- **Change**: Assign `Reserved1[0]` (Byte `0x0009`) as `SrcNodeIDWidth` (`0x00` = legacy v0.9.0 fallback equal to `NodeIDWidth`; `0x02` = `uint16_t`; `0x04` = `uint32_t`; `0x08` = `uint64_t`). **Zero struct size growth.**

---

## 3. Base Data Type Table Extensions (§4.2)

Resolves signed/unsigned ambiguity for v0.11 `I64`/`U64` vector semantics and adds `DECIMAL64` + `BOOL` without growing the 44-byte `AttributeDescriptor`:

| Base Code (`0x7F`) | Base Type Name | Non-Null | Nullable (`0x80`) | `Reserved1` / `Reserved2` | Physical Memory Layout |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x01`–`0x04` | `INT8` .. `INT64` | `0x01`..`0x04` | `0x81`..`0x84` | `0` | **Signed** `int8_t` .. `int64_t` (two's complement) |
| `0x08`–`0x09` | `TIMESTAMP_MS` / `NS` | `0x08`..`0x09` | `0x88`..`0x89` | `0` | **Signed** `int64_t` UTC epoch ms / ns (supports pre-1970 dates) |
| `0x0F` | `BOOL` | `0x0F` | `0x8F` | `0` | 1-bit packed `uint64_t[(K + 63) / 64]` (128B-padded) |
| `0x11` | `UINT8` | `0x11` | `0x91` | `0` | Unsigned `uint8_t` (`0x10` reserved for `INT* \| 0x10` symmetry) |
| `0x12` | `UINT16` | `0x12` | `0x92` | `0` | Unsigned `uint16_t` |
| `0x13` | `UINT32` | `0x13` | `0x93` | `0` | Unsigned `uint32_t` |
| `0x14` | `UINT64` | `0x14` | `0x94` | `0` | Unsigned `uint64_t` |
| `0x15` | `DECIMAL64` | `0x15` | `0x95` | `Reserved1 = scale` (`0..18`), `Reserved2 = precision` (`1..18`) | Scaled signed `int64_t` ($\times 10^{\text{scale}}$, Parquet `DECIMAL64` layout) |
| `0x16` | `DECIMAL128` *(Reserved)* | `0x16` | `0x96` | Reserved | Reserved for future 16-byte signed `int128_t` ($19 \le P \le 38$) |

- **64-Bit String/Bytes Offsets (`VAR_STRING` `0x0B` / `VAR_BYTES` `0x0C`)**:
  - Set `Reserved1` Bit `0` (`0x01`) on `AttributeDescriptor` when `offsets[]` uses `uint64_t` (lifting the 4 GB per-column blob cap to >4 GB while keeping `uint32_t` default when `Reserved1 == 0`).

---

## 4. `VectorANN` Secondary Index Type (§3.4 `IndexType = 0x08`)

- **Problem**: `IndexType` (`0x01..0x07`) lacked a normative descriptor for HNSW / DiskANN indexes queried by `0x69 OP_VECTOR_ANN_SEARCH`.
- **Change**: Define `IndexType = 0x08` (`IMP_INDEX_VECTOR_ANN`) and pack its parameters into the existing 24-byte `ReservedPadding` (`0x0028` – `0x003F`) of `IndexDescriptor`:

| Byte Offset | Field Name | C-ABI Type | Description |
| :--- | :--- | :--- | :--- |
| `0x0028` | `MetricType` | `uint8_t` | `0 = DOT`, `1 = COSINE`, `2 = L2_SQ`, `3 = HAMMING` |
| `0x0029` | `IndexAlgo` | `uint8_t` | `0 = HNSW`, `1 = DiskANN / Vamana`, `2 = IVF_FLAT` |
| `0x002A` – `0x002B` | `GraphM` | `uint16_t` | Max graph degree $M$ (e.g., `16`, `32`) |
| `0x002C` – `0x002F` | `Dimension` | `uint32_t` | Embedding dimension $D$ (must match target `AttributeIndex` dimension) |
| `0x0030` – `0x0033` | `EfDefault` | `uint32_t` | Default `ef_search` when `R[s2]` high 32b is `0` |
| `0x0034` – `0x003F` | `Reserved` | `uint8_t[12]` | `0x00` padding |

---

## 5. Spec Cleanup (§4.4 Topology Inspection)

- Replace legacy v0.10 opcode references (`0x19`–`0x20` `OP_HAS_CSR`..`OP_HAS_DENSE`) in `docs/FORMAT_SPECIFICATION.md` §4.4 with v0.11 `0x3A OP_HAS_TOPOLOGY`.

---

## 6. `M:1` Edge Attribute Indexing & Multi-Snapshot `FederatedSnapshotView`

- **`M:1` (`IMP_REL_CARDINALITY_M_1`) Edge Attributes**: When `CsrRowOffBytes == 0`, `csrColumnIndices[u]` holds `tgt_id` (or `MAX_UINT` if node `u` has no outgoing edge). Edge attributes on `M:1` relations MUST be indexed by source node `u` (length `NodeCount`, with validity bit `0` where `csrColumnIndices[u] == MAX_UINT`), so `OP_GATHER_EDGE_ATTR` remains $O(1)$ without prefix-sum scans.
- **Virtual Super-Relations (`IMP_REL_FEATURE_VIRTUAL`)**: `AttrCount` is strictly `0`; `OP_GATHER_EDGE_ATTR` targeting a virtual relation traps `IMPULSE_VM_ERR_INVALID_OPERAND`. Attributed traversals over virtual relations are lowered by `ImpScheme` into `.accum` sequences over constituent physical relations.
- **Federated Multi-`.imps` Mounting (`FederatedSnapshotView`)**: Multiple `.imps` files may be mounted into a single VM query context with disjoint logical `dom_id` (`0..65535`) and `rel_id` (`0..65535`) ranges. Cross-snapshot business-key hops execute in zero-allocation streaming fashion via `0x55 OP_MAP_KEYS_TO_DENSE` (`subop 3 = .f_to_f`, `subop 4 = .v_to_v`), and `imp_str_handle_t` (`source_tag = 0b00`) carries a `10-bit snap_idx` + `52-bit byte_offset` to keep zero-copy string handles unambiguous across up to 1,024 mounted `.imps` files.
