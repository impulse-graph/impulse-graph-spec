# Electrical Engineering & Digital Circuit Analysis (EDA) Notes for Impulse Graph Engine v0.11

> **Status**: Future Showcase & Domain Notes (`impulse-eda` / `impulse-powergrid` companion)

---

## 1. Netlist Representation in `.imps`

A gate-level netlist (Verilog / EDIF) or PCB schematic is a **hypergraph** (1 driver pin → $k$ fanout pins on a wire/net), which maps 1:1 to a multi-domain `.imps` snapshot:

- **Domains**: `Cell` (gates, flip-flops, transistors), `Pin`, `Net` (wires/traces)
- **Relations**:
  - `(Cell)-[:HAS_PIN]->(Pin)`
  - `(Pin)-[:TIMING_ARC]->(Pin)` (edge attribute: gate delay, or $W$-corner delay columns)
  - `(Pin)-[:DRIVES]->(Net)` and `(Net)-[:FEEDS]->(Pin)` (edge attribute: wire RC delay / conductance $G$ / susceptance $B$)
- **Build-Time Ordering**: Ordering `Pin` dense IDs by **topological level** allows DAG Static Timing Analysis (`0x6C OP_LANE_STATE_WALK.fwd_max_plus`) to converge in a **single sequential pass** rather than $O(\text{depth})$ Bellman-Ford iterations.

---

## 2. EDA Workloads Expressible in v0.11 ISA (Zero New Opcodes)

| Workload | Representative Scale | v0.11 ISA Mapping |
| :--- | :--- | :--- |
| **Multi-Corner Static Timing Analysis (MCMM STA)** | 6502 (~1k gates), 80386 (~70k gates), PicoRV32 / OpenTitan (100k–10M+ pins) | `0x6C OP_LANE_STATE_WALK` (`.fwd_max_plus` Arrival Time, `.rev_min_plus` Required Time, $W=16$ `f32` PVT corners in `64 B/pin`), `0x48` (`slack = RAT - AT`), `0x6E.trace_path` (critical path) |
| **64-Vector Parallel Logic & Fault Simulation** | 64 stimulus vectors or 64 stuck-at-0/1 faults simultaneously | Pillar 5 64-lane frontiers (`F0..F15`) + `0x4C OP_VEC_INT_BITWISE` + active-frontier event filtering (`Tier0`/`Tier1`) |
| **Clock Domain Crossing (CDC) & Cone-of-Influence** | Reachability from `CLK_A` $\cap$ `CLK_B` excluding synchronizer cells | `0x63 OP_LANE_WALK.fwd_fixpoint_plus` (synchronizers in `FLAG_MASKED_S3`) + `0x66 OP_LANE_REDUCE_AND` |
| **PCB Connectivity / Via-Removal Island Check** | Open/short and N-1 trace/via failure analysis | `0x3B OP_GRAPH_KERNEL.cc_afforest` + `0x63.both_fixpoint_star_masked` |
| **DC Power-Grid IR Drop ($G \cdot V = I$)** | Linear resistive mesh solve (Conjugate Gradient / Jacobi) | `0x34 OP_SPMV` + `0x48 OP_VEC_MATH_ARITH` + `0x52 OP_VEC_REDUCE` |
| **AC Steady-State Phasor Analysis ($Y \cdot V = I$)** | Impedance $Z = R + j\omega L$, admittance $Y = G + jB$ | Split `(V_re, V_im)` SoA vectors + `0x4D.fma_v` + `0x49.hypot` (magnitude) + `0x4A.atan2` (phase) + `0x35 OP_WALK_MORSEL` |

---

## 3. Why Split-SoA `(V_re, V_im)` Beats Native Complex Opcodes

In SIMD (AVX2 / AVX-512 / NEON), interleaved `(re, im)` complex arithmetic requires cross-lane shuffles (`vmovsldup`/`vmovshdup`/`vfmaddsub`). Representing complex vectors as a **split SoA register pair `(V_re, V_im)`** (lowered automatically by `ImpK`/`ImpScheme`):
- **Complex multiply**: 4 shuffle-free ops (`mul` + `0x4D OP_VEC_TERNARY.fma_v`):
  - `out_re = a_re * b_re - a_im * b_im`
  - `out_im = a_re * b_im + a_im * b_re`
- **Polar conversion**: `|z| = hypot(re, im)` (`0x49.hypot`) and `arg(z) = atan2(im, re)` (`0x4A.atan2`) — both already in the ISA.
- **Complex SpMV** ($Y \cdot V = (G + jB)(V_r + jV_i)$): Either 4 `0x34 OP_SPMV` calls or 1 fused `0x35 OP_WALK_MORSEL` pass reading `G[e]` and `B[e]` together and scattering `out_re` / `out_im` to `V0`, `V1`.

---

## 4. Non-Fit Boundaries (Out of Scope for RO Graph VM)
- **Nonlinear Transient SPICE** (MOSFET I-V curves): Requires direct sparse LU factorization (KLU / SuperLU) at picosecond timesteps.
- **Physical Placement & Detailed Routing**: Continuously mutates 2D/3D cell coordinates and metal-layer grids.
- **Formal Equivalence (SAT / SMT)**: Backtracking CDCL search with dynamic conflict-clause learning.

---

## 5. Key Academic References
1. **OpenTimer & GPU-Accelerated STA**: Huang et al. (ICCAD 2015); Guo et al., *"HeteroSTA / GPU-Accelerated Static Timing Analysis"* (DAC 2020 / TCAD 2021).
2. **And-Inverter Graphs (ABC)**: Mishchenko et al., *"DAG-Aware AIG Rewriting"* (DAC 2006).
3. **Word-Parallel / Event-Driven Gate Simulation**: Chatterjee, DeOrio & Bertacco, *"Event-Driven Gate Simulation with GP-GPUs"* (DAC 2009).
4. **Multigrid / Iterative Power-Grid IR Drop**: Kozhaya, Nassif & Najm, *"A Multigrid-Like Technique for Power Grid Analysis"* (TCAD 2002).
