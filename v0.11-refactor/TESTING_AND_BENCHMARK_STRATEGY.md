# ImpulseVM v0.11.0 Verification, Differential Fuzzing & Performance Benchmark Strategy

> **Normative Draft (`v0.11.0-ISA-Refactor`)**
> Defines the Dual `ICTX v2` compliance digest protocol, metamorphic geometry test execution, multi-dimensional opcode/subop/3VL coverage gates, contract-guided differential fuzzing, and empirical micro/macro benchmark methodology (`AGENTS.md` §3.7, §3.9, §3.13, §3.18).

---

## 1. Dual `ICTX v2` State Digest Protocol

### 1.1 Motivation: Why Single-Hash `ICTX v1` Is Insufficient for Adaptive Tiers

In v0.10.0, `ICTX v1` hashed flat 64-register tags and payloads (and skipped `TYPE_VALUE_MAP` contents entirely). In v0.11.0:
1. A frontier `{1, 5, 42}` has **identical mathematical meaning** whether stored in `TIER0_INLINE` (default thresholds), `TIER1_PAGED` (`tier0_max = 2` test override), or `TIER2_DENSE` (`N_d <= 64` dense override), and against the pure functional **OCaml Reference Oracle** (which models frontiers mathematically as canonical `NodeSet` / `LaneMap` values).
2. Simultaneously, systems engineers must verify that C++, Rust, and Java 25 make **identical physical tier transitions, lane-width selections (`Width8..64`), and lazy `cached_card` updates** under identical runtime thresholds.

`ICTX v2` solves both requirements simultaneously by emitting a **16-byte dual digest (`logical_hash: u64`, `physical_hash: u64`)** computed via canonical little-endian `XXH3-64` (or FNV-1a-64 / SHA-256 truncated-64 — normative hash function: **XXH3-64 with seed `0x494D505630313130` (`"IMPV0110"`)**).

### 1.2 Wire Serialization for `logical_hash` (Tier-Invariant, 4-Way Oracle Gate)

`logical_hash` serializes **100% of observable VM state** in canonical mathematical form:

1. **Header (`24 B`)**: Magic `"ICTXv2L\0"` (`8 B`), `status: u32`, `pc: u32`, `vm_flags: u16` (`ZF | ST | NF`), `r_valid_mask: u16`, `r_type_word: u64_le`.
2. **Scalar Bank `R0..R15`**: For `i = 0..15`: if `(r_valid_mask >> i) & 1 == 0`, emit `0x00` (`1 B`); else emit `0x01` + `r_regs[i]: u64_le` (with `-0.0` float scalars preserved raw or canonicalized only where specified).
3. **Frontier Bank `F0..F15` (Canonicalized!)**: For `i = 0..15`:
   - If uninitialized: emit `0x00`.
   - Else emit `0x01`, `domain_id: u16_le`, `lane_width_logical: u8` (`1` for 1-bit, `64` for multi-lane + `active_lane_count: u8`), `active_node_count: u64_le`, followed by active nodes in **strictly ascending `node_id: u64_le` order** (with `lane_mask: u64_le` per active node when multi-lane).
   - *Result*: `TIER0_INLINE`, `TIER1_PAGED`, `TIER2_DENSE`, and `ALL_SPAN` produce **bit-for-bit identical** byte streams!
4. **Vector Bank `V0..V15`**: For `i = 0..15`:
   - If uninitialized: emit `0x00`.
   - Else emit `0x01`, `elem_type: u8`, `length: u64_le`, and for `k = 0..length-1`: if `!valid[k]` emit `0x00`, else emit `0x01` + canonical element bytes (`StringView` hashes resolved UTF-8 byte length + UTF-8 bytes from pool, not pool memory offsets!).
5. **Terminal `OP_COLLECT` Slots `0 .. num_outputs - 1`**: Serializes every collected bitset, ID array, vector, scalar, and Arrow RecordBatch column in full (closing v0.10's `TYPE_VALUE_MAP` blind spot).

### 1.3 Wire Serialization for `physical_hash` (Tier-Variant, Systems Engine Gate)

`physical_hash` feeds the entire `logical_hash` stream into XXH3-64 (`seed = 0x5048595330313130`, `"PHYS0110"`) **plus** for each initialized `F0..F15`:
- Physical `tier_tag: u8` (`EMPTY=0`, `TIER0_INLINE=1`, `TIER1_PAGED=2`, `TIER2_DENSE=3`, `ALL_SPAN=4`)
- Physical `lane_width_allocated: u8` (`1, 8, 16, 32, 64`)
- `dirty_page_count: u32_le` (on `TIER1_PAGED`)
- `cached_card_state: i8` (`0` if `cached_card == -1`, `1` if `cached_card >= 0`).

---

## 2. Metamorphic Multi-Profile Compliance Harness

A 10-node unit test in `.impas` would normally remain stuck in `TIER0_INLINE` (`<= 64` nodes) and a single morsel (`<= 2048` edges), leaving `TIER1_PAGED`, `TIER2_DENSE`, multi-morsel loop carry, and parallel worker merging untested on small fixtures.

`run_vm_asm_suite_v11.py` eliminates this blind spot by executing **every positive `.impas` compliance test across 6 metamorphic execution profiles** (unless the `.impas` file pins explicit `.tier_thresholds` for a targeted physical-hash test):

| Profile ID | `tier0_max` | `page_shift` (Page Size) | `tier2_ratio` | `morsel_max` | `max_dop` | Target Mechanism Exercised on Small Fixtures |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`P0-Default`** | `64` | `12` (`4096` nodes) | `1/64` | `2048` (ramp `32..2048`) | `1` | Production single-thread fast path (`physical_hash` baseline). |
| **`P1-ForceTier1`** | `2` | `2` (`4` nodes/page!) | `1/2` | `2048` | `1` | Forces multi-page `page_dir[]` allocation, cross-page `SET_OP`, and `dirty_pages[]` sorting on 10-node graphs! |
| **`P2-ForceTier2`** | `0` | `6` (`64` nodes) | `0` (always dense) | `2048` | `1` | Forces `TIER2_DENSE` + `L1` summary bitset updates and trailing-word masking (`N_d % 64 != 0`). |
| **`P3-MicroMorsel`** | `64` | `12` | `1/64` | **`3` lanes!** | `1` | Splits a 12-edge walk across **4 morsel iterations**, testing morsel state reset, `.jempty_f` skip jumps, and multi-morsel commit accumulation! |
| **`P4-ParallelMorsel`** | `2` | `2` | `1/4` | **`4` lanes** | **`4` threads** | Tests concurrent worker TLS morsel scratchpads, deterministic `SCATTER_ADD` / `SCATTER_ARGMIN` merging, and thread-safe Tier 1/Tier 2 commits! |
| **`P5-OCamlOracle`** | Mathematical | Mathematical | Mathematical | `3` & `2048` | `1` | Normative reference evaluation in `impulse-ocaml`. |

### Pass Criteria & Two-Tier FP Verification Policy
1. **Cross-Profile Metamorphic Invariance (`70` Non-Transcendental Opcodes)**: For any program not invoking `0x49`/`0x4A`/`0x4B` transcendentals, `logical_hash(P0) == logical_hash(P1) == logical_hash(P2) == logical_hash(P3) == logical_hash(P4) == logical_hash(P5)` (**0-ULP bit-identical**) across **all four engines** (OCaml, C++ Opt-ON, C++ Opt-OFF, Java 25).
2. **Transcendental SIMD Verification (`0x49`, `0x4A`, `0x4B`)**: Programs executing `0x49`/`0x4A`/`0x4B` verify exact bit-identity on all validity masks, `NULL`, `±0.0`, `±Inf`, poles, and non-transcendental state, while comparing finite transcendental floats element-wise against the OCaml oracle within normative bounds (`<= 1.0 ULP` on `exp*`/`log*`/`trig`/`hyp`/`cbrt`/`hypot`/`erf`/`erfc`, `<= 2.0 ULP` on `pow`/`lgamma`/`gelu`/`silu`/`softplus`).
3. **Caller-Owned Budgeted Scratch Verification**: Dedicated negative tests pass `scratch_bytes < guaranteed_scratch_bytes` (down to `min_scratch_bytes`) and assert deterministic `IMPULSE_VM_ERR_BUFFER_OVERFLOW` (`11`) with **zero `malloc` calls** (verified via custom allocator interposition / JMH `-prof gc`).
2. **Cross-Engine Physical Identity**: For each concrete profile $P_k \in \{P_0 \dots P_4\}$, `physical_hash_cpp_on(P_k) == physical_hash_cpp_off(P_k) == physical_hash_java25(P_k)`!

---

## 3. Coverage Mandate & Differential Fuzzing (`AGENTS.md` §3.9, §3.18)

### 3.1 Multi-Dimensional Coverage Matrix (Replacing the v0.10 2-File Counter)

In v0.10, `run_vm_asm_suite.py` only checked that each opcode byte appeared in $\ge 2$ `.impas` files — allowing 30+ `MATH_FUNC_*` subops and `NULL` 3VL combinations to pass CI with 0 tests. In v0.11, CI enforces **100% Contract Cell Coverage** derived directly from `isa_v0_11.yaml`:

1. **Opcode × Subop Coverage (`100%` Mandatory)**: Every valid `(opcode, subop)` pair in `isa_v0_11.yaml` MUST appear in $\ge 2$ positive `.impas` test vectors and $\ge 1$ negative test vector (testing bounds/domain/type/validation rejection).
2. **Modifier Flag Coverage (`100%` Mandatory)**: For every opcode declaring non-zero `allowed_flags`, each allowed flag (`FLAG_ACCUM`, `FLAG_SCALAR_RHS`, `FLAG_MASKED_S3`, `FLAG_EXTENDED`) MUST be exercised in at least 1 positive `.impas` vector AND 1 disallowed-flag negative vector.
3. **Kleene 3VL Truth-Table Mandate**: Every comparison/logic/filter/math opcode MUST have dedicated `.impas` coverage over all 3 Kleene states (`TRUE`, `FALSE`, `NULL`), specifically guarding `NULL != const -> NULL`, `NOT(NULL) -> NULL`, `FALSE && NULL -> FALSE`, and `TRUE || NULL -> TRUE`.
4. **C++ / Java Branch Site Instrumentation (`IMP_VM_COV_BRANCH`)**: Retains branch-site hit bitmaps to verify that empty-frontier fast paths, `ALL_SPAN` fast paths, `INT64_MIN / -1` guards, and `N_d % 64 != 0` tail masks execute during CI.

### 3.2 Scale Verification & Contract-Guided Differential Fuzzing (`impulse-verification`)

1. **Synthetic `.imps` Scale Suite (`100K` – `10M` Nodes)**:
   - Built strictly via `impulse-cli` (`impulse-graph generate` / `impulse-graph build` into git-ignored `datasets/` per `AGENTS.md` §3.6 & §3.17 — zero ad-hoc binary writers!).
   - Topologies: Erdős–Rényi uniform, Barabási–Albert power-law (`gamma = 2.1`, max hub degree $> 50,000$ to stress Beamer push/pull & `WALK_2HOP` dedup), high-diameter road-grid mesh (`diameter > 500` to stress Tier 0 / Tier 1 multi-hop BFS), and multi-domain bipartite (`User` `uint32` $\to$ `Product` `uint16` $\to$ `Category` `uint16`).
2. **Grammar-Guided Differential Fuzzer (`tools/fuzz_vm_contracts_v11.py`)**:
   - Generates random type-valid and adversarial (10% mutation rate for verifier fuzzing!) `.impb` v0.11 programs directly from `isa_v0_11.yaml`, including multi-sink `WALK_MORSEL` DAGs, nested `CALL.stride` / `RET` windows, nullable columns, and multi-lane walks.
   - Asserts 4-way `(status, logical_hash)` agreement across 100,000+ seeds in nightly CI and 5,000 seeds per PR.

---

## 4. Empirical Performance Benchmarking Strategy (`impulse-benchmarks`)

> [!IMPORTANT]
> **Empirical Measurement Policy (`AGENTS.md` §3.7 & §3.13)**: No benchmark target below is a claimed result; all metrics MUST be collected from physical hardware execution logs via Google Benchmark (C++20) and JMH (Java 25 FFM + Vector API), with automated CI regression gates enforcing Warmed-Up Java 25 $\le 2\times$ C++ (and failing hard on any $> 5\times$ anomaly).

### 4.1 Core Microbenchmark Matrix (`BM_V11_*` / `V11*Benchmark.java`)

| Benchmark Suite | Parameter Sweep | Baseline Compared Against | Key Engineering Question Answered |
| :--- | :--- | :--- | :--- |
| **`BM_Frontier_TierCrossover`** | $N_d = 10^7$, active $\lvert F \rvert \in \{1, 8, 64, 512, 4096, 65536, 10^6, 5\cdot 10^6\}$ | v0.10 flat `VmBitSet` | Empirically tunes `tier0_max` (`64`), `page_shift` (`12` = 4K vs `14` = 16K), and `tier2_ratio` (`1/64`); verifies **$\le 2\%$ overhead** when $\lvert F \rvert$ is in Tier 2 dense! |
| **`BM_Cardinality_LazyVsEager`** | Push `OP_WALK` with (a) `SET_CARDINALITY` never called, (b) called once per hop, (c) called $3\times$ per hop | Eager per-edge `!(old & mask)` counter vs v0.10 unconditional scan | Quantifies cycles saved when cardinality is unused and verifies SIMD `vpopcntq` over `dirty_pages[]`/`L1` beats per-edge conditional counting. |
| **`BM_Morsel_Vs_LegacyShader`** | 1-clause (`OP_WALK_FILTERED`), 3-clause arithmetic CEL (`OP_WALK_MORSEL`), early-exit `LIMIT 10` (`32->256->2048` ramp), `max_dop` $\in \{1, 4, 8\}$ | v0.10 scalar shaders (`0xA0`–`0xBF`) & `OP_CSR_WALK_PREDICATE` (`0x13`) | Measures throughput gain of L1 morsel SIMD + `.jempty_f` late gather over v0.10 per-edge `MethodHandle` / `ShaderAbortException` / AST walking. |
| **`BM_Kleene3VL_DualMask`** | `VEC_CMP` + `VEC_3VL_OP` (`AND`/`OR`/`NOT`) at `0%`, `10%`, `50%` `NULL` density | Branchy scalar 3VL evaluation | Verifies zero throughput sensitivity to `NULL` density or branch misprediction. |
| **`BM_BiBFS_DegreeBalanced`** | Power-law graph ($N=5\cdot 10^6, M=10^8$): hub-to-leaf vs leaf-to-leaf shortest path | Cardinality-only (`card(F_f) <= card(F_b)`) & unidirectional BFS | Quantifies edge-expansion reduction of `OP_DEGREE.sum_fwd_r` + `OP_WALK.fwd.mask` (`\ F_visited`). |
| **`BM_MultiLane_PagedSlabs`** | $K \in \{2, 8, 32, 64\}$ seeds on $N = 5\cdot 10^7$ nodes (`1..4` hops) | v0.10 eager `long[N]` `VmLaneFrontier` | Measures cold-start allocation latency (`KB` vs `400 MB`) and cache-hit throughput across hops. |
| **`BM_Dispatch_NibbleVsLegacy`** | 10M-instruction tight scalar/control/window `CALL`/`RET` loop | v0.10 64-reg switch + `VALIDATE_REG` + `register_types[]` | Measures interpreter dispatch IPC, `256B` vs `640B` L1 frame residency, flat `(op, subop)` pre-decode, and Java 25 leaf-`MethodHandle` JIT inlining. |
| **`BM_CallerWorkspace_EpochReset`** | 1M consecutive point/2-hop queries reusing 1 thread-local `scratch_ws` on $N_d = 10^8$ | v0.10 `impulse_vm_context_reset` + heap pool | Verifies `0 B/op` allocation, `64B`-masked `4KB` Tier 1 directory reset latency, and `impulse_vm_plan_memory` tightness. |

### 4.2 Zero-Allocation & JIT Inlining Verification Gates (Java 25 & C++20)

1. **Java 25 Hot-Path Bytecode & Allocation Gate**:
   - JMH `-prof gc` MUST report **`0.000 B/op` heap allocation** (`gc.alloc.rate.norm == 0`) across warmed-up execution of `OP_WALK`, `OP_WALK_FILTERED`, `OP_SPMV`, `OP_WALK_MORSEL`, `OP_NODE_FILTER`, and `OP_LANE_WALK` (when `VmContextPool` slabs are warmed).
   - Automated `javap -c` / `-XX:+PrintInlining` check in CI verifies zero `ShaderAbortException` or boxed `Long`/`Double` allocations and confirms every opcode handler method stays under JVM C2 inlining thresholds.
2. **C++20 Auto-Vectorization Report Gate**:
   - CMake `ENABLE_VEC_REPORT` (`-Rpass=loop-vectorize` on Clang / `-fopt-info-vec` on GCC) verifies that `OP_VEC_MATH_ARITH`, `OP_VEC_CMP`, `OP_VEC_3VL_OP`, and `OP_SET_CARDINALITY` vectorize cleanly with zero scalar-fallback regressions.
