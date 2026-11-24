# ImpulseVM v0.11.0 Virtual Machine Architecture Specification

> **Normative Draft (`v0.11.0-ISA-Refactor`)**
> Defines the little-endian 64-bit nibble instruction encoding, split `3 × 16` register banks with packed scalar type tags (`r_type_word`), 256-byte C-ABI execution state, caller-owned `(scratch_buf, result_buf)` zero-allocation workspace, `epoch`-tagged 3-tier adaptive frontiers, static memory bounding (`impulse_vm_plan_memory`), branchless Kleene 3VL, lexical morsels, deterministic fuel accounting, static validation (`impulse_vm_validate`), and C++/Java 25 dispatch guidance.

---

## 1. Universal 64-Bit Nibble-Encoded Instruction Format

### 1.1 Primary 64-Bit Instruction Word (Little-Endian)

All `.impb` instruction words, immediates, and container headers are **little-endian**. Every `impOps` v0.11.0 instruction occupies one 8-byte aligned 64-bit word (`uint64_t`), except 64-bit literal loads (`OP_LOAD_CONST.i64.ext` / `.u64.ext` / `.f64.ext`) which set `FLAG_EXTENDED` (`0x8` in `flags:4`) and consume two consecutive 64-bit words (`16` bytes).

```text
 63                  48 47                  32 31    28 27    24 23    20 19    16 15    12 11     8 7            0
+----------------------+----------------------+--------+--------+--------+--------+--------+--------+--------------+
|       imm16_hi       |       imm16_lo       |   s2   |   s3   |  dst   |   s1   | flags  | subop  |    opcode    |
+----------------------+----------------------+--------+--------+--------+--------+--------+--------+--------------+
|<-------------- imm32 (32b) ---------------->|<-- Byte 3 (8b)->|<-- Byte 2 (8b)->|<-- Byte 1 (8b)->|<- Byte 0 (8b)|
```

#### Exact Bit-Shift Extraction Formulas (`uint64_t w`, Little-Endian)

```c
static inline uint8_t  imp_v11_opcode  (uint64_t w) { return (uint8_t)(w & 0xFFu); }
static inline uint8_t  imp_v11_subop   (uint64_t w) { return (uint8_t)((w >>  8) & 0x0Fu); }
static inline uint8_t  imp_v11_flags   (uint64_t w) { return (uint8_t)((w >> 12) & 0x0Fu); }
static inline uint8_t  imp_v11_s1      (uint64_t w) { return (uint8_t)((w >> 16) & 0x0Fu); }
static inline uint8_t  imp_v11_dst     (uint64_t w) { return (uint8_t)((w >> 20) & 0x0Fu); }
static inline uint8_t  imp_v11_s3      (uint64_t w) { return (uint8_t)((w >> 24) & 0x0Fu); }
static inline uint8_t  imp_v11_s2      (uint64_t w) { return (uint8_t)((w >> 28) & 0x0Fu); }
static inline uint32_t imp_v11_imm32   (uint64_t w) { return (uint32_t)(w >> 32); }
static inline uint16_t imp_v11_imm16_lo(uint64_t w) { return (uint16_t)((w >> 32) & 0xFFFFu); }
static inline uint16_t imp_v11_imm16_hi(uint64_t w) { return (uint16_t)((w >> 48) & 0xFFFFu); }
```

#### Memory Byte Layout (`uint8_t bytes[8]`)

| Byte Offset | Bits in `w` | High Nibble (`bits 7..4`) | Low Nibble (`bits 3..0`) | Role |
| :--- | :--- | :--- | :--- | :--- |
| **Byte `0`** | `w[7:0]` | `opcode[7:4]` | `opcode[3:0]` | Primary opcode (`0x00`..`0xFE`; `0xFF` = `OP_EXTENSION_PAYLOAD`). |
| **Byte `1`** | `w[15:8]` | `flags:4` (`w[15:12]`) | `subop:4` (`w[11:8]`) | 4 global modifier flags (`Byte 1 = (flags << 4) \| subop`) + 4-bit sub-operation selector (`0..15`). |
| **Byte `2`** | `w[23:16]` | `dst:4` (`w[23:20]`) | `s1:4` (`w[19:16]`) | Destination register (`0..15`) + primary source register (`0..15`). |
| **Byte `3`** | `w[31:24]` | `s2:4` (`w[31:28]`) | `s3:4` (`w[27:24]`) | Secondary source (`0..15`) + tertiary source / mask register (`0..15`). |
| **Bytes `4..5`** | `w[47:32]` | — | — | `imm16_lo` (`rel_id`, `domain_id`, `param_id`, `k`, or low half of `imm32`). |
| **Bytes `6..7`** | `w[63:48]` | — | — | `imm16_hi` (`attr_id`, `morsel_end_off`, or high half of `imm32`). |

> [!IMPORTANT]
> **Must-Be-Zero (MBZ) Unused Field Rule**: Any register nibble (`dst`, `s1`, `s2`, `s3`) or immediate half (`imm16_lo`, `imm16_hi`, `imm32`) not consumed by an opcode + `(flags, subop)` combination **MUST be encoded as `0`**. The static verifier (`impulse_vm_validate`) rejects non-zero unused fields with `IMPULSE_VM_ERR_INVALID_OPERAND` (`6`).

### 1.2 128-Bit Extended Word (`FLAG_EXTENDED` + `0xFF OP_EXTENSION_PAYLOAD`)

When `FLAG_EXTENDED` (`flags:4` bit `3`, i.e., `0x8` in nibble / `0x80` in Byte `1`) is set on Word 1 at `bytecode[pc]`, the instruction spans `bytecode[pc]` and `bytecode[pc + 1]`, and normal fallthrough advances `pc` by `2`.

```text
Word 1 (pc):     [ imm32_lo (32b)          | s2:4 | s3:4 | dst:4 | s1:4 | 1xxx:4 | subop:4 | opcode:8 ]
Word 2 (pc + 1): [ imm32_hi (32b)          |         ext_meta24 (24b, MBZ)                  | 0xFF     ]
```

* **64-Bit Constant Reconstruction**: `uint64_t imm64 = ((uint64_t)imp_v11_imm32(w2) << 32) | (uint64_t)imp_v11_imm32(w1);`
* **Why `0xFF` in Byte 0 of Word 2 Is Invariant**: Because Word 1 carries `imm32_lo` and Word 2 carries `imm32_hi` in Bytes `4..7`, Byte `0` of Word 2 is permanently pinned to `0xFF` (`OP_EXTENSION_PAYLOAD`). Any branch targeting `pc + 1` is statically rejected by `impulse_vm_validate` and deterministically traps with `IMPULSE_VM_ERR_VALIDATION_FAILED` (`15`).

### 1.3 Bytecode Container Header (`.impb` v0.11 — 32 Bytes, Little-Endian)

| Offset | Type | Field | Description |
| :--- | :--- | :--- | :--- |
| `0..3` | `uint32_t` | `magic` | `0x494D5042` (`'IMPB'`, little-endian). |
| `4..5` | `uint16_t` | `isa_version` | `0x000B` (`11` for v0.11.0). |
| `6` | `uint8_t` | `header_flags` | Bit `0`: `HAS_CONST_POOL`; Bits `1..7`: MBZ. |
| `7` | `uint8_t` | `max_call_depth` | Declared maximum `OP_CALL` nesting depth (`0..16`; `0` for non-recursive/flat plans, used by `impulse_vm_plan_memory` and enforced at runtime). |
| `8..11` | `uint32_t` | `code_word_count` | Number of 64-bit words in the instruction stream. |
| `12..15` | `uint32_t` | `const_pool_bytes` | Byte length of the trailing 8-byte-aligned Constant Pool section. |
| `16..19` | `uint32_t` | `entry_pc` | Initial `pc` word offset (typically `0`). |
| `20..21` | `uint16_t` | `required_domains` | Minimum domain count expected in bound `.imps` snapshot (`0` = pure compute). |
| `22..23` | `uint16_t` | `reserved` | MBZ (reserved for future capability profiles). |
| `24..31` | `uint64_t` | `program_xxh3_64` | XXH3-64 checksum over `bytecode` + `const_pool`. |

---

## 2. The Four Universal Modifier Flags (`flags:4`)

Byte `1` bits `7..4` (`flags:4`) have fixed, universal meanings across the entire ISA. Setting any bit outside an opcode's `allowed_flags` fails `impulse_vm_validate` with `IMPULSE_VM_ERR_INVALID_OPERAND` (`6`).

| Flag Nibble (`flags:4`) | Byte `1` Mask | ImpAsm Suffix | Name | Universal Semantics |
| :--- | :--- | :--- | :--- | :--- |
| `0x8` (Bit 3) | `0x80` | `.ext` | `FLAG_EXTENDED` | 128-bit instruction (`Word 2` Byte `0 == 0xFF`); `pc += 2`. Permitted only on `OP_LOAD_CONST` (`subop = 4, 5, 6`). |
| `0x4` (Bit 2) | `0x40` | `.accum` | `FLAG_ACCUM` | **Monoid / Set Accumulate into `dst`**: merges output into pre-existing `dst` (`F[dst] \|= out` for frontiers; `V[dst] = V[dst] \oplus out` for `OP_SPMV` and `OP_MORSEL_COMMIT`). Requires `dst` to be pre-initialized in the same domain/type. |
| `0x2` (Bit 1) | `0x20` | `.scalar` | `FLAG_SCALAR_RHS` | **Scalar RHS Broadcast**: switches source nibble `s2` from vector/frontier bank `V[s2]`/`F[s2]` to scalar register `R[s2]` (broadcasting both value and validity bit `r_valid_mask[s2]`; on `OP_NODE_FILTER.between` and `OP_VEC_CMP.between`, also switches `s3` to `R[s3]`). |
| `0x1` (Bit 0) | `0x10` | `.mask` | `FLAG_MASKED_S3` | **Frontier Mask / Exclude on `s3`**: activates nibble `s3` as conditioning frontier `F[s3]` (or morsel mask `MF[s3 & 7]` inside a morsel block). On `OP_WALK`, `OP_WALK_FILTERED`, `OP_WALK_MORSEL`, `OP_LANE_WALK`: **Exclude mask** (`output \ F[s3]`). On `OP_SPMV`, `OP_GATHER_*`, `OP_VEC_*`, `OP_VEC_REDUCE`, `OP_TOP_K`, `OP_COLLECT`, `OP_VECTOR_ANN_SEARCH`, `OP_VECTOR_RERANK`: **Active selection mask**. |

---

## 3. Split `3 × 16` Register Architecture, Packed Scalar Tags & Morsel Aliasing

### 3.1 Three Statically Typed Register Banks

| Bank | Architectural Names | Backing Representation | Domain, Type & Nullability Tracking |
| :--- | :--- | :--- | :--- |
| **Scalar Bank (`R`)** | `R0` .. `R15` | `uint64_t r_regs[16]` + `uint16_t r_valid_mask` + **`uint64_t r_type_word`** | 64-bit scalar values paired with a 16-bit Kleene validity mask (`0 = NULL`, `r_regs[i]` canonicalized to `0ULL`) and a single 64-bit packed type word (`16 × 4`-bit tags, nibble `i` = `(r_type_word >> (i * 4)) & 0xF`). |
| **Frontier Bank (`F`)** | `F0` .. `F15` | `uint32_t f_handles[16]` $\to$ descriptors in caller workspace | Explicit `uint16_t domain_id` (`AGENTS.md` §3.14), `uint8_t tier`, `uint8_t lane_width` (`1, 8, 16, 32, 64`), `int64_t cached_card` (`-1` = unknown), and workspace slab/dense offset. |
| **Vector Bank (`V`)** | `V0` .. `V15` | `uint16_t v_handles[16]` $\to$ descriptors in caller workspace | Typed off-heap vector slice (`I64`, `U64`, `I32`, `U32`, `F64`, `F32`, `BOOL_3VL`, `STR_VIEW`), `domain_id` (or `0xFFFF`), `uint64_t length`, data pointer (`.imps` zero-copy borrow or caller workspace offset), and optional validity bitmap pointer (`NULL` = all-valid fast path). |

#### Packed 4-Bit Scalar Type Tags (`r_type_word`)

| Tag (`0..6`) | Name | Meaning in `R[i]` |
| :--- | :--- | :--- |
| `0` | `SCALAR_NULL_UNSET` | Unwritten / Kleene `NULL` (`r_valid_mask[i] == 0`, `r_regs[i] == 0ULL`). |
| `1` | `SCALAR_I64` | Signed 64-bit two's-complement integer. |
| `2` | `SCALAR_U64` | Unsigned 64-bit integer / dense node ID / count. |
| `3` | `SCALAR_F64` | IEEE-754 double-precision float (`NaN` canonicalized to `NULL`). |
| `4` | `SCALAR_BOOL_3VL` | Kleene 3-valued boolean (`valid=1, val=0/1` or `valid=0, val=0`). |
| `5` | `SCALAR_STR_HANDLE` | 64-bit scalar string handle (`imp_str_handle_t`, §6.3). |
| `6` | `SCALAR_F32_RAW` | Raw 32-bit IEEE-754 float in low 32 bits (`OP_LOAD_CONST.f32_raw`). |

*Note*: `r_type_word` occupies 8 bytes in Cache Line 0, stays in a single CPU register, and saves/restores in 1 move on `OP_CALL`/`OP_RET`/`OP_SWAP`. It enables $O(1)$ runtime type-family validation in `OP_NODE_FILTER` (`INT` vs `FLOAT` vs `STR`) and self-describing `OP_COLLECT.scalar` Arrow outputs.

### 3.2 Lexical Morsel Register Aliasing (`MF0..MF7` & `M0..M7`)

Inside `0x35 OP_WALK_MORSEL` or `0x36 OP_FILTER_MORSEL .. 0x38 OP_MORSEL_END`, each worker thread operates on a pre-carved L1-resident morsel scratchpad inside `scratch_buf` (`MORSEL_MAX = 2048` lanes; `133 KB` per worker thread):

| Nibble Value | `F` Bank Inside Morsel | `V` Bank Inside Morsel | Access Permission |
| :--- | :--- | :--- | :--- |
| **`0 .. 7`** | Outer domain frontiers `F0..F7` | Outer domain vectors `V0..V7` | **Read-Only** in body (`GATHER_VEC`, `SET_CONTAINS`); **Commit-Only** via `OP_MORSEL_COMMIT` (`dst` $\in 0..7$). |
| **`8 .. 15`** | Thread-private morsel masks **`MF0..MF7`** | Thread-private morsel vectors **`M0..M7`** | **Read/Write** thread-private SIMD lanes (`len = morsel_len <= 2048`). |

Pre-populated inputs at block entry: `MF0` (`F8` = active mask `[0..L)`), `M0` (`V8` = topological `src_id` in `OP_WALK_MORSEL` or `node_id` in `OP_FILTER_MORSEL`), `M1` (`V9` = topological `tgt_id`), `M2` (`V10` = canonical CSR `edge_idx`), `M3` (`V11` = `u64` `lane_mask`).

---

## 4. C-ABI Execution State Frame & Sliding Register Windows

### 4.1 Hot Execution Frame (`impulse_vm_state_v11_t` — Exact 256 Bytes, 4 Cache Lines)

Matches C++20, Rust `#[repr(C, align(64))]`, and Java 25 FFM `MemorySegment` layouts byte-for-byte:

```c
typedef struct IMPULSE_ALIGN(64) {
    // --- Cache Line 0 (Bytes 0..63): Control, Flags, Type Word & R0..R3 ---
    uint32_t pc;                        // [0..3]   Current instruction word index
    uint16_t vm_flags;                  // [4..5]   Bit 0: ZF, Bit 1: ST, Bit 2: NF (bits 3..15 MBZ)
    uint16_t r_valid_mask;              // [6..7]   16-bit Kleene validity mask for R0..R15 (1=valid, 0=NULL)
    uint64_t r_type_word;               // [8..15]  16 x 4-bit scalar type tags for R0..R15
    uint16_t call_depth;                // [16..17] Active call stack depth (0..16)
    uint16_t max_dop;                   // [18..19] Active worker parallelism (1..host_max)
    uint32_t win_bases_packed;          // [20..23] r_base:8 | f_base:8 | v_base:8 | spill_base:8
    impulse_vm_workspace_v11_t* ws;     // [24..31] Pointer to caller-owned workspace header (gas, stacks, slabs)
    uint64_t r_regs[4];                 // [32..63] R0..R3 (contiguous with R4..R15 below as r_regs[16])

    // --- Cache Line 1 (Bytes 64..127): Scalar Bank R4..R11 ---
    uint64_t r_regs_4_11[8];            // [64..127]

    // --- Cache Line 2 (Bytes 128..191): R12..R15 + Frontier Handle Table F0..F7 ---
    uint64_t r_regs_12_15[4];           // [128..159]
    uint32_t f_handles[8];              // [160..191]

    // --- Cache Line 3 (Bytes 192..255): Frontier F8..F15 + Vector Handle Table V0..V15 ---
    uint32_t f_handles_8_15[8];         // [192..223]
    uint16_t v_handles[16];             // [224..255]
} impulse_vm_state_v11_t;
```

### 4.2 Condition Flags (`vm_flags`)

| Bit | Mask | Name | Meaning |
| :--- | :--- | :--- | :--- |
| `0` | `0x0001` | **`ZF`** | `1` when output frontier is empty, reduction has 0 active items or value `0`, or scalar result is `0` / `FALSE` / `NULL`. |
| `1` | `0x0002` | **`ST`** | `1` when `OP_STABLE_CHECK`, `OP_WALK.*_fixpoint_*`, or `OP_LANE_WALK.*_fixpoint_*` reaches convergence. |
| `2` | `0x0004` | **`NF`** | `1` when a scalar-producing instruction writes Kleene `NULL` (`r_valid_mask[dst] == 0`). |

### 4.3 Variable-Stride Sliding Register Windows & Exact Spill Capacity

Backed inside the caller-owned workspace (`r_stack[256]`, `f_desc_stack[128]`, `v_desc_stack[128]`, `spill_slots[256]`) and a 16-deep call stack:

- **Exact Spill Quota**: Each call frame owns **`16` frame-local spill slots** (`slot` $\in 0..15$). With `MAX_CALL_DEPTH = 16`, `16 × 16 = 256` slots matches `spill_slots[256]` exactly — `spill_base` can never prematurely overflow before `call_depth == 16`.
- **`OP_CALL` (`0x12`)**: Checks `call_depth < hdr.max_call_depth` (`<= 16`) and `base + stride + 16 <= cap`. Flushes caller `[0..stride-1]` (including `r_valid_mask` bits and `r_type_word` nibbles) to the window stack, shifts caller `[stride..15]` into callee `[0..15-stride]`, resets newly exposed callee slots `[16-stride..15]` to `NULL`/`uninitialized`, advances `spill_base += 16`, and pushes `(return_pc, r_stride, f_stride, v_stride)`.
- **`OP_RET` (`0x13`)**: Deterministically releases all `F`/`V` descriptors in callee-local slots `[16-stride..15]` and the callee's 16 spill slots back to the workspace slab/bump freelist (RAII), decrements `spill_base -= 16`, restores caller `[0..stride-1]`, and jumps to `return_pc`.

---

## 5. Caller-Owned Zero-Allocation Workspace, 3-Tier Frontiers & Static Memory Bounding

### 5.1 Two-Buffer Caller Ownership Contract (Zero `malloc`/`free` in Kernel)

Compiled `.impb` plans and memory-mapped `.imps` snapshots are **100% immutable and stateless** (`oneDNN` `scratchpad_mode::user` model), allowing arbitrary worker threads to execute the same plan concurrently with zero locks. Callers supply **two** aligned byte slices:

```c
// 1. Placement-initialize a caller-owned 128B-aligned scratch buffer ONCE per worker thread.
//    No destructor required: caller frees/drops scratch_buf whenever desired.
IMPULSE_API impulse_vm_status_v11_t impulse_workspace_init(
    void*  scratch_buf,        // Must be 128-byte aligned
    size_t scratch_bytes,
    impulse_vm_workspace_v11_t** out_ws
);

// 2. Static AOT memory planner (O(|code|) CFG liveness + kernel scratch bound).
typedef struct {
    size_t min_scratch_bytes;         // Minimum fixed frame + morsel TLS + 1 Tier-1 page table
    size_t guaranteed_scratch_bytes;  // Exact worst-case peak: GUARANTEED never to return ERR_BUFFER_OVERFLOW
    size_t max_result_bytes;          // Upper bound on terminal OP_COLLECT outputs
} impulse_vm_memory_plan_t;

IMPULSE_API impulse_vm_status_v11_t impulse_vm_plan_memory(
    const void* impb_bytes, size_t impb_len,
    const impulse_snapshot_t* snapshot,
    uint16_t max_dop,
    impulse_vm_memory_plan_t* out_plan
);

// 3. Zero-allocation hot-path execution (noexcept, malloc-free, syscall-free).
IMPULSE_API impulse_vm_status_v11_t impulse_vm_execute_v11(
    const void* impb_bytes, size_t impb_len,
    const impulse_snapshot_t* snapshot,
    const impulse_vm_params_v11_t* params,
    impulse_vm_workspace_v11_t* scratch_ws,  // Per-worker reusable scratch (clobbered on exit)
    void*  result_buf,                       // Per-request 64B-aligned output buffer (OP_COLLECT)
    size_t result_cap,
    size_t* out_result_bytes
);
```

#### Enforced Workspace Invariants
1. **Strict Alignment**: Misaligned `scratch_buf` (`% 128 != 0`) or `result_buf` (`% 64 != 0`) immediately returns `IMPULSE_VM_ERR_INVALID_OPERAND` (`6`) — never internally re-allocates.
2. **Non-Reentrancy Guard (`Hyperscan` Rule)**: Entry executes atomic CAS `ws->in_use: 0 -> 1` (and `1 -> 0` on exit). Concurrent sharing of one `scratch_ws` across two threads fails deterministically with `IMPULSE_VM_ERR_INVALID_OPERAND` (`6`).
3. **Zero `memset` Reset via `epoch` Tagging (`Zstandard` Rule)**: `impulse_workspace_init` stamps `magic`, `capacity`, `in_use = 0`, `uint64_t frontier_epoch = 1`, and bump/freelist slab offsets once. Between queries, resetting the workspace increments `ws->frontier_epoch++` and resets the bump pointer in $O(1)$ (`0` bytes zeroed).
4. **Clobber-on-Exit & Fail-Fast Overflow**: `scratch_ws` contents are undefined after `execute()` returns; terminal `OP_COLLECT` buffers live strictly in caller `result_buf`. Exhausting either buffer deterministically returns `IMPULSE_VM_ERR_BUFFER_OVERFLOW` (`11`) with zero heap fallback.

### 5.2 Unified 3-Tier Adaptive `VmFrontier` (Zero-`memset` Tier 1 Directory)

Every frontier `F0..F15` is bound to `domain_id` (cardinality $N_d$) and `lane_width` $W \in \{1, 8, 16, 32, 64\}$:

| Tier ID | Name | Threshold ($N_d$, active nodes $\lvert F \rvert$) | Physical Layout Inside Caller `scratch_ws` | Footprint ($N_d = 10^8$) |
| :--- | :--- | :--- | :--- | :--- |
| `0` | **`EMPTY`** | $\lvert F \rvert = 0$ | Descriptor-only (`cached_card = 0`). | `0 B` |
| `1` | **`TIER0_INLINE`** | $1 \le \lvert F \rvert \le 64$ ($W=1$) or $\le 32$ `(node, lane_u64)` pairs | Sorted inline array in pre-carved 512B descriptor block (`uint64_t ids[64]`). | `512 B` |
| `2` | **`TIER1_PAGED`** | $\lvert F \rvert > 64$ **and** `dirty_pages < min(256, 0.25 * total_pages)` | **Fixed `4 KB` open-addressed page map** (`512` slots of `(page_id: u32, slab_slot: u32)` guarded by a **`64-byte` occupancy bitmask** `uint64_t occ[8]`, zeroed in 1 cache line on init!) + 4K-node pages carved from `scratch_ws` slab freelist (`512 B`/page for $W=1$; $4096 \times (W/8)$ B/page for multi-lane) + `dirty_pages[]`. | `4 KB` dir + `dirty_pages × 512 B` ($\le$ `132 KB` for $W=1$!) |
| `3` | **`TIER2_DENSE`** | `slab_bytes >= 0.25 * B_dense(d, W)` or `dirty_pages >= 256` or $N_d \le 4096$ | Contiguous 128B-aligned flat array (`ceil(N_d/64)` words for $W=1$, or `uintW_t[N_d]`) + **`L1` summary bitset** (1 bit per 4096 nodes). | `12.5 MB` ($W=1$) + `3.1 KB` `L1` |
| `4` | **`ALL_SPAN`** | $\lvert F \rvert = N_d$ (`OP_INIT_DOMAIN_SPAN`) | Descriptor-only (`cached_card = N_d`). Materializes lazily only if mutated. | `0 B` |

#### Why the `4 KB` (`64B`-Masked) Tier 1 Directory Eliminates Bloat & `memset` Stalls
1. **Zero `O(N_d / 4096)` Directory Bloat**: Even at $N_d = 10^9$, initializing a Tier 1 frontier on raw caller memory zeros **only `64 bytes`** (`occ[8]`), never `977 KB`.
2. **No Tier-1 Bloat Inversion**: Gating Tier 1 $\to$ Tier 2 promotion on **`slab_bytes >= 0.25 * B_dense(d, W)`** (or `256` pages) guarantees Tier 1 never exceeds `25%` of Tier 2 even under adversarial stride-4096 scatter, bounding transient promotion peak to `1.25 × B_dense` (and `impulse_vm_plan_memory` reserves 1 shared promotion slack across the workspace).
3. **Degree Pre-Sizing & Hoisted Dispatch**: `OP_WALK` pre-sizes `F[dst]` directly to `TIER2_DENSE` when edge volume $M_{\text{upper}}$ warrants it and hoists `(SrcTier, DstTier)` dispatch outside inner edge loops.

### 5.3 Lazy Cardinality Memoization (`cached_card = -1`)

- `OP_FSEED`, `OP_INIT_DOMAIN_SPAN`, `TIER0_INLINE` dedup, and word-streaming ops (`OP_SET_OP`, `OP_SET_COMPLEMENT`, `OP_NODE_FILTER`, Pull `OP_WALK`) populate `cached_card` opportunistically in registers at ~0 extra cycles.
- Push `OP_WALK` / `OP_WALK_FILTERED` / `OP_MORSEL_COMMIT.yield_frontier` set `cached_card = 0, ZF = 1` in $O(1)$ if 0 edges hit, else `cached_card = -1, ZF = 0`.
- `OP_SET_CARDINALITY` returns `cached_card` in 1 cycle if `>= 0`, else computes SIMD `vpopcntq` over `dirty_pages[]` (Tier 1) or `L1`-active 512B blocks (Tier 2) and memoizes `cached_card`.

### 5.4 Static Memory Bounding Formula (`impulse_vm_plan_memory`)

`impulse_vm_plan_memory` computes `guaranteed_scratch_bytes` in $O(\lvert P \rvert)$ via CFG register-liveness interference coloring (like `TFLite Micro` / Rust `faer` `StackReq`):
1. **Fixed Frame & Stacks**: `256 B` VM state + `ws` header + `(hdr.max_call_depth + 1)` window/spill stack frames + `max_dop × 133 KB` L1 morsel scratchpads (`M0..M7`, `MF0..MF7`).
2. **Peak Simultaneously Live `F` & `V` Registers**:
   - Each live `F` slot on domain $d$ contributes $\le B_{\text{dense}}(d, W)$ (+ `1` shared `0.25 × max_d B_dense` promotion slack).
   - `OP_LOAD_COLUMN` and `OP_LOAD_CONST_POOL` contribute **`0 B`** unless statically mutated by `OP_VEC_POINT.vec_set` or `.accum` (COW).
   - `OP_VEC_INIT` has exact static length (`imm32` or $N_d$); `OP_SAMPLE_NEIGHBORS.vec_wr` is forbidden in CFG loop SCCs so its acyclic output length is statically exact (`len_in * k`).
3. **Transient Kernel Scratch (`StackReq::any_of` max across instructions)**:
   - Parallel `OP_SPMV` (Push) & `OP_MORSEL_COMMIT.scatter_*` (`max_dop > 1`): **2-phase radix-partitioned L2 morsel buckets = `max_dop × 32 KB`** ($O(1)$ in $N_d$ — never `max_dop × N_d × 8 B`!).
   - `OP_GRAPH_KERNEL`: `.cc_afforest` = `0 B` extra (2-pass in-place min-ID root canonicalization inside `V[dst]`); `.kcore_*` = `16 N_d` bytes (`deg`, `vert`, `pos`, `bin`); `.tri_count_*` = `8 N_d + max_dop × ceil(N_d / 8)` bytes.

---

## 6. CEL Compilation, Branchless Kleene 3VL & 64-Bit `StringView` Handles

### 6.1 Branchless Dual-Bitmask Kleene 3VL (`d <= v`)

Every `BOOL_3VL` vector stores `(valid, data)` bitmasks with canonical invariant `data & ~valid == 0`: `NULL = (0,0)`, `FALSE = (1,0)`, `TRUE = (1,1)`.
- **Comparison (`EQ..GE`, including `NE`)**: `v = vA & vB`; `d = v & raw_cmp(A, B)` (`NULL != 5` $\to$ `NULL`, never `TRUE`).
- **`NOT(A)`**: `v = vA`; `d = vA & ~dA`.
- **`AND(A, B)`**: `d = dA & dB`; `v = (vA & vB) | (vA & ~dA) | (vB & ~dB)` (`FALSE && NULL == FALSE`).
- **`OR(A, B)`**: `d = dA | dB`; `v = (vA & vB) | d` (`TRUE || NULL == TRUE`).
- **Frontier Collapse (`SET_CONVERT.b2f`)**: `frontier_bits = dA` (0 instructions!).

### 6.2 Two-Tier CEL Lowering & Multi-Sink Lexical Morsels

1. **Tier A (Pushdown)**: Atomic node predicates $\to$ `OP_NODE_FILTER` / `OP_INDEX_SCAN`; atomic edge predicates $\to$ `OP_WALK_FILTERED`; algebraic path reductions $\to$ `OP_SPMV`.
2. **Tier B (Lexical Morsels)**: Multi-clause/cross-endpoint CEL compiles to `OP_WALK_MORSEL` / `OP_FILTER_MORSEL .. OP_MORSEL_END` with exponential ramp `32 -> 256 -> 2048` on `max_dop == 1`, forward-only `OP_JCC.jempty_f MF0, +skip` short-circuits, and `1+` `OP_MORSEL_COMMIT` sinks in a single CSR pass.

### 6.3 String Representation: 16-Byte Vector `StringView` vs 64-Bit Scalar `imp_str_handle_t`

- **Vector String Columns (`V` bank)**: 16-byte German-style `StringView` (`[uint32_t byte_len, uint32_t prefix4_be, uint64_t pool_offset]` referencing `.imps` Section 2 Shared String Table). `prefix4_be` (big-endian UTF-8, zero-padded right) resolves $>95\%$ of `EQ`/`NE`/`LT`..`GE`/`STARTS_WITH` in registers without dereferencing `pool_offset`.
- **Scalar String Registers (`R0..R15`, `SCALAR_STR_HANDLE = 5`)**: Exact 64-bit `imp_str_handle_t` (`[source_tag:2 (bits 63..62) | payload:62 (bits 61..0)]`):
  - `source_tag = 0b00`: `bits 61..52` = `10-bit snap_idx` (`0..1023` mounted `.imps` file in a `FederatedSnapshotView`; `0` for single-snapshot execution), `bits 51..0` = `52-bit byte_offset` (up to `4 PB` per `.imps`) into Section 2 Shared String Table.
  - `source_tag = 0b01`: 62-bit entry offset into `.impb` Constant Pool string table.
  - `source_tag = 0b10`: 62-bit index into host `VmQueryParams` string parameter array.
  - `source_tag = 0b11`: **Inline Short String** (`<= 7` UTF-8 bytes): bits `61..59` = `byte_len` (`0..7`), bits `58..56` = `0` (MBZ), bits `55..0` = `bytes[0..6]` zero-padded (zero memory dereference for short literals like `"ACTIVE"`, `"USD"`, `"US"`!).

---

## 7. Multi-Threaded Determinism, Two-Tier FP Policy & Fuel Accounting

1. **Two-Tier Floating-Point Determinism Policy**:
   - **Exact `0-ULP` Bit-Identity (`75` of `78` active opcodes + all special values)**: Every integer, frontier, 3VL, `StringView`, `OP_SPMV`, `OP_GRAPH_KERNEL`, `OP_SAMPLE_NEIGHBORS`, `OP_TOP_K`, `OP_SCALAR_FP_ALU`, `0x48 OP_VEC_MATH_ARITH`, `0x4D OP_VEC_TERNARY`, `0x52 OP_VEC_REDUCE`, `0x6A OP_VECTOR_RERANK`, `0x6B`–`0x6E` `OP_LANE_STATE_*`, and `0x6F OP_VECTOR_POOL` executes to **0-ULP exact IEEE-754 bit-identity** across all 4 engines (verified by `ICTX v2` `logical_hash`), using fixed 64-element pairwise tree-sums (`f64`), 2-phase deterministic radix scatter-reduction, lowest-ID tie-breaking, and universal `NaN -> NULL` canonicalization.
   - **Full-Speed SIMD Transcendentals (`0x49`, `0x4A`, `0x4B` `sigmoid`/`gelu`/`silu`/`softplus`)**: Engines use native SIMD vector math (`SLEEF u10` / `SVML` / `vForce` / Java 25 `DoubleVector.lanewise`) subject to **`<= 1.0 ULP`** (`exp`/`log`/`sin`/`cos`/`tanh`/`cbrt`/`hypot`/`erf`/`erfc`) and **`<= 2.0 ULP`** (`pow`/`lgamma`/`gelu`/`silu`/`softplus`), plus **exact 0-ULP agreement on all special values** (`±0.0`, `±Inf`, `NaN -> NULL`, poles, clamping thresholds).
2. **Deterministic Connected Components & PRNG**: `.cc_afforest` runs 2-pass in-place min-ID canonicalization; `OP_SAMPLE_NEIGHBORS` uses stateless SplitMix64 + Floyd's $O(k)$ selection.
3. **Normative Fuel / Gas Accounting (`ws->gas_remaining`)**:
   - Decremented by **`1`** prior to executing each top-level instruction word (`pc`) and by **`1`** per morsel slice inside `OP_WALK_MORSEL` / `OP_FILTER_MORSEL` (independent of `max_dop` because morsel count is deterministic in CSR order!).
   - When `gas_remaining == 0` before dispatch, execution halts immediately with `IMPULSE_VM_ERR_GAS_EXHAUSTED` (`13`) at the exact current `pc`.

---

## 8. Static Load-Time Bytecode Verifier (`impulse_vm_validate`)

Runs in $O(\text{code\_words})$ before execution:
1. **Opcode, Subop, Flag & MBZ Check** (`ERR_INVALID_OPCODE` / `ERR_INVALID_OPERAND`).
2. **128-Bit `0xFF` Extension Pairing** (`FLAG_EXTENDED` $\iff$ `pc+1` is `0xFF`; no stray `0xFF`).
3. **CFG Branch Bounds & Self-Loop Rejection** (`0 <= target < len`, `target != pc`, `bytecode[target].opcode != 0xFF`).
4. **Static Memory Safety Checks**:
   - Verifies `OP_CALL` DAG depth $\le$ `hdr.max_call_depth` (`<= 16`).
   - Rejects `0x39 OP_SAMPLE_NEIGHBORS.vec_wr` (`subop = 1`) if `V[dst]` feeds back into any CFG strongly connected component (loop cycle).
5. **Lexical Morsel Well-Formedness & Race-Freedom**:
   - Non-nested symmetric `hdr_pc + imm16_hi == end_pc`; no forbidden ops; forward-only intra-morsel jumps using register/morsel `JCC` (`subop 6..9`) only.
   - Body ops write strictly `dst >= 8` (`MF0..MF7` / `M0..M7`); `OP_MORSEL_COMMIT` writes strictly `dst < 8`, reads `s1 >= 8` (and `s2 >= 8` when `!FLAG_SCALAR_RHS`), never aliases `hdr.s1` / `hdr.s3`, and never mixes conflicting monoids on the same `(bank, dst)`.
   - Inside `OP_FILTER_MORSEL`, reading `M1` or `M2` before assignment is rejected.

---

## 9. Engine Dispatch & JIT Implementation Guidance (C++20 & Java 25)

The 78-opcode / `subop:4` layout optimizes wire density and cache locality, but high-frequency hot paths MUST NOT mirror 2-level `(opcode, subop)` switching literally:

1. **C++20 (Clang Threaded `goto` & MSVC `switch`)**:
   - During `impulse_vm_validate`, pre-decode hot `(opcode, subop)` pairs into a flat `uint16_t dense_op` (`~260` entries, `~2.1 KB` jump table in L1d) to collapse Clang threaded dispatch to **1 indirect jump** with per-subop BTB history.
   - Keep `0xFF` out of explicit `switch` labels on MSVC (let `default:` trap it) so the jump table spans `0x00..0x6A` densely.
   - Inline **only** trivial scalar/control ops (`0x00`–`0x14`, `MOV`, `SWAP`) inside `execute()`; mark all coarse-grained kernels (`OP_WALK`, `OP_SPMV`, `OP_VEC_*`, `OP_LANE_*`, `OP_GRAPH_KERNEL`) `[[noinline]]` / `__declspec(noinline)` so the dispatch loop stays $\le 8\text{ KB}$ in L1i without spilling `pc`/`ws`.
2. **Java 25 (`MethodHandle` Combinators & HotSpot C2)**:
   - Resolve static `(opcode, subop, flags)` **at combinator-build time** directly to tiny monomorphic leaf methods (`< 35–325` bytes of bytecode, below C2's `FreqInlineSize = 325` cliff) rather than passing `(subop, flags)` into a monolithic switch method.
   - Bind morsel bodies to flat leaf MH chains (keeping heavy graph kernels out-of-line as independently C2-compiled loops), allowing C2 to emit straight-line SIMD machine code with zero dispatch branches.
