# `v0.11+` Specification & Architecture Plan: Multi-Lane `MITra-RCH` Coalescing (Lesson 4.1) & Kleisli State Projection `TYPE_LANE_STATE` (Lesson 4.2)

* **Repository**: `impulse-graph-spec`
* **Tracking Issue**: [`impulse-graph-spec#23`](https://github.com/impulse-graph/impulse-graph-spec/issues/23)
* **Companion Runtime Issues**:
  * **Lesson 1 & 2 (Physical `WIDTH_8..64` Packing & Sparse `activeWords`)**: [`impulse-graph-core#83`](https://github.com/impulse-graph/impulse-graph-core/issues/83), [`impulse-graph-java#41`](https://github.com/impulse-graph/impulse-graph-java/issues/41)
  * **Lesson 4.1 (`MITra-RCH` Gauss-Seidel + Adaptive Pull-CSC Boolean `FIXPOINT`)**: [`impulse-graph-core#85`](https://github.com/impulse-graph/impulse-graph-core/issues/85), [`impulse-graph-java#42`](https://github.com/impulse-graph/impulse-graph-java/issues/42)
* **Release Horizon**: Post-`v0.10.0` feature lockdown (`v0.10.x` runtime for Lesson 4.1; `v0.11.0+` ISA extension for Lesson 4.2)
* **Target Branch**: `feat/multilane-rch-adaptive-fixpoint`

---

## 1. Executive Phasing: Splitting Lesson 4.1 (`RCH`) from Lesson 4.2 (`TYPE_LANE_STATE`)

Following empirical microbenchmarking (`impulse-benchmarks/BENCHMARK_FINDINGS.md`, `K = 2..512` across `100K`-node / `1M`-edge and `1M`-node / `10M`-edge snapshots) against *Li et al., "MITra: A Framework for Multi-Instance Graph Traversal", PVLDB 16(10): 2551–2564, 2023*, Lesson 4 is partitioned into two cleanly decoupled phases:

| Phase | Scope | ISA / `.imps` Impact | Target Horizon | Tracking Issues |
| :--- | :--- | :--- | :--- | :--- |
| **Lesson 4.1 (`MITra-RCH` + Adaptive Pull-CSC)** | Upgrade unbounded boolean `FIXPOINT` (`0x04`) in `OP_LANE_CSR_WALK` (`0xC3`) & `OP_LANE_CSC_WALK` (`0xC4`) to 2-buffer `vid`-ordered Gauss-Seidel coalescing + dense Pull-CSC switching (`>= N/20`), and align 4-way fuel/flag invariants. | **Zero new opcodes or `.imps` changes** (clarifies `0xC3`/`0xC4` fuel & `ZF` parity in `VM_SPECIFICATION.md`). | Post-`v0.10.0` lockdown (`v0.10.x` / `v0.11.0`), stacked on `#83` / `#41`. | `impulse-graph-core#85`, `impulse-graph-java#42` |
| **Lesson 4.2 (`TYPE_LANE_STATE = 0x11`)** | Generalize Kleisli State Projection (`\langle D, F, S \rangle \xrightarrow{R} \langle D', F', S' \rangle`) across $W \in \{4, 8, 16\}$ numeric SIMD lanes (`0xCC`–`0xD4`) with semirings, witness IDs, Edge Stream Shaders, cross-lane numeric quorum pruning, and $\Delta$-bucketed scheduling. | **New register type `0x11` + opcodes `0xCC`–`0xD4`** (zero `.imps` file format changes). | `v0.11.0+` | `impulse-graph-spec#23` |

---

## 2. Empirical Constraints from `mitra_aside_bench` That Govern `v0.11+` Design

Measured single-thread latencies on `synth_medium.imps` (`100K` nodes, `1M` edges) and `synth_large.imps` (`1M` nodes, `10M` edges) established three hardware invariants that directly constrain `TYPE_LANE_STATE`:

1. **The `64 B/node` Random-Scatter Cache/TLB Wall**:
   * On cache-resident `synth_medium`, widening single-pass `MITra-BFS` from `8 B/node` (`K=64`) to `64 B/node` (`K=512`) beat 64-batched Impulse by `2.10x` (`30.5 ms` vs. `64.1 ms`).
   * On out-of-cache `synth_large` (`1M` nodes), **64-batched Impulse (`8 B/node` per pass = `890.9 ms`) beat wide `64 B/node` `MITra-BFS` (`1,160.5 ms`, `0.768x`)**, `32 B/node` (`446.0` vs. `548.8 ms`, `0.813x`), and `16 B/node` (`226.4` vs. `247.7 ms`, `0.914x`).
   * **Mandatory Design Consequence for `TYPE_LANE_STATE`**:
     For `float32` (`4 B/lane`), **$W = 16$ lanes is already `64 B/node` (1 CPU cache line)**, and $W = 32$ or $64$ would require `128–256 B/node` per buffer — directly inside the TLB/DRAM thrashing regime on $N \ge 1\text{M}$ graphs!
     Therefore, `TYPE_LANE_STATE` **MUST cap physical hardware lane width at $W \in \{4, 8, 16\}$ (`16 B / 32 B / 64 B` per node)** (`W ∈ {2, 4, 8}` for `float64`), batching $K > 16$ multi-seed numeric queries into $\lceil K / 16 \rceil$ cache-resident passes.
2. **Never Allocate 3 Dense Per-Node State Buffers**:
   * `MITra-BFS` suffered `3 × 64 MB = 192 MB` working set (`ans` + `cur_delta` + `next_delta`), whereas `MITra-RCH` cut runtime by **`3.52x–5.45x`** by updating state **in-place** (`2` buffers instead of `3`).
   * **Mandatory Design Consequence**: `TYPE_LANE_STATE` MUST hold **one** in-place `state[N][W]` slab (`64 B/node` max at $W=16$), tracking active vertices exclusively through compact `1 bit/node` summary bitsets (`active_words` or $\Delta$-bucket bitsets, `0.125 B/node` per bucket) plus optional `uint16_t`/`uint8_t` per-node dirty-lane masks (`active_lane_mask[N]`, `1–2 B/node`) so edges only relax lanes that actually improved in the prior step!
3. **Adaptive Push-CSR / Pull-CSC Relaxation on Dense Rounds**:
   * When an active frontier or $\Delta$-bucket exceeds `N / 20` active vertices on an endomorphic relation with CSC (`csc_to_csr_edge_idx` for weighted edges), relaxing target `v = 0..N-1` sequentially via Pull-CSC converts random scatter RMWs on `64 B` cache lines into sequential L1 register accumulations (`float32x16` SIMD `min`/`add`) followed by a single streaming store to `state[v][0..W-1]`.

---

## 3. Normative Clarifications for Lesson 4.1 (`VM_SPECIFICATION.md` §6.11.2)

To enable `impulse-graph-core#85`, `impulse-graph-java#42`, and `impulse-ocaml` to ship `MITra-RCH` + adaptive Pull-CSC with **100% 4-way polyglot parity**:

1. **Defined Modifier Flags on `0xC3` (`OP_LANE_CSR_WALK`) & `0xC4` (`OP_LANE_CSC_WALK`)**:
   * `flags & 0x03 != 0`: `ACCUMULATE` (preserves initial `src` lane bits in `dst`).
   * `flags & 0x04 != 0`: `FIXPOINT` (computes monotone transitive reachability closure; implies `ACCUMULATE` of initial `src` active bits).
   * Valid defined flag mask: `0x07`.
2. **Schedule Invariance & Bounded-Hop Semantics**:
   * When `fixpoint_max_hops` is **unset** (unbounded `*1..`), engines MAY evaluate `FIXPOINT` via level-synchronous Jacobi, `vid`-ordered Gauss-Seidel (`MITra-RCH`: ascending on `0xC3`, descending on `0xC4`), or direction-optimizing Push-CSR / Pull-CSC, because all fair schedules over `(WordT, |, 0)` produce the identical least fixed point.
   * When `fixpoint_max_hops = k` is **set** (`*1..k`), engines MUST evaluate exact $k$-hop bounded level-synchronous closure so forward edges cannot cascade past depth $k$.
3. **Condition Flag (`ZF`) & Fuel Determinism**:
   * Both single-hop and `FIXPOINT` modes set `flags[ZF] = 1` **iff** all `out_lanes[u] == 0` for $u \in [0, N_{\text{dst}})$.
   * Fuel consumption on `0xC3`/`0xC4` MUST be deterministic and **independent of internal Push vs. Pull-CSC crossover heuristics** (1 instruction-level fuel debit at dispatch, plus a deterministic `MAX_FIXPOINT_SWEEPS = 1024` loop cap).

---

## 4. Detailed `v0.11+` Specification Plan for Lesson 4.2 (`TYPE_LANE_STATE = 0x11`)

### 4.1 Register Type `0x11` (`TYPE_LANE_STATE`) Logical & Physical Model
A `TYPE_LANE_STATE` handle represents a domain-bound Kleisli state frontier $\langle D, F, S, W_{\text{prev}} \rangle$ across $K \in [1, 16]$ active lanes:

| Component | Logical Type | Physical Layout (`W` = `4`, `8`, or `16`) | Memory per Node ($W=16$, `f32`) |
| :--- | :--- | :--- | ---: |
| `elem_type` | `FLOAT32` (`0`), `INT32` (`1`), `FLOAT64` (`2`) | Selected at `OP_LANE_STATE_INIT` (`0xCC`) | — |
| `width_tier` ($W$) | `4`, `8`, `16` (`f32`/`i32`); `2`, `4`, `8` (`f64`) | `select_state_width(K)` (64B cache-line aligned) | — |
| `state` | `ElemT[N][W]` | Contiguous row-major `state[u * W + b]` (SIMD vector load per node) | `64 B/node` (`16 B` at $W=4$) |
| `dirty_lane_mask` | `uint16_t[N]` (`uint8_t[N]` for $W \le 8$) | Bit $b = 1$ iff lane $b$ at node $u$ awaits propagation | `2 B/node` |
| `active_words` | `uint64_t[(N+63)/64]` | Bit $u = 1$ iff `dirty_lane_mask[u] != 0` | `0.125 B/node` |
| `reached_lane_mask` | `uint16_t[N]` | Cumulative mask of lanes where `state[u][b]` != semiring identity $\mathbf{0}$ | `2 B/node` |
| `witness_prev` *(opt)* | `uint32_t[N][W]` (`0xFFFFFFFFu` = none) | Allocated **lazily** only when `FLAG_RECORD_WITNESS` is set | `0 B` default (`64 B` if enabled) |

### 4.2 ICTX v1 Canonical State Hashing for `TYPE_LANE_STATE` (`0x11`)
To guarantee 100% 4-way bitwise determinism (`four_way_validation.py`):
1. Emit tag `0x11`, `elem_type` (`u8`), `num_lanes` (`u32_le`), `width_tier` (`u32_le`), `has_witness` (`u8`), `node_count` (`u32_le`).
2. For each $u \in [0, \text{node\_count})$:
   * Emit `reached_lane_mask[u] & active_lane_bitmask` (`u16_le`).
   * For each active lane $b \in [0, \text{num\_lanes})$:
     * Canonicalize IEEE-754 `-0.0` $\to$ `+0.0` and quiet/signaling `NaN` $\to$ canonical quiet `NaN` (`0x7FC00000u` / `0x7FF8000000000000ULL`, matching `v0.10.0` vector math rules) before hashing `u32_le` / `u64_le`.
   * If `has_witness`: emit `witness_prev[u * W + b]` (`u32_le`) for $b \in [0, \text{num\_lanes})$.
*(Note: Internal transient scheduling structures — `dirty_lane_mask`, $\Delta$-buckets — are NOT hashed in ICTX v1, so different SIMD widths or Push/Pull crossovers hash identically!)*

### 4.3 Opcode Surface (`0xCC`–`0xD4`) & Deterministic Tie-Breaking Rules

| Opcode | Mnemonic | Summary & Determinism Contract |
| :---: | :--- | :--- |
| `0xCC` | `OP_LANE_STATE_INIT` | Initializes `TYPE_LANE_STATE` (`0x11`) from `TYPE_LANE_FRONTIER` (`0x10`) or seed vector, setting semiring identity $\mathbf{0}$ (`+inf` for `MIN`, `-inf` for `MAX`, `0` for `SUM`, `1` for `MUL`) on unseeded slots and initial seed values (`0`, `1`, or per-lane vector `R_init`) on active `(u, b)` seeds. |
| `0xCD` | `OP_LANE_CSR_WALK_STATE` | Single-hop or fixed-point forward semiring relaxation across `rel_id` + optional edge attribute `attr_id`. Built-in semirings: `MIN_PLUS` (`0`), `MAX_PLUS` (`1`), `MAX_MUL` (`2`), `SUM_MUL` (`3`, exact lane-local accumulation order ascending source `u` for IEEE-754 determinism!), `MIN_MAX` (`4`). Scheduling flags: `SINGLE_HOP` (`0x00`), `FIXPOINT_SYNC` (`0x04`), `FIXPOINT_DELTA_BUCKET` (`0x08`, $\Delta$ from float register; `MIN_PLUS` / `MIN_MAX` monotone semirings). |
| `0xCE` | `OP_LANE_CSC_WALK_STATE` | Reverse CSC semiring relaxation mirroring `0xCD`. |
| `0xCF` | `OP_LANE_WALK_STREAM_STATE` | Executes programmable Edge Stream Shaders (`0xA0`–`0xBF` / CEL) over `TYPE_LANE_STATE`, enabling multi-attribute edge cost functions (`edge.base_time + lane_param[b] * tgt.penalty`) across all $W$ lanes per edge. |
| `0xD0` | `OP_LANE_STATE_PROJECT` | Vectorized in-domain state endomorphism ($\langle D, S \rangle \to \langle D, S' \rangle$, e.g., PageRank damping `(1 - alpha) * S + alpha * seed`, affine scale/clamp, node-attribute combination). |
| `0xD1` | `OP_LANE_STATE_PRUNE` | Resets `(u, b)` entries failing state bounds (`state[u][b] > cutoff`) back to $\mathbf{0}$, plus **cross-lane numeric hub quorum pruning**: zeroes all lanes at $u$ if $\text{deg}(u) > \text{max\_deg} \land \text{count}_b(\text{state}[u][b] \le \tau) < \text{min\_q}$. |
| `0xD2` | `OP_LANE_STATE_TO_FRONTIER` | Bridges `TYPE_LANE_STATE` (`0x11`) $\to$ `TYPE_LANE_FRONTIER` (`0x10`, `reached_lane_mask` or `state[u][b] <= tau` mask) or `TYPE_BITSET_HANDLE` (`0x04`, quorum $\ge \text{min\_k}$). |
| `0xD3` | `OP_LANE_STATE_REDUCE` | Per-lane (`[K]` vector) or cross-lane (`[N]` node vector: `MIN`, `MAX`, `SUM`, `MEAN`, `ARGMIN`, `ARGMAX`) reduction. **Tie-breaking**: lowest node ID $u$ (per-lane `ARGMIN`/`ARGMAX`) or lowest lane index $b$ (cross-lane `ARGMIN`/`ARGMAX`) strictly wins ties. |
| `0xD4` | `OP_LANE_STATE_TRACE_PATH` | Reconstructs deterministic witness path (`TYPE_NODE_VECTOR`) for `(target_node, lane_b)` across homogeneous or multi-domain `witness_prev` chains. **Witness tie-breaking in `0xCD`–`0xCF`**: on equal relaxed cost (`new_cost == state[v][b]`), `witness_prev[v][b]` retains `min(existing_prev_u, candidate_u)` so witness trees are **100% schedule-invariant** between synchronous, Gauss-Seidel, and $\Delta$-stepping! |

> **Critical Subtlety — Schedule-Invariant Witness Tie-Breaking (`0xCD`/`0xCE` + `0xD4`) & Floating-Point Associativity (`SUM_MUL`)**:
> * For **idempotent extremal semirings** (`MIN_PLUS`, `MAX_PLUS`, `MAX_MUL`, `MIN_MAX`), edge addition `d[u][b] + w(e)` along any given simple path is identical regardless of bucket order, **and** updating `witness_prev[v][b] = u` whenever `new_cost < cur_cost || (new_cost == cur_cost && u < witness_prev[v][b])` makes both final distances **and** witness parent pointers **100% invariant** to $\Delta$-bucket order vs. synchronous Bellman-Ford!
> * For **non-idempotent `SUM_MUL`** (`+` is non-idempotent and IEEE-754 float addition is non-associative!), asynchronous/Gauss-Seidel re-relaxation would double-count paths and reorder float additions across engines. Therefore, `SUM_MUL` **MUST trap with `IMPULSE_VM_ERR_INVALID_FLAGS`** if combined with `FIXPOINT_DELTA_BUCKET` (`0x08`), and in `SINGLE_HOP` / `FIXPOINT_SYNC` MUST accumulate incoming edges in ascending source node ID `u` order (CSC pull order or deterministic source order) so C++, Java, Rust, and OCaml produce bit-identical IEEE-754 results!

---

## 5. TDD Rollout Checklist (When `v0.11` Opens)

1. **Spec & Assembler First (`AGENTS.md` §3.9)**:
   * Add `TYPE_LANE_STATE` (`0x11`) and `0xCC`–`0xD4` to `docs/VM_SPECIFICATION.md`, `docs/IMPAS_SPECIFICATION.md`, `opcodes.json`, and `tools/impas_assembler.py`.
   * Author $\ge 2$ positive and $\ge 2$ negative `.impas` compliance test vectors per opcode (`0xCC`–`0xD4`) in `test-vectors/vm-impas/`, including equal-weight shortest-path witness tie-breaking and `SUM_MUL` + `FIXPOINT_DELTA_BUCKET` negative flag trap tests.
2. **OCaml Normative Reference Oracle (`impulse-ocaml`)**:
   * Implement `vm_lane_state.ml` and ICTX v1 `0x11` hashing first to validate all `.impas` vectors.
3. **C++20 (`impulse-graph-core`) & Java 25 (`impulse-graph-java`) Zero-Allocation Kernels**:
   * Implement Highway/NEON/AVX2 `float32x4`/`x8`/`x16` and Java `FloatVector` (`jdk.incubator.vector`) kernels backed by pre-allocated context byte-arena / `ThreadLocalBufferPool` slabs, passing `javap -c` zero-allocation verification and `four_way_validation.py`.
4. **Clean-Room `MITra-DS` / `MITra-PPR` Benchmark Gate (`impulse-benchmarks`)**:
   * Extend `mitra_aside_bench.cpp` with weighted SSSP (`MITra-DS`) and `PPR` (`MITra-PPR`) on `arm64` and `x86_64` to verify $\Delta$-bucket crossover thresholds empirically.
