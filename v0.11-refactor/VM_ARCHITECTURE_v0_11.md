# ImpulseVM v0.11.0 Virtual Machine Architecture Specification

> **Normative Draft (`v0.11.0-ISA-Refactor`)**
> Defines the binary instruction encoding, split register banks, C-ABI execution state layout, variable-stride sliding windows, 3-tier adaptive frontier engine, branchless Kleene 3VL algebra, lexical morsel execution model, and static load-time verifier (`impulse_vm_validate`).

---

## 1. Universal 64-Bit Nibble-Encoded Instruction Format

### 1.1 Primary 64-Bit Instruction Word (Little-Endian)

Every `impOps` v0.11.0 instruction occupies one 8-byte aligned 64-bit word (`uint64_t`), except 64-bit literal loads (`OP_LOAD_CONST.b64`) which set `FLAG_EXTENDED` (`0x80` in Byte 1) and consume two consecutive 64-bit words (`16` bytes).

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
| **Byte `1`** | `w[15:8]` | `flags:4` (`w[15:12]`) | `subop:4` (`w[11:8]`) | 4 global modifier flags + 4-bit sub-operation selector (`0..15`). |
| **Byte `2`** | `w[23:16]` | `dst:4` (`w[23:20]`) | `s1:4` (`w[19:16]`) | Destination register (`0..15`) + primary source register (`0..15`). |
| **Byte `3`** | `w[31:24]` | `s2:4` (`w[31:28]`) | `s3:4` (`w[27:24]`) | Secondary source (`0..15`) + tertiary source / mask register (`0..15`). |
| **Bytes `4..5`** | `w[47:32]` | — | — | `imm16_lo` (`rel_id`, `domain_id`, `param_id`, `k`, or low half of `imm32`). |
| **Bytes `6..7`** | `w[63:48]` | — | — | `imm16_hi` (`attr_id`, `rel2_id`, `morsel_end_off`, or high half of `imm32`). |

> [!IMPORTANT]
> **Must-Be-Zero (MBZ) Unused Field Rule**: Any register nibble (`dst`, `s1`, `s2`, `s3`) or immediate half (`imm16_lo`, `imm16_hi`, `imm32`) not consumed by an opcode + `(flags, subop)` combination **MUST be encoded as `0`**. The static verifier (`impulse_vm_validate`) and runtime contract checker reject non-zero unused fields with `IMPULSE_VM_ERR_INVALID_OPERAND` (`6`), eliminating covert/undefined encodings and ensuring canonical binary reproducibility.

### 1.2 128-Bit Extended Word (`FLAG_EXTENDED` + `0xFF OP_EXTENSION_PAYLOAD`)

When `FLAG_EXTENDED` (`flags` bit `3`, i.e. `0x8` in `flags:4` / `0x80` in Byte `1`) is set on Word 1 at `bytecode[pc]`, the instruction spans `bytecode[pc]` and `bytecode[pc + 1]`, and normal fallthrough advances `pc` by `2`.

```text
Word 1 (pc):     [ imm32_lo (32b)          | s2:4 | s3:4 | dst:4 | s1:4 | 1xxx:4 | subop:4 | opcode:8 ]
Word 2 (pc + 1): [ imm32_hi (32b)          |         ext_meta24 (24b, MBZ)                  | 0xFF     ]
```

* **64-Bit Constant Reconstruction**:
  `uint64_t imm64 = ((uint64_t)imp_v11_imm32(w2) << 32) | (uint64_t)imp_v11_imm32(w1);`
* **Why `0xFF` in Byte 0 of Word 2 Is Invariant**:
  In v0.10.0, 64-bit constants occupied all 64 bits of Word 2 raw, meaning Byte 0 of Word 2 was an arbitrary data byte (`imm64 & 0xFF`). A wild jump into `pc + 1` could therefore execute arbitrary float/int bytes as a valid opcode! In v0.11.0, Word 1 already carries `imm32_lo` in Bytes `4..7`, so Word 2 only needs Bytes `4..7` for `imm32_hi`, leaving Byte `0` permanently pinned to `0xFF` (`OP_EXTENSION_PAYLOAD`) and Bytes `1..3` (`ext_meta24`) MBZ. Any jump targeting `pc + 1` is statically rejected by `impulse_vm_validate` and traps at runtime with `IMPULSE_VM_ERR_VALIDATION_FAILED` (`15`).

### 1.3 Bytecode Container Header (`.impb` v0.11)

Standalone `.impb` binary programs prepend a 32-byte header (64-bit aligned) ahead of `bytecode[0]` and the read-only Constant Pool:

| Offset | Type | Field | Description |
| :--- | :--- | :--- | :--- |
| `0..3` | `uint32_t` | `magic` | `0x494D5042` (`'IMPB'`, little-endian). |
| `4..5` | `uint16_t` | `isa_version` | `0x000B` (`11` for v0.11.0). |
| `6..7` | `uint16_t` | `header_flags` | Bit `0`: `HAS_CONST_POOL`; Bits `1..15`: MBZ. |
| `8..11` | `uint32_t` | `code_word_count` | Number of 64-bit words in the instruction stream. |
| `12..15` | `uint32_t` | `const_pool_bytes` | Byte length of the trailing 8-byte-aligned Constant Pool section. |
| `16..19` | `uint32_t` | `entry_pc` | Initial `pc` word offset (typically `0`). |
| `20..23` | `uint32_t` | `required_domains` | Minimum domain count expected in bound `.imps` snapshot (`0` = pure compute). |
| `24..31` | `uint64_t` | `program_xxh3_64` | XXH3-64 checksum over `bytecode` + `const_pool`. |

---

## 2. The Four Universal Modifier Flags (`flags:4`)

Byte `1` bits `7..4` (`flags:4`) have **fixed, universal meanings across the entire ISA**. Individual opcodes declare an `allowed_flags_mask` (`4`-bit mask); setting any disallowed flag bit triggers `IMPULSE_VM_ERR_INVALID_OPERAND` (`6`) at validation time.

| Flag Bit (`flags:4`) | Byte `1` Mask | ImpAsm Suffix | Name | Universal Semantics |
| :--- | :--- | :--- | :--- | :--- |
| `0x8` (Bit 3) | `0x80` | `.ext` | `FLAG_EXTENDED` | Instruction consumes `2` 64-bit words (`Word 2` Byte `0 == 0xFF`); `pc` advances by `+2`. Permitted only on `OP_LOAD_CONST` (`subop=4` `B64`). |
| `0x4` (Bit 2) | `0x40` | `.accum` | `FLAG_ACCUM` | **Monoid / Set Accumulate into `dst`**: instead of overwriting `dst`, merges the instruction's output into the pre-existing `dst` value (`F[dst] \|= out` for frontiers; `V[dst] = V[dst] \oplus out` using the instruction's monoid for `OP_SPMV`, `OP_VEC_MATH_ARITH`). Requires `dst` to be already initialized in the same domain/type. |
| `0x2` (Bit 1) | `0x20` | `.scalar` | `FLAG_SCALAR_RHS` | **Scalar RHS Broadcast**: switches source nibble `s2` (and `s3` on `BETWEEN` / scalar-range ops) from vector/frontier bank `V[s2]`/`F[s2]` to scalar register `R[s2]` (broadcasting both the 64-bit value `R[s2]` and its validity bit `(r_valid_mask >> s2) & 1`). |
| `0x1` (Bit 0) | `0x10` | `.mask` | `FLAG_MASKED_S3` | **Frontier Mask / Exclude on `s3`**: activates nibble `s3` as a conditioning frontier `F[s3]` (or morsel mask `MF[s3 & 7]` inside a morsel block):<br>• On `OP_WALK`, `OP_WALK_FILTERED`, `OP_WALK_2HOP`, `OP_WALK_MORSEL`, `OP_LANE_WALK`: **Exclude mask** (`output \ F[s3]`), fused into Beamer Pull target skipping and Push bitset clearing.<br>• On `OP_SPMV`, `OP_GATHER_*`, `OP_VEC_*`, `OP_VEC_REDUCE`, `OP_TOP_K`, `OP_COLLECT`, `OP_VECTOR_ANN_SEARCH`, `OP_VECTOR_RERANK`: **Active selection mask** (restricts evaluation/reduction/output to active indices in `F[s3]`). |

---

## 3. Split `3 × 16` Register Architecture & Lexical Morsel Aliasing

### 3.1 Three Statically Typed Register Banks

Each 4-bit register nibble (`0..15`) addresses one of three disjoint architectural banks determined **statically** by `(opcode, flags, subop)`:

| Bank | Architectural Names | Backing Representation | Domain & Nullability Tracking |
| :--- | :--- | :--- | :--- |
| **Scalar Bank (`R`)** | `R0` .. `R15` | `uint64_t r_regs[16]` + `uint16_t r_valid_mask` | Untagged 64-bit values (`i64`, `u64`, IEEE-754 `f64`, or `StringView` pool handle). Bit `i` of `r_valid_mask` is `1` when valid and `0` when Kleene `NULL` (`r_regs[i]` canonicalized to `0` whenever bit `i == 0`). |
| **Frontier Bank (`F`)** | `F0` .. `F15` | `impulse_frontier_desc_v11_t f_regs[16]` (`16` bytes/slot) | Bound to explicit `uint16_t domain_id` (`AGENTS.md` §3.14), `uint8_t tier` (`EMPTY`, `TIER0_INLINE`, `TIER1_PAGED`, `TIER2_DENSE`, `ALL_SPAN`), `uint8_t lane_width` (`1`, `8`, `16`, `32`, `64`), `int64_t cached_card` (`-1` = unknown), and pool handle. |
| **Vector Bank (`V`)** | `V0` .. `V15` | `impulse_vec_desc_v11_t v_regs[16]` (`16` bytes/slot) | Typed off-heap vector slice (`I64`, `U64`, `I32`, `U32`, `F64`, `F32`, `BOOL_3VL`, `STR_VIEW`), bound to `domain_id` (or `0xFFFF` for unanchored/morsel vectors), `uint64_t length`, data pointer/handle, and optional Arrow validity bitmap pointer (`NULL` ptr = all-valid fast path). |

#### Elimination of Runtime `VALIDATE_REG` and `register_types[64]`
1. **Zero Bounds Checks**: A 4-bit nibble only encodes values `0..15`. Register array indexing `state->r_regs[idx]` cannot overflow a 16-element array by hardware representation.
2. **Zero Tag Dispatch**: Because bank identity is fixed in the opcode contract and element types (`F32` vs `F64` vs `I64`) are either statically verified from `.imps` schema metadata at load time or stored once in `v_regs[i].elem_type` outside inner loops, no per-instruction `register_types[]` tag write occurs.

### 3.2 Lexical Morsel Register Aliasing (`MF0..MF7` & `M0..M7`)

Inside a lexical morsel block (`0x35 OP_WALK_MORSEL` or `0x36 OP_FILTER_MORSEL` through `0x38 OP_MORSEL_END`), each worker thread owns a private L1-resident morsel scratchpad (`MORSEL_MAX = 2048` lanes; `2048 × 8B = 16 KB` per vector, `256 B` per bitmask).

Rather than introducing a fourth register bank or burning a modifier flag, v0.11 partitions the 4-bit `F` and `V` address space inside morsel blocks:

| Nibble Value | `F` Bank Meaning Inside Morsel | `V` Bank Meaning Inside Morsel | Access Permission Inside Morsel |
| :--- | :--- | :--- | :--- |
| **`0 .. 7`** | Outer domain frontiers `F0..F7` | Outer domain vectors `V0..V7` | **Read-Only** during morsel body (`GATHER_VEC`, `SET_CONTAINS`); **Commit-Only** via `OP_MORSEL_COMMIT` (`dst` $\in 0..7$). |
| **`8 .. 15`** | Thread-private morsel masks **`MF0..MF7`** | Thread-private morsel vectors **`M0..M7`** | **Read/Write** thread-private SIMD lanes (`len = morsel_len <= 2048`). |

#### Pre-Populated Morsel Hardware Inputs at Block Entry

| Morsel Alias | Nibble | Populated by `OP_WALK_MORSEL` | Populated by `OP_FILTER_MORSEL` | Element Type |
| :--- | :--- | :--- | :--- | :--- |
| **`MF0`** | `8` (`F8`) | Active edge mask (`[0..morsel_len)` = `1`) | Active node mask (`[0..morsel_len)` = `1`) | 1-bit morsel mask (`4 × uint64_t` per 256 lanes, up to `32 × uint64_t`) |
| **`M0`** | `8` (`V8`) | `src_id` (dense ID in `SrcDomain`) | `node_id` (dense ID in `F[s1].domain_id`) | `U32` or `U64` (matching domain width, zero-extended on gather) |
| **`M1`** | `9` (`V9`) | `tgt_id` (dense ID in `TgtDomain`) | Uninitialized | `U32` or `U64` |
| **`M2`** | `10` (`V10`) | `edge_idx` (CSR/CSC/COO physical edge offset) | Uninitialized | `U64` |
| **`M3`** | `11` (`V11`) | `lane_mask` (propagating `u64` lanes if `F[s1]` is multi-lane, else `1`) | `lane_mask` (node's `u64` lanes if `F[s1]` is multi-lane, else `1`) | `U64` |
| **`M4..M7`**, **`MF1..MF7`** | `12..15` / `9..15` | Scratch vectors / predicate masks | Scratch vectors / predicate masks | Assigned by morsel body ops |

---

## 4. C-ABI Execution State Frame & Sliding Register Windows

### 4.1 Hot Execution Frame (`impulse_vm_state_v11_t` — 256 Bytes, 4 Cache Lines)

The active architectural state frame is 64-byte aligned and exactly **256 bytes** (down from 640 bytes in v0.10.0), matching C++20, Rust `#[repr(C, align(64))]`, and Java 25 FFM `MemorySegment` layouts byte-for-byte:

```c
typedef struct IMPULSE_ALIGN(64) {
    // --- Cache Line 0 (Bytes 0..63): Control, Flags & Scalar Bank R0..R4 ---
    uint32_t pc;                     // [0..3]   Current instruction word index
    uint16_t vm_flags;               // [4..5]   Bit 0: ZF, Bit 1: ST, Bit 2: NF (bits 3..15 MBZ)
    uint16_t r_valid_mask;           // [6..7]   16-bit Kleene validity mask for R0..R15 (1=valid, 0=NULL)
    uint16_t call_depth;             // [8..9]   Active call stack depth (0..16)
    uint16_t max_dop;                // [10..11] Active intra-query degree of parallelism (1..host_max)
    uint16_t r_win_base;             // [12..13] Sliding window base in context->r_stack[]
    uint16_t fv_win_packed;          // [14..15] (f_win_base << 8) | v_win_base
    impulse_vm_context_v11_t* ctx;   // [16..23] Pointer to off-heap VmQueryContext (pools, backing stacks, snapshot)
    uint64_t gas_remaining;          // [24..31] Remaining instruction/edge execution budget (UINT64_MAX = unlimited)
    uint64_t r_regs[4];              // [32..63] R0..R3 hot scalar registers

    // --- Cache Line 1 (Bytes 64..127): Scalar Bank R4..R11 ---
    uint64_t r_regs_4_11[8];         // [64..127] R4..R11 (contiguous with r_regs[0..3] as uint64_t r_regs[16]!)

    // --- Cache Line 2 (Bytes 128..191): Scalar Bank R12..R15 + Frontier Handle Table F0..F7 ---
    uint64_t r_regs_12_15[4];        // [128..159] R12..R15
    uint32_t f_handles[8];           // [160..191] F0..F7 compact descriptor slot IDs

    // --- Cache Line 3 (Bytes 192..255): Frontier F8..F15 + Vector Handle Table V0..V15 ---
    uint32_t f_handles_8_15[8];      // [192..223] F8..F15 compact descriptor slot IDs
    uint16_t v_handles[16];          // [224..255] V0..V15 compact descriptor slot IDs
} impulse_vm_state_v11_t;
```

*(Note: In C/C++, `r_regs` is declared as a single contiguous `uint64_t r_regs[16]` at byte offset `32..159`, `f_handles` as `uint32_t f_handles[16]` at `160..223`, and `v_handles` as `uint16_t v_handles[16]` at `224..255`; split above solely to illustrate exact 64-byte cache-line boundaries.)*

### 4.2 Condition Flags (`vm_flags`)

v0.11 retires the dead `LT`, `GT`, `EQ` flags from v0.10 (which were set by 0 of 166 opcodes) and defines three orthogonal status bits:

| Bit | Mask | Name | Meaning |
| :--- | :--- | :--- | :--- |
| `0` | `0x0001` | **`ZF`** (Zero / Empty / False) | `1` when an output frontier is empty, a reduction has 0 active items or value `0`, or a scalar op produces `0` / `FALSE` / `NULL`. |
| `1` | `0x0002` | **`ST`** (Stable / Converged) | `1` when `OP_STABLE_CHECK`, `OP_WALK.*_FIXPOINT_*`, or `OP_LANE_WALK.*_FIXPOINT_*` reaches convergence. |
| `2` | `0x0004` | **`NF`** (Null Flag) | `1` when a scalar-producing instruction (`OP_LOAD_PARAM`, `OP_SCALAR_*`, `OP_VEC_REDUCE`, `OP_VEC_POINT.vec_get`) writes Kleene `NULL` (`valid == 0`) into `R[dst]`. |

### 4.3 Variable-Stride Sliding Register Windows & Deterministic RAII Pool Release

Empirical analysis of all 505 `.impas` programs shows `p90 = 9` registers and `p99 = 22` registers. For subroutines and compiler-generated plans exceeding 16 registers in a bank, `ImpulseVM` v0.11 provides **SPARC/Itanium-style variable-stride sliding register windows** backed by `ctx` arrays (`r_stack[256]`, `f_desc_stack[128]`, `v_desc_stack[128]`, `spill_slots[256]`) and a 16-deep call frame stack:

1. **`OP_CALL` (`0x12`)**:
   - Encodes independent window strides `r_stride = s1` (`0..15`), `f_stride = s2` (`0..15`), `v_stride = s3` (`0..15`), or `16` across all banks when `subop == 1` (`FULL_WINDOW_16`).
   - Checks `call_depth < 16` and `base + stride + 16 <= stack_cap` (else returns `IMPULSE_VM_ERR_STACK_OVERFLOW`).
   - Flushes caller slots `[0 .. stride - 1]` to the backing window stack and shifts the active window by `+stride`.
   - **Zero-Copy Argument & Return Passing**: Caller registers `[stride .. 15]` automatically appear as callee registers `[0 .. 15 - stride]`! For example, `CALL r_stride=12` preserves `R0..R11` on the window stack while overlapping caller `R12..R15` directly onto callee `R0..R3` for arguments and return values — fixing v0.10's bug where `op_55_call.inc` overwrote `R0..R3` without saving them!
   - Records `(return_pc, r_stride, f_stride, v_stride, spill_base, pool_epoch)` on `ctx->call_frames[call_depth++]`.
2. **`OP_RET` (`0x13`)**:
   - **Deterministic RAII Slab Reclamation**: Every `F` or `V` descriptor in callee-local slots `[16 - f_stride .. 15]` / `[16 - v_stride .. 15]` (not shared with caller `[0 .. 15 - stride]`) automatically returns its leased Tier 1 slabs / Tier 2 bitsets / vector buffers to `ctx->pool` before decrementing `call_depth`!
   - Restores caller `[0 .. stride - 1]` from the backing window stack and jumps to `return_pc`.
3. **Intra-Procedure Spilling (`OP_SPILL` `0x0A` / `OP_RELOAD` `0x0B`)**:
   - Provides 64 frame-relative scratch slots (`imm16_lo` $\in 0..63$) per frame for flat giant kernels without requiring a subroutine call.

---

## 5. Three-Tier Adaptive `VmFrontier` & Lazy Cardinality Memoization

### 5.1 Unified 1-Bit and Multi-Lane Representation in `F0..F15`

Every frontier register `F0..F15` is bound to an explicit `domain_id` ($0 \dots D-1$, cardinality $N_d$) and a `lane_width` $W \in \{1, 8, 16, 32, 64\}$. Its physical storage dynamically inhabits one of three concrete tiers (plus two zero-allocation virtual states `EMPTY` and `ALL_SPAN`):

| Tier ID | Name | Threshold ($N_d$, active nodes $\lvert F \rvert$) | Physical Layout | Memory Footprint ($N_d = 10^8$) |
| :--- | :--- | :--- | :--- | :--- |
| `0` | **`EMPTY`** | $\lvert F \rvert = 0$ | Descriptor-only (`cached_card = 0`). | `0 B` |
| `1` | **`TIER0_INLINE`** | $1 \le \lvert F \rvert \le 64$ (for $W=1$) or $\le 32$ `(node, lane_u64)` pairs | Sorted inline array in pre-allocated 512B descriptor block (`uint64_t ids[64]`). | `512 B` (fits in 8 L1 lines) |
| `2` | **`TIER1_PAGED`** | $64 < \lvert F \rvert < \frac{N_d}{64}$ (1-bit) or active pages $< 25\%$ ($W \in \{8..64\}$) | Two-level **4096-node paged slab**: `uint32_t page_dir[ceil(N_d / 4096)]` (`0xFFFFFFFF` = empty page) + leased 4K-node pages (`512 B`/page for 1-bit; $4096 \times (W/8)$ bytes/page for multi-lane) + `uint32_t dirty_pages[]` list (`dirty_count`). | $\lvert F \rvert = 1000, W=64$: $\le 1000$ pages (typ. $10\text{–}200$ clustered pages = **`320 KB`–`6.4 MB` vs `800 MB`** in v0.10!). |
| `3` | **`TIER2_DENSE`** | $\lvert F \rvert \ge \frac{N_d}{64}$ (or $N_d \le 4096$) | Contiguous 128B-aligned flat array (`uint64_t words[ceil(N_d / 64)]` for $W=1$, or `uintW_t lanes[N_d]`) + **`L1` hierarchical summary bitset** (1 bit per 512B cache-line block = `4096` nodes for $W=1$). | `12.5 MB` ($W=1$) + `3.1 KB` `L1` summary. |
| `4` | **`ALL_SPAN`** | $\lvert F \rvert = N_d$ (`OP_INIT_DOMAIN_SPAN`) | Descriptor-only (`cached_card = N_d`). Materializes lazily only if mutated in-place. | `0 B` |

### 5.2 Zero-Regression Guarantees on Dense Traversals

To prevent per-edge `switch(tier)` overhead inside inner loops:

1. **Degree-Sum Output Pre-Sizing**: Before `OP_WALK` or `OP_LANE_WALK` begins iterating edges of `F[s1]`, it computes an upper bound on output edge volume $M_{\text{upper}}$ (exact $O(|F|)$ sum of `row_offsets[u+1] - row_offsets[u]` when `F[s1]` is `TIER0_INLINE`, or `dirty_count * 4096 * avg_deg` heuristic on `TIER1`).
   - If $M_{\text{upper}} \ge N_{\text{tgt}} / 64$ (or $N_{\text{tgt}} \le 4096$), `F[dst]` is **allocated directly in `TIER2_DENSE`** before the walk begins — zero mid-walk promotion or re-hashing!
   - If $M_{\text{upper}} \le 64$, `F[dst]` starts in `TIER0_INLINE` and executes a flat write + end-of-walk sort/dedup (`cached_card` becomes exact at the end of dedup!).
2. **Hoisted Template Dispatch**: Inner walk/filter kernels are instantiated over `(SrcTier, DstTier)` pairs *outside* the loop (`walk_csr<SrcTier1, DstTier2>(...)`). Inside `DstTier2`, edge scattering executes the identical raw `dst_words[v >> 6] |= (1ULL << (v & 63))` + `l1_summary[v >> 12] |= ...` loop as a flat bitset.
3. **Pool-Recycled Page Directories**: `page_dir[]` arrays (`97.6 KB` at $N_d = 10^8$) are leased from `ctx->pool` and reset in $O(\text{dirty\_count})$ by walking `dirty_pages[0..dirty_count)` (`page_dir[dirty_pages[i]] = 0xFFFFFFFFu`) — **never** `memset` over $N_d / 4096$ entries!

### 5.3 Lazy Cardinality Memoization (`cached_card = -1`)

Every `VmFrontier` descriptor carries `int64_t cached_card`:

| Producer Operation | `cached_card` Update Policy | Cost |
| :--- | :--- | :--- |
| `OP_FSEED`, `OP_INIT_DOMAIN_SPAN`, `TIER0_INLINE` sort-dedup | Exact (`0`, `1`, `N_d`, or `inline_len`). | **0 extra cycles** |
| Word-streaming ops (`OP_SET_OP`, `OP_SET_COMPLEMENT`, `OP_NODE_FILTER`, Pull `OP_WALK`) | Opportunistically accumulated via register `acc += popcnt64(out_word)` while each output word is already in an ALU/SIMD register. | **~0 extra cycles** (hidden under memory store bandwidth) |
| Scatter/Push ops (`OP_WALK` Push, `OP_WALK_FILTERED`, `OP_MORSEL_COMMIT.yield_frontier`) | If 0 edges committed: `cached_card = 0`, `ZF = 1` in $O(1)$. Otherwise: **`cached_card = -1`** (unknown; `ZF = 0` known immediately as soon as $\ge 1$ edge hits!). | **0 per-edge atomic/read-before-write overhead** |
| `OP_SET_CARDINALITY` (`0x24`) | If `cached_card >= 0`, returns `cached_card` in **1 cycle**. If `cached_card == -1`, runs AVX-512/NEON `vpopcntq` strictly over `dirty_pages[]` (Tier 1) or `L1`-active 512B blocks (Tier 2), stores `cached_card = count`, and returns `count`. | Lazy $O(\text{dirty\_blocks})$ SIMD scan once, amortized across subsequent reads |

> [!TIP]
> **Why `OP_DEGREE` + `OP_SET_CARDINALITY` Together Unlock True Beamer / Bidirectional BFS**: On power-law graphs, $|F|$ (`OP_SET_CARDINALITY`) does not predict edge work when 1 hub node has $10^6$ edges. Pairing `OP_DEGREE.sum_fwd_r` ($m_F = \sum_{u \in F} \deg^+(u)$) with `OP_SET_CARDINALITY` gives both exact node count and exact edge volume in $O(|F|)$.

---

## 6. CEL Compilation, Branchless Kleene 3VL & Lexical Morsel Execution

### 6.1 Branchless Dual-Bitmask Kleene Three-Valued Logic (3VL)

Every `BOOL_3VL` vector (`V` bank / morsel `M4..M7`) stores two 64-bit bitmasks per 64 lanes — `valid` ($v$) and `data` ($d$) — enforcing the **canonical invariant `d & ~v == 0`** (`d <= v`):

| Logical Value | `(valid, data)` | Invariant Check |
| :--- | :--- | :--- |
| **`NULL` (Unknown)** | `(0, 0)` | `(0, 1)` is **forbidden**; all ops maintain `data &= valid`. |
| **`FALSE`** | `(1, 0)` | Valid and false. |
| **`TRUE`** | `(1, 1)` | Valid and true. |

#### Exact 64-Way Branchless Bitwise Formulas (`uint64_t`)

1. **Comparison (`a cmp b`, including `NE` `!=`)**:
   - `v_out = v_a & v_b`
   - `d_out = v_out & raw_cmp_mask(a, b)`
   - *Crucial Bug Fix*: When `a` is `NULL` (`v_a = 0`), `a != 5` produces `v_out = 0, d_out = 0` (`NULL`), **never** `TRUE`!
2. **`NOT(a)`**:
   - `v_out = v_a`
   - `d_out = v_a & ~d_a`
   - Verification: `NOT(0,0) = (0,0)` (`NULL`); `NOT(1,0) = (1,1)` (`TRUE`); `NOT(1,1) = (1,0)` (`FALSE`). **2 instructions!**
3. **`AND(a, b)`** (`FALSE && NULL == FALSE`; `TRUE && NULL == NULL`):
   - `f_a = v_a & ~d_a` (*definitely false A*), `f_b = v_b & ~d_b` (*definitely false B*)
   - `d_out = d_a & d_b`
   - `v_out = (v_a & v_b) | f_a | f_b`
   - Verification: `FALSE(1,0) && NULL(0,0)` $\to$ `f_a = 1` $\to$ `v_out = 1, d_out = 0` (`FALSE`)! `TRUE(1,1) && NULL(0,0)` $\to$ `v_out = 0, d_out = 0` (`NULL`)!
4. **`OR(a, b)`** (`TRUE || NULL == TRUE`; `FALSE || NULL == NULL`):
   - `d_out = d_a | d_b`
   - `v_out = (v_a & v_b) | d_out`
   - Verification: `TRUE(1,1) || NULL(0,0)` $\to$ `d_out = 1, v_out = 1` (`TRUE`)! `FALSE(1,0) || NULL(0,0)` $\to$ `d_out = 0, v_out = 0` (`NULL`)! **3 instructions!**
5. **Filter / Frontier Collapse (`BOOL3VL_VEC_TO_FRONTIER`)**:
   - `frontier_bits = d_a` (since `d_a <= v_a`, `d_a == 1` iff `(v_a, d_a) == (1, 1)` `TRUE`; both `FALSE` and `NULL` collapse to `0` in **0 instructions**!).

### 6.2 Two-Tier CEL Compilation & Lexical Multi-Sink Morsel Execution

Compilers (`ImpK`, `ImpLog`, `ImpScheme`, CEL compiler) lower expressions through a strict 2-tier pipeline:

1. **Tier A — Sargable / Semiring Pushdown (Zero Morsel Overhead)**:
   - Single-attribute node predicate (`n.age >= 21`, `n.score BETWEEN 0.5 AND 1.0`, `n.deleted_at IS NULL`) $\to$ `0x44 OP_NODE_FILTER` (or `0x54 OP_INDEX_SCAN` when `.imps` carries a sorted/hash index on `(domain_id, attr_id)`).
   - Single-attribute atomic edge predicate (`e.ts > $min_ts`) $\to$ `0x31 OP_WALK_FILTERED`.
   - Standard algebraic path aggregation (`sum(u.rank * e.weight)`, `min(u.dist + e.cost)`) $\to$ `0x34 OP_SPMV`.
2. **Tier B — Arbitrary Multi-Attribute / Cross-Endpoint CEL Expressions (`OP_WALK_MORSEL` / `OP_FILTER_MORSEL`)**:
   - Multi-clause or arithmetic edge expressions (`src.risk * e.amount > 10000.0 && tgt.country != src.country`) compile to an **inline lexical morsel block** using standard Pillar 4 vector instructions on `M0..M7` and `MF0..MF7`:
   ```impas
   ; Simultaneous frontier yield + weighted risk sum in a SINGLE CSR pass:
   WALK_MORSEL.fwd     F0, rel=0, end=+9          ; M0=src, M1=tgt, M2=edge_idx, MF0=all_active
     GATHER_EDGE_ATTR  M4, M2, rel=0, attr=1      ; M4 = e.amount (f64 + null mask)
     VEC_CMP.gt.scalar M5, M4, R1                 ; M5 = (e.amount > $min_amt) [3VL]
     SET_CONVERT.b2f   MF0, M5                    ; MF0 = surviving lanes
     JCC.jempty_f      MF0, +5                    ; Skip expensive src/tgt gathers if entire morsel failed!
     GATHER_NODE_ATTR.mask M6, M0, MF0, dom=0, attr=2 ; M6 = src.risk (gathered ONLY on surviving MF0!)
     VEC_MATH_ARITH.mul.mask M7, M6, M4, MF0      ; M7 = src.risk * e.amount
     MORSEL_COMMIT.yield_frontier.mask F1, M1, MF0      ; Sink 1: F1 |= tgt_id
     MORSEL_COMMIT.scatter_add.mask    V1, M1, M7, MF0  ; Sink 2: V1[tgt_id] += M7
   MORSEL_END          hdr=-9
   ```

#### Exponential Morsel Ramp for Early-Exit / Point Queries
On single-threaded (`max_dop == 1`) executions or small seed frontiers, the morsel iterator ramps slice capacity **`32` $\to$ `256` $\to$ `2048`** across the first three morsels. Queries that terminate early or touch $< 32$ edges pay zero 2048-lane setup latency while large scans reach full 2048-lane L1 throughput by morsel 3.

### 6.3 Zero-Copy 16-Byte `StringView` Predicates

String columns and constant-pool literals expose German-style 16-byte `StringView` headers (`[uint32_t byte_len, uint32_t prefix4_be, uint64_t pool_offset]` referencing `.imps` Section 2 Shared String Table):
- **`EQ` / `NE`**: Fails in 1 register compare if `byte_len` or `prefix4_be` differs (>95% of non-equal strings never dereference `pool_offset`!). If both `.imps` column and constant literal share dictionary encoding, compares 32-bit dictionary IDs directly.
- **`LT` / `LE` / `GT` / `GE` / `STARTS_WITH`**: Since `prefix4_be` stores the first 4 UTF-8 bytes in **big-endian** unsigned integer order, `a.prefix4_be != b.prefix4_be` resolves lexicographical order in a single unsigned `uint32_t` comparison without touching string heap bytes!

---

## 7. Multi-Threaded Determinism Mandate (`AGENTS.md` §3.18)

All four reference engines (C++ Opt-ON, C++ Opt-OFF, Java 25, OCaml) MUST produce **100% bit-identical registers, frontiers, vectors, and condition flags** regardless of `max_dop` (`1..64` threads):

1. **Deterministic Floating-Point Reductions (`OP_VEC_REDUCE`, `OP_SPMV.PLUS_TIMES`, `OP_MORSEL_COMMIT.SCATTER_ADD`)**:
   - `OP_VEC_REDUCE`: Partitioned into fixed **64-element blocks** reduced via pairwise binary tree (`((x0+x1)+(x2+x3))...`), with block totals folded strictly in ascending block index order `0, 1, 2, ...`.
   - `OP_SPMV` (`REV_PLUS_TIMES` / pull mode): Target-partitioned (1 thread owns target `v` and iterates `col_indices[col_offsets[v]..col_offsets[v+1])` in canonical ascending edge order). In `FWD_PLUS_TIMES` / `MORSEL_COMMIT.SCATTER_ADD` with `max_dop > 1`, threads accumulate into thread-local target partitions or merge thread buffers in deterministic ascending `thread_id = 0 .. dop-1` order over deterministic morsel assignments (`morsel_id` assigned monotonically by CSR edge range) — **never** unordered hardware FP atomic `fetch_add`!
2. **Deterministic Tie-Breaking on `ARGMIN` / `ARGMAX` / `FIRST_TOUCH_SRC` / `TOP_K`**:
   - Ties on metric values are **always** broken by **minimum dense ID** (`u_a < u_b` wins).
   - For `f32` `SCATTER_ARGMIN`, floats are mapped bijectively to order-preserving `uint32_t` keys (`sign ? ~bits : (bits ^ 0x80000000u)`) and packed as `((uint64_t)ord_key << 32) | (uint32_t)src_id`, allowing lock-free atomic `fetch_min_u64` to converge to the exact same `(best_val, min_src_id)` under any thread interleaving!
3. **Deterministic Connected Components (`OP_GRAPH_KERNEL.cc_afforest`)**:
   - After concurrent Shiloach-Vishkin / Afforest link-compress converges, a linear canonicalization pass computes `comp_min[root] = min_{u} u` and relabels `V[dst][u] = comp_min[find(u)]`, guaranteeing `V[dst][u]` equals the minimum dense node ID in `u`'s connected component.
4. **Stateless Deterministic PRNG (`OP_SAMPLE_NEIGHBORS`)**:
   - Neighbor slot `(u, slot_j)` hashes `SplitMix64(query_seed ^ ((uint64_t)u * 0x9E3779B97F4A7C15ULL) ^ (uint64_t)slot_j)`, making output independent of thread scheduling.

---

## 8. Static Load-Time Bytecode Verifier (`impulse_vm_validate`)

Every `.impb` program MUST pass `impulse_vm_validate(program, snapshot_schema)` in $O(\text{code\_words})$ **before** execution begins (both in the interpreter and before Java `MethodHandle` / C++ AOT compilation):

1. **Opcode, Subop, Flag & MBZ Check**: Every word has a valid `opcode`, `subop <= max_subop[opcode]`, `(flags & ~allowed_flags[opcode]) == 0`, and `0` in all unused register nibbles and immediate fields.
2. **128-Bit Extension Pairing**: Every `FLAG_EXTENDED` instruction at `pc` satisfies `pc + 1 < code_word_count` and `bytecode[pc + 1].opcode == 0xFF`; conversely, no `0xFF` word appears without a preceding `FLAG_EXTENDED` word.
3. **Control-Flow Target & Self-Loop Verification**: Every `OP_JMP`, `OP_JCC`, `OP_LOOP_DECR`, and `OP_CALL` target satisfies `0 <= target_pc < code_word_count`, `bytecode[target_pc].opcode != 0xFF`, and `target_pc != pc` (rejecting 0-offset infinite loops unless gas-bounded).
4. **Lexical Morsel Well-Formedness & Race-Freedom**:
   - `OP_WALK_MORSEL` / `OP_FILTER_MORSEL` and `OP_MORSEL_END` match 1:1 with non-nesting lexical ranges (`hdr_pc + imm16_hi == end_pc` and `end_pc - end.imm16_hi == hdr_pc`).
   - **No Nesting, No Calls, No Backward Jumps**: Inside `(hdr_pc, end_pc)`, `OP_WALK*`, `OP_SPMV`, `OP_CALL`, `OP_RET`, `OP_SET_MAX_DOP`, and backward jumps (`offset <= 0`) or jumps exiting `(hdr_pc, end_pc]` are rejected (`IMPULSE_VM_ERR_VALIDATION_FAILED`).
   - **Thread-Private Write Isolation**: Inside `(hdr_pc, end_pc)`, every instruction other than `OP_MORSEL_COMMIT` MUST have `dst >= 8` (`MF0..MF7` or `M0..M7`) and `dst` bank $\in \{F, V\}$ (writing outer `R0..R15`, `F0..F7`, or `V0..V7` inside a parallel morsel body is statically rejected!). Conversely, `OP_MORSEL_COMMIT` MUST have `dst < 8`, `s1 >= 8`, and (unless `FLAG_SCALAR_RHS`) `s2 >= 8`.
   - Outside morsel blocks, referencing `M0..M7` / `MF0..MF7` behaves as normal domain registers `V8..V15` / `F8..F15`, while `OP_MORSEL_COMMIT` and `OP_MORSEL_END` outside a morsel block are rejected.
5. **Static Domain & Schema Type Checking (`AGENTS.md` §3.14)**:
   - When a `.imps` schema is bound at validation time, `rel_id < num_relations`, `domain_id < num_domains`, `attr_id < domain.num_attrs`, and abstract dataflow propagation verifies `F[s1].domain_id == rel.src_domain_id` on `OP_WALK.fwd` (and `rel.tgt_domain_id` on `OP_WALK.rev`), catching cross-domain bugs (`IMPULSE_VM_ERR_DOMAIN_MISMATCH`) before a single edge is touched!
