# ImpulseVM v0.11.0 ISA Refactor — Planning & Specification Suite

> **Status**: Pre-Sign-Off Architectural Specification (`feat/v0.11.0-ISA-Refactor`)
> **Scope**: Side-by-side normative design for `ImpulseVM` v0.11.0 (`impOps` v0.11, `ImpAsm` v0.11, `ICTX v2`). Original v0.10.0 specification files in `../docs/` and `../spec/` remain untouched during planning to enable direct diffing and review.

---

## 1. Refactor Summary & Quantitative Delta

`ImpulseVM` v0.11.0 replaces the organically grown 166-opcode v0.10.0 instruction set with an orthogonal, statically validated, nibble-encoded 64-bit register ISA designed from first principles around the **Kleisli Frontier Propagation & Monoidic Reduction** model (`AGENTS.md` §3.14–§3.15).

| Dimension | v0.10.0 Baseline | v0.11.0 Refactor | Architectural Impact |
| :--- | :--- | :--- | :--- |
| **Active Opcodes** | `166` (+ `0xFF` marker) | **`78`** (+ `0xFF` marker) | **53.0% opcode reduction**; eliminates physical-layout, direction, and type-combinatorial explosion while adding MITra AoS `LANE_STATE` (`0x6B`–`0x6E`) and `OP_VECTOR_POOL` (`0x6F`). |
| **Instruction Width** | Mixed 64-bit / 128-bit (`FLAG_EXTENDED` required for any 3-register op) | **Universal 64-bit** (`[op:8 \| flags:4 \| subop:4 \| dst:4 \| s1:4 \| s2:4 \| s3:4 \| imm32:32]`) | **>99% single-word instructions**; `FLAG_EXTENDED` (`0x80`) used solely for 64-bit scalar literal constants. |
| **Register File** | `64` untyped union slots (`R0..R63`) + runtime `uint8_t register_types[64]` | **`3 × 16` Typed Banks**: `R0..R15` (+ 8B `r_type_word` + `r_valid_mask`), `F0..F15`, `V0..V15` | **64B tag array $\to$ 8B packed `r_type_word`**; 4-bit nibbles cannot index out-of-bounds (`VALIDATE_REG` deleted from hot path). |
| **VM State Frame & Memory** | `640` bytes (`10` cache lines) + internal heap pools | **`256` bytes** (`4` cache lines) + **Caller-Owned `(scratch_buf, result_buf)`** | **60% smaller L1 footprint**, `0` `malloc`/`free` in kernel, `64B`-masked `4KB` Tier 1 directory, and exact static `impulse_vm_plan_memory` sizing. |
| **Sub-Operation Ceiling** | Up to 54 functions inside one `switch` (`OP_VEC_MATH_UNARY`) | **Strict `subop:4` (`0..15`)** across all opcodes | Every opcode handler is $\le 16$ cases, staying below C++ inline / JVM C2 `FreqInlineSize` bytecode cliffs. |
| **Subroutine Register Windows** | Copy-only `R12..R15 -> R0..R3` (clobbered caller `R0..R3` without save) | **Variable-Stride Sliding Windows** (`r_stride`, `f_stride`, `v_stride`) + `OP_SPILL`/`OP_RELOAD` | True recursive subroutines with deterministic RAII arena/slab release on `OP_RET`. |
| **Frontier Representation** | Flat $O(N)$ bitset or eager $O(N)$ `VmLaneFrontier` (`long[N]`) | **Unified 3-Tier Adaptive `VmFrontier`** (Tier 0 inline $\le 64$, Tier 1 4K paged slabs, Tier 2 dense + L1 summary) + lazy `cached_card = -1` | $O(\lvert F \rvert)$ point-seed latency at $N = 10^9$ without penalizing dense sweeps; unifies 1-bit and multi-lane (`Width8..64`) frontiers in `F0..F15`. |
| **CEL Edge & Node Predicates** | 32 `float32`-only scalar shaders (`0xA0`–`0xBF`) + runtime AST walker (`0x13`) | **2-Tier Pushdown + Lexical Multi-Sink Morsels** (`OP_WALK_MORSEL`, `OP_FILTER_MORSEL`, `OP_MORSEL_COMMIT`, `OP_MORSEL_END`) | Full 64-bit integer/timestamp/string precision, branchless dual-bitmask Kleene 3VL, zero per-edge virtual/exception dispatch, parallel `max_dop` execution. |
| **Mock / Setup Opcodes** | 8 bytecode opcodes (`0x08`–`0x0C`, `0x1E`–`0x1F`, `0x73`–`0x74`) | **0 mock opcodes in ISA** (host-bound `.data` directives in `.impas` harness) | Production VM kernel carries zero mock-graph mutators or inline array parsers. |
| **Compliance Hashing** | `ICTX v1` (single hash; skipped `TYPE_VALUE_MAP` payloads) | **Dual `ICTX v2`**: Tier-Invariant `logical_hash` + Tier-Variant `physical_hash` | Enables metamorphic multi-profile tier/morsel/DOP testing across OCaml, C++, Rust, and Java 25. |

---

## 2. Directory Contents

| Document / Schema | Purpose |
| :--- | :--- |
| [README.md](README.md) | Executive summary, locked architectural decisions, and 100% v0.10.0 $\to$ v0.11.0 opcode migration crosswalk. |
| [VM_ARCHITECTURE_v0_11.md](VM_ARCHITECTURE_v0_11.md) | Normative specification of the 64-bit nibble instruction word, global flags, `3 × 16` banks, morsel aliasing (`MF0..MF7` / `M0..M7`), C-ABI state frame, sliding register windows, 3-tier `VmFrontier`, lazy cardinality memoization, Kleene 3VL algebra, lexical morsel execution, and static bytecode validation (`impulse_vm_validate`). |
| [OPCODE_CATALOG_v0_11.md](OPCODE_CATALOG_v0_11.md) | Exhaustive specification of all 78 v0.11.0 opcodes (+ `0xFF` extension word): exact bit encoding, allowed modifier flags, `subop:4` tables, operational semantics, `ImpAsm` usage examples, architectural justification, and edge-case gotchas. |
| [IMPAS_SPECIFICATION_v0_11.md](IMPAS_SPECIFICATION_v0_11.md) | Assembly language grammar (`ImpAsm` v0.11), register/morsel mnemonics, modifier suffixes (`.accum`, `.scalar`, `.mask`, `.ext`), host-bound `.data` topology/attribute/threshold directives, and test expectation headers. |
| [IMPSCM_SPECIFICATION_v0_11.md](IMPSCM_SPECIFICATION_v0_11.md) | Normative ISA-agnostic, storage-layout-agnostic `ImpScheme` (`.impscm`) v0.11 IR specification: concrete S-expression grammar, static per-domain type system, declarative stream/morsel forms, operator catalog, and E2E compiler parity contract. |
| [TESTING_AND_BENCHMARK_STRATEGY.md](TESTING_AND_BENCHMARK_STRATEGY.md) | Dual `ICTX v2` wire protocol, metamorphic geometry profile runner (`Forced-Tier0`, `Paged-Tier1`, `Dense-Tier2`, morsel/DOP sweeps), `(opcode × subop × flag × tier × 3VL)` coverage gates, and empirical JMH / Google Benchmark verification matrix. |
| [FORMAT_SPECIFICATION_v1_0_DELTA.md](FORMAT_SPECIFICATION_v1_0_DELTA.md) | Minimal `.imps` v0.9.0 → v1.0 binary format delta (`cscEdgePerm`, `SrcNodeIDWidth`, `UINT*`/`DECIMAL64`/`BOOL`, `VectorANN` index type, `M:1` & federated mount rules). |
| [V0_11_IMPLEMENTATION_ROADMAP.md](V0_11_IMPLEMENTATION_ROADMAP.md) | Execution milestones (M0–M5), quality exit gates, and concrete AI-assisted issue/PR tracking guide. |
| [DESIGN_NOTES_v0_11.md](DESIGN_NOTES_v0_11.md) | Architectural design notes covering live overlays, multi-anchor fluent DAGs, geospatial, Cypher/ImpK/ImpLog, temporal/timezone policy, `DECIMAL64`, JSON shredding, and Lucene `Codec` integration. |
| [EDA_CIRCUIT_ANALYSIS_NOTES.md](EDA_CIRCUIT_ANALYSIS_NOTES.md) | Digital circuit analysis (EDA) showcase notes: MCMM STA, 64-vector fault sim, CDC, DC IR drop, and AC phasor complex math. |
| [isa_v0_11.yaml](isa_v0_11.yaml) | Machine-readable single source of truth for word layout, flags, error codes, register banks, and all opcode/subop contracts (drives codegen for C++, Java 25, Rust, OCaml, and Python tooling). |

---

## 3. Locked Architectural Decisions Log

The following eight foundational architectural choices were resolved prior to drafting this specification:

1. **Three 16-Slot Register Banks (`R0..R15`, `F0..F15`, `V0..V15`) + Lexical Morsel Aliasing**:
   - `F0..F15` unifies 1-bit frontiers (`lane_width = 1`) and bit-sliced multi-lane frontiers (`lane_width` $\in \{8, 16, 32, 64\}$).
   - Inside `OP_WALK_MORSEL` / `OP_FILTER_MORSEL .. OP_MORSEL_END`, register indices `8..15` refer to thread-private L1 morsel masks (`MF0..MF7`) and morsel vectors (`M0..M7`: `M0=src_id`/`node_id`, `M1=tgt_id`, `M2=edge_idx`, `M3=lane_mask`), while `0..7` remain read-only outer domain state (`R0..R7`, `F0..F7`, `V0..V7`), except as verified commit targets in `OP_MORSEL_COMMIT`.
2. **Untagged 64-Bit Scalars + `uint16_t r_valid_mask`**:
   - `R0..R15` hold raw 64-bit values (`i64`, `u64`, IEEE-754 `f64`, or scalar `StringView` handle) paired with a single 16-bit nullability bitmask `r_valid_mask` (`1 = valid`, `0 = Kleene NULL`). Static load-time verification (`impulse_vm_validate`) tracks scalar representations across control-flow joins.
3. **Byte 1 `[flags:4 | subop:4]` Split & Strict 16-Subop Ceiling**:
   - High nibble of Byte 1 holds 4 universal modifier flags; low nibble holds `subop:4` (`0..15`). Vector math is partitioned into five cohesive opcodes (`OP_VEC_MATH_ARITH`, `OP_VEC_MATH_EXP_LOG`, `OP_VEC_MATH_TRIG_HYP`, `OP_VEC_MATH_ACT`, `OP_VEC_INT_BITWISE`), each with $\le 16$ subops.
4. **Universal Global Modifier Flags (`flags:4`)**:
   - `0x8` (`0x80` in Byte 1): `FLAG_EXTENDED` (128-bit instruction paired with `0xFF` `OP_EXTENSION_PAYLOAD` in Word 2).
   - `0x4` (`0x40` in Byte 1): `FLAG_ACCUM` (monoid/union accumulate into `dst` rather than overwrite).
   - `0x2` (`0x20` in Byte 1): `FLAG_SCALAR_RHS` (nibble `s2` addresses scalar `R[s2]` instead of `V[s2]`/`F[s2]`).
   - `0x1` (`0x10` in Byte 1): `FLAG_MASKED_S3` (nibble `s3` addresses exclude/active mask frontier `F[s3]` or morsel `MF[s3 & 7]`).
5. **Inline Lexical Multi-Sink Morsel Blocks**:
   - Replaces scalar edge shaders (`0xA0`–`0xBF`) and runtime CEL AST walkers (`0x13`). Supports forward-only skip jumps (`OP_JCC.jempty_f MF0, +offset`) and **1 or more `OP_MORSEL_COMMIT` sinks** per pass, verified race-free by `impulse_vm_validate` for `max_dop` worker parallelism.
6. **Showcase Algorithm De-Bloat & Deterministic Kernel Retention**:
   - Removes 15+ composite/stub showcase opcodes (`LOUVAIN`, `ISOMORPHISM`, `MOTIF_MATCH_3`, `REBAC_CHECK`, `ISLAND_DETECT`, `BRANDES_*`, `DELTA_STEP_RELAX`, `CC_HOOK_COMPRESS`, `SPARSE_MATVEC`, `ROARING_*`). Retains irreducible whole-graph linear kernels in `OP_GRAPH_KERNEL` (`CC_AFFOREST` with deterministic min-ID canonicalization, `KCORE`, `TRIANGLE_COUNT`) plus SplitMix64-deterministic `OP_SAMPLE_NEIGHBORS`.
7. **Complete Removal of Bytecode Mock Opcodes**:
   - Deletes `0x08`–`0x0C` (`OP_INIT_MOCK_*`, `OP_LOAD_INLINE_*`), `0x1E`–`0x1F`, and `0x73`–`0x74`. Test topologies and attributes are declared in `.data` directives parsed by the harness and bound to `VmQueryContext` via C-ABI prior to `pc = 0`. Real query literals (`IN [1, 2, 3]`) use zero-copy `OP_LOAD_CONST_POOL`.
8. **Dual `ICTX v2` Compliance & Metamorphic Geometry Verification**:
   - Every test execution emits both a tier-invariant `logical_hash` (canonicalized mathematical content) and a tier-variant `physical_hash` (including tier tags, lane widths, and slab geometry), allowing `.impas` compliance suites to re-run under overridden tier/morsel/DOP profiles alongside 100K–10M synthetic scale generators.

---

## 4. Complete v0.10.0 $\to$ v0.11.0 Opcode Migration Crosswalk (All 166 Opcodes)

Every opcode defined in v0.10.0 (`tools/contracts.json` and `impulse_vm.h`) is accounted for below with its exact v0.11.0 disposition.

### 4.1 System, Inputs, Constants & Mock Setup (`0x00`–`0x0C`)

| v0.10 Hex | v0.10 Mnemonic | Disposition | v0.11 Target / Replacement | Technical Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | `OP_HALT` | **Retained** | `0x00 OP_HALT` | Identical clean termination semantics. |
| `0x01` | `OP_NOP` | **Retained** | `0x01 OP_NOP` | Canonical alignment / patch nop; all fields MBZ. |
| `0x02` | `OP_INIT_INPUT_NODE` | **Consolidated** | `0x07 OP_LOAD_PARAM` (`subop=1` `PARAM_FRONTIER` or `subop=0` + `0x20 OP_FSEED`) | Unifies host parameter binding across scalars, seed nodes/sets, and embedding vectors; binds explicit `domain_id`. |
| `0x03` | `OP_INIT_INPUT_SET` | **Consolidated** | `0x07 OP_LOAD_PARAM` (`subop=1` `PARAM_FRONTIER`) | Directly binds host seed set into 3-tier `F[dst]` with explicit `domain_id`. |
| `0x04` | `OP_LOAD_CONST_INT` | **Consolidated** | `0x05 OP_LOAD_CONST` (`subop=0` `I32_SEXT`, `subop=1` `U32_ZEXT`, `subop=4` `B64` w/ `.ext`) | Single constant loader handles 32-bit inline and 64-bit extended constants plus explicit `NULL` (`subop=5`). |
| `0x05` | `OP_MAP_KEYS_TO_DENSE` | **Retained & Moved** | `0x55 OP_MAP_KEYS_TO_DENSE` | Moved to Pillar 4 Index/Key block; supports host param keys (`F[dst]`), key vectors (`V[dst]`), and single key (`R[dst]`). |
| `0x06` | `OP_LOAD_CONST_FLOAT` | **Consolidated** | `0x05 OP_LOAD_CONST` (`subop=2` `F32_TO_F64`, `subop=4` `B64` w/ `.ext`) | Unified into `OP_LOAD_CONST`; `f32` immediates fit in 1 word without `FLAG_EXTENDED`. |
| `0x07` | `OP_LOAD_CONST_STR_PREFIX` | **Replaced** | `0x06 OP_LOAD_CONST_POOL` (`subop=2` `STR_VIEW`) | Replaces lossy 8-byte prefix-only hack with full 16-byte `StringView` (`[len:32, prefix4:32, offset:64]`) backed by constant pool. |
| `0x08` | `OP_LOAD_INLINE_ARRAY` | **Split / Retired** | `0x06 OP_LOAD_CONST_POOL` (query literals) or `.data` `.node_attr` (test mocks) | Eliminates multi-word inline variable-length bytecode instructions that broke fixed-stride PC validation. |
| `0x09` | `OP_INIT_MOCK_GRAPH` | **Removed (Harness)** | `.data` `.csr_inline` / `.csc_inline` | Mock topology construction belongs in the test harness prior to `pc = 0`, never inside the production VM loop. |
| `0x0A` | `OP_LOAD_INLINE_SET` | **Split / Retired** | `0x06 OP_LOAD_CONST_POOL` (`subop=1`) or `0x20 OP_FSEED` | Eliminates variable-length inline set payloads from the instruction stream. |
| `0x0B` | `OP_INIT_MOCK_NODE_ATTR` | **Removed (Harness)** | `.data` `.node_attr` | Moved to host-bound test harness `.data` section. |
| `0x0C` | `OP_INIT_MOCK_EDGE_ATTR` | **Removed (Harness)** | `.data` `.edge_attr` | Moved to host-bound test harness `.data` section (also fixes v0.10 §6.9 spec collision where `0x0C` was listed as Reserved). |

### 4.2 Core Traversal, Topology & Scratch Index Ops (`0x0E`–`0x1F`)

| v0.10 Hex | v0.10 Mnemonic | Disposition | v0.11 Target / Replacement | Technical Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `0x0E` | `OP_CSR_WALK_2HOP` | **Retired (Composed)** | `2× 0x30 OP_WALK` (Tier 0 512B L1 inline intermediate + `.mask F0`) | Obsoleted by v0.11's 3-tier `VmFrontier` (`TIER0_INLINE` stays in L1; dense 2-hop needed an intermediate dedup frontier anyway); removes hidden intermediate `D_1` scratch from `impulse_vm_plan_memory`. |
| `0x0F` | `OP_CSR_WALK_STATE` | **Consolidated** | `0x34 OP_SPMV` (`subop=10` `FWD_FIRST_TOUCH_SRC`) | Replaces race-prone parent-pointer walk with deterministic min-`src_id` tie-broken `OP_SPMV` semiring step. |
| `0x10` | `OP_CSR_WALK` | **Consolidated** | `0x30 OP_WALK` (`subop=0` `FWD`) | Physical storage (CSR/CSC/COO/Dense) and push/pull direction switching are internal to `OP_WALK`; fixes $O(N/64)$ empty-output `ZF` scan bug. |
| `0x11` | `OP_CSR_WALK_FILTERED` | **Generalized** | `0x31 OP_WALK_FILTERED` | Supports all 6 comparators (`EQ..GE`) + `IS_NULL`/`IS_NOT_NULL` in both `FWD` and `REV` directions inside a single 64-bit word. |
| `0x12` | `OP_CSR_DEGREE` | **Generalized** | `0x33 OP_DEGREE` | Supports frontier out/in-degree sum (`R[dst]`), per-node degree vector (`V[dst]`), and single-node degree (`R[dst]`). |
| `0x13` | `OP_CSR_WALK_PREDICATE` | **Retired** | `0x31 OP_WALK_FILTERED` or `0x35 OP_WALK_MORSEL` | Deletes the runtime recursive CEL AST pointer-chasing evaluator (`impulse_cel_eval_edge`) from the VM kernel. |
| `0x14` | `OP_NODE_FILTER` | **Generalized & Fixed** | `0x44 OP_NODE_FILTER` | Fixes v0.10 float fallthrough bug; supports all numeric/dict column types, all 6 comparators, `BETWEEN`, and null predicates with strict Kleene 3VL. |
| `0x15` | `OP_NODE_FILTER_STR_PREFIX` | **Replaced** | `0x40 OP_LOAD_COLUMN` + `0x47 OP_VEC_STR_PRED` + `0x26 OP_SET_CONVERT` (or `OP_FILTER_MORSEL`) | Replaces 8-byte prefix-only filter with exact `StringView` (`len` + `prefix4` + tail `memcmp`) predicates (`EQ`, `STARTS_WITH`, `ENDS_WITH`, `CONTAINS`). |
| `0x16` | `OP_CSR_WALK_REDUCE_SUM` | **Consolidated** | `0x34 OP_SPMV` (`subop=0` `.fwd_plus_times.scalar` w/ `R=1.0`) | Strict special case of `OP_SPMV` with scalar identity RHS. |
| `0x17` | `OP_CSR_WALK_REDUCE` | **Consolidated** | `0x34 OP_SPMV` (`subop=0,2,4` + `.scalar`) | Unified into `OP_SPMV` semiring monoids (`R=1.0` for sum, `R=0.0` for min/max). |
| `0x18` | `OP_CSC_WALK` | **Consolidated** | `0x30 OP_WALK` (`subop=1` `REV`) | Reverse traversal is `subop=1` on `OP_WALK`; uses CSC or falls back to CSR/COO transparently. |
| `0x19` | `OP_HAS_CSR` | **Consolidated** | `0x3A OP_HAS_TOPOLOGY` (`subop=0`) | Folded into unified snapshot introspection opcode. |
| `0x1A` | `OP_HAS_CSC` | **Consolidated** | `0x3A OP_HAS_TOPOLOGY` (`subop=1`) | Folded into `OP_HAS_TOPOLOGY`. |
| `0x1B` | `OP_HAS_COO` | **Consolidated** | `0x3A OP_HAS_TOPOLOGY` (`subop=2`) | Folded into `OP_HAS_TOPOLOGY`. |
| `0x1C` | `OP_HAS_KEY_CATALOG` | **Consolidated** | `0x3A OP_HAS_TOPOLOGY` (`subop=4`) | Folded into `OP_HAS_TOPOLOGY`. |
| `0x1D` | `OP_ADAPTIVE_WALK` | **Consolidated** | `0x30 OP_WALK` | `OP_WALK` natively performs exact degree-volume Beamer push/pull selection with fused `\ F_exclude` pre-check; also resolves `0x1D` spec collision. |
| `0x1E` | `OP_CREATE_SCRATCH_INDEX` | **Removed** | `.imps` Snapshot Index (`0x54 OP_INDEX_SCAN`) | Violated read-only zero-allocation query model (`AGENTS.md` §3.4); indexes are built into immutable `.imps` snapshots. |
| `0x1F` | `OP_DROP_SCRATCH_INDEX` | **Removed** | None (Read-Only `.imps` Indexes) | Paired with removal of `OP_CREATE_SCRATCH_INDEX`. |

### 4.3 Vector Predicates, Masks, Math, Set Algebra & State Ops (`0x20`–`0x3D`)

| v0.10 Hex | v0.10 Mnemonic | Disposition | v0.11 Target / Replacement | Technical Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `0x20` | `OP_VEC_CMP_EQ` | **Consolidated** | `0x45 OP_VEC_CMP` (`subop=0` `EQ`) | Unifies all 6 comparators (`EQ`, `NE`, `LT`, `LE`, `GT`, `GE`) + `BETWEEN` in 1 single-word opcode with dual-bitmask Kleene 3VL; resolves `0x20` spec collision. |
| `0x21` | `OP_VEC_CMP_GT` | **Consolidated** | `0x45 OP_VEC_CMP` (`subop=4` `GT`) | Unified into `OP_VEC_CMP`. |
| `0x22` | `OP_VEC_CMP_LT` | **Consolidated** | `0x45 OP_VEC_CMP` (`subop=2` `LT`) | Unified into `OP_VEC_CMP`. |
| `0x23` | `OP_VEC_CMP_BETWEEN` | **Consolidated** | `0x45 OP_VEC_CMP` (`subop=6` `BETWEEN_INCL`) | Fits in a single 64-bit word (`dst, s1=val, s2=lo, s3=hi`) without `FLAG_EXTENDED`. |
| `0x24` | `OP_MASK_AND` | **Split (Typed)** | `0x46 OP_VEC_3VL_OP` (`subop=0` `AND`) / `0x22 OP_SET_OP` (`subop=1` `INTERSECT`) | Separates Kleene 3VL boolean logic (`FALSE && NULL == FALSE`) from 2-valued frontier set intersection. |
| `0x25` | `OP_MASK_OR` | **Split (Typed)** | `0x46 OP_VEC_3VL_OP` (`subop=1` `OR`) / `0x22 OP_SET_OP` (`subop=0` `UNION`) | Separates Kleene 3VL boolean logic (`TRUE \|\| NULL == TRUE`) from 2-valued frontier set union. |
| `0x26` | `OP_MASK_NOT` | **Split & Fixed** | `0x46 OP_VEC_3VL_OP` (`subop=2` `NOT`) / `0x23 OP_SET_COMPLEMENT` | Fixes critical v0.10 Kleene 3VL bug where `MASK_NOT` inverted `NULL` (`0`) into `TRUE` (`1`). |
| `0x27` | `OP_VEC_BLEND` | **Retained & Moved** | `0x4E OP_VEC_BLEND` | Fits `(dst, cond=s1, t=s2, f=s3)` in a single 64-bit word; adds explicit Kleene-propagating vs SQL `CASE WHEN` subops. |
| `0x2A` | `OP_ASSERT_FINITE` | **Consolidated** | `0x46 OP_VEC_3VL_OP` (`subop=11` `ASSERT_FINITE`) | Folded into vector validity/IEEE-754 predicate opcode. |
| `0x2D` | `OP_VEC_MATH_UNARY` | **Split (4-Way $\le 16$)** | `0x48 OP_VEC_MATH_ARITH`, `0x49 OP_VEC_MATH_EXP_LOG`, `0x4A OP_VEC_MATH_TRIG_HYP`, `0x4B OP_VEC_MATH_ACT`, `0x4C OP_VEC_INT_BITWISE` | Breaks 42-case mega-switch into $\le 16$-subop JIT-inlinable opcodes; moves bitwise ops (`POPCOUNT`/`CLZ`/`CTZ`) onto native `i64`/`u64` without lossy float casts. |
| `0x2E` | `OP_VEC_MATH_BINARY` | **Split (Cohesive)** | `0x48 OP_VEC_MATH_ARITH`, `0x49` (`POW`), `0x4A` (`ATAN2`, `HYPOT`), `0x4B` (`LEAKY_RELU`), `0x4C` (`SHL..ROTR`) | Eliminates duplicate encodings with `EWISE_ADD`/`VECTOR_DIV` and fits in 1 64-bit word (`FLAG_SCALAR_RHS` handles vector-scalar). |
| `0x2F` | `OP_VEC_MATH_TERNARY` | **Retained & Moved** | `0x4D OP_VEC_TERNARY` | Fits 4 register nibbles `(dst, s1, s2, s3)` in **1 64-bit word** (no longer requires 128-bit `FLAG_EXTENDED`). |
| `0x30` | `OP_SET_UNION` | **Consolidated** | `0x22 OP_SET_OP` (`subop=0` `UNION`) | Polymorphic across Tier 0/1/2 and multi-lane frontiers; enforces `domain_id` equality. |
| `0x31` | `OP_SET_INTERSECT` | **Consolidated** | `0x22 OP_SET_OP` (`subop=1` `INTERSECT`) | Unified into `OP_SET_OP`. |
| `0x32` | `OP_SET_DIFFERENCE` | **Consolidated** | `0x22 OP_SET_OP` (`subop=2` `DIFF`) | Unified into `OP_SET_OP` (also absorbs `0x8A OP_FRONTIER_DIFF` and `0x6C OP_ROARING_BITMAP_AND_NOT`). |
| `0x33` | `OP_SET_CARDINALITY` | **Enhanced** | `0x24 OP_SET_CARDINALITY` | Uses $O(1)$ `cached_card` memoization or SIMD `vpopcntq` over dirty slabs; adds multi-lane cardinality subops (`1..4`). |
| `0x34` | `OP_VECTOR_MUL_ATTR` | **Replaced** | `0x40 OP_LOAD_COLUMN` + `0x48 OP_VEC_MATH_ARITH` (`MUL`) | `LOAD_COLUMN` is a 0-copy pointer bind, making a fused attribute-multiply opcode redundant. |
| `0x35` | `OP_VECTOR_REDUCE_SUM` | **Consolidated** | `0x52 OP_VEC_REDUCE` (`subop=0` `SUM`) | Eliminates duplicate with `0x45 OP_REDUCE`; adds deterministic 64-wide tree-sum across OpenMP threads. |
| `0x36` | `OP_VECTOR_DIV` | **Consolidated** | `0x48 OP_VEC_MATH_ARITH` (`subop=3` `DIV`) / `0x4D OP_VEC_TERNARY` (`SAFE_DIV`) | Eliminates duplicate vector division opcode. |
| `0x37` | `OP_VECTOR_STR_CONCAT` | **Retired** | Host / Post-`COLLECT` formatting | Eliminates variable-length string heap allocation inside the read-only SIMD VM kernel. |
| `0x38` | `OP_FLOAT_VECTOR_SCALE` | **Consolidated** | `0x48 OP_VEC_MATH_ARITH` (`subop=2` `MUL` + `FLAG_SCALAR_RHS`) | Orthogonal scalar-RHS modifier replaces dedicated float-scale opcode. |
| `0x39` | `OP_L1_NORM_DIFF` | **Consolidated** | `0x27 OP_STABLE_CHECK` (`subop=1` `VEC_L1_CONV`) | Directly computes $\lVert V[s1] - V[s2] \rVert_1 \le \epsilon$, writing norm to `R[dst]` and setting `ST`. |
| `0x3A` | `OP_PROJECT_STATE` | **Replaced** | `0x48`–`0x4F` Vector Ops / `0x36 OP_FILTER_MORSEL` | Resolves §6.9 spec collision (`0x3A` listed as Reserved) and replaces opaque state-handle packing (`TYPE_FRONTIER_STATE`) with explicit `F` + `V` registers. |
| `0x3B` | `OP_COALESCE` | **Retained & Moved** | `0x4F OP_COALESCE` | Supports both `COALESCE(V, V)` and `COALESCE(V, R)` (`FLAG_SCALAR_RHS`) in 1 word. |
| `0x3C` | `OP_EXTRACT_VALIDITY` | **Consolidated** | `0x46 OP_VEC_3VL_OP` (`subop=5` `IS_NOT_NULL`) + `0x26 OP_SET_CONVERT` | Unified into Kleene 3VL null-inspection subops. |
| `0x3D` | `OP_VECTOR_TIME_VALID_AT` | **Consolidated** | `0x4D OP_VEC_TERNARY` (`subop=4` `TIME_VALID_AT`) | Clean 3-operand temporal interval check `valid_from <= ts && (isnull(valid_to) \|\| ts < valid_to)`. |

### 4.4 GraphBLAS, Control Flow & Extended Showcase Ops (`0x40`–`0x75`)

| v0.10 Hex | v0.10 Mnemonic | Disposition | v0.11 Target / Replacement | Technical Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `0x40` | `OP_CC_AFFOREST` | **Consolidated & Fixed** | `0x3B OP_GRAPH_KERNEL` (`subop=0` `CC_AFFOREST`) | Adds mandatory min-node-ID component canonicalization pass for 100% deterministic multi-threaded component labels. |
| `0x41` | `OP_MXV` | **Consolidated** | `0x34 OP_SPMV` (`FWD_*` subops) | Unifies `MXV`, `VXM`, `SPARSE_MATVEC`, and `WALK_REDUCE` into one orthogonal semiring opcode. |
| `0x42` | `OP_VXM` | **Consolidated** | `0x34 OP_SPMV` (`REV_*` / `FWD_*` transpose convention) | Unified into `OP_SPMV` (`FWD` propagates $Src \to Tgt$; `REV` propagates $Tgt \to Src$). |
| `0x43` | `OP_EWISE_ADD` | **Consolidated** | `0x48 OP_VEC_MATH_ARITH` (`subop=0` `ADD`) | Eliminates duplicate elementwise addition opcode. |
| `0x44` | `OP_EWISE_MULT` | **Consolidated** | `0x48 OP_VEC_MATH_ARITH` (`subop=2` `MUL`) | Eliminates duplicate elementwise multiplication opcode. |
| `0x45` | `OP_REDUCE` | **Consolidated** | `0x52 OP_VEC_REDUCE` | Unifies `SUM`, `MIN`, `MAX`, `COUNT_VALID`, `MEAN`, `L1_NORM`, `L2_NORM_SQ`, `ARGMIN`, `ARGMAX`, `ANY_TRUE`, `ALL_TRUE`. |
| `0x46` | `OP_CC_HOOK_COMPRESS` | **Retired** | `0x3B OP_GRAPH_KERNEL` (`CC_AFFOREST`) | Internal sub-step of Connected Components; exposing raw hook/compress risked non-deterministic union-find parent trees. |
| `0x47` | `OP_TC_SWEEP_BATCH` | **Consolidated** | `0x3B OP_GRAPH_KERNEL` (`subop=3,4` `TRIANGLE_COUNT_*`) | Unified into deterministic whole-graph / per-node DODG wedge-intersection triangle counter. |
| `0x48` | `OP_BRANDES_FORWARD` | **Retired (Macro)** | `ImpK` / `ImpScheme` subroutine (`OP_SPMV` + `OP_CALL`) | Composite multi-source algorithm belongs in compiler standard library, not hardcoded microcode. |
| `0x49` | `OP_BRANDES_BACKWARD` | **Retired (Macro)** | `ImpK` / `ImpScheme` subroutine | Paired with `OP_BRANDES_FORWARD`. |
| `0x4A` | `OP_DELTA_STEP_RELAX` | **Retired (Macro)** | `OP_SPMV` (`MIN_PLUS` + `FLAG_ACCUM`) / `OP_WALK_MORSEL` | Bucketed delta-stepping expresses directly as `NODE_FILTER` bucket selection + `SPMV.MIN_PLUS`. |
| `0x4B` | `OP_READ_EDGE_WEIGHT` | **Consolidated** | `0x40 OP_LOAD_COLUMN` (`subop=1`) / `0x42 OP_GATHER_EDGE_ATTR` | Redundant specialized wrapper over edge column loading/gathering. |
| `0x50` | `OP_JMP` | **Retained & Moved** | `0x0F OP_JMP` | PC-relative signed 32-bit word offset (`pc += imm32_s`), statically bounds-checked at load time. |
| `0x51` | `OP_JZ` | **Consolidated** | `0x10 OP_JCC` (`subop=0` `JZ`) | Unified into 10-condition `OP_JCC` (`JZ`, `JNZ`, `JST`, `JNST`, `JNULL`, `JNNULL`, `JTRUE_R`, `JFALSE_OR_NULL_R`, `JEMPTY_F`, `JNONEMPTY_F`). |
| `0x52` | `OP_JNZ` | **Consolidated** | `0x10 OP_JCC` (`subop=1` `JNZ`) | Unified into `OP_JCC`. |
| `0x53` | `OP_LOOP_DECR` | **Retained & Moved** | `0x11 OP_LOOP_DECR` | Decrements `R[dst]` and branches if `> 0`. |
| `0x54` | `OP_STABLE_CHECK` | **Retained & Moved** | `0x27 OP_STABLE_CHECK` | Supports both exact frontier bit-equality (`subop=0`) and $L_1$-norm vector tolerance (`subop=1`). |
| `0x55` | `OP_CALL` | **Redesigned** | `0x12 OP_CALL` | Fixes v0.10 caller-clobber bug via variable-stride sliding windows (`s1=r_stride`, `s2=f_stride`, `s3=v_stride`). |
| `0x56` | `OP_RET` | **Redesigned** | `0x13 OP_RET` | Restores caller window bases and deterministically releases callee `F`/`V` pool allocations (RAII). |
| `0x57` | `OP_ENTER_FRAME` | **Consolidated** | `0x12 OP_CALL` + `0x0A OP_SPILL` | Window shifting is fused into `OP_CALL`, saving 2 instructions per subroutine invocation. |
| `0x58` | `OP_LEAVE_FRAME` | **Consolidated** | `0x13 OP_RET` + `0x0B OP_RELOAD` | Window restoration and RAII cleanup are fused into `OP_RET`. |
| `0x5A` | `OP_THROW` | **Retained & Moved** | `0x03 OP_THROW` | Raises `IMPULSE_VM_ERR_USER_THROW` with user error code in `imm32`. |
| `0x5B` | `OP_ASSERT` | **Retained & Moved** | `0x04 OP_ASSERT` | Supports scalar, frontier non-empty, `ZF`, `ST`, and `NOT_NULL` assertions. |
| `0x5C` | `OP_TRAP` | **Retained & Moved** | `0x02 OP_TRAP` | Host/debugger trap (`IMPULSE_VM_ERR_TRAP`). |
| `0x60` | `OP_SAMPLE_NEIGHBORS` | **Retained & Specified** | `0x39 OP_SAMPLE_NEIGHBORS` (`subop=0,1`) | Mandates stateless SplitMix64 + Lemire bounded multiplication for 4-way bit-identical multi-threaded output. |
| `0x61` | `OP_RANDOM_WALK` | **Consolidated** | `0x39 OP_SAMPLE_NEIGHBORS` (`subop=2` `RANDOM_WALK_STEP`) | Single-step SplitMix64 walk transition chained via `OP_LOOP_DECR` or `ImpK` loop. |
| `0x62` | `OP_SCATTER_GATHER` | **Consolidated** | `0x43 OP_GATHER_VEC` + `0x37 OP_MORSEL_COMMIT` (`SCATTER_*`) | Decomposed into clean race-free vector gather and morsel scatter-reduce primitives. |
| `0x63` | `OP_REBAC_CHECK` | **Retired (DSL)** | `ImpLog` Datalog rule $\to$ `OP_WALK` (`FWD_FIXPOINT_STAR`) + `OP_SET_CONTAINS` | ReBAC (`impulse-authz`) compiles cleanly to primitive Kleisli walks without bespoke VM opcodes. |
| `0x64` | `OP_ROARING_BITMAP_AND` | **Consolidated** | `0x22 OP_SET_OP` (`subop=1` `INTERSECT`) | Physical sparse/paged tiering (Tier 1 4K slabs) is transparent inside `VmFrontier`. |
| `0x65` | `OP_ISLAND_DETECT` | **Retired (DSL)** | `OP_WALK_FILTERED` (breaker status) + `OP_GRAPH_KERNEL` (`CC_AFFOREST`) | Showcase `impulse-powergrid` algorithm expresses directly over filtered topology + Afforest CC. |
| `0x66` | `OP_SPARSE_MATVEC` | **Consolidated** | `0x34 OP_SPMV` | Duplicate of `OP_MXV` (`0x41`); eliminated. |
| `0x67` | `OP_LOUVAIN_MODULARITY` | **Retired (Library)** | `ImpK` macro / host analytics library | Multi-level graph coarsening mutates topology across phases, violating read-only single-instruction VM bounds. |
| `0x68` | `OP_KCORE_DECOMPOSITION` | **Consolidated** | `0x3B OP_GRAPH_KERNEL` (`subop=1,2` `KCORE*`) | Retained as an irreducible linear-time peeling kernel under `OP_GRAPH_KERNEL`. |
| `0x69` | `OP_MOTIF_MATCH_3` | **Retired (Macro)** | `0x3B OP_GRAPH_KERNEL` (`TRIANGLE_COUNT`) / `OP_WALK_MORSEL` | General motif enumeration belongs in compiler plans over morsel joins. |
| `0x6A` | `OP_GRAPH_ISOMORPHISM` | **Retired (NP-Hard)** | Host solver / `ImpLog` candidate pruning | Backtracking search with unbounded state trees does not belong in a single SIMD bytecode opcode. |
| `0x6B` | `OP_ROARING_BITMAP_OR` | **Consolidated** | `0x22 OP_SET_OP` (`subop=0` `UNION`) | Absorbed into 3-tier polymorphic `OP_SET_OP`. |
| `0x6C` | `OP_ROARING_BITMAP_AND_NOT` | **Consolidated** | `0x22 OP_SET_OP` (`subop=2` `DIFF`) | Absorbed into 3-tier polymorphic `OP_SET_OP`. |
| `0x70` | `OP_MOV` | **Retained & Moved** | `0x08 OP_MOV` (`subop=0..2`) | Explicit bank-typed copy/COW-alias (`MOV_R`, `MOV_F`, `MOV_V`). |
| `0x71` | `OP_CLEAR_REG` | **Consolidated** | `0x08 OP_MOV` (`subop=3..5` `CLEAR_R`, `CLEAR_F`, `CLEAR_V`) | Deterministically returns `F`/`V` backing slabs to the context pool early when desired. |
| `0x72` | `OP_LOAD_INDIRECT` | **Replaced** | `0x43 OP_GATHER_VEC` / `0x51 OP_VEC_POINT` (`VEC_GET`) | Replaces untyped register-indirect addressing (which defeated static register analysis) with typed vector indexing. |
| `0x73` | `OP_ALLOC_SCRATCH` | **Removed** | Automatic `VmContextPool` slab/arena leasing + `0x50 OP_VEC_INIT` | Bytecode never manages raw byte pointers. |
| `0x74` | `OP_ASSERT_SCRATCH_BYTES` | **Removed (Harness)** | C-ABI `impulse_vm_context_stats_v11_t` inspection in test harness | Arena watermarks are verified via C-ABI telemetry rather than dedicated VM opcodes. |
| `0x75` | `OP_SET_MAX_DOP` | **Retained & Moved** | `0x14 OP_SET_MAX_DOP` | Controls worker parallelism (`1..host_threads`) with guaranteed bit-identical determinism. |

### 4.5 Columnar Gathers, Multi-Layout Walk Variants & Terminal Collects (`0x80`–`0x95`)

| v0.10 Hex | v0.10 Mnemonic | Disposition | v0.11 Target / Replacement | Technical Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `0x80` | `OP_LOAD_COLUMN_VECTOR` | **Retained & Moved** | `0x40 OP_LOAD_COLUMN` | Zero-copy binds node (`subop=0`) or edge (`subop=1`) `.imps` columns + validity bitmasks into `V[dst]`. |
| `0x81` | `OP_GATHER_NODE_ATTR` | **Retained & Moved** | `0x41 OP_GATHER_NODE_ATTR` | Indexed gather into `V[dst]` (and morsel `M4..M7` over `M0`/`M1`) with `FLAG_MASKED_S3` support. |
| `0x82` | `OP_GATHER_EDGE_ATTR` | **Retained & Moved** | `0x42 OP_GATHER_EDGE_ATTR` | Indexed edge attribute gather (primary attribute loader over `M2 = edge_idx` inside `OP_WALK_MORSEL`). |
| `0x83` | `OP_BRIN_ZONE_SKIP` | **Internalized** | Automatic inside `0x44 OP_NODE_FILTER` & `0x31 OP_WALK_FILTERED` | Physical zone-map skipping is an automatic storage-engine optimization when `.imps` block min/max metadata exists. |
| `0x84` | `OP_CSR_WALK_DIRECT_STORE` | **Internalized** | `0x30 OP_WALK` (Tier 0 inline fast path) | Single-source / tiny-degree direct store is handled automatically by `VmFrontier` Tier 0 (`<= 64` inline IDs). |
| `0x85` | `OP_CSR_WALK_DENSE_STREAM` | **Internalized** | `0x30 OP_WALK` (Tier 2 dense fast path) | Automatic inside `OP_WALK` when `F[s1]` or pre-sized `F[dst]` is Tier 2. |
| `0x86` | `OP_COO_WALK` | **Consolidated** | `0x30 OP_WALK` | Physical COO layout dispatch is internal to `OP_WALK`. |
| `0x87` | `OP_CSC_WALK_DIRECT_STORE` | **Internalized** | `0x30 OP_WALK` (`subop=1` `REV`, Tier 0 fast path) | Automatic inside `OP_WALK`. |
| `0x88` | `OP_FIXPOINT_KLEENE_STAR` | **Consolidated** | `0x30 OP_WALK` (`subop=3..6` `*_FIXPOINT_PLUS` / `*_FIXPOINT_STAR`) | Folded directly into `OP_WALK` (and `OP_LANE_WALK`) subops with fused `\ F_exclude` delta frontier tracking. |
| `0x89` | `OP_SWAP_REG` | **Retained & Moved** | `0x09 OP_SWAP` (`SWAP_R`, `SWAP_F`, `SWAP_V`) | Bank-typed $O(1)$ descriptor swap. |
| `0x8A` | `OP_FRONTIER_DIFF` | **Consolidated** | `0x22 OP_SET_OP` (`subop=2` `DIFF`) | Duplicate of `OP_SET_DIFFERENCE` (`0x32`); eliminated. |
| `0x8B` | `OP_COO_WALK_FILTERED` | **Consolidated** | `0x31 OP_WALK_FILTERED` | Physical COO layout dispatch is internal to `OP_WALK_FILTERED`. |
| `0x8C` | `OP_COO_WALK_REDUCE` | **Consolidated** | `0x34 OP_SPMV` | Physical COO layout dispatch is internal to `OP_SPMV`. |
| `0x8D` | `OP_COO_WALK_DIRECT_STORE` | **Internalized** | `0x30 OP_WALK` | Automatic inside `OP_WALK`. |
| `0x8E` | `OP_DENSE_WALK` | **Consolidated** | `0x30 OP_WALK` | Physical Dense layout dispatch is internal to `OP_WALK`. |
| `0x8F` | `OP_DENSE_WALK_BITMATRIX` | **Consolidated** | `0x30 OP_WALK` | Physical BitMatrix `vpopcntq` intersection is internal to `OP_WALK`. |
| `0x90` | `OP_COLLECT_BITSET` | **Consolidated** | `0x57 OP_COLLECT` (`subop=0` `COLLECT_FRONTIER_BITSET`) | Unified into terminal `OP_COLLECT`. |
| `0x91` | `OP_COLLECT_ARRAY` | **Consolidated** | `0x57 OP_COLLECT` (`subop=1` `COLLECT_FRONTIER_IDS`, `subop=2` `COLLECT_VEC`) | Unified into terminal `OP_COLLECT`. |
| `0x92` | `OP_MAP_DENSE_TO_KEYS` | **Retained & Moved** | `0x56 OP_MAP_DENSE_TO_KEYS` | Translates dense domain IDs back to external Key Catalog strings / `u64` keys. |
| `0x93` | `OP_COLLECT_VALUE_MAP` | **Replaced** | `0x57 OP_COLLECT` (`subop=2` `COLLECT_VEC` w/ `FLAG_MASKED_S3` or `subop=4` `COLLECT_TABLE_COLUMN`) | Eliminates heap-allocated hash maps (`TYPE_VALUE_MAP`) and `ICTX v1` unhashed-payload blind spots in favor of zero-copy Arrow columns. |
| `0x94` | `OP_DENSE_WALK_REDUCE` | **Consolidated** | `0x34 OP_SPMV` | Internal physical dispatch of `OP_SPMV`. |
| `0x95` | `OP_DENSE_WALK_DIRECT_STORE` | **Internalized** | `0x30 OP_WALK` | Internal physical dispatch of `OP_WALK`. |

### 4.6 Scalar Edge-Stream Shader Sub-ISA (`0xA0`–`0xBF`) — Complete Retirement

All **32** scalar `float32` edge-stream shader opcodes are **retired** and replaced by lexical morsel vectorization (`0x35 OP_WALK_MORSEL .. 0x38 OP_MORSEL_END`) executing standard Pillar 4 vector instructions over L1-resident `M0..M7` / `MF0..MF7` morsel slices:

| v0.10 Hex Range | v0.10 Mnemonics | v0.11 Replacement | Bug / Bottleneck Eliminated |
| :--- | :--- | :--- | :--- |
| `0xA0`, `0xA9`, `0xAA` | `OP_COO_WALK_STREAM`, `OP_CSR_WALK_STREAM`, `OP_CSC_WALK_STREAM` | `0x35 OP_WALK_MORSEL` (`subop=0` `FWD`, `subop=1` `REV`) | Fixes `shader_pc` stored in `inst.flags` colliding with `0x80` (`FLAG_EXTENDED`) whenever `shader_pc >= 128`. |
| `0xA1`, `0xA2` | `OP_STREAM_FUNC_BEGIN`, `OP_STREAM_FUNC_END` | Inline lexical `OP_WALK_MORSEL .. 0x38 OP_MORSEL_END` | Eliminates per-edge `MethodHandle.invokeExact` / callback overhead and per-rejected-edge `ShaderAbortException` throw/catch in Java. |
| `0xA3`, `0xA4`, `0xAB` | `OP_STREAM_LOAD_SRC`, `OP_STREAM_LOAD_EDGE`, `OP_STREAM_LOAD_TGT` | `0x41 OP_GATHER_NODE_ATTR` (over `M0`/`M1`), `0x42 OP_GATHER_EDGE_ATTR` (over `M2`) | Preserves full `i64`/`u64`/`f64`/`StringView` types and Arrow nullability bitmasks instead of coercing attributes to `float32`. |
| `0xBA`, `0xBB`, `0xBC` | `OP_STREAM_LOAD_SRC_ID`, `OP_STREAM_LOAD_TGT_ID`, `OP_STREAM_LOAD_EDGE_ID` | Pre-bound `M0` (`src_id`), `M1` (`tgt_id`), `M2` (`edge_idx`) (`u32`/`u64`) | Fixes catastrophic `float32` precision corruption on node/edge IDs $> 2^{24}$ (`16,777,216`). |
| `0xBD` | `OP_STREAM_LOAD_CONST` | Outer `0x05 OP_LOAD_CONST` + `FLAG_SCALAR_RHS` inside morsel | Constants hoist outside the morsel loop into `R0..R7` at zero per-morsel cost. |
| `0xA5`–`0xA6`, `0xAC`–`0xAF` | `OP_STREAM_MATH_ADD`, `OP_STREAM_MATH_DIV`, `OP_STREAM_MATH_SUB`, `OP_STREAM_MATH_MUL`, `OP_STREAM_MATH_MOD`, `OP_STREAM_MATH_UNARY` | Standard `0x48`–`0x4C` `OP_VEC_MATH_*` on `M0..M7` | Eliminates duplicate scalar shader ALU; unlocks all 54 math/bitwise ops inside edge predicates with SIMD vectorization. |
| `0xB0`–`0xB6` | `OP_STREAM_CMP_EQ`, `OP_STREAM_CMP_NEQ`, `OP_STREAM_CMP_GT`, `OP_STREAM_CMP_LT`, `OP_STREAM_LOGIC_AND`, `OP_STREAM_LOGIC_OR`, `OP_STREAM_LOGIC_NOT` | `0x45 OP_VEC_CMP` + `0x46 OP_VEC_3VL_OP` on `M0..M7` | Fixes Kleene 3VL bug (`NaN != 5` returning `true` via `!(NaN == 5)` in `ShaderOps.java`); adds missing `LE`/`GE`/`BETWEEN`/string ops. |
| `0xB7` | `OP_STREAM_SELECT` | `0x4E OP_VEC_BLEND` on `M0..M7` | Fixes C++/OCaml vs Java `falseReg` bit-unpacking bug (`inst.flags` vs `payload >> 24`) in a single 4-nibble word. |
| `0xA7` | `OP_STREAM_FILTER` | `0x26 OP_SET_CONVERT` (`BOOL3VL_VEC_TO_FRONTIER` $\to$ `MF0`) + optional `0x10 OP_JCC.jempty_f MF0, +skip` | Branchless bitmask narrowing across 64 lanes per word, with fast $O(1)$ skip when an entire morsel fails an early filter. |
| `0xA8`, `0xB8`, `0xB9`, `0xBE`, `0xBF` | `OP_STREAM_REDUCE`, `OP_STREAM_REDUCE_ARGMIN`, `OP_STREAM_REDUCE_ARGMAX`, `OP_STREAM_YIELD`, `OP_STREAM_SCATTER_REDUCE` | `0x37 OP_MORSEL_COMMIT` (`YIELD_FRONTIER`, `SCATTER_ADD/MIN/MAX/ARGMIN/ARGMAX`, `COUNT_ADD_R`) | Supports **1+ commit sinks** in a single CSR pass with deterministic 64-bit `(key32 << 32) \| tie_break_u32` `ARGMIN`/`ARGMAX`. |

### 4.7 Multi-Lane Bit-Sliced & Vector ANN Ops (`0xC0`–`0xCB`, `0xFF`)

| v0.10 Hex | v0.10 Mnemonic | Disposition | v0.11 Target / Replacement | Technical Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `0xC0` | `OP_LANE_INIT_SEEDS` | **Retained & Moved** | `0x60 OP_LANE_INIT_SEEDS` | Allocates in Tier 1 4K-node paged `VmFrontier` slabs instead of eager `800 MB` dense `long[N]` arrays. |
| `0xC1` | `OP_LANE_INIT_GROUPS` | **Retained & Moved** | `0x61 OP_LANE_INIT_GROUPS` | Writes into unified `F[dst]` bank with Tier 1 paged multi-lane slabs. |
| `0xC2` | `OP_LANE_SET_EDGE_MASK` | **Retired (Redundant)** | `0x40 OP_LOAD_COLUMN.edge_attr` / `0x08 OP_MOV.v` / `0x50 OP_VEC_INIT` | Edge visibility masks are ordinary `U64[M_r]` vectors passed directly to `0x63 OP_LANE_WALK` (`subop 7, 9`). |
| `0xC3` | `OP_LANE_CSR_WALK` | **Consolidated** | `0x63 OP_LANE_WALK` (`subop=0` `FWD`, `3..4` `FWD_FIXPOINT_*`) | Unifies forward, reverse, fixpoint, and edge-masked multi-lane walks; supports `FLAG_MASKED_S3` visited-lane pruning. |
| `0xC4` | `OP_LANE_CSC_WALK` | **Consolidated** | `0x63 OP_LANE_WALK` (`subop=1` `REV`, `5..6` `REV_FIXPOINT_*`) | Unified into `OP_LANE_WALK`. |
| `0xC5` | `OP_LANE_PRUNE_MASK` | **Generalized** | `0x64 OP_LANE_BITWISE` (`PRUNE_LANE_MASK`, `KEEP_LANE_MASK`, `CLEAR_VISITED_LANES`, `EXTRACT_SINGLE_LANE`) | Generalizes lane mask manipulation and single-lane extraction in `F0..F15`. |
| `0xC6` | `OP_LANE_FILTER_QUORUM` | **Retained & Moved** | `0x65 OP_LANE_FILTER_QUORUM` | Collapses multi-lane `F[s1]` to 1-bit `F[dst]` (`>= k`, `== k`, `<= k`). |
| `0xC7` | `OP_LANE_REDUCE_AND` | **Retained & Moved** | `0x66 OP_LANE_REDUCE_AND` | Intersects active lanes into 1-bit `F[dst]`. |
| `0xC8` | `OP_LANE_REDUCE_ATTR` | **Retained & Moved** | `0x67 OP_LANE_REDUCE_ATTR` | Per-lane `SUM`/`MIN`/`MAX`/`COUNT` over node attribute vector `V[s2]` into `V[dst]`. |
| `0xC9` | `OP_LANE_SET_COVER` | **Retired (Heuristic)** | `ImpK` loop (`LANE_BITWISE` + `VEC_INT_BITWISE.popcount` + `VEC_REDUCE.argmax`) | Narrow $O(k \cdot N)$ greedy heuristic retired alongside other composite showcase algorithms. |
| `0xCA` | `OP_VECTOR_ANN_SEARCH` | **Fixed & Moved** | `0x69 OP_VECTOR_ANN_SEARCH` | Outputs rank-ordered `V[dst]` node IDs (preserving similarity order) and accepts `F[s3]` pre-filter mask (`FLAG_MASKED_S3`). |
| `0xCB` | `OP_VECTOR_RERANK_DOT` | **Generalized** | `0x6A OP_VECTOR_RERANK` (`DOT`, `COSINE`, `NEG_L2_SQ`, `L1_DIST`) | Generalizes exact SIMD reranking across all four standard embedding metrics; composes with `0x53 OP_TOP_K`. |
| `0xFF` | `OP_EXTENSION_PAYLOAD` | **Retained & Hardened** | `0xFF OP_EXTENSION_PAYLOAD` | Word 2 **always** carries `0xFF` in Byte 0 (`imm32_hi` in Bytes `4..7`), guaranteeing wild jumps into Word 2 deterministically fail validation and trap at runtime. |
