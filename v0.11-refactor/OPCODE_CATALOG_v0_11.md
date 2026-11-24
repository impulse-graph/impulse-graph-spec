# ImpulseVM v0.11.0 Normative Opcode Catalog (`impOps` v0.11)

> **Normative Draft (`v0.11.0-ISA-Refactor`)**
> Exhaustive opcode-by-opcode specification for all **78 active opcodes** (`0x00`–`0x14`, `0x20`–`0x27`, `0x30`–`0x3B` excluding `0x32`, `0x40`–`0x57`, `0x60`–`0x6F` excluding `0x62` and `0x68`) plus `0xFF OP_EXTENSION_PAYLOAD`.
> Every entry specifies exact nibble layouts, allowed modifier flags (`flags:4`), sub-operation selectors (`subop:4` $\le 15$), condition flag mutations (`ZF`, `ST`, `NF`), `ImpAsm` v0.11 usage, first-principles architectural justification, and implementation gotchas.

---

## 0. Master Opcode Map & Pillar Index

| Hex Range | Pillar | Count | Reserved Headroom | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `0x00`–`0x14` | **Pillar 1 — System, Constants, Scalar ALU & Windowed Control** | `21` | `0x15`–`0x1F` (`11` free) | Traps, constants, host params, register moves/spills, 64b int/FP/3VL scalar ALU, branches, sliding-window `CALL`/`RET`, `SET_MAX_DOP`. |
| `0x20`–`0x27` | **Pillar 2 — Polymorphic Frontier & Set Algebra** | `8` | `0x28`–`0x2F` (`8` free) | Domain-bound 3-tier & multi-lane seeding, set algebra (`UNION`, `INTERSECT`, `DIFF`, `SYM_DIFF`, `COMPLEMENT`), lazy `CARDINALITY`, `CONTAINS`, `CONVERT`, `STABLE_CHECK`. |
| `0x30`–`0x3B` | **Pillar 3 — Graph Topology, Semiring SpMV, Morsel & Kernels** | `11` | `0x32`, `0x3C`–`0x3F` (`5` free) | Layout-agnostic `WALK`, `WALK_FILTERED`, `DEGREE`, `SPMV`, inline lexical morsels (`WALK_MORSEL`, `FILTER_MORSEL`, `MORSEL_COMMIT`, `MORSEL_END`), `SAMPLE_NEIGHBORS`, `HAS_TOPOLOGY`, `GRAPH_KERNEL`. |
| `0x40`–`0x57` | **Pillar 4 — Columnar Vectors, 5-Way Math, 3VL, Strings, Index & Collect** | `24` | `0x58`–`0x5F` (`8` free) | Zero-copy `LOAD_COLUMN`, `GATHER_*`, `NODE_FILTER`, `VEC_CMP` (with `.in_set`), `VEC_3VL_OP`, `VEC_STR_PRED`, 5-way split math (`<= 16` subops each), `TERNARY`, `BLEND`, `COALESCE`, `VEC_INIT`, `VEC_POINT` (with `.vec_len`), `VEC_REDUCE`, `TOP_K`, `INDEX_SCAN`, `MAP_KEYS_*`, `COLLECT`. |
| `0x60`–`0x6A` | **Pillar 5 — Multi-Lane Bit-Sliced & Vector ANN** | `9` | `0x62`, `0x68`, `0x6B`–`0xFE` (`150` free) | Paged multi-lane seeding, `LANE_WALK`, `LANE_BITWISE`, `QUORUM`, `REDUCE_AND`, `REDUCE_ATTR`, ordered `VECTOR_ANN_SEARCH`, multi-metric `VECTOR_RERANK`. |
| `0xFF` | **Extension Marker** | `1` | — | Mandatory Word-2 guard byte for `FLAG_EXTENDED` (`0x8` nibble / `0x80` Byte 1) 128-bit literal loads. |

### Universal Nibble Notation, Byte Order & Master Status Codes

- **Byte Order**: All `.impb` 64-bit instruction words, immediates, and container headers are **little-endian**.
- **Word Layout**: `[imm16_hi:16 | imm16_lo:16 | s2:4 | s3:4 | dst:4 | s1:4 | flags:4 | subop:4 | opcode:8]` where `Byte 1 = (flags << 4) | subop`.
- **`flags:4` (4-bit nibble values used throughout this catalog)**: `0x8 = EXT` (`FLAG_EXTENDED`), `0x4 = ACCUM` (`FLAG_ACCUM`), `0x2 = SCALAR` (`FLAG_SCALAR_RHS`), `0x1 = MASK` (`FLAG_MASKED_S3`).
- **`MBZ`**: Must-Be-Zero. Non-zero unused nibbles/immediates fail `impulse_vm_validate` with `IMPULSE_VM_ERR_INVALID_OPERAND` (`6`).
- **`r_type_word`**: 64-bit packed `16 × 4`-bit scalar type word for `R0..R15` (`0=NULL_UNSET`, `1=I64`, `2=U64`, `3=F64`, `4=BOOL_3VL`, `5=STR_HANDLE`, `6=F32_RAW`).

| Code | Status Enum | Normative Condition |
| :--- | :--- | :--- |
| `0` | `IMPULSE_VM_OK` | Clean halt (`OP_HALT`) or successful validation. |
| `1` | `IMPULSE_VM_ERR_INVALID_OPCODE` | Unknown opcode byte or undefined `subop:4`. |
| `2` | `IMPULSE_VM_ERR_OUT_OF_BOUNDS` | Node/edge/domain/rel/attr/param/vector/PC index out of bounds. |
| `3` | `IMPULSE_VM_ERR_NULL_SNAPSHOT` | Graph/attribute/index op invoked without a bound `.imps` snapshot. |
| `4` | `IMPULSE_VM_ERR_STACK_OVERFLOW` | `OP_CALL` depth `>= max_call_depth` (`<= 16`), window stack overflow, or spill slot `>= 16`. |
| `5` | `IMPULSE_VM_ERR_STACK_UNDERFLOW` | `OP_RET` at `call_depth == 0`. |
| `6` | `IMPULSE_VM_ERR_INVALID_OPERAND` | Disallowed `flags:4` bit, non-zero MBZ field, misaligned buffer, `in_use` reentrancy, or invalid argument (`clamp lo > hi`). |
| `7` | `IMPULSE_VM_ERR_USER_THROW` | Explicit `OP_THROW`. |
| `8` | `IMPULSE_VM_ERR_ASSERTION_FAILED` | Failed `OP_ASSERT` or `OP_VEC_3VL_OP.assert_finite`. |
| `9` | `IMPULSE_VM_ERR_TRAP` | Explicit `OP_TRAP`. |
| `10` | `IMPULSE_VM_ERR_DOMAIN_MISMATCH` | Frontier/relation/set domain ID mismatch (`AGENTS.md` §3.14). |
| `11` | `IMPULSE_VM_ERR_BUFFER_OVERFLOW` | Caller-owned `scratch_ws` or `result_buf` capacity exceeded (zero `malloc` fallback). |
| `12` | `IMPULSE_VM_ERR_FLOATING_POINT` | Reserved for strict IEEE-754 exception mode. |
| `13` | `IMPULSE_VM_ERR_GAS_EXHAUSTED` | Deterministic fuel budget (`ws->gas_remaining == 0`) reached. |
| `14` | `IMPULSE_VM_ERR_TYPE_MISMATCH` | Incompatible `r_type_word` scalar type, vector `elem_type`, lane width, or uninitialized `F`/`V` register read. |
| `15` | `IMPULSE_VM_ERR_VALIDATION_FAILED` | Unpaired `0xFF`, jump into `0xFF`, malformed/racy morsel block, or `.vec_wr` in CFG loop SCC. |

---

## Pillar 1 — System, Constants, Scalar ALU & Windowed Control (`0x00`–`0x14`)

---

### `0x00` — `OP_HALT`
* **Summary**: Cleanly terminates VM program execution and returns `IMPULSE_VM_OK` (`0`).
* **Encoding**:
  - `flags:4`: `0x0` (none allowed); `subop:4`: `0` (`HALT_OK`)
  - `dst`: `0` (MBZ); `s1`: `0` (MBZ); `s2`: `0` (MBZ); `s3`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: Unchanged (preserves final `ZF`, `ST`, `NF` for host inspection and `ICTX v2` hashing).
* **Operational Semantics**: Stops dispatch at the current `pc` (`state->pc` remains pointing at the `OP_HALT` word) without releasing terminal `OP_COLLECT` buffers in `VmQueryContext`.
* **ImpAsm Usage**:
  ```impas
  COLLECT.frontier_ids F1, out=0
  HALT
  ```
* **Justification**: Explicit termination prevents speculative fall-off past `code_word_count` and preserves exact stopping `pc` for trace diagnostics.
* **Gotchas**:
  1. Executing past `code_word_count - 1` without encountering `OP_HALT` returns `IMPULSE_VM_ERR_OUT_OF_BOUNDS` (`2`), **never** an implicit `OK`.
  2. `OP_HALT` inside a lexical morsel block (`OP_WALK_MORSEL .. OP_MORSEL_END`) is **forbidden** by `impulse_vm_validate` (`IMPULSE_VM_ERR_VALIDATION_FAILED`), because worker threads executing morsels in parallel have no deterministic sequential halt order.
  3. Notice that all-zero memory (`0x0000000000000000`) decodes as `OP_HALT`; therefore `impulse_vm_validate` requires `.impb` headers (`magic == 0x494D5042`, `xxh3_64` checksum) so zeroed buffers are never executed accidentally.

---

### `0x01` — `OP_NOP`
* **Summary**: Architectural no-operation; advances `pc` by `+1`.
* **Encoding**:
  - `flags:4`: `0x0`; `subop:4`: `0`; `dst, s1, s2, s3`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Operational Semantics**: `state->pc += 1`.
* **ImpAsm Usage**:
  ```impas
  NOP
  ```
* **Justification**: Provides 64-byte cache-line loop alignment padding for hot AOT/JIT loops and patchable instrumentation slots without perturbing register state.
* **Gotchas**: Non-zero nibbles or `imm32` in `OP_NOP` are rejected by MBZ validation (`ERR_INVALID_OPERAND`); debuggers/compilers needing metadata tags must use `.debug` sections rather than stuffing payload bits into `OP_NOP`.

---

### `0x02` — `OP_TRAP`
* **Summary**: Synchronous debugger / host breakpoint trap (`IMPULSE_VM_ERR_TRAP` = `9`).
* **Encoding**:
  - `flags:4`: `0x0`; `subop:4`: `0`; `dst, s1, s2, s3`: `0` (MBZ); `imm32`: `trap_id` (`uint32_t`)
  - `vm_flags` updated: None.
* **Operational Semantics**: Halts dispatch immediately with `pc` pointing at the `OP_TRAP` instruction and records `trap_id` in `ctx->last_error_code`, returning `IMPULSE_VM_ERR_TRAP` (`9`). Host debuggers may inspect `impulse_vm_state_v11_t`, advance `pc += 1`, and resume execution.
* **ImpAsm Usage**:
  ```impas
  TRAP 42
  ```
* **Justification**: Enables non-destructive single-stepping and compiler unreachable-branch guards (`__builtin_unreachable()` lowering).
* **Gotchas**: Unlike `OP_THROW` (which represents query-level semantic errors like schema constraint violations), `OP_TRAP` signals VM/debugger-level interception and is disallowed inside morsel blocks.

---

### `0x03` — `OP_THROW`
* **Summary**: Raises a deterministic user/query-level runtime exception (`IMPULSE_VM_ERR_USER_THROW` = `7`).
* **Encoding**:
  - `flags:4`: `0x0`; `dst, s2, s3`: `0` (MBZ); `imm32`: `user_err_code`
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` (`0..1`))**:

| `subop` | Mnemonic | `s1` Operand | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.imm` | `0` (MBZ) | Raises `IMPULSE_VM_ERR_USER_THROW` with `imm32` error code only. |
| `1` | `.reg` | `R[s1]` | Raises `IMPULSE_VM_ERR_USER_THROW` with `imm32` error code and auxiliary payload `R[s1]`. |

* **Operational Semantics**: Stores `imm32` (and `R[s1]` if `subop == 1`) into `ctx->error_info` and terminates execution with `IMPULSE_VM_ERR_USER_THROW` (`7`) at current `pc`.
* **ImpAsm Usage**:
  ```impas
  THROW.imm 1001
  THROW.reg R3, 1002
  ```
* **Justification**: Allows `ImpLog` integrity rules and `ImpK` domain preconditions to abort cleanly with structured error codes without overloading hardware traps.
* **Gotchas**: Forbidden inside parallel morsel blocks (`OP_WALK_MORSEL .. OP_MORSEL_END`); to abort on malformed data inside a vector/morsel pass, accumulate an invalid lane mask and check after `OP_MORSEL_END` with `OP_JCC` + `OP_THROW`.

---

### `0x04` — `OP_ASSERT`
* **Summary**: Runtime invariant verification; traps with `IMPULSE_VM_ERR_ASSERTION_FAILED` (`8`) on failure.
* **Encoding**:
  - `flags:4`: `0x0`
  - `dst, s2, s3`: `0` (MBZ); `imm32`: `assert_tag` (`uint32_t`)
  - `vm_flags` updated: None (`OP_ASSERT` never mutates `ZF`/`ST`/`NF`!).
* **Sub-Operations (`subop:4`)**:

| `subop` | Mnemonic | Bank of `s1` | Pass Condition |
| :--- | :--- | :--- | :--- |
| `0` | `.true_r` | `R[s1]` | `valid(R[s1]) == 1 && R[s1] != 0` |
| `1` | `.nonempty_f` | `F[s1]` | `!is_empty(F[s1])` ($O(1)$ check, no popcount needed) |
| `2` | `.empty_f` | `F[s1]` | `is_empty(F[s1])` |
| `3` | `.zf_set` | `s1=0` (MBZ) | `(vm_flags & FLAG_VM_ZF) != 0` |
| `4` | `.zf_clear` | `s1=0` (MBZ) | `(vm_flags & FLAG_VM_ZF) == 0` |
| `5` | `.st_set` | `s1=0` (MBZ) | `(vm_flags & FLAG_VM_ST) != 0` |
| `6` | `.not_null_r` | `R[s1]` | `valid(R[s1]) == 1` |
| `7` | `.is_null_r` | `R[s1]` | `valid(R[s1]) == 0` |

* **ImpAsm Usage**:
  ```impas
  ASSERT.nonempty_f F0, 101
  ASSERT.true_r     R2, 102
  ```
* **Justification**: Essential for self-checking `.impas` compliance vectors and compiler debug builds without perturbing `vm_flags` between instructions.
* **Gotchas**:
  1. **Kleene `NULL` Fails `.true_r`**: If `R[s1]` has `r_valid_mask` bit `0` (`NULL`), `ASSERT.true_r` **MUST fail** even if raw register bits happened to be non-zero (canonical invariant already forces `r_regs[s1] == 0` when invalid).
  2. `ASSERT.nonempty_f` MUST NOT trigger a full `vpopcntq` scan on a `cached_card == -1` frontier; checking `tier != EMPTY` (and `dirty_count > 0` / `L1 != 0`) suffices in $O(1)$.

---

### `0x05` — `OP_LOAD_CONST`
* **Summary**: Loads a 32-bit inline constant, 64-bit extended constant, or Kleene `NULL` into scalar register `R[dst]`.
* **Encoding**:
  - `flags:4`: `0x0`, or `0x8` (`FLAG_EXTENDED`) **if and only if** `subop` $\in \{4, 5, 6\}$
  - `s1, s2, s3`: `0` (MBZ)
  - `vm_flags` updated: `ZF = (!valid || R[dst] == 0)`, `NF = !valid` (`ST` preserved); updates `r_type_word` nibble `dst`.
* **Sub-Operations (`subop:4` `0..7`)**:

| `subop` | Mnemonic | Width | `r_type_word` Tag | Semantics in `R[dst]` | `r_valid_mask[dst]` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0` | `.i32` | 64b (1 word) | `SCALAR_I64 (1)` | `(uint64_t)(int64_t)(int32_t)imm32` (sign-extended `i64`) | `1` |
| `1` | `.u32` | 64b (1 word) | `SCALAR_U64 (2)` | `(uint64_t)(uint32_t)imm32` (zero-extended `u64`) | `1` |
| `2` | `.f32` | 64b (1 word) | `SCALAR_F64 (3)` | Promotes IEEE-754 `float` in `imm32` to `double` (`NaN` $\to$ `NULL`, tag `0`) | `1` (`0` if `NaN`) |
| `3` | `.f32_raw` | 64b (1 word) | `SCALAR_F32_RAW (6)` | Zero-extends raw 32-bit `float` into low 32 bits (`NaN` $\to$ `NULL`, tag `0`) | `1` (`0` if `NaN`) |
| `4` | `.i64` (`.ext`) | 128b (2 words) | `SCALAR_I64 (1)` | `((uint64_t)w2.imm32 << 32) \| (uint64_t)w1.imm32` | `1` |
| `5` | `.u64` (`.ext`) | 128b (2 words) | `SCALAR_U64 (2)` | `((uint64_t)w2.imm32 << 32) \| (uint64_t)w1.imm32` | `1` |
| `6` | `.f64` (`.ext`) | 128b (2 words) | `SCALAR_F64 (3)` | `((uint64_t)w2.imm32 << 32) \| (uint64_t)w1.imm32` (`NaN` $\to$ `NULL`, tag `0`) | `1` (`0` if `NaN`) |
| `7` | `.null` | 64b (1 word) | `SCALAR_NULL_UNSET (0)` | `R[dst] = 0ULL` (`imm32` MBZ) | **`0`** |

* **ImpAsm Usage**:
  ```impas
  LOAD_CONST.i32      R0, -1
  LOAD_CONST.f32      R1, 0.85            ; Promoted to exact IEEE-754 f64 in 1 word!
  LOAD_CONST.f64.ext  R2, 0.8             ; Full 64-bit double (2 words, w2[0]=0xFF)
  LOAD_CONST.null     R3                  ; Kleene NULL (r_valid_mask bit 3 = 0)
  ```
* **Justification**: Replaces `OP_LOAD_CONST_INT` (`0x04`) and `OP_LOAD_CONST_FLOAT` (`0x06`). Typing `.i64`/`.u64`/`.f64` explicitly populates `r_type_word` and canonicalizes `NaN -> NULL` at load time across all FP consumers (`OP_SCALAR_FP_ALU`, `OP_SCALAR_3VL.cmp_*_f64`, `OP_NODE_FILTER`, `OP_VEC_*`).
* **Gotchas**:
  1. Using `subop` $\in \{4, 5, 6\}$ without `FLAG_EXTENDED` (`0x8`), or setting `FLAG_EXTENDED` on any other `subop`, is rejected by `impulse_vm_validate` (`ERR_INVALID_OPERAND`).
  2. Loading `-0.0` via `.f32`/`.f64`: `-0.0` is valid (`valid=1`); `-0.0 == 0.0` sets `ZF = 1`, while preserving the sign bit in `R[dst]` for `COPYSIGN`.

---

### `0x06` — `OP_LOAD_CONST_POOL`
* **Summary**: Zero-copy binds an immutable literal (`IN [...]` array, static node set, or `StringView`) from the `.impb` Constant Pool into `V[dst]`, `F[dst]`, or `R[dst]`.
* **Encoding**:
  - `flags:4`: `0x0` (or `0x4` `FLAG_ACCUM` when `subop == 1`)
  - `s1, s2, s3`: `0` (MBZ)
* **Sub-Operations (`subop:4`)**:

| `subop` | Mnemonic | `dst` Bank | Immediate Fields | Semantics |
| :--- | :--- | :--- | :--- | :--- |
| `0` | `.vec` | `V[dst]` | `imm32 = pool_entry_id` | Binds typed read-only constant vector (`I64`, `F64`, `STR_VIEW`, etc.) directly from Constant Pool memory (`COW/read-only` flag set on descriptor). |
| `1` | `.frontier` | `F[dst]` | `imm16_lo = pool_entry_id`, `imm16_hi = domain_id` | Initializes `F[dst]` bound to `domain_id` from sorted dense ID list in Constant Pool (validates `max_id < N_domain`). |
| `2` | `.str` | `R[dst]` | `imm32 = pool_entry_id` | Loads 64-bit `imp_str_handle_t` (`tag = 0b01` const pool, or `0b11` inline if `<= 7` UTF-8 bytes) into `R[dst]` (`SCALAR_STR_HANDLE`) (`valid=1`, `NF=0`, `ZF=(byte_len==0)`). |

* **ImpAsm Usage**:
  ```impas
  LOAD_CONST_POOL.str      R1, pool=0          ; "ACTIVE"
  LOAD_CONST_POOL.vec      V1, pool=1          ; [10, 20, 30, 42]
  LOAD_CONST_POOL.frontier F0, pool=1, dom=0
  ```
* **Justification**: Replaces `OP_LOAD_CONST_STR_PREFIX` (`0x07`), `OP_LOAD_INLINE_ARRAY` (`0x08`), and `OP_LOAD_INLINE_SET` (`0x0A`) without embedding variable-length raw arrays inside the executable instruction stream.
* **Gotchas**:
  1. Vectors loaded via `LOAD_CONST_POOL.vec` point directly into read-only `.impb` constant-pool memory (`is_readonly_borrow = 1`). Any instruction that attempts in-place mutation (`OP_VEC_POINT.vec_set` or `FLAG_ACCUM`) MUST allocate a writable arena buffer (`copy-on-write`) rather than writing into `.impb` memory!
  2. For `.frontier`, if any constant ID in `pool_entry_id` is $\ge N_{\text{domain}}$, returns `IMPULSE_VM_ERR_OUT_OF_BOUNDS` (`2`).

---

### `0x07` — `OP_LOAD_PARAM`
* **Summary**: Loads a host-supplied query parameter from `VmQueryContext` into `R[dst]`, `F[dst]`, or `V[dst]`.
* **Encoding**:
  - `flags:4`: `0x0` (or `0x4` `FLAG_ACCUM` on `subop == 1`)
  - `s1, s2, s3`: `0` (MBZ)
* **Sub-Operations (`subop:4`)**:

| `subop` | Mnemonic | `dst` Bank | Immediate Layout | Semantics |
| :--- | :--- | :--- | :--- | :--- |
| `0` | `.scalar` | `R[dst]` | `imm16_lo = param_id`, `imm16_hi = expected_scalar_type` | Loads host scalar parameter (`1=I64`, `2=U64`, `3=F64`, `4=BOOL_3VL`, `5=STR_HANDLE` 64-bit `imp_str_handle_t`). If host bound `NULL`, sets `r_valid_mask[dst]=0, R[dst]=0, NF=1, ZF=1`. |
| `1` | `.frontier` | `F[dst]` | `imm16_lo = param_id`, `imm16_hi = domain_id` | Binds host seed node or seed node array into 3-tier `F[dst]` for `domain_id` (`AGENTS.md` §3.14); sets `ZF = is_empty(F[dst])`. |
| `2` | `.vec` | `V[dst]` | `imm16_lo = param_id`, `imm16_hi = expected_elem_type` | Zero-copy borrows host vector parameter (e.g. `f32[D]` query embedding for `OP_VECTOR_ANN_SEARCH`). |

* **ImpAsm Usage**:
  ```impas
  LOAD_PARAM.frontier F0, param=0, dom=0     ; Anchor seed frontier on User domain (dom 0)
  LOAD_PARAM.scalar   R1, param=1, type=f64  ; $min_weight
  LOAD_PARAM.vec      V0, param=2, type=f32  ; $query_embedding[768]
  ```
* **Justification**: Unifies `OP_INIT_INPUT_NODE` (`0x02`), `OP_INIT_INPUT_SET` (`0x03`), scalar `$param` injection, and ANN query-vector binding into a single parameterized entrypoint with mandatory `domain_id` enforcement (`AGENTS.md` §3.14).
* **Gotchas**:
  1. Missing/unbound `param_id >= ctx->param_count` returns `IMPULSE_VM_ERR_OUT_OF_BOUNDS` (`2`); mismatched host parameter type vs `imm16_hi` returns `IMPULSE_VM_ERR_TYPE_MISMATCH` (`14`). (Explicitly bound SQL/CEL `NULL` on `.scalar` is valid and sets `NF = 1`.)
  2. Host seed IDs $\ge N_{\text{domain}}$ on `.frontier` return `IMPULSE_VM_ERR_OUT_OF_BOUNDS` (`2`) — never silently masked or wrapped.

---

### `0x08` — `OP_MOV`
* **Summary**: Copies a register within the same bank (via O(1) COW descriptor sharing for `F`/`V`) or explicitly resets/releases a register.
* **Encoding**:
  - `flags:4`: `0x0`
  - `s2, s3`: `0` (MBZ); `imm32`: `0` (except `imm16_lo = domain_id` on `.clear_f`)
* **Sub-Operations (`subop:4`)**:

| `subop` | Mnemonic | Bank | Operands | Semantics |
| :--- | :--- | :--- | :--- | :--- |
| `0` | `.r` | `R` | `dst`, `s1` | `R[dst] = R[s1]`; copies validity bit `s1 -> dst`; sets `ZF`, `NF`. |
| `1` | `.f` | `F` | `dst`, `s1` | Shares/clones `F[s1]` into `F[dst]` (ref-counted COW slab lease; releases prior `F[dst]`); sets `ZF = is_empty(F[dst])`. |
| `2` | `.v` | `V` | `dst`, `s1` | Shares/clones `V[s1]` into `V[dst]` (ref-counted COW buffer lease; releases prior `V[dst]`). |
| `3` | `.clear_r` | `R` | `dst` (`s1=0`) | `R[dst] = 0`, `valid[dst] = 1`, `ZF = 1, NF = 0`. |
| `4` | `.clear_f` | `F` | `dst` (`s1=0`, `imm16_lo=domain_id`) | Releases `F[dst]` slabs back to `ctx->pool`, leaving empty frontier in `domain_id` (`cached_card=0, ZF=1`). |
| `5` | `.clear_v` | `V` | `dst` (`s1=0`) | Releases `V[dst]` buffer back to `ctx->pool` immediately (`uninitialized`). |

* **ImpAsm Usage**:
  ```impas
  MOV.f       F2, F0          ; O(1) COW snapshot of frontier F0 before fixed-point step
  MOV.clear_v V4              ; Eagerly return large temporary column buffer to pool
  ```
* **Justification**: Replaces `OP_MOV` (`0x70`) and `OP_CLEAR_REG` (`0x71`). COW reference counting on `ctx->pool` descriptors makes `MOV.f F_prev, F_curr` before an in-place `.accum` walk $O(1)$ until `F_curr` is mutated.
* **Gotchas**: On `MOV.f F_dst, F_dst` (self-move), implementations MUST handle `dst == s1` as a no-op *before* decrementing the old `F[dst]` slab refcount (classic use-after-release self-assignment trap!).

---

### `0x09` — `OP_SWAP`
* **Summary**: $O(1)$ zero-copy swap of two registers within the same bank.
* **Encoding**:
  - `flags:4`: `0x0`; `s2, s3`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` `0..3`)**:

| `subop` | Mnemonic | Bank (`dst`, `s1`) | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.r` | `R[dst] <-> R[s1]` | Swaps 64-bit values and `r_valid_mask` bits `dst` and `s1`. |
| `1` | `.f` | `F[dst] <-> F[s1]` | $O(1)$ swap of frontier descriptor handles. |
| `2` | `.v` | `V[dst] <-> V[s1]` | $O(1)$ swap of vector descriptor handles. |

* **Operational Semantics**: Exchanges `R[dst] <-> R[s1]` (including their `r_valid_mask` bits!), `f_handles[dst] <-> f_handles[s1]`, or `v_handles[dst] <-> v_handles[s1]` in 2 register moves without touching underlying slab/vector memory.
* **ImpAsm Usage**:
  ```impas
  SWAP.v V0, V1   ; Ping-pong PageRank rank_curr <-> rank_next in 2 cycles!
  SWAP.f F0, F1   ; Ping-pong BFS frontier_curr <-> frontier_next
  ```
* **Justification**: Iterative graph algorithms (`PageRank`, `BFS`, `Bellman-Ford`, `Katz`) alternate `curr` and `next` buffers on every step; `SWAP` swaps their pool handles in $O(1)$ while keeping both pre-allocated buffers hot for reuse on the next iteration.
* **Gotchas**: On `SWAP.r`, forgetting to swap bits `dst` and `s1` in `state->r_valid_mask` will corrupt Kleene `NULL` tracking!

---

### `0x0A` — `OP_SPILL`
* **Summary**: Spills register `s1` from bank (`R`, `F`, or `V`) into frame-local spill slot `imm16_lo` (`0..15`).
* **Encoding**:
  - `flags:4`: `0x0`; `dst, s2, s3`: `0` (MBZ); `imm16_lo`: `slot` (`0..15`), `imm16_hi`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` (`0..2`))**:

| `subop` | Mnemonic | `s1` Bank | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.r` | `R[s1]` | Saves `(R[s1], valid[s1])` into frame spill slot `imm16_lo`. |
| `1` | `.f` | `F[s1]` | Saves COW-retained frontier handle `F[s1]` into frame spill slot `imm16_lo`. |
| `2` | `.v` | `V[s1]` | Saves COW-retained vector handle `V[s1]` into frame spill slot `imm16_lo`. |

* **Operational Semantics**: Copies `(R[s1], valid[s1])` or COW-increments the descriptor handle of `F[s1]`/`V[s1]` into `ctx->spill_area[spill_base + slot]`. Checks `slot < 16` and `spill_base + slot < 256` (`ERR_STACK_OVERFLOW` otherwise); also saves/restores the 4-bit `r_type_word` tag for `.r`.
* **ImpAsm Usage**:
  ```impas
  SPILL.f F7, slot=0
  ```
* **Justification**: Guarantees register allocation completeness for arbitrarily wide DAG queries (>16 live variables in one bank) without expanding register fields past 4 bits. Inside `OP_WALK_MORSEL` / `OP_FILTER_MORSEL` (`morsel_role = body_v_only`), `OP_SPILL.v` (`subop = 2`) is permitted **exclusively** for morsel-private vectors `V8..V15` (`M0..M7`) into thread-private morsel spill slots `0..15` (`16 KB`/slot, statically bounded in `impulse_vm_plan_memory`), eliminating the 4-temporary ceiling for deeply nested CEL edge expressions.
* **Gotchas**:
  1. Spilling an `F` or `V` register retains a COW lease on its slab/arena buffer until either overwritten in `slot` or automatically reclaimed when the enclosing `OP_RET` pops `spill_base`.
  2. Inside a morsel block, `OP_SPILL.r`, `OP_SPILL.f`, or `OP_SPILL.v` with `s1 < 8` (outer `V0..V7`) MUST fail static validation (`IMPULSE_VM_ERR_VALIDATION_FAILED`).

---

### `0x0B` — `OP_RELOAD`
* **Summary**: Reloads frame-local spill slot `imm16_lo` (`0..15`) into `dst` in bank (`R`, `F`, or `V`).
* **Encoding**:
  - `flags:4`: `0x0`; `s1, s2, s3`: `0` (MBZ); `imm16_lo`: `slot` (`0..15`), `imm16_hi`: `0` (MBZ)
  - `vm_flags` updated: On `.r`: `ZF`, `NF`; on `.f`: `ZF`; on `.v`: unchanged.
* **Sub-Operations (`subop:4` (`0..2`))**:

| `subop` | Mnemonic | `dst` Bank | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.r` | `R[dst]` | Restores `(value, valid)` from spill slot `imm16_lo` into `R[dst]` (updates `ZF`, `NF`). |
| `1` | `.f` | `F[dst]` | Restores frontier handle from spill slot `imm16_lo` into `F[dst]` (updates `ZF`). |
| `2` | `.v` | `V[dst]` | Restores vector handle from spill slot `imm16_lo` into `V[dst]`. |

* **Operational Semantics**: Restores the spilled value/descriptor from `ctx->spill_area[spill_base + slot]` into `dst` (verifying that `slot` was previously written in the current frame with the matching bank tag, else `IMPULSE_VM_ERR_TYPE_MISMATCH` `14`).
* **ImpAsm Usage**:
  ```impas
  RELOAD.f F7, slot=0
  ```
* **Justification**: Symmetric counterpart to `OP_SPILL`.
* **Gotchas**: Reloading does **not** invalidate the spill slot (a spilled constant or frontier inside a loop can be `RELOAD`ed on every iteration without re-spilling).

---

### `0x0C` — `OP_SCALAR_INT_ALU`
* **Summary**: 64-bit integer & bitwise scalar ALU on `R[dst] = op(R[s1], rhs)` with strict Kleene `NULL` propagation and UB-free division/shifts.
* **Encoding**:
  - `flags:4`: `0x0`
  - `s3` Addressing Mode: `s3 == 0` $\to$ register mode (`rhs = R[s2]`, `imm32` MBZ); `s3 == 1` $\to$ immediate mode (`rhs = (int64_t)(int32_t)imm32`, `valid_rhs = 1`, `s2` MBZ). (For unary `subop == 10` `NOT`, `s2=0, s3=0, imm32=0`.)
  - `vm_flags` updated: `ZF = (!valid[dst] || R[dst] == 0)`, `NF = !valid[dst]`.
* **Sub-Operations (`subop:4` (`0..15`))**:

| `subop` | Mnemonic | Operation (`i64` two's complement / `u64`) | Division / Overflow Behavior |
| :--- | :--- | :--- | :--- |
| `0` | `.add` | `a + b` | Wrapping two's-complement 64-bit (`u64` cast in C++ to avoid signed UB). |
| `1` | `.sub` | `a - b` | Wrapping two's-complement 64-bit. |
| `2` | `.mul` | `a * b` | Wrapping low 64-bit product. |
| `3` | `.div_s` | `a / b` (signed) | `b == 0` $\to$ Kleene `NULL` (`valid=0, dst=0`); `INT64_MIN / -1` $\to$ `INT64_MIN` (no x86 `#DE` trap!). |
| `4` | `.div_u` | `u64(a) / u64(b)` | `b == 0` $\to$ Kleene `NULL` (`valid=0, dst=0`). |
| `5` | `.rem_s` | `a % b` (signed) | `b == 0` $\to$ Kleene `NULL`; `INT64_MIN % -1` $\to$ `0` (no `#DE` trap!). |
| `6` | `.rem_u` | `u64(a) % u64(b)` | `b == 0` $\to$ Kleene `NULL`. |
| `7` | `.and` | `a & b` | Bitwise AND (propagates `valid_a & valid_b`; for 3VL logic use `OP_SCALAR_3VL`!). |
| `8` | `.or` | `a \| b` | Bitwise OR. |
| `9` | `.xor` | `a ^ b` | Bitwise XOR. |
| `10` | `.not` | `~a` | Bitwise complement (`s2=0, s3=0`). |
| `11` | `.shl` | `u64(a) << (b & 63)` | Shift count masked `& 63` (matches x86 `shlq`, ARM64 `lsl`, Java `<<`, OCaml `shift_left`). |
| `12` | `.shr_u` | `u64(a) >> (b & 63)` | Logical unsigned right shift (`& 63`). |
| `13` | `.shr_s` | `i64(a) >> (b & 63)` | Arithmetic signed right shift (`& 63`). |
| `14` | `.min_s` | `a < b ? a : b` | Signed `i64` minimum. |
| `15` | `.max_s` | `a > b ? a : b` | Signed `i64` maximum. |

* **ImpAsm Usage**:
  ```impas
  SCALAR_INT_ALU.add     R2, R0, R1      ; s3=0: R2 = R0 + R1
  SCALAR_INT_ALU.add.imm R0, R0, 1       ; s3=1: R0 = R0 + 1
  SCALAR_INT_ALU.shl.imm R3, R2, 4       ; s3=1: R3 = R2 << 4
  ```
* **Justification**: v0.10 lacked a general scalar integer ALU completely, forcing loop index arithmetic or degree-ratio heuristics (`m_fwd * 10 < m_rev`) to abuse vector math or host workarounds.
* **Gotchas**:
  1. **x86-64 `idivq` Hardware Trap (`SIGFPE`)**: On x86-64, signed `INT64_MIN / -1` and `INT64_MIN % -1` raise a hardware `#DE` fault in C++, whereas Java `Long.divide` / ARM64 `sdiv` return `INT64_MIN` and `0`. C++ and Rust implementations **MUST** explicitly guard `(a == INT64_MIN && b == -1)` before executing signed `/` or `%`!
  2. **C++ Signed Overflow UB**: `ADD`, `SUB`, `MUL` MUST cast `a` and `b` to `uint64_t` in C++ before computing `+`, `-`, `*` so `-O3` never exploits signed integer overflow UB.

---

### `0x0D` — `OP_SCALAR_FP_ALU`
* **Summary**: IEEE-754 double-precision (`f64`) scalar arithmetic, rounding, FMA, and numeric conversions on `R0..R15`.
* **Encoding**:
  - `flags:4`: `0x0`
  - `vm_flags` updated: `ZF = (!valid[dst] || as_f64(R[dst]) == 0.0)`, `NF = !valid[dst]`.
* **Sub-Operations (`subop:4` (`0..15`))**:

| `subop` | Mnemonic | Arity | Semantics (`f64` bit-cast in `R`) |
| :--- | :--- | :--- | :--- |
| `0` | `.add` | Binary (`s1, s2`) | `a + b` |
| `1` | `.sub` | Binary (`s1, s2`) | `a - b` |
| `2` | `.mul` | Binary (`s1, s2`) | `a * b` |
| `3` | `.div` | Binary (`s1, s2`) | `b == 0.0 ? NULL : (a / b)` (Kleene `NULL` on div-by-zero; use `.safe_div` for fallback). |
| `4` | `.neg` | Unary (`s1`) | `-a` |
| `5` | `.abs` | Unary (`s1`) | `fabs(a)` |
| `6` | `.sqrt` | Unary (`s1`) | `a < 0.0 ? NULL : sqrt(a)` |
| `7` | `.min` | Binary (`s1, s2`) | `a < b ? a : b` (`min(-0.0, +0.0) = -0.0`) |
| `8` | `.max` | Binary (`s1, s2`) | `a > b ? a : b` (`max(-0.0, +0.0) = +0.0`) |
| `9` | `.fma` | Ternary (`s1, s2, s3`) | `fma(a, b, c)` (single-rounding IEEE-754 fused multiply-add) |
| `10` | `.floor` | Unary (`s1`) | `floor(a)` |
| `11` | `.ceil` | Unary (`s1`) | `ceil(a)` |
| `12` | `.round` | Unary (`s1`) | `round_half_away_from_zero(a)` (`std::round` — note Java `Math.round` differs on `.5` negatives!) |
| `13` | `.i64_to_f64` | Unary (`s1`) | `(double)(int64_t)R[s1]` |
| `14` | `.f64_to_i64` | Unary (`s1`) | UB-free saturating `trunc(a)` clamped to `[INT64_MIN, INT64_MAX]` (`±Inf` clamps; `NULL` propagates). |
| `15` | `.safe_div` | Ternary (`s1, s2, s3`) | `(b == 0.0 \|\| !valid[s2]) ? R[s3] : (a / b)` |

* **ImpAsm Usage**:
  ```impas
  ; PageRank teleport scalar: base = (1.0 - damping) / N
  SCALAR_FP_ALU.i64_to_f64 R3, R2          ; R3 = (double)N
  SCALAR_FP_ALU.sub        R4, R0, R1      ; R4 = 1.0 - 0.85
  SCALAR_FP_ALU.div        R5, R4, R3      ; R5 = 0.15 / N
  ```
* **Justification**: Enables dynamic query threshold computation, PageRank damping normalization `(1 - d) / N + d * dangling_sum / N`, and degree-skew cost formulas directly in VM scalar registers.
* **Gotchas**:
  1. **`NaN` $\to$ Kleene `NULL` Canonicalization**: Any operation producing `isnan(res)` (such as `Inf - Inf` or `0.0 * Inf`) MUST canonicalize `valid[dst] = 0, R[dst] = 0ULL` so x86 and ARM64 NaN payload differences can never diverge in `ICTX v2`!
  2. **Java `Math.round` vs C `round()`**: Java `Math.round(-2.5)` rounds toward $+\infty$ (`-2`), whereas C `round(-2.5)` and OCaml `Float.round (-2.5)` round half away from zero (`-3.0`). Java MUST implement `.round` as `Math.copySign(Math.floor(Math.abs(x) + 0.5), x)`!
  3. **`min(-0.0, +0.0)`**: Plain C `a < b ? a : b` returns `+0.0` when `a = +0.0, b = -0.0`, whereas Java `Math.min(+0.0, -0.0)` returns `-0.0`! All 4 engines MUST check `(a == 0.0 && b == 0.0)` and combine sign bits (`|=` for `.min`, `&=` for `.max`) to match IEEE-754 `minimum`/`maximum` bit-identically.

---

### `0x0E` — `OP_SCALAR_3VL`
* **Summary**: Scalar Kleene three-valued comparisons, logical connectives, null checks, and scalar `COALESCE` on `R0..R15` + `r_valid_mask`.
* **Encoding**:
  - `flags:4`: `0x0`
  - `s3`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: `ZF = (!v || R[dst] == 0)`, `NF = !v`.
* **Sub-Operations (`subop:4` (`0..15`))**:

| `subop` | Mnemonic | Operands | Semantics (Outputs `0` or `1` in `R[dst]`, except `COALESCE`) |
| :--- | :--- | :--- | :--- |
| `0` | `.cmp_eq_i64` | `s1, s2` | `v = va & vb`; `d = v & (i64(a) == i64(b))` |
| `1` | `.cmp_ne_i64` | `s1, s2` | `v = va & vb`; `d = v & (i64(a) != i64(b))` (**`NULL != 5` $\to$ `NULL`!**) |
| `2` | `.cmp_lt_i64` | `s1, s2` | `v = va & vb`; `d = v & (i64(a) < i64(b))` (`.gt_i64` swaps `s1, s2` in assembler!) |
| `3` | `.cmp_le_i64` | `s1, s2` | `v = va & vb`; `d = v & (i64(a) <= i64(b))` (`.ge_i64` swaps `s1, s2` in assembler!) |
| `4` | `.cmp_lt_u64` | `s1, s2` | `v = va & vb`; `d = v & (u64(a) < u64(b))` |
| `5` | `.cmp_le_u64` | `s1, s2` | `v = va & vb`; `d = v & (u64(a) <= u64(b))` |
| `6` | `.cmp_eq_f64` | `s1, s2` | `v = va & vb`; `d = v & (f64(a) == f64(b))` |
| `7` | `.cmp_ne_f64` | `s1, s2` | `v = va & vb`; `d = v & (f64(a) != f64(b))` |
| `8` | `.cmp_lt_f64` | `s1, s2` | `v = va & vb`; `d = v & (f64(a) < f64(b))` |
| `9` | `.cmp_le_f64` | `s1, s2` | `v = va & vb`; `d = v & (f64(a) <= f64(b))` |
| `10` | `.and` | `s1, s2` | Kleene AND (`FALSE && NULL == FALSE`, `TRUE && NULL == NULL`) |
| `11` | `.or` | `s1, s2` | Kleene OR (`TRUE \|\| NULL == TRUE`, `FALSE \|\| NULL == NULL`) |
| `12` | `.not` | `s1` (`s2=0`) | Kleene NOT (`NOT(NULL) == NULL`, `NOT(FALSE) == TRUE`) |
| `13` | `.is_null` | `s1` (`s2=0`) | `v = 1, d = !va` (always valid 2-valued `0`/`1`) |
| `14` | `.is_not_null` | `s1` (`s2=0`) | `v = 1, d = va` (always valid 2-valued `0`/`1`) |
| `15` | `.coalesce` | `s1, s2` | `va ? (va, R[s1]) : (vb, R[s2])` |

* **ImpAsm Usage**:
  ```impas
  ; Bidirectional BFS step direction check: if (deg_fwd <= deg_rev) walk_fwd else walk_rev
  SCALAR_3VL.cmp_le_u64 R4, R2, R3
  JCC.jfalse_or_null_r  R4, +walk_rev
  ```
* **Justification**: Provides full SQL/CEL Kleene truth-table semantics for scalar parameters, cardinality/degree comparisons, and guard expressions while fitting signed, unsigned, float64, 3VL logic, and `COALESCE` into 16 subops via operand-commuted `.gt`/`.ge` assembler aliases.
* **Gotchas**: Because `ZF = 1` whenever `R[dst]` is **either** `FALSE` (`v=1, d=0`) **or** `NULL` (`v=0, d=0`), `JCC.jnz` (or `JCC.jtrue_r`) branches **only** on Kleene `TRUE`, matching SQL/CEL `WHERE` / `IF` semantics! Never treat `JZ` as "definitely Kleene `FALSE`" unless `NF == 0` is also checked!

---

### `0x0F` — `OP_JMP`
* **Summary**: Unconditional PC-relative jump by signed 32-bit word offset `imm32`.
* **Encoding**:
  - `flags:4`: `0x0`; `subop:4`: `0`; `dst, s1, s2, s3`: `0` (MBZ); `imm32`: `int32_t word_offset`
  - `vm_flags` updated: None.
* **Operational Semantics**: `state->pc = (uint32_t)((int64_t)state->pc + (int64_t)(int32_t)imm32)`.
* **ImpAsm Usage**:
  ```impas
  JMP +done_label
  ```
* **Justification**: Position-independent signed word offset allows relocatable `ImpScheme` macro blocks without jump-target patching tables.
* **Gotchas**:
  1. Offset is relative to the `OP_JMP` instruction's own `pc` (matching v0.10 `op_50_jmp.inc`), so `imm32 == +1` is a fallthrough no-op and `imm32 == 0` is a self-loop rejected by `impulse_vm_validate` (`ERR_VALIDATION_FAILED`).
  2. Inside a lexical morsel block, `OP_JMP` MUST have `imm32 > 0` and `pc + imm32 <= morsel_end_pc` (forward-only intra-morsel jump).

---

### `0x10` — `OP_JCC`
* **Summary**: Conditional PC-relative branch testing `vm_flags` (`ZF`, `ST`, `NF`), scalar `R[s1]`, or frontier `F[s1]`.
* **Encoding**:
  - `flags:4`: `0x0`
  - `dst, s2, s3`: `0` (MBZ); `imm32`: `int32_t word_offset`
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` (`0..9`))**:

| `subop` | Mnemonic | `s1` Bank | Branch Taken Condition |
| :--- | :--- | :--- | :--- |
| `0` | `.jz` | `0` (MBZ) | `ZF == 1` |
| `1` | `.jnz` | `0` (MBZ) | `ZF == 0` |
| `2` | `.jst` | `0` (MBZ) | `ST == 1` (converged) |
| `3` | `.jnst` | `0` (MBZ) | `ST == 0` (not yet converged) |
| `4` | `.jnull` | `0` (MBZ) | `NF == 1` |
| `5` | `.jnnull` | `0` (MBZ) | `NF == 0` |
| `6` | `.jtrue_r` | `R[s1]` | `valid[s1] == 1 && R[s1] != 0` |
| `7` | `.jfalse_or_null_r` | `R[s1]` | `valid[s1] == 0 \|\| R[s1] == 0` |
| `8` | `.jempty_f` | `F[s1]` / `MF[s1&7]` | `is_empty(F[s1])` ($O(1)$ check!) |
| `9` | `.jnonempty_f` | `F[s1]` / `MF[s1&7]` | `!is_empty(F[s1])` ($O(1)$ check!) |

* **ImpAsm Usage**:
  ```impas
  ; Inside a morsel block, skip expensive target gathers if 0 lanes survived first filter:
  JCC.jempty_f MF0, +skip_to_end
  ```
* **Justification**: Replaces `OP_JZ` (`0x51`) and `OP_JNZ` (`0x52`), fixes the v0.10 harness `ST`-vs-`LT` flag confusion, and adds direct register/frontier branches (`.jtrue_r`, `.jempty_f`) that work cleanly inside parallel morsel blocks without mutating shared `vm_flags`!
* **Gotchas**: Inside `(morsel_hdr_pc, morsel_end_pc)`, **only** register/morsel-private predicates (`.jtrue_r`, `.jfalse_or_null_r`, `.jempty_f` on `MF0..MF7`, `.jnonempty_f` on `MF0..MF7`) with **positive** `imm32 > 0` (`pc + imm32 <= morsel_end_pc`) are permitted by `impulse_vm_validate`, because shared `vm_flags` are not updated per-thread inside parallel morsel bodies!

---

### `0x11` — `OP_LOOP_DECR`
* **Summary**: Decrements loop counter `R[dst]` and branches by `imm32` if `R[dst] > 0`.
* **Encoding**:
  - `flags:4`: `0x0`; `subop:4`: `0`; `dst`: counter `R[dst]`; `s1, s2, s3`: `0` (MBZ); `imm32`: `int32_t word_offset`
  - `vm_flags` updated: `ZF = (R[dst] == 0)`.
* **Operational Semantics**: Requires `valid[dst] == 1` (if `R[dst]` is `NULL`, returns `IMPULSE_VM_ERR_INVALID_OPERAND` `6`). Computes `int64_t next = (int64_t)((uint64_t)R[dst] - 1ULL)`, writes `R[dst] = (uint64_t)next`, sets `ZF = (next == 0)`, and if `next > 0` sets `pc += (int32_t)imm32`, else `pc += 1`.
* **ImpAsm Usage**:
  ```impas
  LOAD_CONST.i32 R0, 20       ; 20 PageRank iterations
  pr_loop:
    SPMV.fwd_plus_times V1, F0, V0, rel=0, attr=0xFFFF
    SWAP.v              V0, V1
    LOOP_DECR           R0, pr_loop
  ```
* **Justification**: Single-instruction fused decrement-and-branch eliminates loop overhead in fixed-iteration `PageRank`, `HITS`, and $k$-step random walks.
* **Gotchas**: If `R[dst]` starts $\le 0$ (e.g. `0` iterations), `R[dst]` decrements once to `-1` and **falls through** (`next > 0` is false); compilers emitting potentially-0-trip loops should guard entry with `JCC.jfalse_or_null_r` or pre-check `R[dst] <= 0`.

---

### `0x12` — `OP_CALL`
* **Summary**: Invokes subroutine at `pc + (int32_t)imm32` while shifting `(R, F, V)` register windows by `(s1, s2, s3)`.
* **Encoding**:
  - `flags:4`: `0x0`
  - `dst`: `0` (MBZ); `imm32`: `int32_t word_offset`
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` (`0..1`))**:

| `subop` | Mnemonic | Stride Nibbles (`s1, s2, s3`) | Window Shift Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.stride` | `s1=r_stride, s2=f_stride, s3=v_stride` (`0..15`) | Shifts `(R, F, V)` windows by `(s1, s2, s3)`; overlaps `[stride..15]` into callee `[0..15-stride]`. |
| `1` | `.full16` | `s1=0, s2=0, s3=0` (MBZ) | Shifts all three banks by full `16` slots (`0` register overlap; complete callee isolation). |

* **Operational Semantics**:
  1. Verifies `call_depth < hdr.max_call_depth` (`<= 16`), `r_win_base + r_stride + 16 <= 256`, `f_win_base + f_stride + 16 <= 128`, `v_win_base + v_stride + 16 <= 128`, and `spill_base + 16 <= 256` (else returns `IMPULSE_VM_ERR_STACK_OVERFLOW` `4`).
  2. Saves caller registers `[0 .. stride - 1]` (plus `r_valid_mask` bits and `r_type_word` nibbles) onto workspace backing window stacks, shifts `[stride .. 15]` down into callee `[0 .. 15 - stride]`, initializes newly exposed high registers `[16 - stride .. 15]` to clean empty/`NULL` state, and advances `spill_base += 16`.
  3. Pushes `(return_pc = pc + 1, r_stride, f_stride, v_stride)` onto `ws->call_frames[call_depth++]` and sets `pc = pc + (int32_t)imm32`.
* **ImpAsm Usage**:
  ```impas
  ; Save R0..R11, F0..F11, V0..V11; pass args/ret in R12..R15 -> callee R0..R3, F12..F15 -> F0..F3:
  CALL.stride r=12, f=12, v=12, +bfs_helper
  ```
* **Justification**: Replaces broken v0.10 `OP_CALL` (`0x55`, which overwrote `R0..R3` without saving them) and eliminates `OP_ENTER_FRAME` (`0x57`) overhead.
* **Gotchas**: Any newly exposed callee registers `[16 - stride .. 15]` in `R` start as Kleene `NULL` (`valid=0`), and in `F`/`V` start `uninitialized` — the callee cannot spy on stale values from previous subroutine calls!

---

### `0x13` — `OP_RET`
* **Summary**: Returns from subroutine, restoring caller register windows and deterministically releasing all callee-local `F`/`V` pool allocations (RAII).
* **Encoding**:
  - `flags:4`: `0x0`; `subop:4`: `0`; `dst, s1, s2, s3`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: Preserved from callee (allows returning status in `ZF`/`ST` as well as overlapping window registers).
* **Operational Semantics**:
  1. Checks `call_depth > 0` (else returns `IMPULSE_VM_ERR_STACK_UNDERFLOW` `5`).
  2. Pops `(return_pc, r_stride, f_stride, v_stride)` from `ctx->call_frames[--call_depth]`.
  3. **RAII Workspace Reclamation**: Releases all `F` descriptors in `[16 - f_stride .. 15]`, all `V` descriptors in `[16 - v_stride .. 15]`, and all `F`/`V` descriptors in the callee's `16` spill slots back to the caller workspace slab freelist, and decrements `spill_base -= 16`.
  4. Shifts overlapping return registers `[0 .. 15 - stride]` (plus validity bits and `r_type_word` nibbles) back to `[stride .. 15]`, restores saved caller `[0 .. stride - 1]` from the window stack, and sets `pc = return_pc`.
* **ImpAsm Usage**:
  ```impas
  RET
  ```
* **Justification**: Replaces `OP_RET` (`0x56`) + `OP_LEAVE_FRAME` (`0x58`) and guarantees zero off-heap slab/buffer leaks across recursive helper calls without garbage collection.
* **Gotchas**: To return a frontier or vector to the caller, the callee MUST place it inside the shared overlap window `[0 .. 15 - stride]` (so `stride` MUST be $\le 15$ for that bank; `.full16` isolates all 16 registers and reclaims all 16 on `RET`!).

---

### `0x14` — `OP_SET_MAX_DOP`
* **Summary**: Configures maximum intra-instruction worker parallelism (`state->max_dop`).
* **Encoding**:
  - `flags:4`: `0x0`; `dst, s2, s3`: `0` (MBZ); `imm16_hi`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` (`0..1`))**:

| `subop` | Mnemonic | Source | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.imm` | `imm16_lo = dop` (`s1=0`) | Clamps `imm16_lo` to `[1, host_max_threads]` and updates `state->max_dop`. |
| `1` | `.reg` | `R[s1]` (`imm32=0`) | Clamps `R[s1]` to `[1, host_max_threads]` and updates `state->max_dop`. |

* **Operational Semantics**: Clamps requested `dop` (`<= 0` $\to$ `1`; `> ctx->host_max_threads` $\to$ `ctx->host_max_threads`) and writes `state->max_dop`.
* **ImpAsm Usage**:
  ```impas
  SET_MAX_DOP.imm 4
  ```
* **Justification**: Enables query governors under high multi-tenant QPS to cap intra-query OpenMP/ForkJoin worker fan-out to `1` while batch analytics scale to all cores, and enables compliance harnesses to test `max_dop = 1` vs `max_dop = 4` deterministically.
* **Gotchas**: Changing `max_dop` **MUST NEVER** change `logical_hash` or `physical_hash` (`AGENTS.md` §3.18); any opcode implementation whose output changes when `SET_MAX_DOP` varies is non-compliant!

---

## Pillar 2 — Polymorphic Frontier & Set Algebra (`0x20`–`0x27`)

---

### `0x20` — `OP_FSEED`
* **Summary**: Initializes or point-mutates a 1-bit domain-bound frontier `F[dst]`.
* **Encoding**:
  - `flags:4`: `0x0`, or `0x4` (`FLAG_ACCUM` allowed on `subop = 1, 2`)
  - `s2, s3`: `0` (MBZ)
  - `vm_flags` updated: `ZF = is_empty(F[dst])`.
* **Sub-Operations (`subop:4`)**:

| `subop` | Mnemonic | Operands | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.empty` | `dst`, `imm16_hi=domain_id` (`s1=0, imm16_lo=0`) | Initializes `F[dst]` as `EMPTY` ($W=1$) in `domain_id` (`cached_card = 0, ZF = 1`). |
| `1` | `.single_imm` | `dst`, `imm16_lo=node_u16`, `imm16_hi=domain_id` | Initializes `F[dst]` in `TIER0_INLINE` containing `{node_u16}` (or inserts if `.accum`); bounds-checks `node_u16 < N_domain`. |
| `2` | `.single_reg` | `dst`, `s1=R[s1]`, `imm16_hi=domain_id` | If `R[s1]` is `NULL`: yields empty frontier (or no-op if `.accum`). Else bounds-checks `0 <= R[s1] < N_domain` (`ERR_OUT_OF_BOUNDS` `2` if out of range) and seeds `{R[s1]}`. |
| `3` | `.insert_reg` | `dst`, `s1=R[s1]` (`imm32=0`) | Mutates existing 1-bit `F[dst]` by inserting `R[s1]` (promotes Tier 0 $\to$ Tier 1 if exceeding 64 unique IDs; updates `cached_card` if `>= 0`). |
| `4` | `.remove_reg` | `dst`, `s1=R[s1]` (`imm32=0`) | Removes `R[s1]` from existing 1-bit `F[dst]` (updates `cached_card` if `>= 0`). |

* **ImpAsm Usage**:
  ```impas
  FSEED.single_imm       F0, node=42, dom=0
  FSEED.single_reg.accum F0, R1, dom=0
  ```
* **Justification**: Provides $O(1)$ zero-heap-allocation Tier 0 seeding at any graph scale ($N_d = 10^9$) while strictly binding `domain_id` (`AGENTS.md` §3.14).
* **Gotchas**:
  1. Using `.accum` (`FSEED.single_reg.accum`) when `F[dst]` is already initialized to a *different* `domain_id` (or is multi-lane $W > 1$) fails with `IMPULSE_VM_ERR_DOMAIN_MISMATCH` (`10`) / `ERR_TYPE_MISMATCH` (`14`).
  2. Negative signed `i64` values in `R[s1]` (`(uint64_t)R[s1] >= N_domain`) fail bounds check (`ERR_OUT_OF_BOUNDS` `2`).

---

### `0x21` — `OP_INIT_DOMAIN_SPAN`
* **Summary**: $O(1)$ virtual initialization of `F[dst]` to all nodes `[0, N_d)` of `domain_id = imm16_lo`.
* **Encoding**:
  - `flags:4`: `0x0`; `subop:4`: `0`; `dst`: `F[dst]`; `s1, s2, s3`: `0` (MBZ); `imm16_lo`: `domain_id`, `imm16_hi`: `0` (MBZ)
  - `vm_flags` updated: `ZF = (N_d == 0)`.
* **Operational Semantics**: Validates `domain_id < snapshot.num_domains` (`ERR_NULL_SNAPSHOT` `3` if no snapshot, `ERR_OUT_OF_BOUNDS` `2` if invalid domain) and sets `F[dst]` descriptor to virtual tier `ALL_SPAN` (`domain_id`, `lane_width = 1`, `cached_card = N_d`) in **0 bytes allocated** (`EMPTY` if $N_d == 0$).
* **ImpAsm Usage**:
  ```impas
  INIT_DOMAIN_SPAN F0, dom=0          ; Anchor all User nodes in O(1)!
  NODE_FILTER.gt.scalar F1, F0, R1, dom=0, attr=0
  ```
* **Justification**: Replaces v0.10's `TYPE_CSR_SPAN` hack (which only worked on some opcodes and failed on `SET_DIFFERENCE`/`SET_CARDINALITY`) with a first-class `VmFrontier` tier (`ALL_SPAN`) universally accepted by **every** `F`-consuming opcode!
* **Gotchas**: Downstream `OP_SET_OP`, `OP_WALK`, `OP_SPMV`, `OP_NODE_FILTER`, and `OP_SET_CARDINALITY` MUST handle `ALL_SPAN` directly without materializing an $N_d$-bit array first (e.g., `INTERSECT(ALL_SPAN, B) == B`; `DIFF(ALL_SPAN, B) == COMPLEMENT(B)`!).

---

### `0x22` — `OP_SET_OP`
* **Summary**: Polymorphic binary set algebra (`UNION`, `INTERSECT`, `DIFF`, `SYM_DIFF`) over same-domain frontiers `F[s1]` and `F[s2]`.
* **Encoding**:
  - `flags:4`: `0x0` (none allowed; use `SET_OP.union F0, F0, F2` for in-place accumulation)
  - `dst`: `F[dst]`; `s1`: `F[s1]`; `s2`: `F[s2]`; `s3`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: `ZF = is_empty(F[dst])`.
* **Sub-Operations (`subop:4` (`0..3`))**:

| `subop` | Mnemonic | Set / Multi-Lane Operation | Bitwise Word Formula |
| :--- | :--- | :--- | :--- |
| `0` | `.union` | $A \cup B$ | `w_a \| w_b` |
| `1` | `.intersect` | $A \cap B$ | `w_a & w_b` |
| `2` | `.diff` | $A \setminus B$ | `w_a & ~w_b` |
| `3` | `.sym_diff` | $A \triangle B$ | `w_a ^ w_b` |

* **Operational Semantics**:
  1. Verifies `F[s1].domain_id == F[s2].domain_id` (`ERR_DOMAIN_MISMATCH` `10` if unequal) and `F[s1].lane_width == F[s2].lane_width` (`ERR_TYPE_MISMATCH` `14` if unequal).
  2. Dispatches optimal cross-tier kernel:
     - `Tier 0 ∩ Any`: $O(|A|)$ membership probe into $B$, outputting `Tier 0` (`<= 64` items) in nanoseconds even if $B$ is `Tier 2` (`12.5 MB`)!
     - `Tier 1 ∩ Tier 1`: Iterates the smaller `dirty_pages[]` list and intersects only co-resident 4K pages!
     - `Tier 1 \ Tier 2` / `Tier 2 op Tier 2`: Word-streams 64-bit words while accumulating `popcnt64(out_word)` in a scalar register to populate `F[dst].cached_card` at **zero extra cost**!
     - Multi-lane ($W \in \{8..64\}$): Applies bitwise `|`, `&`, `& ~`, `^` across per-node $W$-bit lane words.
* **ImpAsm Usage**:
  ```impas
  SET_OP.diff  F2, F1, F0         ; delta = next \ visited
  SET_OP.union F0, F0, F2         ; visited |= delta
  ```
* **Justification**: Consolidates `OP_SET_UNION` (`0x30`), `OP_SET_INTERSECT` (`0x31`), `OP_SET_DIFFERENCE` (`0x32`), `OP_FRONTIER_DIFF` (`0x8A`), and all three `OP_ROARING_BITMAP_*` (`0x64`, `0x6B`, `0x6C`) into 1 orthogonal domain-safe instruction.
* **Gotchas**:
  1. **Aliasing (`dst == s1` or `dst == s2`)**: `SET_OP.union F0, F0, F1` is ubiquitous; kernels MUST support in-place `dst == s1` and `dst == s2` without corrupting input pages mid-loop!
  2. When `Tier 1` intersection or difference clears all bits in a 4K page (`page_or_acc == 0`), that page MUST be released/unlinked from `dirty_pages[]` so `is_empty(F[dst])` (`dirty_count == 0`) remains exact!

---

### `0x23` — `OP_SET_COMPLEMENT`
* **Summary**: Domain-bounded set complement `F[dst] = [0, N_d) \ F[s1]`.
* **Encoding**:
  - `flags:4`: `0x0`; `subop:4`: `0`; `dst`: `F[dst]`; `s1`: `F[s1]` (must be 1-bit $W=1$); `s2, s3`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: `ZF = is_empty(F[dst])`.
* **Operational Semantics**: Produces a 1-bit frontier in `F[s1].domain_id` containing every dense ID $u \in [0, N_d)$ not in `F[s1]`. Fast paths: `COMPLEMENT(EMPTY) -> ALL_SPAN`; `COMPLEMENT(ALL_SPAN) -> EMPTY`. For `Tier 0`/`Tier 1`/`Tier 2`, writes `Tier 2` (unless $N_d - |F| \le 64$) and sets `cached_card = (F[s1].cached_card >= 0) ? (N_d - F[s1].cached_card) : popcnt_acc`.
* **ImpAsm Usage**:
  ```impas
  SET_COMPLEMENT F1, F0
  ```
* **Justification**: Replaces `OP_MASK_NOT` (`0x26`) for 2-valued domain sets while keeping Kleene 3VL negation (`NOT(NULL) = NULL`) cleanly separated in `OP_VEC_3VL_OP.not` (`0x46`).
* **Gotchas**: **Trailing Bit Masking Bug**: When $N_d \bmod 64 \ne 0$, bitwise `~word` sets high padding bits `[N_d % 64 .. 63]` to `1`! Implementations **MUST** mask the final `uint64_t` word with `((1ULL << (N_d & 63)) - 1ULL)` — failing to do so corrupts `SET_CARDINALITY`, `WALK` bounds, and `ICTX v2` hashes!

---

### `0x24` — `OP_SET_CARDINALITY`
* **Summary**: Computes or reads memoized cardinality of 1-bit or multi-lane frontier `F[s1]` into `R[dst]`.
* **Encoding**:
  - `flags:4`: `0x0`
  - `s2, s3`: `0` (MBZ); `imm32`: `0` (except `imm16_lo = lane_idx` on `subop == 4`)
  - `vm_flags` updated: `ZF = (R[dst] == 0)`, `NF = 0`.
* **Sub-Operations (`subop:4`)**:

| `subop` | Mnemonic | Required `F[s1]` | Semantics Written to `R[dst]` (`u64`, `valid=1`) |
| :--- | :--- | :--- | :--- |
| `0` | `.card_1bit` | $W = 1$ | Exact $\lvert F[s1] \rvert$. Returns `cached_card` in $O(1)$ if `>= 0`; else SIMD `vpopcntq` over `dirty_pages[]` / `L1` blocks and memoizes `F[s1].cached_card`. |
| `1` | `.lane_pop_sum` | $W \in \{8..64\}$ | $\sum_{u=0}^{N_d-1} \text{popcnt}(\text{lanes}[u])$ across all active lanes. |
| `2` | `.lane_any_nodes` | $W \in \{8..64\}$ | Count of nodes $u$ with $\text{lanes}[u] \ne 0$. |
| `3` | `.lane_all_nodes` | $W \in \{8..64\}$ | Count of nodes $u$ where `(lanes[u] & active_lane_mask) == active_lane_mask`. |
| `4` | `.single_lane` | $W \in \{8..64\}$ | Count of nodes active in lane `imm16_lo` (`0 <= imm16_lo < W`). |

* **ImpAsm Usage**:
  ```impas
  SET_CARDINALITY.card_1bit R0, F1
  ```
* **Justification**: Unifies lazy memoized 1-bit cardinality and multi-lane reachability counting without burning a global modifier flag on `OP_WALK`.
* **Gotchas**: On `subop == 3` (`.lane_all_nodes`), if `F[s1]` was initialized with `K = 0` seeds (`active_lane_mask == 0`), `.lane_all_nodes` MUST return `0` (not $N_d$!).

---

### `0x25` — `OP_SET_CONTAINS`
* **Summary**: $O(1)$ point membership or lane-word lookup of node `R[s2]` in frontier `F[s1]`.
* **Encoding**:
  - `flags:4`: `0x0`
  - `dst`: `R[dst]`; `s1`: `F[s1]`; `s2`: `R[s2]`; `s3`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: `ZF = (!valid[dst] || R[dst] == 0)`, `NF = !valid[dst]`.
* **Sub-Operations (`subop:4` (`0..1`))**:

| `subop` | Mnemonic | Required `F[s1]` | Result in `R[dst]` (`NULL` if `R[s2]` is `NULL`) |
| :--- | :--- | :--- | :--- |
| `0` | `.contains_1bit` | $W = 1$ | `1` if `R[s2]` $\in F[s1]$, else `0`. |
| `1` | `.get_lane_mask` | $W \in \{8..64\}$ | Zero-extended $W$-bit active lane mask of node `R[s2]` in `F[s1]`. |

* **Operational Semantics**: If `R[s2]` is Kleene `NULL`, writes `NULL` (`valid[dst]=0, R[dst]=0, NF=1, ZF=1`). Otherwise verifies `0 <= R[s2] < N_domain` (`ERR_OUT_OF_BOUNDS` `2` if out of bounds) and probes `F[s1]` (`EMPTY -> 0`, `ALL_SPAN -> 1`, `TIER0_INLINE -> SIMD/binary search over <= 64 sorted IDs`, `TIER1_PAGED -> page_dir[u >> 12]`, `TIER2_DENSE -> bit test`).
* **ImpAsm Usage**:
  ```impas
  ; ReBAC check: did transitive walk from User reach target Resource R2?
  WALK.fwd_fixpoint_star F1, F0, rel=0
  SET_CONTAINS.contains_1bit R3, F1, R2
  ```
* **Justification**: Replaces dedicated `OP_REBAC_CHECK` (`0x63`) by composing cleanly with `OP_WALK` / `OP_LANE_WALK` for sub-microsecond point reachability checks.
* **Gotchas**: Note that `SET_CONTAINS` is a scalar terminal/guard probe (`s1=F, s2=R -> dst=R`); per `AGENTS.md` §3.16, compilers MUST NEVER emit scalar VM loops calling `SET_CONTAINS` per node when `OP_SET_OP.intersect` handles set filtering natively.

---

### `0x26` — `OP_SET_CONVERT`
* **Summary**: Converts between `F` frontiers, sorted dense-ID `V` vectors, and Kleene `BOOL_3VL` vectors.
* **Encoding**:
  - `flags:4`: `0x0` (or `0x4` `FLAG_ACCUM` on `subop = 1, 2`)
  - `s2, s3`: `0` (MBZ); `imm32`: `0` (`imm16_lo = domain_id` on `subop == 1` outside morsel)
  - `vm_flags` updated: `ZF = is_empty_or_zero(dst)`.
* **Sub-Operations (`subop:4`)**:

| `subop` | Mnemonic | Signature | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.f2v_ids` | `V[dst] <- F[s1]` | Extracts active dense IDs from 1-bit `F[s1]` in **strictly ascending order** into `V[dst]` (`U32` if $N_d \le 2^{32}$, else `U64`, `domain_id = 0xFFFF` compact list); sets `F[s1].cached_card = len`, `ZF = (len == 0)`. |
| `1` | `.v2f_ids` | `F[dst] <- V[s1]`, `imm16_lo=domain_id` | Scatters valid dense IDs from `V[s1]` (`I64`/`U64`/`I32`/`U32`) into 1-bit `F[dst]` in `domain_id` (skips `NULL` vector elements; bounds-checks `< N_domain`). |
| `2` | `.b2f` | `F[dst] <- V[s1]` | **Kleene 3VL Collapse**: converts domain-aligned (or morsel-aligned `M -> MF`) `BOOL_3VL` vector `V[s1]` into 1-bit frontier `F[dst]` (`bits = data` since `data <= valid`; both `FALSE` and `NULL` map to `0`!). Zero-copy bitmask borrow when `Tier 2` / morsel `MF`! |
| `3` | `.f2b` | `V[dst] <- F[s1]` | Converts 1-bit `F[s1]` (`domain_id` or morsel `MF`) into `BOOL_3VL` vector `V[dst]` with `valid = all_ones`, `data = frontier_bits`. |

* **ImpAsm Usage**:
  ```impas
  ; Inside morsel: collapse 3VL predicate M5 into morsel active mask MF0
  SET_CONVERT.b2f MF0, M5
  ; After ANN search (which outputs rank-ordered V1), convert top candidates to F1 for graph walk:
  SET_CONVERT.v2f_ids F1, V1, dom=0
  ```
* **Justification**: Bridges ordered candidate vectors (`OP_VECTOR_ANN_SEARCH`, `OP_TOP_K`), unordered 3-tier sets (`F0..F15`), and 3VL predicate vectors (`V0..V15` / `M4..M7`) while keeping every other opcode's destination bank 100% static!
* **Gotchas**:
  1. `.f2v_ids` **MUST** output IDs in ascending order even when `F[s1]` is `TIER1_PAGED` (where `dirty_pages[]` insertion order may be unsorted! Sort `dirty_pages[0..dirty_count)` by `page_id` before emitting IDs!).
  2. Inside a morsel block, `.b2f` (`M_src -> MF_dst`) with `.accum` performs `MF_dst |= data`; to *narrow* an existing morsel mask (`MF0 &= cond`), use `SET_CONVERT.b2f MF1, M5` + `SET_OP.intersect MF0, MF0, MF1` (or `VEC_CMP ... .mask MF0` + `SET_CONVERT.b2f MF0, M5`, since unmasked lanes in a `.mask MF0` comparison already output `NULL (0,0)` $\to$ `0`!).

---

### `0x27` — `OP_STABLE_CHECK`
* **Summary**: Tests fixed-point convergence between two frontiers (`F[s1] == F[s2]`) or two numeric state vectors ($||V[s1] - V[s2]||_1 \le \epsilon$).
* **Encoding**:
  - `flags:4`: `0x0` (none allowed; on `subop=1`, `s3` directly addresses `R[s3]` tolerance $\epsilon$)
  - `imm32`: `0` (MBZ)
* **Sub-Operations (`subop:4`)**:

| `subop` | Mnemonic | Signature | Convergence Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.frontier_eq` | `s1=F[s1], s2=F[s2]` (`dst=0, s3=0`) | Exact set/lane equality across `F[s1]` and `F[s2]` (same `domain_id` and `lane_width`). Fast reject if both `cached_card >= 0` and unequal! Sets `ST = eq`, `ZF = eq`. |
| `1` | `.vec_l1` | `dst=R[dst], s1=V[s1], s2=V[s2], s3=R[s3]` | Computes deterministic 64-block pairwise $L_1$ distance $d = \sum_i \lvert V[s1][i] - V[s2][i] \rvert$ into `R[dst]` (`f64`, `valid=1`), setting `ST = (d <= as_f64(R[s3]))`, `ZF = (d == 0.0)`, `NF = 0`. |

* **ImpAsm Usage**:
  ```impas
  STABLE_CHECK.vec_l1 R6, V1, V0, R5   ; R6 = ||V1 - V0||_1; ST = (R6 <= R5)
  JCC.jnst            pr_loop          ; Repeat until converged!
  ```
* **Justification**: Unifies `OP_STABLE_CHECK` (`0x54`) and `OP_L1_NORM_DIFF` (`0x39`) into a single convergence primitive supporting both discrete set reachability (`Datalog` / `BFS`) and continuous numeric relaxation (`PageRank` / `Eigenvector` / `Belief Propagation`).
* **Gotchas**:
  1. On `.frontier_eq` across different tiers (e.g. `F[s1]` is `TIER1_PAGED` after deletions while `F[s2]` is `TIER0_INLINE`), equality MUST compare **logical membership**, NEVER raw tier tags!
  2. On `.vec_l1`, if at index $i$ both `V[s1][i]` and `V[s2][i]` are `NULL`, their difference contributes `0.0`; if at least one lane has exactly one `NULL` (e.g. newly discovered SSSP distance vs `NULL`/unreached), that lane contributes `0.0` to the finite sum `R[dst]` while `ST` is forced to `0` (`not converged`)!

---

## Pillar 3 — Graph Topology, Semiring SpMV, Lexical Morsels & Kernels (`0x30`–`0x3B`)

---

### `0x30` — `OP_WALK`
* **Summary**: Physical-layout-agnostic 1-bit frontier expansion (`CSR`, `CSC`, `COO`, `Dense BitMatrix`) with automatic Beamer Push/Pull direction switching, fused exclude masking (`\ F[s3]`), and native transitive closure (`R^+`, `R^*`).
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM`), `0x1` (`FLAG_MASKED_S3`) allowed (`0x5` combined)
  - `dst`: `F[dst]` ($W=1$); `s1`: `F[s1]` ($W=1$); `s2`: `0` (MBZ); `s3`: `0`, or `F[s3]` exclude frontier (`F[s3].dom == out_dom`) when `FLAG_MASKED_S3` is set
  - `imm16_lo`: `rel_id`, `imm16_hi`: `0` (`k` on `subop == 7`)
  - `vm_flags` updated: `ZF = is_empty(F[dst])`; `ST = 1` on `subop 3..6` (and `subop 7` if converged early, else `ST = 0`).
* **Sub-Operations (`subop:4` (`0..7`))**:

| `subop` | Mnemonic | Domain Constraint (`rel = imm16_lo`) | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.fwd` | `F[s1].dom == rel.src_dom` $\to$ `F[dst].dom = rel.tgt_dom` | 1-hop forward expansion $Src \to Tgt$ (`imm16_hi` MBZ). |
| `1` | `.rev` | `F[s1].dom == rel.tgt_dom` $\to$ `F[dst].dom = rel.src_dom` | 1-hop reverse expansion $Tgt \to Src$ (`imm16_hi` MBZ). |
| `2` | `.both` | Endo-relation (`rel.src_dom == rel.tgt_dom`) | 1-hop undirected union `fwd(F[s1]) \| rev(F[s1])`. |
| `3` | `.fwd_fixpoint_plus` | Endo-relation (`src_dom == tgt_dom`) | Transitive closure $R^+(F[s1])$ ($\ge 1$ hops); sets `ST = 1` on convergence. |
| `4` | `.fwd_fixpoint_star` | Endo-relation (`src_dom == tgt_dom`) | Reflexive-transitive closure $R^*(F[s1]) = F[s1] \cup R^+(F[s1])$; sets `ST = 1`. |
| `5` | `.rev_fixpoint_plus` | Endo-relation (`src_dom == tgt_dom`) | Reverse transitive closure $(R^{-1})^+(F[s1])$; sets `ST = 1`. |
| `6` | `.rev_fixpoint_star` | Endo-relation (`src_dom == tgt_dom`) | Reverse reflexive-transitive closure $(R^{-1})^*(F[s1])$; sets `ST = 1`. |
| `7` | `.fwd_bounded` | Endo-relation (`src_dom == tgt_dom`) | Cumulative $1..k$ hop union ($\bigcup_{i=1}^{k} R^i(F[s1])$) where `k = imm16_hi` (`k >= 1`); sets `ST = 1` if delta empties before hop $k$. |

* **Operational Semantics**:
  1. Validates `rel_id < snapshot.num_relations` and verifies `F[s1].domain_id` (and `F[s3].domain_id` if `.mask`, `F[dst].domain_id` if `.accum`) against `rel.src_domain_id` / `rel.tgt_domain_id` (`ERR_DOMAIN_MISMATCH` `10` on mismatch).
  2. **Beamer Push/Pull + Fused Exclude (`\ F[s3]`)**: When both CSR and CSC exist on `rel_id`, computes/estimates active edge volume $m_{F[s1]}$ vs unexcluded target count. In Pull mode with `FLAG_MASKED_S3`, **skips any target $v \in F[s3]$ before reading `col_offsets[v]`** and breaks out of `col_indices` on the **first** neighbor $u \in F[s1]$!
  3. **Zero-Scan Empty `ZF` & Lazy `cached_card`**: Tracks `bool any_hit` in registers during Push scatter; if `!any_hit` (and not `.accum` on non-empty `dst`), sets `F[dst] = EMPTY, cached_card = 0, ZF = 1` in $O(1)$ (fixing v0.10 `op_10_csr_walk.inc`'s $O(N_d / 64)$ empty-bitset scan!). Otherwise sets `ZF = 0` and `cached_card = -1` on Push (or exact `popcnt_acc` on Pull!).
* **ImpAsm Usage**:
  ```impas
  ; Single-instruction BFS delta step: F_next = Walk(F_frontier, rel=0) \ F_visited
  WALK.fwd.mask       F2, F1, F0, rel=0      ; F2 = neighbors(F1) \ F0
  SET_OP.union        F0, F0, F2             ; F0 |= F2 (visited)
  ```
* **Justification**: Replaces **15** v0.10 opcodes (`OP_CSR_WALK`, `OP_CSC_WALK`, `OP_COO_WALK`, `OP_DENSE_WALK`, `OP_DENSE_WALK_BITMATRIX`, `OP_ADAPTIVE_WALK`, `OP_FIXPOINT_KLEENE_STAR`, and all `*_DIRECT_STORE` / `*_DENSE_STREAM` variants) with a single mathematical Kleisli frontier operator (`AGENTS.md` §3.15).
* **Gotchas**:
  1. Calling `.both` or `.*_fixpoint_*` (`subop 2..7`) on a **bipartite / cross-domain** relation where `rel.src_domain_id != rel.tgt_domain_id` is a domain type error (`IMPULSE_VM_ERR_DOMAIN_MISMATCH` `10`), caught statically by `impulse_vm_validate` when schema is bound!
  2. When `F[s1]` aliases `F[dst]` (`WALK.fwd F0, F0, rel=0` without `.accum`), `OP_WALK` MUST write into a newly leased destination frontier and swap/release old `F0` at completion — never mutate `F0` while iterating `F0`!
  3. On `.fwd_fixpoint_plus` with `.mask F_excl`, `F_excl` is excluded on **every** hop (preventing traversal *through* excluded/revoked nodes, not merely post-filtering the final set!).

---

### `0x31` — `OP_WALK_FILTERED`
* **Summary**: Fused single-attribute sargable edge-filtered walk (`F[dst] = { v | (u, v, e) \in E(rel), u \in F[s1], edge_attr[e] cmp R[s2] }`).
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM`), `0x1` (`FLAG_MASKED_S3`) allowed (`FLAG_SCALAR_RHS` not needed: `s2` is **always** `R[s2]`!)
  - `dst`: `F[dst]`; `s1`: `F[s1]`; `s2`: `R[s2]` (`0` on `subop 6,7,14,15`); `s3`: `0`, or `F[s3]` exclude mask if `.mask`
  - `imm16_lo`: `rel_id`, `imm16_hi`: `edge_attr_id`
  - `vm_flags` updated: `ZF = is_empty(F[dst])`.
* **Sub-Operations (`subop:4` `0..15`)**:

| `subop` (`FWD`) | `subop` (`REV`) | Comparator on `edge_attr[e]` vs `R[s2]` |
| :--- | :--- | :--- |
| `0` (`.eq`) | `8` (`.rev_eq`) | `attr[e] == R[s2]` |
| `1` (`.ne`) | `9` (`.rev_ne`) | `attr[e] != R[s2]` (Kleene 3VL: `NULL` edge attr $\to$ `FALSE`, never `TRUE`!) |
| `2` (`.lt`) | `10` (`.rev_lt`) | `attr[e] < R[s2]` |
| `3` (`.le`) | `11` (`.rev_le`) | `attr[e] <= R[s2]` |
| `4` (`.gt`) | `12` (`.rev_gt`) | `attr[e] > R[s2]` |
| `5` (`.ge`) | `13` (`.rev_ge`) | `attr[e] >= R[s2]` |
| `6` (`.is_not_null`) | `14` (`.rev_is_not_null`) | `valid(attr[e]) == 1` (`s2` MBZ) |
| `7` (`.is_null`) | `15` (`.rev_is_null`) | `valid(attr[e]) == 0` (`s2` MBZ) |

* **Operational Semantics**:
  - **Kleene Short-Circuit**: On `subop 0..5, 8..13`, if `R[s2]` is `NULL` (`r_valid_mask` bit `s2 == 0`), every edge comparison evaluates to Kleene `NULL` (non-true); `OP_WALK_FILTERED` immediately skips edge scanning in **$O(1)$** and produces an empty delta (`F[dst] = EMPTY` unless `.accum`)!
  - Automatically exploits `.imps` edge BRIN min/max zone maps or per-vertex sorted edge runs via binary search when present.
* **ImpAsm Usage**:
  ```impas
  ; Temporal walk: traverse edges with timestamp >= $since excluding already-visited F0
  WALK_FILTERED.ge.mask F2, F1, R1, F0, rel=0, attr=0
  ```
* **Justification**: Covers $>80\%$ of real-world edge predicates (timestamps, weights, status codes, relation subtypes) in **1 64-bit instruction** with zero morsel setup overhead, replacing `OP_CSR_WALK_FILTERED`, `OP_COO_WALK_FILTERED`, and `OP_BRIN_ZONE_SKIP`.
* **Gotchas**: Reverse filtered walks (`subop 8..15`) on snapshots where CSC stores a permutation `csc_edge_perm[idx]` MUST index `edge_attr[csc_edge_perm[idx]]` (or CSC-aligned edge attribute column), never raw CSR edge index `idx`!

---

### `0x33` — `OP_DEGREE`
* **Summary**: Exact topological degree inspection (frontier degree sum, per-node degree vector, or single-node point degree).
* **Encoding**:
  - `flags:4`: `0x1` (`FLAG_MASKED_S3` allowed on `subop = 2, 3`)
  - `s2`: `0` (MBZ); `s3`: `0` or `F[s3]` (`subop 2,3` w/ `.mask`); `imm16_lo`: `rel_id`, `imm16_hi`: `0` (MBZ)
  - `vm_flags` updated: On `R[dst]` subops (`0, 1, 4, 5`): `ZF = (!valid[dst] || R[dst] == 0)`, `NF = !valid[dst]`.
* **Sub-Operations (`subop:4` (`0..5`))**:

| `subop` | Mnemonic | Signature | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.sum_fwd_r` | `R[dst] <- F[s1]` | Exact edge volume $\sum_{u \in F[s1]} \deg^+(u)$ (`u64`, `valid=1`). |
| `1` | `.sum_rev_r` | `R[dst] <- F[s1]` | Exact reverse edge volume $\sum_{v \in F[s1]} \deg^-(v)$ (`u64`, `valid=1`). |
| `2` | `.vec_fwd_v` | `V[dst] <- (s1=0)` | Per-node out-degree vector `V[dst][u] = deg^+(u)` (`U32`/`U64` over `rel.src_dom`; masked by `F[s3]` if `.mask`). |
| `3` | `.vec_rev_v` | `V[dst] <- (s1=0)` | Per-node in-degree vector `V[dst][v] = deg^-(v)` over `rel.tgt_dom`. |
| `4` | `.node_fwd_r` | `R[dst] <- R[s1]` | Single-node $O(1)$ `row_offsets[u+1] - row_offsets[u]` (`NULL` propagates). |
| `5` | `.node_rev_r` | `R[dst] <- R[s1]` | Single-node $O(1)$ `col_offsets[v+1] - col_offsets[v]` (`NULL` propagates). |

* **ImpAsm Usage**:
  ```impas
  ; Exact edge-balanced bidirectional BFS heuristic:
  DEGREE.sum_fwd_r R2, F1, rel=0
  DEGREE.sum_rev_r R3, F2, rel=0
  ```
* **Justification**: Generalizes `OP_CSR_DEGREE` (`0x12`). `sum_fwd_r` / `sum_rev_r` compute exact active edge counts in $O(|F|)$ sequential/gather reads of `row_offsets`, preventing hub-skewed bidirectional BFS explosions; `vec_fwd_v` supplies out-degrees for `PageRank` (`rank[u] / out_deg[u]`).
* **Gotchas**: When `F[s1]` is `ALL_SPAN` on `.sum_fwd_r` / `.sum_rev_r`, return `rel.num_edges` in **$O(1)$** from the relation header without summing $N_d$ offset pairs!

---

### `0x34` — `OP_SPMV`
* **Summary**: Unified GraphBLAS Semiring Sparse Matrix-Vector Multiplication (`V[dst] = A(rel) \otimes_{\oplus} rhs` over active frontier `F[s1]`).
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM`, allowed on `subop 0..6` only; disallowed on `subop 7, 8`), `0x2` (`FLAG_SCALAR_RHS`: `s2` is `R[s2]`; use `R=1.0` on `.fwd_plus_times` or `R=0.0` on `.fwd_min_plus`/`.fwd_max_plus` for edge-only reductions!), `0x1` (`FLAG_MASKED_S3`: `F[s3]` target mask)
  - `dst`: `V[dst]`; `s1`: `F[s1]` (active source frontier); `s2`: `V[s2]` (or `R[s2]` w/ `.scalar`; `0` on `subop 7`); `s3`: `0` or `F[s3]` target mask (`.mask`)
  - `imm16_lo`: `rel_id`, `imm16_hi`: `edge_attr_id` (`0xFFFF` = unweighted topological edge weight `1` / `0` identity)
  - `vm_flags` updated: `ZF = (active_updated_targets == 0)`.
* **Sub-Operations (`subop:4` `0..8`)**:

| `subop` | Mnemonic | Logical Dir | Semiring $(\oplus, \otimes, \mathbb{0})$ | Typical Workload |
| :--- | :--- | :--- | :--- | :--- |
| `0` | `.fwd_plus_times` | $Src \to Tgt$ | $(+, \times, 0)$ | Forward PageRank (`V_next[v] = sum_{u->v} contrib[u]`, physically Pull via CSC!), Markov walk, GNN sum |
| `1` | `.rev_plus_times` | $Tgt \to Src$ | $(+, \times, 0)$ | Transpose SpMV (`V_next[u] = sum_{u->v} contrib[v]`), reverse PageRank / HITS hubs |
| `2` | `.fwd_min_plus` | $Src \to Tgt$ | $(\min, +, +\infty)$ | Weighted SSSP / Bellman-Ford relaxation |
| `3` | `.rev_min_plus` | $Tgt \to Src$ | $(\min, +, +\infty)$ | Reverse shortest paths to target |
| `4` | `.fwd_max_plus` | $Src \to Tgt$ | $(\max, +, -\infty)$ | Critical path / PERT scheduling |
| `5` | `.fwd_max_times` | $Src \to Tgt$ | $(\max, \times, 0)$ | Viterbi / max-trust propagation |
| `6` | `.fwd_min_max` | $Src \to Tgt$ | $(\min, \max, +\infty)$ | Minimax bottleneck path |
| `7` | `.fwd_first_src` | $Src \to Tgt$ | $(\min_u, u, \text{NULL})$ (`s2=0, attr=0xFFFF`) | Deterministic BFS parent pointer (`min` `src_id` tie-break) |
| `8` | `.fwd_argmin_plus` | $Src \to Tgt$ | $(\arg\min_u, d[u]+w, \text{NULL})$ | Writes winning predecessor `src_id` (`U32`/`U64`) for SSSP path reconstruction |

* **ImpAsm Usage**:
  ```impas
  ; Unweighted PageRank forward propagation (physically executed via CSC Pull when CSC exists):
  ; V_next[v] = sum_{(u->v)} V_contrib[u]
  SPMV.fwd_plus_times V2, F0, V1, rel=0, attr=0xFFFF
  ; Weighted SSSP relaxation accumulating into V_dist: V_dist[v] = min(V_dist[v], V_dist[u] + e.cost)
  SPMV.fwd_min_plus.accum V0, F1, V0, rel=0, attr=0
  ```
* **Justification**: Replaces **9** v0.10 opcodes (`OP_MXV`, `OP_VXM`, `OP_SPARSE_MATVEC`, `OP_CSR_WALK_REDUCE_SUM`, `OP_CSR_WALK_REDUCE`, `OP_COO_WALK_REDUCE`, `OP_DENSE_WALK_REDUCE`, `OP_CSR_WALK_STATE`, `OP_DELTA_STEP_RELAX`).
* **Gotchas**:
  1. **Unreached Targets & Kleene `NULL` vs Identity `0`**: For `.fwd_plus_times` without `.accum`, unreached targets receive `0.0` (`valid=1`); for `min`/`max`/`first_src` without `.accum`, unreached targets receive Kleene `NULL` (`valid=0`, representing $\pm\infty$ / unvisited) so `NODE_FILTER` / `VEC_CMP` can cleanly distinguish reached from unreached nodes!
  2. **Deterministic Multi-Threaded `PLUS_TIMES`**: Never use unordered hardware atomic `fetch_add` on floats! Use CSC target-partitioned Pull when available, or deterministic thread-partitioned / ascending-thread-ID buffer reduction on Push.
  3. **In-Place Aliasing (`V[dst] == V[s2]` in Bellman-Ford)**: Gauss-Seidel asynchronous in-place updates (`dst == s2` mutated mid-pass) depend on thread execution order! When `dst == s2`, `OP_SPMV` MUST evaluate Jacobi-style against a read-only snapshot of `V[s2]` and merge at end-of-step so `max_dop=1` and `max_dop=16` remain 100% bit-identical!

---

### `0x35` — `OP_WALK_MORSEL`
* **Summary**: Opens an inline lexical edge-morsel vectorized block over `F[s1]` along `rel_id = imm16_lo`, streaming $\le 2048$-edge L1 slices into thread-private `MF0` and `M0..M3`.
* **Encoding**:
  - `flags:4`: `0x1` (`FLAG_MASKED_S3`: pre-filters targets against `\ F[s3]` before emitting morsel lanes!)
  - `dst`: `0` (MBZ); `s1`: `F[s1]` (`0..7`); `s2`: `0` (MBZ); `s3`: `0`, or `F[s3]` (`0..7`) when `.mask`
  - `imm16_lo`: `rel_id`, `imm16_hi`: `end_word_offset` (unsigned relative word offset `end_pc - hdr_pc` to matching `0x38 OP_MORSEL_END`)
  - `vm_flags` updated: Updated at `OP_MORSEL_END` (`ZF = (total_committed_items == 0)`).
* **Sub-Operations (`subop:4` (`0..1`))**:

| `subop` | Mnemonic | Expansion Direction | Domain Requirement (`rel = imm16_lo`) |
| :--- | :--- | :--- | :--- |
| `0` | `.fwd` | Forward ($Src \to Tgt$) | `F[s1].dom == rel.src_dom`; optional `.mask` `F[s3].dom == rel.tgt_dom`. |
| `1` | `.rev` | Reverse ($Tgt \to Src$) | `F[s1].dom == rel.tgt_dom`; optional `.mask` `F[s3].dom == rel.src_dom`. |

* **Operational Semantics**:
  1. Partitions active edges of `F[s1]` on `rel_id` into deterministic monotonic morsels (`32 -> 256 -> 2048` ramp on `max_dop == 1`; fixed `2048` per worker on `max_dop > 1`). If `F[s1]` is empty, still clears all non-`.accum` `OP_MORSEL_COMMIT` sinks (`F -> EMPTY`, `scatter_* -> identity`, `count_add_r -> 0`), invalidates `M0..M7`/`MF0..MF7`, and jumps directly to `pc + end_word_offset + 1` with `ZF = 1`!
  2. For each non-empty morsel of length $L \in [1, 2048]$, populates thread-private registers:
     - `MF0` (`F8`): bits `[0..L)` = `1`
     - `M0` (`V8`): `src_id[0..L)` — **always** topological `src_id` in `rel.src_domain_id` (both `.fwd` and `.rev`), eliminating endpoint swap bugs on reverse morsel walks.
     - `M1` (`V9`): `tgt_id[0..L)` — **always** topological `tgt_id` in `rel.tgt_domain_id`.
     - `M2` (`V10`): `edge_idx[0..L)` (physical edge attribute index)
     - `M3` (`V11`): `lane_mask[0..L)` (`u64` active lane bits of the expanding endpoint).
  3. Executes body `(hdr_pc, end_pc)` per morsel across up to `state->max_dop` worker threads.
* **ImpAsm Usage**:
  ```impas
  WALK_MORSEL.fwd.mask F1, F0, rel=0, end=+6
    GATHER_EDGE_ATTR   M4, M2, rel=0, attr=0
    GATHER_NODE_ATTR   M5, M0, dom=0, attr=1
    VEC_CMP.gt         M6, M4, M5
    SET_CONVERT.b2f    MF0, M6
    MORSEL_COMMIT.yield_frontier.mask F2, M1, MF0, dom=1
  MORSEL_END           hdr=6
  ```
* **Justification**: Replaces all 32 scalar `float32` edge-stream shader opcodes (`0xA0`–`0xBF`) and the recursive runtime CEL AST evaluator (`0x13`), preserving full 64-bit types, Kleene 3VL, multi-sink commits, and parallel SIMD vectorization.
* **Gotchas**:
  1. **Output Aliasing Hazard**: Neither `F[s1]` nor `F[s3]` may alias any `OP_MORSEL_COMMIT` destination `F[dst]`/`V[dst]` inside the block (`impulse_vm_validate` rejects `commit_dst == hdr.s1 || commit_dst == hdr.s3` with `ERR_VALIDATION_FAILED`, preventing race conditions during parallel execution!).
  2. If `OP_MORSEL_COMMIT` targets `F[dst]` without `.accum` on `OP_MORSEL_COMMIT`, wait: across *multiple morsels* of the *same* `WALK_MORSEL` pass, morsels accumulate into that pass's output! **Crucial Distinction**: Without `.accum` on `OP_MORSEL_COMMIT`, `F[dst]`/`V[dst]` is cleared **once at `OP_WALK_MORSEL` entry** before morsel 0 runs, and all morsels of the pass merge into it; with `.accum` on `OP_MORSEL_COMMIT`, `F[dst]`/`V[dst]` retains its pre-`WALK_MORSEL` contents and adds the pass's commits on top!

---

### `0x36` — `OP_FILTER_MORSEL`
* **Summary**: Opens an inline lexical node-morsel vectorized block over `F[s1]`, streaming $\le 2048$ active node IDs at a time into `MF0` (`F8`), `M0` (`V8 = node_id`), and `M3` (`V11 = lane_mask`).
* **Encoding**:
  - `flags:4`: `0x0`; `subop:4`: `0`
  - `dst`: `0` (MBZ); `s1`: `F[s1]` (`0..7`); `s2, s3`: `0` (MBZ)
  - `imm16_lo`: `0` (MBZ; domain inherited from `F[s1]`), `imm16_hi`: `end_word_offset`
  - `vm_flags` updated: At `OP_MORSEL_END` (`ZF = (total_committed_items == 0)`).
* **ImpAsm Usage**:
  ```impas
  ; Evaluate (u.price * (1.0 - u.discount) < 50.0) over sparse/medium F0 in L1 cache without N-wide temp vectors!
  ; R0 = -1.0, R1 = 1.0, R2 = 50.0
  FILTER_MORSEL             F0, end=+8
    GATHER_NODE_ATTR        M4, M0, dom=0, attr=0         ; price
    GATHER_NODE_ATTR        M5, M0, dom=0, attr=1         ; discount
    VEC_TERNARY.fma_r.scalar M5, M5, R0, R1               ; M5 = (-1.0) * discount + 1.0 = (1.0 - discount)
    VEC_MATH_ARITH.mul      M4, M4, M5                    ; M4 = price * (1.0 - discount)
    VEC_CMP.lt.scalar       M6, M4, R2                    ; M6 = (M4 < 50.0) [3VL]
    SET_CONVERT.b2f         MF1, M6                       ; MF1 = surviving active mask
    MORSEL_COMMIT.yield_frontier.mask F1, M0, MF1, dom=0  ; Commit surviving node IDs to F1
  MORSEL_END                hdr=8
  ```
* **Justification**: Without `OP_FILTER_MORSEL`, evaluating a 4-term arithmetic CEL expression on a 500-node frontier in a $10^8$-node domain via full-column `LOAD_COLUMN` + `VEC_MATH` would allocate `800 MB` of temporary vectors! `FILTER_MORSEL` evaluates the expression purely in `16 KB` L1 morsel registers proportional to $|F[s1]|$.
* **Gotchas**: Inside `FILTER_MORSEL`, `M1` (`tgt_id`) and `M2` (`edge_idx`) are **uninitialized**; `impulse_vm_validate` statically rejects reading `M1` or `M2` before assignment inside a `FILTER_MORSEL` block!

---

### `0x37` — `OP_MORSEL_COMMIT`
* **Summary**: Commits surviving thread-private morsel lanes into an outer domain register `F[dst]`, `V[dst]`, or `R[dst]` (`dst` $\in 0..7$).
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM`: preserve pre-block `dst` state across block entry), `0x2` (`FLAG_SCALAR_RHS`: `s2` is outer scalar `R[s2]`), `0x1` (`FLAG_MASKED_S3`: `s3` is morsel mask `MF[s3 & 7]`, else defaults to `MF0`)
  - `imm16_lo`: `domain_id` (required on `subop 0, 1` when `.accum` is not set; `0` otherwise), `imm16_hi`: `0` (MBZ)
* **Sub-Operations (`subop:4` `0..9`)**:

| `subop` | Mnemonic | `dst` Bank (`0..7`) | Operands (`s1` $\in 8..15$; `s2` $\in 8..15$ or `R[s2]` w/ `.scalar`) | Semantics (for each active lane $i$ in mask) |
| :--- | :--- | :--- | :--- | :--- |
| `0` | `.yield_frontier` | `F[dst]` ($W=1$) | `s1=M_idx` (`s2=0`) | Sets dense node `M[s1][i]` in `F[dst]`. |
| `1` | `.yield_lane_or` | `F[dst]` ($W>1$) | `s1=M_idx`, `s2=M_lanes` | Bitwise-ORs `M[s2][i]` into `F[dst]` at node `M[s1][i]`. |
| `2` | `.scatter_add` | `V[dst]` | `s1=M_idx`, `s2=M_val`/`R[s2]` | Deterministic scatter-sum `V[dst][idx] += val` (skips `NULL` `val`). |
| `3` | `.scatter_min` | `V[dst]` | `s1=M_idx`, `s2=M_val`/`R[s2]` | `V[dst][idx] = min(V[dst][idx], val)`. |
| `4` | `.scatter_max` | `V[dst]` | `s1=M_idx`, `s2=M_val`/`R[s2]` | `V[dst][idx] = max(V[dst][idx], val)`. |
| `5` | `.scatter_min_src` | `V[dst]` | `s1=M_idx`, `s2=M_src` | Deterministic min-ID parent update (`U32`/`U64`). |
| `6` | `.scatter_argmin` | `V[dst]` (`U64`) | `s1=M_idx`, `s2=M_packed64` | Atomic/deterministic min on `(ord_key32 << 32) \| tie_id32`. |
| `7` | `.scatter_argmax` | `V[dst]` (`U64`) | `s1=M_idx`, `s2=M_packed64` | Atomic/deterministic max on `(ord_key32 << 32) \| (~tie_id32)`. |
| `8` | `.count_add_r` | `R[dst]` (`U64`) | `s1=0, s2=0` | Adds `popcnt(active_mask)` to outer scalar `R[dst]`. |

* **ImpAsm Usage**:
  ```impas
  MORSEL_COMMIT.yield_frontier.mask F2, M1, MF0, dom=1
  MORSEL_COMMIT.scatter_min.accum.mask V2, M1, M7, MF0
  ```
* **Justification**: Replaces `OP_STREAM_YIELD`, `OP_STREAM_REDUCE`, `OP_STREAM_SCATTER_REDUCE`, `OP_STREAM_REDUCE_ARGMIN`, and `OP_STREAM_REDUCE_ARGMAX`, while enabling **multi-sink single-pass fusion** (emitting both a target frontier and multiple reduced attribute vectors in one CSR scan).
* **Gotchas**:
  1. Validated strictly inside `(morsel_hdr_pc, morsel_end_pc)`: `dst` MUST be `< 8`; `s1` (when used) MUST be `>= 8`; `s2` (when used and `!FLAG_SCALAR_RHS`) MUST be `>= 8`; `s3` (when `.mask`) MUST be `>= 8` (`MF0..MF7`). For `scatter_*` (`subop 2..7`), `V[dst]` MUST be pre-initialized (defining target length & element type): without `.accum`, `V[dst]` is reset to the monoid identity (`0` for `scatter_add`, `NULL` for `min/max/argmin/argmax`) once at block entry; with `.accum`, pre-block values are preserved.
  2. Two distinct `OP_MORSEL_COMMIT` instructions inside the same morsel block MUST NOT target the **same** `dst` register with conflicting reduction monoids (`impulse_vm_validate` enforces unique `(bank, dst)` per morsel block or identical commutative monoid).

---

### `0x38` — `OP_MORSEL_END`
* **Summary**: Lexical closing delimiter of `OP_WALK_MORSEL` or `OP_FILTER_MORSEL`; merges worker partitions and sets `ZF`.
* **Encoding**:
  - `flags:4`: `0x0`; `subop:4`: `0`; `dst, s1, s2, s3`: `0` (MBZ)
  - `imm16_lo`: `0` (MBZ), `imm16_hi`: `hdr_word_distance` (unsigned distance `end_pc - hdr_pc`, matching `hdr.imm16_hi`)
  - `vm_flags` updated: `ZF = (total_committed_items_across_all_sinks == 0)`.
* **Operational Semantics**: Marks the end of a single morsel body iteration; once all morsels complete, merges thread-local reduction buffers in deterministic ascending morsel/thread order and advances `pc = end_pc + 1`.
* **ImpAsm Usage**:
  ```impas
  MORSEL_END hdr=6
  ```
* **Justification**: Explicit symmetric `end_word_offset` / `hdr_word_distance` pairing makes AOT region compilation, OpenMP loop outlining, and Java `MethodHandle` morsel-body specialization $O(1)$ without control-flow graph reconstruction.
* **Gotchas**: Morsel-private contents of `MF0..MF7` and `M0..M7` (`F8..F15`, `V8..V15`) are **clobbered/invalidated** upon exiting `OP_MORSEL_END` (`impulse_vm_validate` marks indices `8..15` uninitialized after `OP_MORSEL_END`).

---

### `0x39` — `OP_SAMPLE_NEIGHBORS`
* **Summary**: Deterministic SplitMix64-seeded uniform neighbor sampling and single-step random walk transition.
* **Encoding**:
  - `flags:4`: `0x0`
  - `s3`: `0` (MBZ)
  - `vm_flags` updated: `ZF = is_empty_or_all_null(dst)`.
* **Sub-Operations (`subop:4` (`0..3`))**:

| `subop` | Mnemonic | Signature | Semantics (`rel_id = imm16_lo`, `fanout_k = imm16_hi`) |
| :--- | :--- | :--- | :--- |
| `0` | `.frontier_wor` | `F[dst] <- F[s1], R[s2]` | Samples up to `k` neighbors **without replacement** per $u \in F[s1]$ (`FWD`) and unions into 1-bit `F[dst]`. |
| `1` | `.vec_wr` | `V[dst] <- V[s1], R[s2]` | For each seed `V[s1][i]`, samples exactly `k` neighbors **with replacement** into `V[dst]` (`len = len(V[s1]) * k`; isolated nodes with $\deg^+(u) == 0$ emit Kleene `NULL` lanes!). |
| `2` | `.rw_step_fwd` | `V[dst] <- V[s1], R[s2]` | Advances each active walker `V[s1][i]` (`k=1` MBZ/`1`) by 1 uniform outgoing edge using `R[s2]` step seed (walkers at dead-ends emit `NULL` or stay if `subop=3`). |
| `3` | `.rw_step_stay` | `V[dst] <- V[s1], R[s2]` | Same as `.rw_step_fwd`, but walkers at dead-ends ($\deg^+(u) == 0$) remain at `u`. |

* **Normative PRNG Formula (4-Way Bit-Identity Mandate)**:
  For seed index/node $u$, slot $j \in [0, k)$, given `uint64_t seed = R[s2]`:
  ```c
  uint64_t z = seed ^ ((uint64_t)u * 0x9E3779B97F4A7C15ULL) ^ ((uint64_t)j * 0xBF58476D1CE4E5B9ULL);
  z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
  uint64_t r = z ^ (z >> 31);
  // Index within [0, deg): r % deg (exact 64-bit unsigned remainder for simple cross-language oracle parity!)
  ```
  For `.frontier_wor` (`deg > k`): runs deterministic $k$-step partial Fisher-Yates (Floyd's $O(k)$ sample algorithm: for $t = \text{deg} - k \dots \text{deg} - 1$, draw $p = r(u, t) \bmod (t + 1)$; if $p$ already chosen, insert $t$, else insert $p$!). **Floyd's algorithm uses $O(k)$ time and $O(k)$ stack space with zero $O(\deg)$ array copy even on million-degree hubs!**
* **ImpAsm Usage**:
  ```impas
  ; GraphSAGE 2-layer [25, 10] deterministic neighborhood sampling:
  SAMPLE_NEIGHBORS.frontier_wor F1, F0, R0, rel=0, k=25
  SCALAR_INT_ALU.add.imm        R0, R0, 1
  SAMPLE_NEIGHBORS.frontier_wor F2, F1, R0, rel=0, k=10
  ```
* **Justification**: Consolidates `OP_SAMPLE_NEIGHBORS` (`0x60`) and `OP_RANDOM_WALK` (`0x61`) for `impulse-gnn` while guaranteeing exact 4-way polyglot output identity across C++, Rust, Java 25, and OCaml at any thread count.
* **Gotchas**:
  1. **Static Memory Bound on `.vec_wr`**: `impulse_vm_validate` rejects `subop == 1` (`.vec_wr`) whenever `V[dst]` participates in a CFG loop strongly connected component (preventing unbounded $k^{\text{iters}}$ exponential vector growth). Acyclic multi-layer GraphSAGE `[25, 10]` is legal with exact static bound; looped sampling uses `.frontier_wor` ($\le N_d$) or `.rw_step_*` (constant length).
  2. Never use `std::mt19937`, `java.util.Random`, or thread-id-seeded RNGs — all four engines MUST implement the exact SplitMix64 + Floyd's $O(k)$ selection formula above!

---

### `0x3A` — `OP_HAS_TOPOLOGY`
* **Summary**: Queries `.imps` snapshot structural metadata, index presence, or domain/relation cardinalities into `R[dst]`.
* **Encoding**:
  - `flags:4`: `0x0`
  - `s1, s2, s3`: `0` (MBZ)
  - `vm_flags` updated: `ZF = (R[dst] == 0)`, `NF = 0`.
* **Sub-Operations (`subop:4` (`0..9`))**:

| `subop` | Mnemonic | Immediates | Result in `R[dst]` (`u64`, `valid=1`) |
| :--- | :--- | :--- | :--- |
| `0` | `.has_csr` | `imm16_lo=rel_id` | `1` if forward CSR present on `rel_id`, else `0`. |
| `1` | `.has_csc` | `imm16_lo=rel_id` | `1` if reverse CSC present on `rel_id`, else `0`. |
| `2` | `.has_coo` | `imm16_lo=rel_id` | `1` if COO edge pairs present on `rel_id`, else `0`. |
| `3` | `.has_dense` | `imm16_lo=rel_id` | `1` if Dense BitMatrix present on `rel_id`, else `0`. |
| `4` | `.has_key_cat` | `imm16_lo=domain_id` | `1` if external Key Catalog present on `domain_id`, else `0`. |
| `5` | `.has_node_attr` | `imm16_lo=dom_id, imm16_hi=attr_id` | `1` if node attribute column exists, else `0`. |
| `6` | `.has_edge_attr` | `imm16_lo=rel_id, imm16_hi=attr_id` | `1` if edge attribute column exists, else `0`. |
| `7` | `.has_index` | `imm16_lo=dom_id, imm16_hi=attr_id` | `1` if sorted/hash secondary index exists on `(dom_id, attr_id)`, else `0`. |
| `8` | `.domain_card` | `imm16_lo=domain_id` | Exact node count $N_d$ of `domain_id`. |
| `9` | `.rel_edges` | `imm16_lo=rel_id` | Exact edge count $M_r$ of `rel_id`. |

* **ImpAsm Usage**:
  ```impas
  HAS_TOPOLOGY.domain_card R2, dom=0
  ```
* **Justification**: Replaces 4 separate `OP_HAS_*` opcodes (`0x19`–`0x1C`) and exposes $N_d$ / $M_r$ directly to dynamic query plans (such as `1.0 / N_d` PageRank initialization!).
* **Gotchas**: For `subop 0..7`, an out-of-range `rel_id` / `attr_id` returns `0` cleanly (since its purpose is capability probing!), whereas on `.domain_card` / `.rel_edges` (`subop 8, 9`), an out-of-range ID returns `IMPULSE_VM_ERR_OUT_OF_BOUNDS` (`2`)! (If `ctx->snapshot == NULL`, all subops return `ERR_NULL_SNAPSHOT` `3`.)

---

### `0x3B` — `OP_GRAPH_KERNEL`
* **Summary**: Irreducible whole-graph linear/wedge topology kernels (`CC_AFFOREST`, `KCORE`, `TRIANGLE_COUNT`).
* **Encoding**:
  - `flags:4`: `0x1` (`FLAG_MASKED_S3`: restricts subgraph to `F[s3]` induced vertex set!)
  - `s1, s2`: `0` (MBZ); `s3`: `0` or `F[s3]` vertex-induced subgraph mask (`.mask`)
  - `vm_flags` updated: `ZF = is_zero_or_empty(dst)`.
* **Sub-Operations (`subop:4` (`0..4`))**:

| `subop` | Mnemonic | `dst` Bank | Semantics (`rel_id = imm16_lo` must be endo-relation `src_dom == tgt_dom`) |
| :--- | :--- | :--- | :--- |
| `0` | `.cc_afforest` | `V[dst]` (`U32`/`U64`) | Weakly Connected Components (treats `rel_id` as undirected `CSR ∪ CSC`). **Canonicalizes every component label to the minimum dense node ID in that component!** |
| `1` | `.kcore_nums` | `V[dst]` (`U32`) | Undirected $k$-core peeling writing exact coreness number `core[u]` for every node $u \in [0, N_d)$. |
| `2` | `.kcore_frontier` | `F[dst]` ($W=1$) | Extracts 1-bit frontier `{ u \| core[u] >= imm16_hi }`. |
| `3` | `.tri_count_total` | `R[dst]` (`U64`) | Total undirected simple triangle count (self-loops & parallel multi-edges deduplicated in DODG orientation `deg(u) < deg(v) \|\| (deg(u)==deg(v) && u < v)`). |
| `4` | `.tri_count_vec` | `V[dst]` (`U64`) | Per-node undirected simple triangle participation count `tri[u]`. |

* **ImpAsm Usage**:
  ```impas
  ; Island detection in impulse-powergrid: filter closed breakers into induced mask or walk, run CC:
  GRAPH_KERNEL.cc_afforest.mask V0, F1, rel=0
  ```
* **Justification**: Retains the three graph-theoretic kernels whose pointer-jumping (`Afforest`), bucketed queue peeling (`k-core`), or degree-ordered wedge intersection (`Triangle Count`) cannot be expressed in linear work via level-synchronous `OP_SPMV`, while retiring 15+ composite/stub showcase opcodes.
* **Gotchas**:
  1. **Mandatory Component Canonicalization on `.cc_afforest`**: Concurrent Shiloach-Vishkin / Afforest sampling chooses arbitrary root IDs depending on thread race winners! Without the final $O(N_d)$ `comp_min[root] = min(comp_min[root], u); label[u] = comp_min[root]` pass, C++ `max_dop=4` and OCaml produce different component IDs!
  2. When `.mask F[s3]` is active on `.cc_afforest` or `.kcore_nums`, excluded nodes $u \notin F[s3]$ MUST receive Kleene `NULL` (`valid=0`) in `V[dst]`!

---

## Pillar 4 — Columnar Vectors, Split Math, Kleene 3VL, Strings, Indices & Collect (`0x40`–`0x57`)

---

### `0x40` — `OP_LOAD_COLUMN`
* **Summary**: Zero-copy binds an immutable `.imps` node or edge attribute column (plus Arrow validity bitmap) into `V[dst]`.
* **Encoding**:
  - `flags:4`: `0x0`
  - `dst`: `V[dst]`; `s1, s2, s3`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` (`0..1`))**:

| `subop` | Mnemonic | Immediates (`imm16_lo, imm16_hi`) | Bound Slice in `V[dst]` |
| :--- | :--- | :--- | :--- |
| `0` | `.node_attr` | `domain_id, attr_id` | Zero-copy node column (`len = N_d`, `domain_id = imm16_lo`) + validity bitmap. |
| `1` | `.edge_attr` | `rel_id, attr_id` | Zero-copy edge column (`len = M_r`, `domain_id = 0xFFFF`) + validity bitmap. |

* **Operational Semantics**: Binds `V[dst]` directly to the memory-mapped `.imps` column pointer and nullability bitmap (`is_readonly_borrow = 1`, `length = N_d` or `M_r`, `domain_id = dom_id` or `0xFFFF` for edges) in **$O(1)$ with 0 bytes copied**. Narrow integer columns (`I8`, `I16`, `U8`, `U16`) either expose typed stride metadata or widen lazily on first arithmetic consumption.
* **ImpAsm Usage**:
  ```impas
  LOAD_COLUMN.node_attr V0, dom=0, attr=2
  ```
* **Justification**: Directly embodies the zero-copy memory-mapped `.imps` architecture (`AGENTS.md` §3.1).
* **Gotchas**: Forbidden inside morsel blocks (`dst < 8` disallowed, and loading an $N_d$-element full column into `M0..M7` violates morsel slice length `L`). Inside morsels, use `OP_GATHER_NODE_ATTR` / `OP_GATHER_EDGE_ATTR`!

---

### `0x41` — `OP_GATHER_NODE_ATTR`
* **Summary**: Indexed gather of node attribute `(domain_id = imm16_lo, attr_id = imm16_hi)` over an index vector, compact frontier, or single scalar node ID.
* **Encoding**:
  - `flags:4`: `0x1` (`FLAG_MASKED_S3`: skips unmasked lanes in `F[s3]` / `MF[s3 & 7]`, marking them `NULL` `valid=0`!)
  - `s2`: `0` (MBZ); `s3`: `0` or `F[s3]`/`MF[s3&7]` (`.mask` on `subop 0`)
* **Sub-Operations (`subop:4`)**:

| `subop` | Mnemonic | Signature | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.vec` | `V[dst] <- V[s1]` | For each valid lane $i$: `V[dst][i] = attr[V[s1][i]]`, `valid[i] = mask[i] & valid_idx[i] & valid_col[idx]`. Primary node attribute loader inside `OP_WALK_MORSEL` (`M0`/`M1` $\to$ `M4..M7`) and `OP_FILTER_MORSEL`! |
| `1` | `.frontier_compact` | `V[dst] <- F[s1]` | Gathers `attr[u]` for active nodes $u \in F[s1]$ in ascending $u$ order (`len = card(F[s1])`). |
| `2` | `.scalar` | `R[dst] <- R[s1]` | Point lookup of `attr[R[s1]]` into scalar `R[dst]` (updates `r_valid_mask[dst]`, `ZF`, `NF`). |

* **ImpAsm Usage**:
  ```impas
  ; Inside morsel: gather tgt.country only for lanes still active in MF0
  GATHER_NODE_ATTR.vec.mask M5, M1, MF0, dom=1, attr=3
  ```
* **Justification**: Enables selective late-materialization inside morsels (when paired with `.mask MF0`, rejected edges never pay random DRAM gather misses on target node attributes!).
* **Gotchas**: Out-of-bounds index `V[s1][i] >= N_domain` on an active valid lane MUST return `IMPULSE_VM_ERR_OUT_OF_BOUNDS` (`2`) — **never** read out-of-bounds off-heap `.imps` memory! When `.mask` is set and lane $i$ has `mask[i] == 0`, `V[s1][i]` is **not** dereferenced or bounds-checked (`valid[dst][i] = 0`).

---

### `0x42` — `OP_GATHER_EDGE_ATTR`
* **Summary**: Indexed gather of edge attribute `(rel_id = imm16_lo, attr_id = imm16_hi)` at physical edge indices `V[s1]` (typically `M2 = edge_idx` inside `OP_WALK_MORSEL`).
* **Encoding**:
  - `flags:4`: `0x1` (`FLAG_MASKED_S3`)
  - `s2`: `0` (MBZ); `s3`: `0` or `F[s3]`/`MF[s3&7]` (`.mask`)
  - `imm16_lo`: `rel_id`, `imm16_hi`: `edge_attr_id`
* **Sub-Operations (`subop:4` (`0..1`))**:

| `subop` | Mnemonic | Signature | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.vec` | `V[dst] <- V[s1]` | Indexed vector gather `edge_attr[V[s1][i]]` (masked by `F[s3]`/`MF[s3&7]` if `.mask`). |
| `1` | `.scalar` | `R[dst] <- R[s1]` | Single edge attribute lookup `edge_attr[R[s1]]` into `R[dst]` (updates `ZF`, `NF`). |

* **ImpAsm Usage**:
  ```impas
  GATHER_EDGE_ATTR.vec M4, M2, rel=0, attr=0
  ```
* **Justification**: Replaces `OP_STREAM_LOAD_EDGE` (`0xA4`) and `OP_READ_EDGE_WEIGHT` (`0x4B`). When `M2` comes from CSR forward expansion, `M2` contains contiguous runs `[row_offsets[u] .. row_offsets[u+1])`, allowing the gather kernel to detect unit-stride runs and execute unaligned SIMD loads (`vmovdqu`) instead of slow `vpgatherdd`!
* **Gotchas**: On CSC reverse morsel walks (`WALK_MORSEL.rev`), `M2` already carries the translated CSR edge index (`csc_edge_perm[k]`) populated by `WALK_MORSEL.rev`, so `GATHER_EDGE_ATTR` indexes the canonical edge column uniformly!

---

### `0x43` — `OP_GATHER_VEC`
* **Summary**: Indirect in-register vector gather: `V[dst][i] = V[s1][V[s2][i]]`.
* **Encoding**:
  - `flags:4`: `0x1` (`FLAG_MASKED_S3`); `subop:4`: `0`
  - `dst`: `V[dst]` (`M4..M7` inside morsel); `s1`: `V[s1]` (data table); `s2`: `V[s2]` (index vector, e.g. `M0`/`M1`); `s3`: `0` or `F[s3]`/`MF[s3&7]` (`.mask`); `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Operational Semantics**: For each active lane $i$, if `valid_idx[i] == 0`, sets `valid_dst[i] = 0`; else bounds-checks `idx = V[s2][i] < len(V[s1])` (`ERR_OUT_OF_BOUNDS` `2` if exceeded) and copies `(valid_s1[idx], V[s1][idx])` to `V[dst][i]`.
* **ImpAsm Usage**:
  ```impas
  ; Inside WALK_MORSEL: read dynamically computed outer node scores V0[src_id] and V0[tgt_id]
  GATHER_VEC M4, V0, M0       ; M4 = score[src_id]
  GATHER_VEC M5, V0, M1       ; M5 = score[tgt_id]
  ```
* **Justification**: Replaces untyped `OP_LOAD_INDIRECT` (`0x72`) and read-side `OP_SCATTER_GATHER` (`0x62`), allowing morsel expressions to reference dynamically computed VM state vectors (`state.dist`, `state.rank`) alongside static `.imps` columns.
* **Gotchas**: In-place aliasing `dst == s1` (`GATHER_VEC V0, V0, V1`) MUST write to a fresh buffer before replacing `V0`!

---

### `0x44` — `OP_NODE_FILTER`
* **Summary**: Fused in-domain node attribute predicate filter (`F[dst] = { u \in F[s1] | attr(u) cmp rhs }`) across **all** `.imps` numeric/boolean/dict column types under strict Kleene 3VL.
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM`), `0x2` (`FLAG_SCALAR_RHS`: `s2` is `R[s2]`, and on `BETWEEN` `s3` is `R[s3]`)
  - `imm16_lo`: `domain_id`, `imm16_hi`: `attr_id`
  - `vm_flags` updated: `ZF = is_empty(F[dst])`.
* **Sub-Operations (`subop:4` (`0..8`))**:

| `subop` | Mnemonic | Operands | Predicate (`NULL` attr or `NULL` rhs $\to$ `0`!) |
| :--- | :--- | :--- | :--- |
| `0` | `.eq` | `s1=F_in`, `s2=V[s2]/R[s2]` | `attr[u] == rhs` |
| `1` | `.ne` | `s1=F_in`, `s2=V[s2]/R[s2]` | `attr[u] != rhs` (`NULL != 5` $\to$ excluded!) |
| `2` | `.lt` | `s1=F_in`, `s2=V[s2]/R[s2]` | `attr[u] < rhs` |
| `3` | `.le` | `s1=F_in`, `s2=V[s2]/R[s2]` | `attr[u] <= rhs` |
| `4` | `.gt` | `s1=F_in`, `s2=V[s2]/R[s2]` | `attr[u] > rhs` |
| `5` | `.ge` | `s1=F_in`, `s2=V[s2]/R[s2]` | `attr[u] >= rhs` |
| `6` | `.between` | `s1=F_in`, `s2=lo`, `s3=hi` | `lo <= attr[u] && attr[u] <= hi` |
| `7` | `.is_null` | `s1=F_in` (`s2=0, s3=0`) | `valid(attr[u]) == 0` |
| `8` | `.is_not_null` | `s1=F_in` (`s2=0, s3=0`) | `valid(attr[u]) == 1` |

* **ImpAsm Usage**:
  ```impas
  NODE_FILTER.between.scalar F1, F0, R1, R2, dom=0, attr=1   ; age BETWEEN 21 AND 65 in 1 word!
  ```
* **Justification**: Fixes the severe v0.10 bug in `op_14_node_filter.inc` (which only implemented `==` on `INT8..INT64` and silently returned `true` on `FLOAT32`/`FLOAT64`!), automatically exploits `.imps` BRIN min/max block headers on `ALL_SPAN` / `Tier 2` scans, and evaluates `Tier 0` / `Tier 1` inputs in $O(|F[s1]|)$ without scanning all $N_d$ rows!
* **Gotchas**:
  1. `FLAG_MASKED_S3` (`0x1`) is disallowed on `OP_NODE_FILTER` because `F[s1]` **is already** the input conditioning frontier (and `s3` holds `hi` on `.between`)!
  2. Mixed int/float scalar comparisons (e.g. `INT64` column vs `F64` scalar `R[s2]`): scalar type MUST match column family (`INT` vs `FLOAT`); compilers widen/narrow constants at compile time (`ERR_TYPE_MISMATCH` `14` if mismatched, preventing silent `(int64_t)double_bits` reinterpretation!).

---

### `0x45` — `OP_VEC_CMP`
* **Summary**: Branchless SIMD vector comparison producing a dual-bitmask Kleene `BOOL_3VL` vector in `V[dst]`.
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS`: `s2` is `R[s2]`, and on `.between` `s3` is `R[s3]`), `0x1` (`FLAG_MASKED_S3` allowed on `subop 0..5`)
  - `dst`: `V[dst]` (`BOOL_3VL`); `s1`: `V[s1]`; `s2`: `V[s2]`/`R[s2]`; `s3`: `0`, `F[s3]` (`.mask` on `0..5`), or `V[s3]`/`R[s3]` (on `.between`); `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` `0..7`)**:

| `subop` | Mnemonic | Operands | Kleene 3VL Predicate (`NULL` operand $\to$ `NULL (0,0)`) |
| :--- | :--- | :--- | :--- |
| `0` | `.eq` | `s1, s2` | `s1 == s2` |
| `1` | `.ne` | `s1, s2` | `s1 != s2` (`NULL != x` $\to$ `NULL`, never `TRUE`!) |
| `2` | `.lt` | `s1, s2` | `s1 < s2` |
| `3` | `.le` | `s1, s2` | `s1 <= s2` |
| `4` | `.gt` | `s1, s2` | `s1 > s2` |
| `5` | `.ge` | `s1, s2` | `s1 >= s2` |
| `6` | `.between` | `s1, s2=lo, s3=hi` | `lo <= s1 && s1 <= hi` (`.mask` disallowed on `subop=6`) |
| `7` | `.in_set` | `s1=V[s1], s2=V[s2]` | SQL/Kleene 3VL membership `V[s1][i] in V[s2]` (`.scalar` disallowed; if `V[s1][i]` is `NULL` $\to$ `NULL`; if match found $\to$ `TRUE`; else if `V[s2]` contains any `NULL` $\to$ `NULL`, else `FALSE`). |

* **Operational Semantics**: Computes `v_out = mask & v_s1 & v_s2 (& v_s3)` and `d_out = v_out & cmp(s1, s2 [, s3])` across 64 lanes per `uint64_t` mask word.
* **ImpAsm Usage**:
  ```impas
  VEC_CMP.ne.scalar M6, M4, R1   ; If M4[i] is NULL, M6[i] = NULL (0,0), NEVER TRUE (1,1)!
  ```
* **Justification**: Consolidates `OP_VEC_CMP_EQ` (`0x20`), `OP_VEC_CMP_GT` (`0x21`), `OP_VEC_CMP_LT` (`0x22`), `OP_VEC_CMP_BETWEEN` (`0x23`), and `OP_STREAM_CMP_*` (`0xB0`–`0xB3`), adding native `.ne`, `.le`, `.ge` so compilers NEVER have to synthesize `!=` as `NOT(EQ)` (which caused the v0.10 `NULL != 5 == true` bug!).
* **Gotchas**: On `.between` (`subop == 6`), `s3` is the upper-bound operand, so `FLAG_MASKED_S3` (`0x1`) is disallowed on `subop == 6` (`ERR_INVALID_OPERAND`).

---

### `0x46` — `OP_VEC_3VL_OP`
* **Summary**: Branchless dual-bitmask Kleene 3VL boolean connectives, SQL `IS [NOT] NULL` / `IS TRUE` / `IS FALSE` predicates, and IEEE-754 finiteness checks/assertions.
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS` allowed on `subop 0, 1, 3`), `0x1` (`FLAG_MASKED_S3`: unmasked lanes always emit `NULL (0, 0)`, including on `subop 4..7`)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` (`0..11`))**:

| `subop` | Mnemonic | Input `V[s1]` | Exact Dual-Bitmask Output `(v, d)` in `V[dst]` (`BOOL_3VL`) |
| :--- | :--- | :--- | :--- |
| `0` | `.and` | `BOOL_3VL` (`s1, s2`) | `d = dA & dB`; `v = (vA & vB) \| (vA & ~dA) \| (vB & ~dB)` |
| `1` | `.or` | `BOOL_3VL` (`s1, s2`) | `d = dA \| dB`; `v = (vA & vB) \| d` |
| `2` | `.not` | `BOOL_3VL` (`s1`) | `v = vA`; `d = vA & ~dA` |
| `3` | `.xor` | `BOOL_3VL` (`s1, s2`) | `v = vA & vB`; `d = v & (dA ^ dB)` |
| `4` | `.is_null` | Any `V[s1]` | `v = ~0ULL`; `d = ~vA` (2-valued total predicate!) |
| `5` | `.is_not_null` | Any `V[s1]` | `v = ~0ULL`; `d = vA` (replaces `OP_EXTRACT_VALIDITY` `0x3C`!) |
| `6` | `.is_true` | `BOOL_3VL` (`s1`) | `v = ~0ULL`; `d = dA` (SQL `IS TRUE`: `NULL -> FALSE (1,0)`) |
| `7` | `.is_false` | `BOOL_3VL` (`s1`) | `v = ~0ULL`; `d = vA & ~dA` (SQL `IS FALSE`: `NULL -> FALSE (1,0)`) |
| `8` | `.is_nan` | `F32`/`F64` (`s1`) | `v = vA`; `d = vA & isnan(x)` |
| `9` | `.is_inf` | `F32`/`F64` (`s1`) | `v = vA`; `d = vA & isinf(x)` |
| `10` | `.is_finite` | `F32`/`F64` (`s1`) | `v = vA`; `d = vA & isfinite(x)` |
| `11` | `.assert_finite` | `F32`/`F64` (`s1`, `dst=0`) | Traps with `IMPULSE_VM_ERR_ASSERTION_FAILED` (`8`) if any active valid lane is `±Inf` or `NaN` (`imm32 = tag`). |

* **ImpAsm Usage**:
  ```impas
  VEC_3VL_OP.not M5, M5          ; Preserves NULL -> NULL!
  VEC_3VL_OP.and M6, M5, M4      ; FALSE && NULL -> FALSE!
  ```
* **Justification**: Replaces `OP_MASK_AND`, `OP_MASK_OR`, `OP_MASK_NOT`, `OP_EXTRACT_VALIDITY`, `OP_ASSERT_FINITE`, `OP_STREAM_LOGIC_*`, and `MATH_FUNC_ISNAN/ISINF/ISFINITE` with exact Kleene 3VL semantics in 2–4 bitwise instructions per 64 rows.
* **Gotchas**: On `.is_null`, `.is_not_null`, `.is_true`, and `.is_false` (`subop 4..7`), the trailing bits `[len % 64 .. 63]` of the final `uint64_t` word MUST be masked to `0` so out-of-range lanes above `len` never appear as `1`!

---

### `0x47` — `OP_VEC_STR_PRED`
* **Summary**: Zero-copy 16-byte `StringView` (`[len:u32, prefix4_be:u32, offset:u64]`) & dictionary-ID vector comparisons/substring predicates producing `BOOL_3VL` in `V[dst]`.
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS`: `s2` is `R[s2]` holding 64-bit `imp_str_handle_t` with tag `SCALAR_STR_HANDLE`, or `U64` length on `.len_eq`), `0x1` (`FLAG_MASKED_S3`)
  - `vm_flags` updated: None.
  - `imm32`: `0` (MBZ)
* **Sub-Operations (`subop:4` (`0..9`))**:

| `subop` | Mnemonic | Semantics (UTF-8 bytewise lexicographical / exact match) |
| :--- | :--- | :--- |
| `0` | `.eq` | `a == b` (1-cycle reject on `len` or `prefix4_be` mismatch; dict-ID fast path when shared pool!) |
| `1` | `.ne` | `a != b` (Kleene `NULL` propagates!) |
| `2` | `.lt` | `a < b` (unsigned byte order; resolved in registers via `prefix4_be` whenever first 4 bytes differ!) |
| `3` | `.le` | `a <= b` |
| `4` | `.gt` | `a > b` |
| `5` | `.ge` | `a >= b` |
| `6` | `.starts_with` | `a` has byte prefix `b` (`len(a) >= len(b)` + `prefix4_be` fast check + tail `memcmp`) |
| `7` | `.ends_with` | `a` has byte suffix `b` (`len(a) >= len(b)` + tail `memcmp`) |
| `8` | `.contains` | `b` is a contiguous byte substring of `a` (SIMD two-byte first/last needle scan) |
| `9` | `.len_eq` | `byte_len(a) == u64(rhs)` (evaluates 100% inside `StringView` header without touching pool bytes!) |

* **ImpAsm Usage**:
  ```impas
  LOAD_CONST_POOL.str         R1, pool=0       ; "https://impulsegraph.io/"
  VEC_STR_PRED.starts_with.scalar M5, M4, R1
  ```
* **Justification**: Replaces lossy 8-byte `OP_LOAD_CONST_STR_PREFIX` (`0x07`) and `OP_NODE_FILTER_STR_PREFIX` (`0x15`), which could not distinguish strings sharing an 8-byte prefix!
* **Gotchas**: `prefix4_be` MUST be stored in **big-endian** `uint32_t` byte order (zero-padded on the right for strings shorter than 4 bytes, e.g. `"ab"` $\to$ `0x61620000u`); storing little-endian `uint32_t` reverses lexicographical `<`/`>` order on x86/ARM64! Notice subtle corner case when `prefix4_be` ties on short strings containing embedded `\0` bytes (`"ab\0"` len 3 vs `"ab"` len 2): when `a.prefix4_be == b.prefix4_be` and `min(len_a, len_b) <= 4`, tie-break by `len_a cmp len_b`!

---

### `0x48` — `OP_VEC_MATH_ARITH`
* **Summary**: Hardware-SIMD vector arithmetic, roots, min/max, and IEEE-754 rounding (`16` subops `0..15`, zero `libm` transcendental calls).
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS` on binary `0..7`), `0x1` (`FLAG_MASKED_S3`)
  - `vm_flags` updated: None.
  - `imm32`: `0` (MBZ)
* **Sub-Operations (`subop:4` (`0..15`))**:

| `subop` | Mnemonic | Arity | Supported Types | Semantics (`NULL` propagates!) |
| :--- | :--- | :--- | :--- | :--- |
| `0` | `.add` | Binary (`s1, s2`) | `I64, U64, F32, F64` | `x + y` (wrapping 64b on int) |
| `1` | `.sub` | Binary (`s1, s2`) | `I64, U64, F32, F64` | `x - y` |
| `2` | `.mul` | Binary (`s1, s2`) | `I64, U64, F32, F64` | `x * y` |
| `3` | `.div` | Binary (`s1, s2`) | `I64, U64, F32, F64` | `y == 0` $\to$ Kleene `NULL` (`valid=0, data=0`); `INT64_MIN / -1` $\to$ `INT64_MIN` |
| `4` | `.rem` | Binary (`s1, s2`) | `I64, U64, F32, F64` | `y == 0` $\to$ `NULL`; `fmod(x, y)` on floats |
| `5` | `.min` | Binary (`s1, s2`) | `I64, U64, F32, F64` | `min(x, y)` (`min(-0.0, +0.0) = -0.0`) |
| `6` | `.max` | Binary (`s1, s2`) | `I64, U64, F32, F64` | `max(x, y)` (`max(-0.0, +0.0) = +0.0`) |
| `7` | `.copysign` | Binary (`s1, s2`) | `F32, F64` | `copysign(x, y)` |
| `8` | `.neg` | Unary (`s1`, `s2=0`) | `I64, F32, F64` | `-x` |
| `9` | `.abs` | Unary (`s1`, `s2=0`) | `I64, F32, F64` | $\lvert x \rvert$ (`abs(INT64_MIN)` wraps to `INT64_MIN` two's-complement) |
| `10` | `.sqrt` | Unary (`s1`, `s2=0`) | `F32, F64` | `x < 0 ? NULL : sqrt(x)` |
| `11` | `.rsqrt` | Unary (`s1`, `s2=0`) | `F32, F64` | `x <= 0 ? NULL : (1 / sqrt(x))` (exact IEEE division, NOT 12-bit `vrsqrtps` approx!) |
| `12` | `.floor` | Unary (`s1`, `s2=0`) | `F32, F64` | `floor(x)` |
| `13` | `.ceil` | Unary (`s1`, `s2=0`) | `F32, F64` | `ceil(x)` |
| `14` | `.trunc` | Unary (`s1`, `s2=0`) | `F32, F64` | `trunc(x)` |
| `15` | `.round` | Unary (`s1`, `s2=0`) | `F32, F64` | `round_half_away_from_zero(x)` |

* **ImpAsm Usage**:
  ```impas
  VEC_MATH_ARITH.mul.scalar V2, V1, R1     ; V2 = V1 * 0.85
  VEC_MATH_ARITH.add.scalar V2, V2, R5     ; V2 = V2 + (0.15 / N)
  ```
* **Justification**: Every single one of `subop 0..15` lowers directly to native AVX-512 / ARM64 NEON / Java `jdk.incubator.vector` instructions without calling `libm`, keeping the hot arithmetic handler tiny and JIT-inlinable. Consolidates `OP_EWISE_ADD`, `OP_EWISE_MULT`, `OP_VECTOR_DIV`, `OP_FLOAT_VECTOR_SCALE`, and `OP_STREAM_MATH_*`.
* **Gotchas**: On `.rsqrt` (`subop == 11`), hardware `vrsqrt14pd` / `vrsqrtps` differs across Intel, AMD, and Apple Silicon! To preserve `AGENTS.md` §3.18 bit-identity (within 0 ULP on algebraic ops), compute `1.0 / sqrt(x)` (for `F32`, compute `(float)(1.0 / sqrt((double)x))` in `f64` then narrow to `f32` for 0-ULP cross-engine identity).

---

### `0x49` — `OP_VEC_MATH_EXP_LOG`
* **Summary**: Exponential, logarithmic, power, root, and statistical error/gamma vector functions (`14` subops `0..13`, `F32`/`F64`).
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS` allowed on binary `8=pow, 10=hypot`), `0x1` (`FLAG_MASKED_S3`)
  - `dst`: `V[dst]` (`F32`/`F64`); `s1`: `V[s1]`; `s2`: `0` (unary) or `V[s2]`/`R[s2]` (binary `8, 10`); `s3`: `0` or `F[s3]` (`.mask`)
  - `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` `0..13`)**:

| `subop` | Mnemonic | Arity | Formula / Semantics (`NULL` propagates) |
| :--- | :--- | :--- | :--- |
| `0` | `.exp` | Unary (`s1`) | $e^x$ |
| `1` | `.exp2` | Unary (`s1`) | $2^x$ |
| `2` | `.exp10` | Unary (`s1`) | $10^x$ |
| `3` | `.expm1` | Unary (`s1`) | $e^x - 1$ (accurate near $x = 0$) |
| `4` | `.log` | Unary (`s1`) | $\ln(x)$ (`x < 0` $\to$ `NULL`; `x == 0` $\to$ `-Inf`) |
| `5` | `.log2` | Unary (`s1`) | $\log_2(x)$ (`x < 0` $\to$ `NULL`) |
| `6` | `.log10` | Unary (`s1`) | $\log_{10}(x)$ (`x < 0` $\to$ `NULL`) |
| `7` | `.log1p` | Unary (`s1`) | $\ln(1 + x)$ (`x < -1` $\to$ `NULL`) |
| `8` | `.pow` | Binary (`s1, s2`) | $x^y$ (`NaN` domain errors $\to$ `NULL`) |
| `9` | `.cbrt` | Unary (`s1`) | $\sqrt[3]{x}$ |
| `10` | `.hypot` | Binary (`s1, s2`) | $\sqrt{x^2 + y^2}$ (overflow/underflow-safe) |
| `11` | `.erf` | Unary (`s1`) | Gauss error function $\operatorname{erf}(x)$ |
| `12` | `.erfc` | Unary (`s1`) | Complementary error function $\operatorname{erfc}(x) = 1 - \operatorname{erf}(x)$ |
| `13` | `.lgamma` | Unary (`s1`) | $\ln \lvert \Gamma(x) \rvert$ (poles at non-positive integers $\to$ `+Inf`) |

* **ImpAsm Usage**:
  ```impas
  VEC_MATH_EXP_LOG.log1p V1, V0
  ```
* **Justification**: Isolates transcendental `exp`/`log`/`pow`/`erf`/`lgamma` kernels (`<= 14` cases) from hot arithmetic dispatch.
* **Gotchas**:
  1. Domain errors producing `NaN` (`log(x)` for `x < 0`, `pow(-2.0, 0.5)`) canonicalize to Kleene `NULL` (`valid=0, data=0`), whereas `log(0.0)` produces `-Inf` (`valid=1`) and `lgamma(x)` at non-positive integers (`x <= 0 && floor(x) == x`) produces `+Inf` (`valid=1`).
  2. **Two-Tier FP Precision Policy**: Engines may use full-speed native SIMD vector math (`SLEEF u10` / `SVML` / `vForce` / Java `DoubleVector.lanewise`) subject to `<= 1.0 ULP` (`exp*`, `log*`, `cbrt`, `hypot`, `erf`, `erfc`) and `<= 2.0 ULP` (`pow`, `lgamma`), with exact `0-ULP` agreement on all special values (`±0.0`, `±Inf`, `NaN -> NULL`, poles).

---

### `0x4A` — `OP_VEC_MATH_TRIG_HYP`
* **Summary**: Circular, inverse circular, spatial `sinc`/`atan2`, and Poincaré hyperbolic vector functions (`14` subops `0..13`, `F32`/`F64`).
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS` allowed on binary `6=atan2`), `0x1` (`FLAG_MASKED_S3`)
  - `dst`: `V[dst]` (`F32`/`F64`); `s1`: `V[s1]`; `s2`: `0` (unary) or `V[s2]`/`R[s2]` (binary `6=atan2`); `s3`: `0` or `F[s3]` (`.mask`)
  - `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` `0..13`)**:

| `subop` | Mnemonic | Arity | Formula / Semantics (`NULL` propagates) |
| :--- | :--- | :--- | :--- |
| `0` | `.sin` | Unary (`s1`) | $\sin(x)$ (`±Inf` $\to$ `NULL`) |
| `1` | `.cos` | Unary (`s1`) | $\cos(x)$ (`±Inf` $\to$ `NULL`) |
| `2` | `.tan` | Unary (`s1`) | $\tan(x)$ (`±Inf` $\to$ `NULL`) |
| `3` | `.asin` | Unary (`s1`) | $\arcsin(x)$ ($\lvert x \rvert > 1 \to$ `NULL`) |
| `4` | `.acos` | Unary (`s1`) | $\arccos(x)$ ($\lvert x \rvert > 1 \to$ `NULL`) |
| `5` | `.atan` | Unary (`s1`) | $\arctan(x)$ |
| `6` | `.atan2` | Binary (`s1, s2`) | $\operatorname{atan2}(y = s1, x = s2)$ |
| `7` | `.sinc` | Unary (`s1`) | $\lvert x \rvert < \epsilon \; ? \; 1.0 : \sin(x) / x$ ($\epsilon = 10^{-7}$ `f32`, $10^{-15}$ `f64`) |
| `8` | `.sinh` | Unary (`s1`) | $\sinh(x)$ |
| `9` | `.cosh` | Unary (`s1`) | $\cosh(x)$ |
| `10` | `.tanh` | Unary (`s1`) | $\tanh(x)$ |
| `11` | `.asinh` | Unary (`s1`) | $\operatorname{asinh}(x)$ |
| `12` | `.acosh` | Unary (`s1`) | $\operatorname{acosh}(x)$ ($x < 1 \to$ `NULL`) |
| `13` | `.atanh` | Unary (`s1`) | $\operatorname{atanh}(x)$ ($\lvert x \rvert > 1 \to$ `NULL`; $\lvert x \rvert == 1 \to \pm\infty$) |

* **ImpAsm Usage**:
  ```impas
  VEC_MATH_TRIG_HYP.atan2 V2, V0, V1
  ```
* **Justification**: Groups periodic and hyperbolic transcendentals (`<= 14` subops) cleanly for geospatial bearing/Haversine formulas and hyperbolic GNN embeddings.
* **Gotchas**: On `.sinc`, use exact threshold `fabsf(x) < 1e-7f` (`F32`) and `fabs(x) < 1e-15` (`F64`) returning `1.0` to avoid `0.0 / 0.0 -> NaN` around zero. Uses the same `<= 1.0 ULP` native SIMD transcendental policy + `0-ULP` special-value contract as `0x49`.

---

### `0x4B` — `OP_VEC_MATH_ACT`
* **Summary**: Graph Neural Network (GNN) & neural activation functions (`6` subops `0..5`, `F32`/`F64`, `10` reserved subop slots for future activations).
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS` allowed on binary `1=leaky_relu`), `0x1` (`FLAG_MASKED_S3`)
  - `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` `0..5`)**:

| `subop` | Mnemonic | Arity | Exact Normative Formula (`NULL` propagates) |
| :--- | :--- | :--- | :--- |
| `0` | `.relu` | Unary (`s1`) | `x > 0 ? x : +0.0` (note: `-0.0` canonicalizes to `+0.0`!) |
| `1` | `.leaky_relu` | Binary (`s1, s2`) | `x > 0 ? x : (alpha * x)` where `alpha` is `V[s2]` or `R[s2]` (`.scalar`, e.g. `0.01`) |
| `2` | `.sigmoid` | Unary (`s1`) | `1 / (1 + exp(-x))` |
| `3` | `.gelu` | Unary (`s1`) | `x <= -15 ? 0 : (x >= 15 ? x : 0.5 * x * (1 + tanh(k0 * (x + 0.044715 * x^3))))` |
| `4` | `.silu` | Unary (`s1`) | `isinf(x) ? (x > 0 ? +Inf : 0) : x / (1 + exp(-x))` |
| `5` | `.softplus` | Unary (`s1`) | `x > thresh ? x : log1p(exp(x))` (`thresh = 20.0f` for `F32`, `40.0` for `F64`) |

* **ImpAsm Usage**:
  ```impas
  VEC_MATH_ACT.leaky_relu.scalar V1, V0, R1   ; R1 = 0.01
  ```
* **Justification**: Supports inline `impulse-gnn` message-passing feature transformations without overflowing `OP_VEC_MATH_ARITH` or `TRIG_HYP` past 16 subops, and eliminates v0.10's unary-vs-binary `MATH_FUNC_LEAKY_RELU` ambiguity by making `alpha` an explicit `s2` operand.
* **Gotchas**: Preserve the exact clamping thresholds on `.gelu` (`±15.0`), `.silu` (`-Inf -> 0.0` instead of `-Inf * 0 -> NaN`!), and `.softplus` (`20.0f` / `40.0` overflow guard) across all 4 engines, using normative constants `k0 = 0.7978845608028654` (`f64`, $\sqrt{2/\pi}$) / `0.7978845608f` (`f32`) and `k1 = 0.044715` in `.gelu` (`<= 2.0 ULP` SIMD policy on `sigmoid`/`gelu`/`silu`/`softplus`; `0-ULP` exact on `relu`/`leaky_relu`).

---

### `0x4C` — `OP_VEC_INT_BITWISE`
* **Summary**: Native 64-bit / 32-bit integer vector bitwise logic, shifts, rotations, bit-counting, and byte-swap (`14` subops `0..13`, `I64`/`U64`/`I32`/`U32`).
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS` allowed on binary `0..2, 4..9`), `0x1` (`FLAG_MASKED_S3`)
  - `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` `0..13`)**:

| `subop` | Mnemonic | Arity | Semantics (Shift/rotate count masked `& (W_bits - 1)`) |
| :--- | :--- | :--- | :--- |
| `0` | `.and` | Binary (`s1, s2`) | `x & y` |
| `1` | `.or` | Binary (`s1, s2`) | `x \| y` |
| `2` | `.xor` | Binary (`s1, s2`) | `x ^ y` |
| `3` | `.not` | Unary (`s1`) | `~x` |
| `4` | `.and_not` | Binary (`s1, s2`) | `x & ~y` |
| `5` | `.shl` | Binary (`s1, s2`) | `x << (y & mask)` |
| `6` | `.shr_u` | Binary (`s1, s2`) | `(uint)x >> (y & mask)` |
| `7` | `.shr_s` | Binary (`s1, s2`) | `(int)x >> (y & mask)` |
| `8` | `.rotl` | Binary (`s1, s2`) | Rotate left (`s == 0 ? x : (x << s) \| (x >> (W - s))`) |
| `9` | `.rotr` | Binary (`s1, s2`) | Rotate right (`s == 0 ? x : (x >> s) \| (x << (W - s))`) |
| `10` | `.popcount` | Unary (`s1`) | Hardware population count (`0..64` / `0..32`) |
| `11` | `.clz` | Unary (`s1`) | Count leading zeros (`x == 0 ? W : clz(x)`) |
| `12` | `.ctz` | Unary (`s1`) | Count trailing zeros (`x == 0 ? W : ctz(x)`) |
| `13` | `.bswap` | Unary (`s1`) | Byte-reverse (`bswap32` / `bswap64`) |

* **ImpAsm Usage**:
  ```impas
  ; Pack deterministic ARGMIN key: (ord_f32 << 32) | src_id
  VEC_INT_BITWISE.shl.scalar M6, M5, R3    ; R3 = 32
  VEC_INT_BITWISE.or         M6, M6, M0
  ```
* **Justification**: Fixes v0.10's broken discrete math design (`MATH_FUNC_POPCOUNT..ROTR` in `impulse_math_ops.h`), which forced bitwise operations through `float32`/`float64` casts (`impulse_f64_to_u64_clamped`), losing precision above $2^{53}$!
* **Gotchas**:
  1. `__builtin_clzll(0)` and `__builtin_ctzll(0)` are **undefined behavior** in C/C++! Always guard `x == 0 ? width_bits : builtin(x)`.
  2. In `.rotl` / `.rotr`, shifting by `W - s` when `s == 0` (`x >> 64`) is **also UB** in C/C++! Always guard `s == 0` or mask `(W - s) & (W - 1)`.

---

### `0x4D` — `OP_VEC_TERNARY`
* **Summary**: Single-word 3-operand vector math and temporal interval predicates (`V[dst] = op(V[s1], s2, s3)`).
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS`: uniformly switches `s2` from `V[s2]` to `R[s2]` on `subop 0..7`; disallowed on `subop 8`)
  - `dst`: `V[dst]`; `s1`: `V[s1]`; `s2`: `V[s2]` (or `R[s2]` w/ `.scalar`); `s3`: `V[s3]` (`_v` subops) or `R[s3]` (`_r` subops); `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` `0..9`)**:

| `subop` | Mnemonic | `s3` Bank | Semantics (`s2` is `V[s2]`, or `R[s2]` when `.scalar` is set) |
| :--- | :--- | :--- | :--- |
| `0` | `.fma_v` | `V[s3]` | `fma(V[s1], s2, V[s3])` — with `.scalar`, executes **AXPY** `a * x + y` in 1 word! |
| `1` | `.fma_r` | `R[s3]` | `fma(V[s1], s2, R[s3])` — with `.scalar`, executes affine `a * x + b` (and `1.0 - x` via `a = -1, b = 1`)! |
| `2` | `.lerp_v` | `V[s3]` | `s1 + V[s3] * (s2 - s1)` |
| `3` | `.lerp_r` | `R[s3]` | `s1 + R[s3] * (s2 - s1)` |
| `4` | `.clamp_v` | `V[s3]` | `clamp(x=V[s1], lo=s2, hi=V[s3])` (`lo > hi` $\to$ `ERR_INVALID_OPERAND` `6`) |
| `5` | `.clamp_r` | `R[s3]` | `clamp(x=V[s1], lo=s2, hi=R[s3])` — with `.scalar`, clamps to scalar `[R_lo, R_hi]`! |
| `6` | `.safe_div_v` | `V[s3]` | `(s2 == 0 \|\| !valid_s2) ? V[s3] : (V[s1] / s2)` |
| `7` | `.safe_div_r` | `R[s3]` | `(s2 == 0 \|\| !valid_s2) ? R[s3] : (V[s1] / s2)` — without `.scalar`, vector div w/ scalar fallback! |
| `8` | `.time_valid_at_r` | `R[s3]` | Outputs `BOOL_3VL`: `V[s1] <= R[s3] && (isnull(V[s2]) \|\| R[s3] < V[s2])` (`.scalar` disallowed) |
| `9` | `.mul_div_i64_r` | `R[s3]` | Overflow-safe `DECIMAL(P<=18, S)` scaling: `(i128(V[s1]) * i128(s2)) / i128(R[s3])` with half-even (banker's) rounding; returns Kleene `NULL` if `R[s3] == 0` or final quotient overflows `i64`. |

* **ImpAsm Usage**:
  ```impas
  ; Temporal edge validity check inside WALK_MORSEL: valid_from <= $now && (valid_to IS NULL || $now < valid_to)
  VEC_TERNARY.time_valid_at_r M6, M4, M5, R1
  ; AXPY (V_out = R_alpha * V_x + V_y) in 1 word:
  VEC_TERNARY.fma_v.scalar    V2, V0, R1, V1
  ```
* **Justification**: Replaces 128-bit `OP_VEC_MATH_TERNARY` (`0x2F`) and `OP_VECTOR_TIME_VALID_AT` (`0x3D`) inside **a single 64-bit word** thanks to 4-bit register nibbles `(dst, s1, s2, s3)`!
* **Gotchas**: Notice `.time_valid_at` intentionally treats `valid_to == NULL` (`!valid_s2[i]`) as **open-ended future validity (`+∞`, i.e. currently active)**, whereas `valid_from == NULL` (`!valid_s1[i]`) or `ts == NULL` (`!valid_s3`) produces Kleene `NULL`!

---

### `0x4E` — `OP_VEC_BLEND`
* **Summary**: Vector conditional ternary select (`cond ? true_val : false_val`) with explicit Kleene-propagating vs SQL `CASE WHEN` modes.
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS`: `s2` reads `R[s2]`)
  - `dst`: `V[dst]`; `s1`: `V[s1]` (`BOOL_3VL`); `s2`: `V[s2]` (or `R[s2]` w/ `.scalar`); `s3`: `V[s3]` or `R[s3]`; `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` `0..3`)**:

| `subop` | Mnemonic | `s3` Bank | `NULL` Condition (`v_cond == 0`) Behavior |
| :--- | :--- | :--- | :--- |
| `0` | `.kleene_vv` | `V[s3]` | Propagates `NULL` (`valid_dst = 0`) when `cond` is `NULL`. |
| `1` | `.kleene_vr` | `R[s3]` | Same as `.kleene_vv`, with false branch read from scalar `R[s3]`. |
| `2` | `.case_vv` | `V[s3]` | SQL `CASE WHEN cond THEN s2 ELSE s3 END`: `FALSE` **and** `NULL` both select `s3`! |
| `3` | `.case_vr` | `R[s3]` | Same as `.case_vv`, with `ELSE` branch read from scalar `R[s3]`. |

* **ImpAsm Usage**:
  ```impas
  ; SQL CASE WHEN e.tier == 1 THEN e.weight * 2.0 ELSE 1.0 END:
  VEC_BLEND.case_vr M7, M5, M6, R2
  ```
* **Justification**: Replaces 128-bit `OP_VEC_BLEND` (`0x27`) and broken `OP_STREAM_SELECT` (`0xB7`, where Java and C++ unpacked `falseReg` from different bytes!) in a single 64-bit word, while cleanly distinguishing strict 3VL ternary from SQL `CASE WHEN ... ELSE`!
* **Gotchas**: Combining `.scalar` (`s2 = R[s2]`) with `.kleene_vr` / `.case_vr` (`s3 = R[s3]`) selects between **two scalar registers** `R[s2]` and `R[s3]` per vector lane — e.g. `cond ? 1.0 : 0.0` in 1 instruction without materializing constant vectors!

---

### `0x4F` — `OP_COALESCE`
* **Summary**: Vector null-coalescing select (`V[dst][i] = valid_s1[i] ? V[s1][i] : rhs[i]`).
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS`: `rhs = R[s2]`), `0x1` (`FLAG_MASKED_S3`)
  - `subop:4`: `0`; `dst`: `V[dst]`; `s1`: `V[s1]`; `s2`: `V[s2]` or `R[s2]`; `s3`: `0` or `F[s3]` (`.mask`); `imm32`: `0` (MBZ)
  - `vm_flags` updated: None.
* **Operational Semantics**: When `V[s1]` has `valid_ptr == NULL` (all-valid `.imps` column fast path!), `OP_COALESCE` short-circuits in **$O(1)$** via COW alias `V[dst] = V[s1]` without touching a single element! Otherwise `valid_dst = v_s1 | v_s2` and blends `V[s2]`/`R[s2]` into null lanes of `V[s1]`.
* **ImpAsm Usage**:
  ```impas
  COALESCE.scalar M4, M4, R0    ; Replace NULL edge weights with default 1.0 in R0
  ```
* **Justification**: Essential for sanitizing nullable `.imps` columns before arithmetic without evaluating 3-operand `VEC_BLEND`.
* **Gotchas**: If *both* `V[s1][i]` and `rhs` are `NULL` (`R[s2]` has `r_valid_mask[s2] == 0`), lane $i$ remains `NULL` (`valid_dst[i] = 0`).

---

### `0x50` — `OP_VEC_INIT`
* **Summary**: Allocates and initializes a typed vector `V[dst]` filled with a scalar value (or `NULL`).
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS`: fill value from `R[s2]`; if `FLAG_SCALAR_RHS == 0`, fills with `0` / `valid=1`; if `FLAG_SCALAR_RHS == 1` and `R[s2]` is Kleene `NULL`, fills all lanes with `NULL` (`valid=0`))
  - `dst`: `V[dst]`; `s1`: `0` (MBZ — removes sentinel-0 ambiguity and guarantees exact static memory bounds); `s2`: `0` (or `R[s2]` w/ `.scalar`); `s3`: `0` (MBZ)
  - `imm32`: literal element count (including `0`) on `subop 0..6`; `imm16_lo = domain_id, imm16_hi = 0` on `subop 8..14`
  - `vm_flags` updated: None.
* **Sub-Operations (`subop:4` `0..6` literal `imm32` length; `8..14` domain-sized $N_d$)**:

| `subop` (Explicit Len) | `subop` (Domain Len $N_d$) | Element Type | Bytes / Element (+ `1/8 B` validity) |
| :--- | :--- | :--- | :--- |
| `0` (`.i64`) | `8` (`.dom_i64`) | `INT64` | `8 B` |
| `1` (`.u64`) | `9` (`.dom_u64`) | `UINT64` | `8 B` |
| `2` (`.i32`) | `10` (`.dom_i32`) | `INT32` | `4 B` |
| `3` (`.u32`) | `11` (`.dom_u32`) | `UINT32` | `4 B` |
| `4` (`.f64`) | `12` (`.dom_f64`) | `FLOAT64` | `8 B` |
| `5` (`.f32`) | `13` (`.dom_f32`) | `FLOAT32` | `4 B` |
| `6` (`.bool_3vl`) | `14` (`.dom_bool_3vl`) | `BOOL_3VL` | `2/8 B` (`valid` + `data` bitmasks) |

* **ImpAsm Usage**:
  ```impas
  ; Initialize SSSP distance vector V0[0..N_d) to NULL (+infinity / unreached) on domain 0:
  LOAD_CONST.null              R0
  VEC_INIT.dom_f64.scalar      V0, R0, dom=0
  ; Seed source node R1 distance = 0.0:
  LOAD_CONST.f32               R2, 0.0
  VEC_POINT.vec_set            V0, R1, R2
  ```
* **Justification**: Replaces ad-hoc `OP_ALLOC_SCRATCH` (`0x73`) and `OP_LOAD_INLINE_ARRAY` (`0x08`) for initializing `PageRank`, `SSSP`, and accumulator vectors at runtime domain scale $N_d$.
* **Gotchas**: When filling with `R[s2] = NULL` (`r_valid_mask[s2] == 0`), `OP_VEC_INIT` only needs to zero the `valid_mask` (`N_d / 8` bytes = `12.5 MB` at $10^8$ vs `800 MB` data array, or lazy zeroed page flags), saving $64\times$ memory write bandwidth!

---

### `0x51` — `OP_VEC_POINT`
* **Summary**: Controlled point read/write between scalar `R` and vector `V`, plus bulk numeric vector type casting.
* **Encoding**:
  - `flags:4`: `0x0`
  - `s3`: `0` (MBZ)
* **Sub-Operations (`subop:4` (`0..2`))**:

| `subop` | Mnemonic | Signature | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.vec_get` | `R[dst] <- V[s1][R[s2]]` | Bounds-checks `R[s2] < len(V[s1])`; reads element + validity bit into `R[dst]` (widening `I32->I64`, `U32->U64`, `F32->F64`); sets `ZF`, `NF`. |
| `1` | `.vec_set` | `V[dst][R[s1]] <- R[s2]` | Bounds-checks `R[s1] < len(V[dst])`; triggers COW unshare if `V[dst]` is read-only/shared; writes `(valid[s2], R[s2])` at index `R[s1]`. |
| `2` | `.vec_cast` | `V[dst] <- V[s1]`, `imm16_lo=tgt_type` | Vectorized SIMD cast across `[0..len)` (`0=I64, 1=U64, 2=I32, 3=U32, 4=F64, 5=F32`), preserving validity bitmap (`F64->I64` uses UB-free saturating `trunc`). |
| `3` | `.vec_len` | `R[dst] <- V[s1]` (`s2=0, imm32=0`) | $O(1)$ read of `len(V[s1])` into `R[dst]` (`SCALAR_U64`, `valid=1`; sets `ZF = (len == 0)`, `NF = 0`). |

* **ImpAsm Usage**:
  ```impas
  VEC_POINT.vec_set  V0, R1, R2          ; V0[seed] = 0.0
  VEC_POINT.vec_cast V3, V2, type=f64    ; Cast out_degree U32 vector V2 -> F64 vector V3
  ```
* **Justification**: Solves point seed initialization (`dist[start] = 0`) and integer-to-float vector promotion (`1.0 / (double)out_deg[u]`) cleanly in bytecode.
* **Gotchas**:
  1. **COW Unshare Mandatory on `.vec_set`**: Calling `.vec_set` on a vector bound via `OP_LOAD_COLUMN` (memory-mapped `.imps` file!) without COW copying first would segfault (`SIGBUS`/`SIGSEGV`) on read-only `mmap` pages!
  2. Per `AGENTS.md` §3.16, `.vec_get` / `.vec_set` are strictly for seed setup and scalar result inspection — never for imperative per-node VM loops!

---

### `0x52` — `OP_VEC_REDUCE`
* **Summary**: Deterministic parallel SIMD reduction of `V[s1]` into scalar `R[dst]` (skipping `NULL` elements; optionally masked by `F[s3]`).
* **Encoding**:
  - `flags:4`: `0x1` (`FLAG_MASKED_S3`: restricts reduction to active nodes in `F[s3]`)
  - `s2`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: `ZF = (!valid[dst] || R[dst] == 0)`, `NF = !valid[dst]`.
* **Sub-Operations (`subop:4` (`0..10`))**:

| `subop` | Mnemonic | Empty / All-`NULL` Result | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.sum` | `0` / `0.0` (`valid=1`) | Deterministic 64-block pairwise tree sum (`I64`, `U64`, `F32->F64`, `F64`). |
| `1` | `.min` | `NULL` (`valid=0, NF=1`) | Minimum valid element. |
| `2` | `.max` | `NULL` (`valid=0, NF=1`) | Maximum valid element. |
| `3` | `.count_valid` | `0` (`valid=1`) | Count of active non-`NULL` elements (`u64`). |
| `4` | `.mean` | `NULL` (`valid=0, NF=1`) | `sum / (double)count_valid` (`f64`). |
| `5` | `.l1_norm` | `0.0` (`valid=1`) | $\sum \lvert x_i \rvert$ (`f64`). |
| `6` | `.l2_norm_sq` | `0.0` (`valid=1`) | $\sum x_i^2$ (`f64`). |
| `7` | `.argmin` | `NULL` (`valid=0, NF=1`) | Index $i$ (`u64`) of minimum valid value (**lowest index $i$ wins ties!**). |
| `8` | `.argmax` | `NULL` (`valid=0, NF=1`) | Index $i$ (`u64`) of maximum valid value (**lowest index $i$ wins ties!**). |
| `9` | `.any_true` | `0` (`valid=1`) | `1` if at least one active `BOOL_3VL` lane is `TRUE (1,1)`, else `0`. |
| `10` | `.all_true` | `1` (`valid=1`) | `1` if every active lane is `TRUE (1,1)`, else `0`. |

* **ImpAsm Usage**:
  ```impas
  ; Sum dangling-node PageRank mass over sink frontier F_dangling (F3):
  VEC_REDUCE.sum.mask R4, V0, F3
  ```
* **Justification**: Consolidates `OP_VECTOR_REDUCE_SUM` (`0x35`) and `OP_REDUCE` (`0x45`) while adding `.mask F[s3]` (essential for summing dangling PageRank mass or subgraph aggregates without materializing a masked copy of `V0`!).
* **Gotchas**: **Floating-Point Reassociation**: Multi-threaded reductions MUST compute each fixed 64-element block's pairwise tree sum in `double` (`f64`) and sum block totals in ascending block index order `0 .. num_blocks - 1` so `max_dop = 1` and `max_dop = 16` match to **0 ULP**!

---

### `0x53` — `OP_TOP_K`
* **Summary**: Deterministic bounded heap / SIMD quickselect over score vector `V[s1]`, outputting ordered top-$k$ indices or scores into `V[dst]`.
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS`: `k = R[s2]`, else `k = imm16_lo`), `0x1` (`FLAG_MASKED_S3`: restricts candidates to `F[s3]`)
  - `imm16_lo`: `k` (MBZ if `.scalar`), `imm16_hi`: `0` (MBZ)
  - `vm_flags` updated: `ZF = (len(V[dst]) == 0)`.
* **Sub-Operations (`subop:4` (`0..3`))**:

| `subop` | Mnemonic | Output `V[dst]` | Ordering & Tie-Breaking |
| :--- | :--- | :--- | :--- |
| `0` | `.desc_ids` | `U32`/`U64` indices | Largest `k` valid scores descending; **equal scores broken by ascending index `i`**! |
| `1` | `.asc_ids` | `U32`/`U64` indices | Smallest `k` valid scores ascending; **equal scores broken by ascending index `i`**! |
| `2` | `.desc_scores` | Same type as `V[s1]` | Sorted score values matching `.desc_ids`. |
| `3` | `.asc_scores` | Same type as `V[s1]` | Sorted score values matching `.asc_ids`. |

* **ImpAsm Usage**:
  ```impas
  ; Return top 10 highest-PageRank nodes within candidate frontier F1:
  TOP_K.desc_ids.mask V3, V0, F1, k=10
  ```
* **Justification**: Closes a glaring gap in v0.10 (where `PageRank` and `VECTOR_RERANK_DOT` computed score vectors with no VM opcode to extract `ORDER BY score DESC LIMIT k`!).
* **Gotchas**: `NULL` lanes in `V[s1]` are **never** selected into top-$k$; if fewer than `k` valid active candidates exist (`M < k`), `len(V[dst]) == M` (`k == 0` yields empty `V[dst]`, `ZF = 1`). Note `-0.0 == +0.0` in score comparison, so tie-breaking between `-0.0` at node `3` and `+0.0` at node `7` MUST place node `3` first!

---

### `0x54` — `OP_INDEX_SCAN`
* **Summary**: $O(\log N_d)$ / $O(1)$ point or range lookup against an immutable `.imps` secondary attribute index `(domain_id = imm16_lo, attr_id = imm16_hi)` into 1-bit `F[dst]`.
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM`) (`s2` and `s3` are **always** scalar registers `R[s2]`, `R[s3]`)
  - `s1`: `0` (MBZ)
  - `vm_flags` updated: `ZF = is_empty(F[dst])`.
* **Sub-Operations (`subop:4` (`0..6`))**:

| `subop` | Mnemonic | Scalar Bounds | Matched Predicate |
| :--- | :--- | :--- | :--- |
| `0` | `.eq` | `R[s2]` (`s3=0`) | `attr == R[s2]` |
| `1` | `.between_cc` | `R[s2], R[s3]` | `R[s2] <= attr && attr <= R[s3]` (closed-closed `[lo, hi]`) |
| `2` | `.between_co` | `R[s2], R[s3]` | `R[s2] <= attr && attr < R[s3]` (closed-open `[lo, hi)`) |
| `3` | `.lt` | `R[s2]` (`s3=0`) | `attr < R[s2]` |
| `4` | `.le` | `R[s2]` (`s3=0`) | `attr <= R[s2]` |
| `5` | `.gt` | `R[s2]` (`s3=0`) | `attr > R[s2]` |
| `6` | `.ge` | `R[s2]` (`s3=0`) | `attr >= R[s2]` |

* **ImpAsm Usage**:
  ```impas
  INDEX_SCAN.eq F0, R1, dom=0, attr=0
  ```
* **Justification**: Replaces runtime scratch-index mutation (`0x1E`/`0x1F`) with zero-copy queries over `.imps` sorted/Elias-Fano/hash secondary indexes, automatically falling back to `OP_NODE_FILTER` over `ALL_SPAN` if no physical index section exists on `(dom_id, attr_id)`!
* **Gotchas**: If `R[s2]` (or `R[s3]` on `.between_*`) is Kleene `NULL`, `OP_INDEX_SCAN` returns an `EMPTY` delta (`ZF = 1` unless `.accum`) in $O(1)$.

---

### `0x55` — `OP_MAP_KEYS_TO_DENSE`
* **Summary**: Translates external domain keys (`.imps` Section 2 Key Catalog strings or `u64` keys) into 0-indexed dense domain IDs `[0, N_d)`.
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM` allowed on `subop == 0` and `subop == 3`)
  - `s2, s3`: `0` (MBZ)
* **Sub-Operations (`subop:4` (`0..4`))**:

| `subop` | Mnemonic | Signature | Missing-Key Behavior |
| :--- | :--- | :--- | :--- |
| `0` | `.param_to_f` | `F[dst] <- param_id=imm16_hi, dom=imm16_lo` (`s1=0`) | Missing external keys in host parameter set are **ignored** (not added to `F[dst]`); sets `ZF = is_empty(F[dst])`. |
| `1` | `.vec_to_v` | `V[dst] <- V[s1], dom=imm16_lo` (`imm16_hi=0`) | Positional 1:1 mapping (`len(V[dst]) == len(V[s1])`); missing keys produce Kleene `NULL` (`valid=0`) at that lane! |
| `2` | `.scalar_to_r` | `R[dst] <- R[s1], dom=imm16_lo` (`imm16_hi=0`) | Maps single external key `R[s1]` to dense ID `R[dst]`; missing key sets `R[dst] = NULL` (`valid=0, NF=1, ZF=1`)! |
| `3` | `.f_to_f` | `F[dst] <- F[s1], src_dom=imm16_hi, tgt_dom=imm16_lo` | Fused streaming dense-to-dense business-key bridge (`0 B` intermediate key vector; works across same-snapshot domains or federated `.imps` mounts!). Unmatched keys are omitted; sets `ZF = is_empty(F[dst])`. |
| `4` | `.v_to_v` | `V[dst] <- V[s1], src_dom=imm16_hi, tgt_dom=imm16_lo` | Fused rank-preserving dense-ID vector bridge (`len(V[dst]) == len(V[s1])`); unmatched keys write Kleene `NULL` (`valid=0`). |

* **ImpAsm Usage**:
  ```impas
  MAP_KEYS_TO_DENSE.param_to_f F0, dom=0, param=0
  ```
* **Justification**: Upgrades v0.10 `OP_MAP_KEYS_TO_DENSE` (`0x05`) with explicit `domain_id` scoping (`AGENTS.md` §3.14) and clean Kleene `NULL` semantics for missing keys on vector/scalar lookups.
* **Gotchas**: Invoking `OP_MAP_KEYS_TO_DENSE` on a domain without a Key Catalog returns `IMPULSE_VM_ERR_OUT_OF_BOUNDS` (`2`) (probed beforehand via `OP_HAS_TOPOLOGY.has_key_cat`).

---

### `0x56` — `OP_MAP_DENSE_TO_KEYS`
* **Summary**: Translates 0-indexed dense domain IDs `[0, N_d)` back to external Key Catalog `StringView` or `U64` keys.
* **Encoding**:
  - `flags:4`: `0x0`
  - `s2, s3`: `0` (MBZ); `imm16_lo`: `domain_id`, `imm16_hi`: `0` (MBZ)
* **Sub-Operations (`subop:4` (`0..2`))**:

| `subop` | Mnemonic | Signature | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.vec` | `V[dst] <- V[s1]` | Translates dense IDs in `V[s1]` positional 1:1 into external `StringView`/`U64` keys in `V[dst]` (preserves rank order!). |
| `1` | `.frontier_sorted` | `V[dst] <- F[s1]` | Translates active nodes of 1-bit `F[s1]` in ascending dense ID order into `V[dst]`. |
| `2` | `.scalar` | `R[dst] <- R[s1]` | Translates single dense ID `R[s1]` into external `StringView`/`U64` key in `R[dst]`. |

* **ImpAsm Usage**:
  ```impas
  TOP_K.desc_ids         V2, V0, k=10
  MAP_DENSE_TO_KEYS.vec  V3, V2, dom=0    ; Preserves exact Top-10 rank order!
  ```
* **Justification**: Replaces `OP_MAP_DENSE_TO_KEYS` (`0x92`) with both rank-preserving `.vec` translation (for `TOP_K` and `VECTOR_ANN_SEARCH`!) and `.frontier_sorted` translation.
* **Gotchas**: Any valid dense ID `>= N_domain` returns `IMPULSE_VM_ERR_OUT_OF_BOUNDS` (`2`); `NULL` lanes in `V[s1]` propagate `NULL` to `V[dst]`.

---

### `0x57` — `OP_COLLECT`
* **Summary**: Materializes terminal query outputs (`F`, `V`, `R`, or multi-column Arrow table columns) into `VmQueryContext` output slots.
* **Encoding**:
  - `flags:4`: `0x1` (`FLAG_MASKED_S3` allowed on `subop = 2, 4`: compacts `V[s1]` over active nodes in `F[s3]`!)
  - `dst, s2`: `0` (MBZ)
  - `vm_flags` updated: `ZF = is_empty_output`.
* **Sub-Operations (`subop:4` (`0..4`))**:

| `subop` | Mnemonic | Source `s1` | Materialized Output in `ctx->outputs[imm16_lo]` |
| :--- | :--- | :--- | :--- |
| `0` | `.frontier_bitset` | `F[s1]` | Zero-copy/packed dense bitset `[0, N_d)` (or multi-lane slab view) + `domain_id`. |
| `1` | `.frontier_ids` | `F[s1]` | Contiguous Arrow array of ascending dense node IDs (`U32`/`U64`). |
| `2` | `.vec` | `V[s1]` | Arrow columnar buffer + validity bitmap in caller `result_buf` (if `.mask F[s3]`, compacts values `V[s1][u]` for $u \in F[s3]$ in ascending $u$ order, aligned with `SET_CONVERT.f2v_ids`). |
| `3` | `.scalar` | `R[s1]` | Self-describing scalar value + validity bit + `r_type_word` tag in caller `result_buf`. |
| `4` | `.table_col` | `V[s1]` | Binds `V[s1]` (compacted by `F[s3]` if `.mask`) as column `imm16_hi` of Arrow RecordBatch `imm16_lo`. |

* **ImpAsm Usage**:
  ```impas
  ; Project (node_id, distance) for all reached nodes F1 into Arrow RecordBatch 0:
  SET_CONVERT.f2v_ids     V2, F1
  COLLECT.table_col       V2, batch=0, col=0
  COLLECT.table_col.mask  V0, F1, batch=0, col=1
  HALT
  ```
* **Justification**: Replaces `OP_COLLECT_BITSET` (`0x90`), `OP_COLLECT_ARRAY` (`0x91`), and heap-hash-table `OP_COLLECT_VALUE_MAP` (`0x93`) with zero-copy Arrow RecordBatch columns (`AGENTS.md` §3.15), and ensures **100% of collected data is hashed by `ICTX v2`** (fixing the `ICTX v1` `TYPE_VALUE_MAP` blind spot!).
* **Gotchas**: All columns bound to the same RecordBatch `imm16_lo` via `.table_col` MUST have identical row counts (`ERR_INVALID_OPERAND` `6` if mismatched).

---

## Pillar 5 — Multi-Lane Bit-Sliced Execution & Vector ANN (`0x60`–`0x6A`)

---

### `0x60` — `OP_LANE_INIT_SEEDS`
* **Summary**: Initializes a multi-lane bit-sliced frontier `F[dst]` (`Width8/16/32/64`) in **Tier 1 4K-node paged slabs** from seed node vector `V[s1]`.
* **Encoding**:
  - `flags:4`: `0x0`
  - `dst`: `F[dst]`; `s1`: `V[s1]` (`len <= 64`); `s2, s3`: `0` (MBZ); `imm16_lo`: `domain_id`, `imm16_hi`: `0` (MBZ)
  - `vm_flags` updated: `ZF = (active_seed_count == 0)`.
* **Sub-Operations (`subop:4` (`0..1`))**:

| `subop` | Mnemonic | Allocated `lane_width` | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.auto_width` | Smallest of `{8, 16, 32, 64}` $\ge \operatorname{len}(V[s1])$ | Minimizes Tier 1 4K-page byte width (`4 KB`..`32 KB`/page). |
| `1` | `.force_w64` | `64` | Forces 64-bit lane words (when later merging dynamically up to 64 lanes). |

* **Operational Semantics**: Validates `len(V[s1]) <= 64` (`ERR_BUFFER_OVERFLOW` `11` if `> 64`). Assigns lane $k \in [0, \text{len})$ to seed `u = V[s1][k]` (`lanes[u] |= (1ULL << k)`; `NULL` lanes in `V[s1]` leave lane $k$ empty) inside **Tier 1 4K-node paged slabs** (`Tier 2` if $N_d \le 4096$). Records `active_lane_count = len(V[s1])`.
* **ImpAsm Usage**:
  ```impas
  LANE_INIT_SEEDS.auto_width F0, V0, dom=0
  ```
* **Justification**: Fixes the catastrophic v0.10 memory regression in `VmLaneFrontier.java:108` where 2 seeds on $10^8$ nodes zeroed an `800 MB` `long[N]` array — Tier 1 allocates at most `2` 4K pages (`8 KB` for `Width8`!) in microseconds!
* **Gotchas**: Duplicate seed IDs in `V[s1]` (e.g. `V[s1] = [5, 5]`) set **both** lane bits `0` and `1` on node `5` (`lanes[5] = 0b11`) — never collapse duplicate lanes!

---

### `0x61` — `OP_LANE_INIT_GROUPS`
* **Summary**: Initializes multi-lane frontier `F[dst]` from `(node_ids = V[s1], group_lane_ids = V[s2])`.
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM`); `subop:4`: `0`
  - `dst`: `F[dst]`; `s1`: `V[s1]` (dense node IDs); `s2`: `V[s2]` (lane indices `0..63`); `s3`: `0` (MBZ); `imm16_lo`: `domain_id`, `imm16_hi`: `lane_width` (`0` = auto from `max_lane`, or `8/16/32/64`)
  - `vm_flags` updated: `ZF = is_empty(F[dst])`.
* **ImpAsm Usage**:
  ```impas
  LANE_INIT_GROUPS F0, V0, V1, dom=0, width=64
  ```
* **Justification**: Enables multi-cohort / multi-group simultaneous BFS where each cohort ($g \in 0..63$) contains arbitrary many seed nodes.
* **Gotchas**: Any valid lane index in `V[s2]` $\ge 64$ (or $\ge \text{width}$ if explicit) returns `IMPULSE_VM_ERR_OUT_OF_BOUNDS` (`2`).

---

### `0x63` — `OP_LANE_WALK`
* **Summary**: Bit-sliced multi-lane frontier traversal (`lanes_dst[v] |= lanes_src[u]`) across `FWD`, `REV`, `BOTH`, `FIXPOINT`, and `EDGE_MASKED` modes over Tier 1 paged slabs or Tier 2 dense arrays.
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM`), `0x1` (`FLAG_MASKED_S3`: excludes 1-bit `F[s3]` nodes **or** subtracts per-lane visited bits `~F[s3]` when `F[s3]` is multi-lane!)
  - `vm_flags` updated: `ZF = is_empty(F[dst])`, `ST = 1` on fixpoint subops.
* **Sub-Operations (`subop:4` (`0..8`))**:

| `subop` | Mnemonic | Operands | Semantics (`rel_id = imm16_lo`) |
| :--- | :--- | :--- | :--- |
| `0` | `.fwd` | `F[dst] <- F[s1]` | 1-hop $Src \to Tgt$ bit-sliced OR propagation. |
| `1` | `.rev` | `F[dst] <- F[s1]` | 1-hop $Tgt \to Src$ bit-sliced OR propagation. |
| `2` | `.both` | `F[dst] <- F[s1]` | Undirected 1-hop propagation (`src_dom == tgt_dom`). |
| `3` | `.fwd_fixpoint_plus` | `F[dst] <- F[s1]` | Multi-lane transitive closure $R^+$; tracks per-lane delta `next & ~visited`! Sets `ST = 1`. |
| `4` | `.fwd_fixpoint_star` | `F[dst] <- F[s1]` | Reflexive-transitive closure $R^*$; sets `ST = 1`. |
| `5` | `.rev_fixpoint_plus` | `F[dst] <- F[s1]` | Reverse multi-lane transitive closure; sets `ST = 1`. |
| `6` | `.rev_fixpoint_star` | `F[dst] <- F[s1]` | Reverse reflexive-transitive closure; sets `ST = 1`. |
| `7` | `.fwd_edge_masked` | `F[dst] <- F[s1], V[s2]` | `lanes_dst[v] \|= (lanes_src[u] & edge_mask[e])` (`V[s2]` = `U64[M_r]`). |
| `8` | `.both_fixpoint_star` | `F[dst] <- F[s1]` (`s2=0` MBZ) | Undirected unweighted multi-lane reflexive-transitive closure. |
| `9` | `.both_fixpoint_star_masked` | `F[dst] <- F[s1], V[s2]` | Undirected edge-masked reachability via `V[s2]` (`U64[M_r]`, allowing `V0..V15` — 64-contingency N-1 island check in 1 instruction!). |

* **ImpAsm Usage**:
  ```impas
  ; Simultaneous 64-seed BFS step pruning per-lane visited bits in F0:
  LANE_WALK.fwd.mask  F2, F1, F0, rel=0     ; F2[v] = (OR_{u->v} F1[u]) & ~F0[v]
  SET_OP.union        F0, F0, F2            ; F0[v] |= F2[v]
  ```
* **Justification**: Replaces `OP_LANE_CSR_WALK` (`0xC3`) and `OP_LANE_CSC_WALK` (`0xC4`) while adding per-lane visited pruning (`.mask F_visited`) and 64-way edge-masked fixpoint reachability (`64×` speedup for N-1 contingency & batch ReBAC).
* **Gotchas**: In `.fwd_fixpoint_*`, a node `u` MUST be re-expanded on hop $t+1$ **if and only if at least one NEW lane bit** became set on `u` at hop $t$ (`delta_lanes[u] = new_lanes[u] & ~visited_lanes[u] != 0`)! Treating `u` as 1-bit visited after lane 0 visits `u` would drop lanes `1..63`!

---

### `0x64` — `OP_LANE_BITWISE`
* **Summary**: Bitwise lane-mask filtering, pruning, and single-lane extraction on multi-lane frontiers.
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS` on `subop 0, 1`)
  - `vm_flags` updated: `ZF = is_empty(F[dst])`.
* **Sub-Operations (`subop:4` (`0..3`))**:

| `subop` | Mnemonic | Signature | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.prune_mask` | `F[dst] <- F[s1], R[s2]` | Clears lane bits set in `R[s2]`: `lanes[u] &= ~R[s2]` (replaces `0xC5`). |
| `1` | `.keep_mask` | `F[dst] <- F[s1], R[s2]` | Retains only lane bits set in `R[s2]`: `lanes[u] &= R[s2]`. |
| `2` | `.and_not_lanes` | `F[dst] <- F[s1], F[s2]` | Per-node `F[s1][u] & ~F[s2][u]`. |
| `3` | `.extract_lane` | `F[dst] <- F[s1], imm16_lo=lane_k` | Extracts single lane `lane_k` (`0..63`) into a **1-bit frontier** `F[dst]` ($W=1$)! |

* **ImpAsm Usage**:
  ```impas
  LANE_BITWISE.extract_lane F3, F0, lane=0
  ```
* **Justification**: Generalizes `OP_LANE_PRUNE_MASK` (`0xC5`) and provides `.extract_lane` so individual lane results seamlessly compose with 1-bit `F` ops.
* **Gotchas**: When `.prune_mask` or `.keep_mask` zeroes every node in a Tier 1 4K page, release that page from `dirty_pages[]` so `ZF` and `dirty_count` stay exact!

---

### `0x65` — `OP_LANE_FILTER_QUORUM`
* **Summary**: Collapses multi-lane frontier `F[s1]` into a 1-bit frontier `F[dst]` ($W=1$) keeping nodes whose active lane popcount satisfies quorum `k`.
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM`), `0x2` (`FLAG_SCALAR_RHS`: `k = R[s2]`, else `k = imm16_lo`)
  - `dst`: `F[dst]` ($W=1$); `s1`: `F[s1]` ($W>1$); `s3`: `0` (MBZ)
  - `vm_flags` updated: `ZF = is_empty(F[dst])`.
* **Sub-Operations (`subop:4` (`0..2`))**:

| `subop` | Mnemonic | Quorum Condition on $c = \operatorname{popcnt}(\text{lanes}[u])$ |
| :--- | :--- | :--- |
| `0` | `.at_least` | $c \ge k$ |
| `1` | `.exact` | $c == k$ |
| `2` | `.at_most_nonzero` | $1 \le c \le k$ (excludes unreached `0`-lane nodes!) |

* **ImpAsm Usage**:
  ```impas
  ; Find entities reachable from at least 3 of 10 watchlist seeds:
  LANE_FILTER_QUORUM.at_least F2, F1, k=3
  ```
* **Justification**: Core primitive for multi-seed entity resolution, fraud ring detection, and NornicDB multi-anchor hybrid graph retrieval.
* **Gotchas**: Notice `.at_least` with `k == 0` matches all `[0, N_d)` (`ALL_SPAN`); `.at_most_nonzero` intentionally requires `popcnt >= 1` so unreached nodes (`lanes[u] == 0`) are not selected!

---

### `0x66` — `OP_LANE_REDUCE_AND`
* **Summary**: Intersects active lanes of `F[s1]` into a 1-bit frontier `F[dst]` (`{ u | (lanes[u] & target_mask) == target_mask }`).
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM`), `0x2` (`FLAG_SCALAR_RHS`: when `0`, `s2=0` MBZ and `target_mask = impulse_make_active_mask_u64(F[s1].active_lane_count)`; when `1`, `target_mask = R[s2]`)
  - `subop:4`: `0`; `dst`: `F[dst]` ($W=1$); `s1`: `F[s1]` ($W>1$); `s3`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: `ZF = is_empty(F[dst])`.
* **ImpAsm Usage**:
  ```impas
  ; Bidirectional / multi-seed meeting points reachable from ALL seeds:
  LANE_REDUCE_AND F2, F1
  ```
* **Justification**: Single-pass SIMD comparison over Tier 1 `dirty_pages[]` finds exact common ancestors / meeting points of up to 64 seeds simultaneously.
* **Gotchas**: If `target_mask == 0` (`0` active seeds), `OP_LANE_REDUCE_AND` MUST output `EMPTY` (`ZF = 1`), **not** `ALL_SPAN` (`(0 & 0) == 0` vacuous truth trap; same if `R[s2]` is `NULL` or `0` under `.scalar`).

---

### `0x67` — `OP_LANE_REDUCE_ATTR`
* **Summary**: Reduces node vector `V[s2]` independently for each active lane $k \in [0, K)$ of multi-lane `F[s1]`, writing a $K$-element vector into `V[dst]`.
* **Encoding**:
  - `flags:4`: `0x0`
  - `dst`: `V[dst]` (`len = F[s1].active_lane_count`); `s1`: `F[s1]` ($W>1$); `s2`: `V[s2]` (`0` on `.count`); `s3`: `0` (MBZ); `imm32`: `0` (MBZ)
  - `vm_flags` updated: `ZF = (len(V[dst]) == 0)`.
* **Sub-Operations (`subop:4` (`0..3`))**:

| `subop` | Mnemonic | Per-Lane Reduction (`k = 0 .. K-1`) | Empty-Lane Output |
| :--- | :--- | :--- | :--- |
| `0` | `.sum` | Deterministic 64-block sum of `V[s2][u]` where bit $k$ set | `0` / `0.0` (`valid=1`) |
| `1` | `.min` | Minimum valid `V[s2][u]` where bit $k$ set | `NULL` (`valid=0`) |
| `2` | `.max` | Maximum valid `V[s2][u]` where bit $k$ set | `NULL` (`valid=0`) |
| `3` | `.count` | Count of active nodes in lane $k$ (`s2=0` MBZ) | `0` (`valid=1`) |

* **ImpAsm Usage**:
  ```impas
  ; Sum generation MW (V0) per contingency scenario (lanes 0..63 in F1):
  LANE_REDUCE_ATTR.sum V1, F1, V0
  ```
* **Justification**: Computes 64 independent subgraph aggregations in one cache-coherent pass over `V[s2]` and `F[s1]`'s dirty pages.
* **Gotchas**: Lanes with 0 valid matched nodes receive `0` on `.sum`/`.count` and Kleene `NULL` (`valid=0`) on `.min`/`.max`. Deterministic ascending node-ID reduction order (64-node blocks) is mandatory for `.sum` on floats!

---

### `0x69` — `OP_VECTOR_ANN_SEARCH`
* **Summary**: Queries an `.imps` HNSW / DiskANN vector index `(domain_id = imm16_lo, ann_index_id = imm16_hi)` with query embedding `V[s1]`, outputting **rank-ordered** candidate dense node IDs into `V[dst]`.
* **Encoding**:
  - `flags:4`: `0x1` (`FLAG_MASKED_S3`: pre-filters candidate nodes to `F[s3]`; `s2` always addresses `R[s2]`, so `FLAG_SCALAR_RHS` is disallowed)
  - `subop:4` (`0..1`):
    - `0` (`.ids`): top-`k` search (`R[s2]` low 32b = `k`, high 32b = `ef_search` override or `0`), writing rank-ordered `U32`/`U64` dense node IDs into `V[dst]`.
    - `1` (`.radius`): distance/similarity threshold search (`R[s2]` = `f64` cutoff threshold), writing matching rank-ordered dense node IDs into `V[dst]` (bounded by `result_buf` / `scratch_buf` capacity).
  - `dst`: `V[dst]`; `s1`: `V[s1]` (`F32[D]` query embedding); `s2`: `R[s2]`; `s3`: `0` or `F[s3]` filter mask (`.mask`)
  - `imm16_lo`: `domain_id`, `imm16_hi`: `ann_index_id`
  - `vm_flags` updated: `ZF = (len(V[dst]) == 0)`.
* **ImpAsm Usage**:
  ```impas
  ; Hybrid Graph + Vector search: find top 50 ANN matches within 2-hop graph neighborhood F1!
  LOAD_CONST.i32         R2, 50
  VECTOR_ANN_SEARCH.mask V1, V0, R2, F1, dom=0, idx=0
  ```
* **Justification**: Fixes v0.10 `OP_VECTOR_ANN_SEARCH` (`0xCA`), which could write candidates into an unordered bitset (destroying similarity ranking!) and lacked native `.mask F[s3]` subgraph pre-filtering for hybrid GraphRAG queries.
* **Gotchas**:
  1. Validates `len(V[s1]) == index.dimension` (`ERR_INVALID_OPERAND` `6` if mismatched) and rejects `NaN` / `NULL` lanes in query embedding `V[s1]`.
  2. Equal HNSW distance scores MUST break ties by ascending dense node ID `u` for 4-way deterministic output!

---

### `0x6A` — `OP_VECTOR_RERANK`
* **Summary**: Exact SIMD similarity/distance scoring of candidate nodes `V[s1]` against query embedding `V[s2]` using `.imps` embedding column `(domain_id = imm16_lo, attr_id = imm16_hi)`, writing `F32` scores into `V[dst]`.
* **Encoding**:
  - `flags:4`: `0x1` (`FLAG_MASKED_S3`)
  - `dst`: `V[dst]` (`F32`, `len = len(V[s1])`); `s1`: `V[s1]` (candidate dense IDs); `s2`: `V[s2]` (`F32[D]` query vector); `s3`: `0` or `F[s3]`
  - `vm_flags` updated: `ZF = (len(V[dst]) == 0)`.
* **Sub-Operations (`subop:4` (`0..7`))**:

| `subop` | Mnemonic | Formula | Higher-is-Better? |
| :--- | :--- | :--- | :--- |
| `0` | `.dot` | $\sum_{d=0}^{D-1} q_d \cdot v_d$ (`q = V[s2]`, `v = emb[V[s1][i]]`) | Yes (`TOP_K.desc_ids`) |
| `1` | `.cosine` | $\frac{q \cdot v}{\max(\epsilon, \lVert q \rVert_2 \cdot \lVert v \rVert_2)}$ ($\epsilon = 10^{-12}$) | Yes (`TOP_K.desc_ids`) |
| `2` | `.neg_l2_sq` | $-\sum_{d=0}^{D-1} (q_d - v_d)^2$ | Yes (`TOP_K.desc_ids`) |
| `3` | `.l2_sq` | $\sum_{d=0}^{D-1} (q_d - v_d)^2$ | Lower-is-Better (`TOP_K.asc_ids`) |
| `4` | `.pair_dot` | Pairwise `dot(emb[V[s1][i]], emb[V[s2][i]])` (`morsel_role: body_pair_only`) | Yes |
| `5` | `.pair_cosine` | Pairwise `cosine(emb[V[s1][i]], emb[V[s2][i]])` (enables semantic edge pruning inside `OP_WALK_MORSEL`!) | Yes |
| `6` | `.pair_neg_l2_sq` | Pairwise `-l2_sq(emb[V[s1][i]], emb[V[s2][i]])` | Yes |
| `7` | `.pair_l2_sq` | Pairwise `l2_sq(emb[V[s1][i]], emb[V[s2][i]])` | Lower-is-Better |

* **ImpAsm Usage**:
  ```impas
  ; Exact cosine rerank of 200 HNSW candidates V1 -> top 10 exact node IDs V4:
  VECTOR_RERANK.cosine V2, V1, V0, dom=0, attr=4
  TOP_K.desc_ids       V3, V2, k=10              ; V3 = top-10 positions [0..199] in V1
  GATHER_VEC           V4, V1, V3                ; V4 = top-10 dense node IDs!
  ```
* **Justification**: Generalizes `OP_VECTOR_RERANK_DOT` (`0xCB`) across `DOT`, `COSINE`, and `L2` while composing orthogonally with `OP_TOP_K` and `OP_GATHER_VEC`.
* **Gotchas**: Accumulate dot products / squared differences in **`double` (`f64`)** (or deterministic 16-lane pairwise `f32` tree) before rounding the final scalar per candidate to `f32`, preventing AVX-512 16-wide vs NEON 4-wide FMA associativity drift across architectures!

---

### `0x6B` — `OP_LANE_STATE_INIT`
* **Summary**: Allocates and initializes a 2D numeric multi-lane state slab (`LANE_STATE`, `state[N_d][W]`) in `V[dst]` backed by caller-owned `scratch_buf`, plus a compact `1 bit/node` active summary bitset and `uint16_t active_lane_mask[N_d]` (MITra Lesson 4.2).
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS`: seed value from `R[s2]` on `subop 4`)
  - `dst`: `V[dst]`; `s1`: `F[s1]` (multi-lane seed frontier on `subop 4`, `0` MBZ otherwise); `s2`: `R[s2]` (optional seed value); `s3`: `0` (MBZ); `imm16_lo`: `domain_id`, `imm16_hi`: `lane_width W`
  - `vm_flags` updated: `ZF = (N_d == 0)`.
* **Sub-Operations (`subop:4` (`0..5`))**:

| `subop` | Mnemonic | Semantics |
| :--- | :--- | :--- |
| `0` | `.zero_f32` | Allocate `f32[N_d][W]` (`W ∈ {4, 8, 16}`, $\le 64\text{ B/node}$) initialized to `0.0f`. |
| `1` | `.inf_f32` | Allocate `f32[N_d][W]` (`W ∈ {4, 8, 16}`, $\le 64\text{ B/node}$) initialized to `+Inf`. |
| `2` | `.zero_f64` | Allocate `f64[N_d][W]` (`W ∈ {2, 4, 8}`, $\le 64\text{ B/node}$) initialized to `0.0`. |
| `3` | `.inf_f64` | Allocate `f64[N_d][W]` (`W ∈ {2, 4, 8}`, $\le 64\text{ B/node}$) initialized to `+Inf`. |
| `4` | `.from_frontier_seeds` | Seed active `(u, b)` entries in `V[dst]` from multi-lane frontier `F[s1]` with `R[s2]` (or `0.0`/`1.0`). |
| `5` | `.with_witness` | Attach `uint32_t witness_prev[N_d][W]` in `scratch_buf` (initialized to `0xFFFFFFFF`) for `OP_LANE_STATE_REDUCE.trace_path`. |

* **Gotchas**: `W` is strictly capped at $\le 64\text{ B/node}$ (`W <= 16` for `f32`, `W <= 8` for `f64`) to stay under the random-scatter cache/TLB wall observed in `mitra_aside_bench`; larger `K` batches into `ceil(K / W)` passes.

---

### `0x6C` — `OP_LANE_STATE_WALK`
* **Summary**: Single-hop or fixed-point multi-lane semiring relaxation over `LANE_STATE` in `V[s1]` $\to$ `V[dst]` across `rel_id = imm16_lo` and optional edge attribute `attr_id = imm16_hi` (`0xFFFF` = unweighted `1.0`), using adaptive Push-CSR / Pull-CSC execution.
* **Encoding**:
  - `flags:4`: `0x4` (`FLAG_ACCUM` = fixpoint), `0x2` (`FLAG_SCALAR_RHS` = $\Delta$-bucket step from `R[s2]` for monotone semirings), `0x1` (`FLAG_MASKED_S3` = active/exclusion frontier `F[s3]`)
  - `dst`: `V[dst]`; `s1`: `V[s1]`; `s2`: `R[s2]` ($\Delta$ when `FLAG_SCALAR_RHS` set, `0` MBZ otherwise); `s3`: `F[s3]` (when `FLAG_MASKED_S3` set, `0` MBZ otherwise)
  - `vm_flags` updated: `ZF = (active_count == 0)`, `ST = 1` on fixpoint convergence.
* **Sub-Operations (`subop:4` (`0..9`))**:

| `subop` | Mnemonic | Semiring $(\oplus, \otimes)$ | Direction |
| :--- | :--- | :--- | :--- |
| `0` / `5` | `.fwd_min_plus` / `.rev_min_plus` | $(\min, +)$ — Multi-seed weighted SSSP | CSR / CSC |
| `1` / `6` | `.fwd_max_plus` / `.rev_max_plus` | $(\max, +)$ — Longest/critical path | CSR / CSC |
| `2` / `7` | `.fwd_max_mul` / `.rev_max_mul` | $(\max, \times)$ — Max-reliability / Viterbi | CSR / CSC |
| `3` / `8` | `.fwd_sum_mul` / `.rev_sum_mul` | $(+, \times)$ — Multi-seed PPR / Markov walks | CSR / CSC |
| `4` / `9` | `.fwd_min_max` / `.rev_min_max` | $(\min, \max)$ — Minimax bottleneck path | CSR / CSC |

* **Gotchas**:
  1. **Schedule-Invariant Witness Tie-Breaking**: When `witness_prev` is attached, update `witness_prev[v][b] = u` iff `new_cost < cur_cost || (new_cost == cur_cost && u < witness_prev[v][b])`, guaranteeing identical witness trees across synchronous, Gauss-Seidel, and $\Delta$-stepping schedules.
  2. **Deterministic `SUM_MUL` Guard**: Combining `subop 3` or `8` (`.fwd_sum_mul` / `.rev_sum_mul`) with `FLAG_SCALAR_RHS` ($\Delta$-bucket async stepping) MUST trap `IMPULSE_VM_ERR_INVALID_OPERAND` (`6`). Synchronous `SUM_MUL` accumulates incoming edges in ascending source-ID `u` order (CSC Pull).

---

### `0x6D` — `OP_LANE_STATE_OP`
* **Summary**: Vectorized in-domain `LANE_STATE` projection, pruning, and frontier bridging.
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS`)
  - `dst`: `V[dst]` (`subop 0..2`) or `F[dst]` (`subop 3..4`); `s1`: `V[s1]` (`LANE_STATE`); `s2`: `R[s2]` (`alpha`/cutoff/quorum); `s3`: `R[s3]` (optional `max_deg` on `subop 2`)
  - `vm_flags` updated: `ZF = is_empty(dst)`.
* **Sub-Operations (`subop:4` (`0..4`))**:

| `subop` | Mnemonic | Semantics |
| :--- | :--- | :--- |
| `0` | `.project_affine` | `V[dst][u][b] = (1 - alpha) * V[s1][u][b] + alpha * seed` (`alpha = R[s2]`, PageRank/PPR damping). |
| `1` | `.prune_cutoff` | Resets lanes with `V[s1][u][b] > R[s2]` back to semiring identity. |
| `2` | `.prune_hub_quorum` | Zeroes all lanes at `u` if `deg(u) > R[s3]` and fewer than `imm32` lanes satisfy `V[s1][u][b] <= R[s2]`. |
| `3` | `.to_lane_frontier` | Bridges `V[s1]` (`LANE_STATE`) $\to$ multi-lane frontier `F[dst]` where `V[s1][u][b] <= R[s2]`. |
| `4` | `.to_quorum_frontier` | Bridges `V[s1]` $\to$ 1-bit frontier `F[dst]` where active lane count $\ge R[s2]$. |

---

### `0x6E` — `OP_LANE_STATE_REDUCE`
* **Summary**: Reduces a `LANE_STATE` slab per-lane (`[W]` vector, `FLAG_SCALAR_RHS = 0`) or cross-lane (`[N_d]` node vector, `FLAG_SCALAR_RHS = 1`), or reconstructs a deterministic witness path.
* **Encoding**:
  - `flags:4`: `0x2` (`FLAG_SCALAR_RHS`: `0` = per-lane `[W]`, `1` = cross-lane `[N_d]`)
  - `dst`: `V[dst]`; `s1`: `V[s1]` (`LANE_STATE`, or `R[s1]` target node on `subop 6`); `s2`: `R[s2]` (lane index `b` on `subop 6`, `0` MBZ otherwise); `s3`: `0` (MBZ)
  - `vm_flags` updated: `ZF = (len(V[dst]) == 0)`.
* **Sub-Operations (`subop:4` (`0..6`))**:

| `subop` | Mnemonic | Semantics |
| :--- | :--- | :--- |
| `0`..`3` | `.min`, `.max`, `.sum`, `.mean` | Per-lane or cross-lane numeric reduction skipping identity/NULL lanes. |
| `4` / `5` | `.argmin` / `.argmax` | Returns winning node ID (per-lane) or lane index (cross-lane); lowest index strictly wins ties. |
| `6` | `.trace_path` | Reconstructs deterministic `u32` witness path in `V[dst]` for `(target=R[s1], lane=R[s2])` from `witness_prev`. |

---

### `0x6F` — `OP_VECTOR_POOL`
* **Summary**: Loads a single node's `[D]` embedding vector, pools a frontier's embeddings into a centroid/sum `[D]` vector, or L2-normalizes a dense embedding vector in `V[dst]` for in-VM node-to-ANN, TransE (`h + r`), and GraphRAG query expansion.
* **Encoding**:
  - `flags:4`: `0x0`; `s2, s3`: `0` (MBZ)
  - `dst`: `V[dst]` (`F32[D]`); `s1`: `R[s1]` (dense node ID on `subop 0`), `F[s1]` (frontier on `subop 1..2`), or `V[s1]` (`F32[D]` on `subop 3`); `imm16_lo`: `domain_id`, `imm16_hi`: `attr_id` (`0` on `subop 3`)
  - `vm_flags` updated: `ZF = (len(V[dst]) == 0 || norm == 0)`.
* **Sub-Operations (`subop:4` (`0..3`))**:

| `subop` | Mnemonic | `s1` Bank | Semantics |
| :--- | :--- | :--- | :--- |
| `0` | `.load_node` | `R[s1]` | Copies `emb[dom, attr][R[s1]]` into `V[dst]` (`F32[D]`). |
| `1` | `.mean_pool` | `F[s1]` | Computes deterministic ascending-node-ID centroid `mean_{u ∈ F[s1]} emb[u]` into `V[dst]` (`F32[D]`). |
| `2` | `.sum_pool` | `F[s1]` | Computes deterministic ascending-node-ID sum `sum_{u ∈ F[s1]} emb[u]` into `V[dst]` (`F32[D]`). |
| `3` | `.l2_norm` | `V[s1]` | Unit-normalizes `V[s1]` ($v / \max(10^{-12}, \lVert v \rVert_2)$) into `V[dst]`. |

---

## Extension Word Pseudo-Opcode (`0xFF`)

### `0xFF` — `OP_EXTENSION_PAYLOAD`
* **Summary**: Mandatory Word-2 guard marker for 128-bit (`FLAG_EXTENDED`) instructions.
* **Encoding**:
  - Byte `0`: `0xFF`; Bytes `1..3` (`ext_meta24`): `0x000000` (MBZ); Bytes `4..7`: `imm32_hi` (`uint32_t`)
* **Operational Semantics**: Never dispatched directly (`pc` advances across it by `+2` from the preceding `OP_LOAD_CONST.b64.ext` instruction). Any direct execution attempt returns `IMPULSE_VM_ERR_VALIDATION_FAILED` (`15`).
* **Justification & Gotcha**: Pinning Byte `0` to `0xFF` while storing the 64-bit constant as `(w2.imm32 << 32) | w1.imm32` guarantees that **no valid data constant can ever masquerade as an executable opcode in Word 2**.
