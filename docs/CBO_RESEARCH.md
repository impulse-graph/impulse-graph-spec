# Cost-Based Optimizer (CBO) Research Notes — Impulse Graph Engine (vFuture)

**Status**: Living Research Document (M5 / v0.11.0 ISA Refactor baseline)  
**Target**: vFuture CBO & Adaptive Query Execution (`ImpScheme` → `ImpAsm` lowering + `ImpulseVM` runtime heuristics)

---

## 1. Executive Summary & Architectural Split

Impulse Graph Engine's v0.11 ISA (`OP_WALK`, `OP_WALK_MORSEL`, `OP_SET_CARDINALITY`, `OP_HAS_TOPOLOGY`, `OP_JCC`) separates **macro-adaptivity** (algorithmic plan choice) from **micro-adaptivity** (physical representation & hardware execution):

| Layer | Owns | Mechanism | Rationale |
| :--- | :--- | :--- | :--- |
| **Compiler + ImpAsm (CBO)** | **Macro / Algorithmic plan switching**: CSR vs. CSC vs. COO layout selection, index probe vs. attribute scan, join order, dense $O(N)$ scatter sink vs. sparse accumulator, multi-hop push vs. reverse-morsel pull. | Static snapshot statistics ($\lvert V_d \rvert$, $\lvert E_r \rvert$, avg degree, available layouts/indexes) + runtime `OP_SET_CARDINALITY` (`0x24`) + `OP_CMP_U64` + `OP_JCC`. | Multi-instruction plan changes can only be emitted by the compiler; branch overhead is amortized over thousands of edges. |
| **ImpulseVM Runtime** | **Micro / Physical adaptivity**: Frontier Tier 0/1/2 transitions (and dirty-page promotion), Beamer push/pull inside plain `OP_WALK`, masked-morsel sparse-vs-SIMD cutoff, hardware SIMD width (NEON / AVX2 / AVX-512 / Java `DoubleVector`). | Internal VM heuristics & `V11Geometry` thresholds. | Depends on microarchitectural constants (L1D size, vector width, dirty-page count); emitting guards around every op in `.impas` would bloat bytecode and degrade I-cache. |

---

## 2. Empirical Baseline Data (Apple Silicon ARM64, `bench_shader_100k_1m.imps`)

All timings below are empirical medians measured on physical ARM64 hardware over a 100K-node / 1M-edge `.imps` snapshot (`N = 100,000`, `E = 1,000,000`, avg degree 10, `f64` node attrs `score`, `cap` + `f64` edge attr `weight`):

- **T0 / T1 / T2**: `proj = (score[u] * w[e] + 1.5) / (cap[v] + 0.5); if (proj > 2.5) out[v] += proj` (~79% selectivity)
- **W3**: `if (w[e] > 9.5) { out[v] += sqrt(score[u] * w[e]) + cap[v]; }` (~4.9% selectivity)

### 2.1 v0.10 Edge Stream Shader vs. v0.11 Lexical Morsel (Pre-SIMD → Post-SIMD)

| Workload | C++20 v0.10 | C++20 v0.11 (Scalar) | C++20 v0.11 (NEON+Gather) | C++ vs v0.10 | Java 25 v0.10 | Java 25 v0.11 (Scalar) | Java 25 v0.11 (`DoubleVector`+Gather) | Java vs v0.10 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **T0** (64 seeds, 640 edges, Tier 0) | `0.037 ms` | `0.198 ms` | `0.188 ms` | `0.20×` | `0.060 ms` | `0.467 ms` | `0.324 ms` | `0.18×` |
| **T1** (10K seeds, 100K edges, Tier 1) | `3.244 ms` | `3.046 ms` | `1.251 ms` (79.9 MEPS) | **2.59×** | `5.023 ms` | `4.126 ms` | `2.078 ms` (48.1 MEPS) | **2.42×** |
| **T2** (100K seeds, 1M edges, Tier 2) | `32.179 ms` | `27.885 ms` | `10.238 ms` (97.7 MEPS) | **3.14×** | `44.785 ms` | `34.545 ms` | `13.223 ms` (75.6 MEPS) | **3.39×** |
| **W3** (1M edges, 4.9% sel, `sqrt`) | `12.692 ms` | `8.177 ms` | `4.483 ms` (223.1 MEPS) | **2.83×** | `22.782 ms` | `14.247 ms` | `7.017 ms` (142.5 MEPS) | **3.25×** |

### 2.2 COO Morsel (`OP_WALK_MORSEL.coo_fwd`) vs. CSR Morsel (`OP_WALK_MORSEL.fwd`)

Measured on Java 25 over off-heap `MemorySegment` COO arrays on the same `N = 100,000` node domain (Tier 2 full seeds):

| Relation Density | CSR Morsel (`.fwd`) | COO Morsel (`.coo_fwd`) | Winner |
| :--- | ---: | ---: | :--- |
| **Dense 1M edges** ($\lvert E \rvert / \lvert V \rvert = 10.0$) | `13.223 ms` (75.6 MEPS) | `14.262 ms` (70.1 MEPS) | CSR (`1.08×`) |
| **Sparse 15K edges** ($\lvert E \rvert / \lvert V \rvert = 0.15$) | `0.866 ms` (17.3 MEPS) | `0.756 ms` (19.8 MEPS) | **COO (`1.15×`)** |

---

## 3. Concrete CBO & Runtime Findings

### 3.1 Fixed $O(N)$ Dense Scatter Sink Overhead Dominates Tier 0
In **T0** (64 seeds, 640 edges on `N = 100,000`), v0.11 spent `0.188 ms` (C++) / `0.390 ms` (Java) vs. v0.10's `0.033 ms` / `0.088 ms` because the program initialized, copied/zeroed, and `OP_VEC_REDUCE`'d a full `N = 100,000`-element dense `V0` vector (`800 KB`) for only 515 active edges.

**CBO Rule to Explore**:
- When $\lvert F_0 \rvert \cdot \overline{\text{deg}}(R) \ll N$ (e.g., $< N / 16$), avoid domain-wide dense scatter vectors (`V0[N]`).
- Emit a runtime `OP_SET_CARDINALITY` branch:
  - **Small frontier**: accumulate into a sparse/local sink or direct scalar reduction (`OP_MORSEL_COMMIT.count_add_r` / scalar sum) without touching $O(N)$ memory.
  - **Large frontier**: use dense `V0[N]` + `OP_MORSEL_COMMIT.scatter_add`.

### 3.2 Dynamic COO vs. CSR Dispatch (`OP_WALK` / `OP_WALK_MORSEL`)
The optimal layout depends on **both** static relation sparsity ($\lvert E \rvert$ vs. $\lvert V \rvert$) **and** dynamic frontier size ($\lvert F \rvert$):
- CSR cost: $O(\lvert F \rvert \cdot c_{\text{row}} + \text{touched\_edges} \cdot c_{\text{edge}})$ — pays $\lvert F \rvert$ random `row_offsets[u]` probes even when most rows are empty.
- COO scan cost: $O(\lvert E \rvert \cdot c_{\text{coo}})$ — sequential scan over $\lvert E \rvert$ edges, independent of $\lvert V \rvert$ and $\lvert F \rvert$.
- **Crossover**: On a `10M`-node domain with a `15K`-edge relation:
  - If $\lvert F \rvert = 50$ (Tier 0): CSR touches 50 rows ($\ll 15\text{K}$); CSR wins decisively.
  - If $\lvert F \rvert = 500\text{K}$ (Tier 2): COO scans 15K edges sequentially instead of 500K random CSR row lookups; COO wins by an order of magnitude (even when COO is sorted `(tgt, src)` for a forward walk!).
- **ImpAsm Pattern**:
  ```asm
  SET_CARDINALITY.card_1bit R1, F0
  CMP_U64.gt                R2, R1, R_coo_threshold   ; compile-time threshold from |E|
  JCC.jnz                   R2, use_coo
  WALK_MORSEL.fwd           F0, rel=R, ...
  JMP                       done
  use_coo:
  WALK_MORSEL.coo_fwd       F0, rel=R, ...
  done:
  ```

### 3.3 Tier 1 → Tier 2 Promotion Under SIMD (`tier2_denom` vs. Dirty-Page Ratio)
Current `kGeomP0` uses `tier0_max = 64`, `page_shift = 12` (4,096 nodes = 512 B/page), `tier2_denom = 64` (1.56% density).
- With SIMD `OP_SET_OP` (`vorrq_u64`/`vandq_u64`/`veorq_u64` on NEON, `vpord`/`vpandd` on AVX2/AVX-512), dense Tier 2 bitsets run at sequential memory bandwidth with zero page-table indirection.
- By the birthday paradox on a uniform frontier with 4,096-node pages:
  - At `1/64` (1.56%): $\mathbb{E}[\text{bits/page}] = 64 \implies P(\text{dirty}) \approx 100\%$.
  - At `1/512` (0.20%): $\mathbb{E}[\text{bits/page}] = 8 \implies P(\text{dirty}) = 99.97\%$.
  - At `1/2048` (0.05%): $\mathbb{E}[\text{bits/page}] = 2 \implies P(\text{dirty}) = 86.5\%$.
- **Recommendation**: Keep `tier0_max = 64` (4 cache lines). For Tier 1 → Tier 2, explore promoting by **dirty-page ratio** (`dirty_pages * 2 >= total_pages`, i.e., $\ge 50\%$ pages dirty) instead of `card / N` alone. This promotes early on uniform frontiers (~0.02% density) while staying paged on spatially clustered subgraphs (power-grid islands, partitioned IDs).

### 3.4 Morsel Size (`morsel_max`) vs. L1D Cache Residency
- At `morsel_max = 2048`: each `f64`/`u64` morsel vector is 16 KB. `M0..M3` (64 KB) + 4 scratch vectors `M4..M7` (64 KB) = **128 KB**, which saturates Apple Silicon L1D (128 KB) and **spills into L2** on x86 (32–48 KB L1D).
- At `morsel_max = 512`: 4 KB/vector → 32 KB for 8 live vectors (fits 100% in L1D on both ARM64 and x86, with 64 4×-unrolled NEON/AVX2 iterations per morsel).
- **Empirical Apple Silicon ARM64 Sweep (1M edges, Highway NEON + Java `DoubleVector`)**:

| `morsel_max` | C++20 T2 (79% sel) | C++20 W3 (4.9% sel) | Java 25 T2 (79% sel) | Java 25 W3 (4.9% sel) |
| ---: | ---: | ---: | ---: | ---: |
| `128` | `10.460 ms` (95.6 MEPS) | `4.982 ms` (200.7 MEPS) | `14.661 ms` (68.2 MEPS) | `7.736 ms` (129.3 MEPS) |
| `256` | **`9.880 ms` (101.2 MEPS)** | `4.749 ms` (210.6 MEPS) | `13.558 ms` (73.8 MEPS) | `7.055 ms` (141.8 MEPS) |
| **`512`** | `10.187 ms` (98.2 MEPS) | `4.635 ms` (215.7 MEPS) | **`13.312 ms` (75.1 MEPS)** | `6.791 ms` (147.3 MEPS) |
| **`1024`** | `10.319 ms` (96.9 MEPS) | **`4.561 ms` (219.2 MEPS)** | `13.471 ms` (74.2 MEPS) | **`6.663 ms` (150.1 MEPS)** |
| `2048` | `10.424 ms` (95.9 MEPS) | `4.630 ms` (216.0 MEPS) | `13.394 ms` (74.7 MEPS) | `6.918 ms` (144.6 MEPS) |
| `4096` | `10.425 ms` (95.9 MEPS) | `4.664 ms` (214.4 MEPS) | *(capped at 2048 in `V11Workspace`)* | *(capped at 2048)* |

- **Joint sweet spot**: `morsel_max = 512`–`1024` (peaks C++20 T2 at `256`–`512` and W3 at `1024`; peaks Java 25 T2 at `512` and W3 at `1024`; also stays inside x86 32–48 KB L1D).

### 3.5 Masked Morsel Selectivity Cutoff (Sparse Scalar vs. Dense SIMD)
- On **W3** (4.9% selectivity), switching masked morsel ops from 256-lane `contains_1bit` binary search to sparse `mask_ids[k]` iteration cut runtime **4.96×** (`40.84 ms → 8.18 ms`, and `5.18 ms` with NEON on the unmasked filter).
- Above ~35–50% selectivity, running the unmasked SIMD kernel and bitwise-ANDing `out_valid` with the mask bitset is faster than indirect `mask_ids[k]` indexing.
- **Runtime Rule**: Inside morsels, dispatch masked ops to sparse `mask_ids[k]` when `mask_cnt * 3 < len` (< 33% active) and to dense SIMD + mask-AND otherwise.

### 3.6 Codegen Rules That Enable Hardware Auto-Vectorization
Disassembly of `v11_vm_dispatch.cpp.o` (`objdump -d`) proved that **0 NEON FP instructions** were emitted for morsel math before refactoring, even under `-O3 -DNDEBUG`. Three patterns blocked vectorization:
1. `subop` dispatch inside the lane loop.
2. Per-lane validity bit-twiddling (`vbits[i >> 6] |= 1ULL << (i & 63)`) creating a loop-carried read-modify-write dependency.
3. Per-lane `if (!std::isnan(r))` branches.

Hoisting `subop`, running contiguous `__restrict` SIMD loops, and packing validity word-at-a-time unlocked **174 NEON FP instructions** and **2.2×–2.7× speedups** with 100% bitwise ICTX v2 parity.

---

## 4. Future CBO Research Backlog (vFuture)

1. **Secondary Index vs. Attribute Scan Crossover**:
   - Use `OP_SET_CARDINALITY` + `OP_HAS_TOPOLOGY` (`.has_index`) to choose between probing a ZoneMap / InvertedBitSet / MPHF index (`OP_INDEX_PROBE` + `OP_SET_OP.intersect`) vs. direct `OP_GATHER_NODE_ATTR` + `OP_VEC_CMP` on the active frontier.
2. **Multi-Hop Join Ordering & Direction Reversal (Meet-in-the-Middle)**:
   - For `(A)-[R1]->(B)-[R2]->(C)` with selective filters on both `A` and `C`, estimate $\lvert F_A \rvert \cdot \overline{\text{deg}}(R_1)$ vs. $\lvert F_C \rvert \cdot \overline{\text{deg}}(R_2^{-1})$ (when CSC/COO is present) to choose forward, reverse, or bidirectional meet-in-the-middle execution.
3. **Predicate Pushdown & Filter Reordering Inside Morsels**:
   - Order cheap/selective edge-attribute filters (`w[e] > 9.5`) *before* expensive node-attribute gathers (`score[u]`, `cap[v]`) and transcendental ops (`sqrt`, `div`), emitting `OP_JCC.jempty_f` to short-circuit empty morsels completely (demonstrated in **W3**: `193.1 MEPS`).
4. **Multi-Lane Width Auto-Selection (`w8` / `w16` / `w32` / `w64`)**:
   - Select the narrowest lane width matching the batch size of simultaneous seeds to keep multi-lane state arrays cache-resident.
5. **Cross-Compiler SIMD Codegen Regression Gate (CI)**:
   - Automated CI check (`objdump -d` on Linux/macOS GCC+Clang, `dumpbin /disasm` on Windows MSVC) asserting non-zero vector FP/bitmask instruction counts for every `impulse::vm::v11::simd::*` kernel across `x86_64` (AVX2/FMA) and `arm64` (NEON).
