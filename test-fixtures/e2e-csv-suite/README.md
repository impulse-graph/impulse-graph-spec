# Canonical E2E CSV & Multi-Language Query Suite (`e2e-csv-suite`)

This directory contains the canonical cross-language End-to-End (E2E) CSV compilation, binary snapshot inspection, and multi-frontend query verification suite for **Impulse Graph Engine** (`impulse-graph` Specification v0.9.0).

## 1. Suite Architecture & Pipeline

1. **CSV-to-Snapshot Compilation (`manifest.json`)**:
   Compiled on-the-fly during test execution via `impulse-graph build --manifest manifest.json --output <tmp>/e2e_suite.imps` (zero binary `.imps` blobs committed to Git).
2. **16 Node Domains (`domains/*.csv`, IDs `0..15`)**:
   - **Part A (`0..9`)**: Entity & Property-Graph domains (`User`, `Profile`, `Department`, `Product`, `Order`, `Tag`, `Task`, `Group`, `Resource`, `Sensor`) covering `string`, `uint32`, and `uint64` keys, isolated boundary nodes (`u14`, `u15`), and nullable (`0x80 | base_type`) validity-bitmap columns across `int8`, `int16`, `int32`, `int64`, `float32`, `float64`, and `string`.
   - **Part B (`10..15`)**: GraphBLAS Pure Math & Vector domains (`MatEmpty0` [$N=0$], `MatVec10` [$N=10$], `MatGrid50` [$N=50$], `MatBit64` [$N=64$], `MatNet100` [$N=100$], `MatFeature50` [$N=50$]) with known algebraic properties and deterministic nullable validity bitmaps.
3. **26 Relations (`relations/*.csv`, IDs `0..25`)**:
   Ordered strictly by non-decreasing `(src_domain, tgt_domain)` and ensuring every domain `0..15` is a `src_domain` of at least one relation so `SnapshotWriter::finalize_to_writer` preserves relation IDs `0..25` 1:1 without injecting synthetic `<Domain>_nodes` carrier relations.
   Covers `1:1`, `1:N`, `N:1`, `N:M`, self-loops, cycles, diamond DAGs, CSR-only (`USER_RATED_PRODUCT`, `include_csc: false`), COO relations, $0 \times 0$ empty matrix, $50 \times 50$ zero and identity matrices, 1D ring Laplacian $C_{50}$, $64 \times 64$ cyclic permutation, $100 \times 100$ 3-component row-stochastic graph, and $100 \times 50$ / $50 \times 100$ rectangular bipartite matrices.
4. **Shared Multi-Language Query Corpus (`queries/`)**:
   - `queries/cypher/*.cypher`: 6 openCypher queries (`1:1`, mixed CSR+CSC 2-hop, fusable 2-hop, Kleene star `*`, undirected `COUNT`, 64-lane `IN [0,1,2]` + quorum).
   - `queries/implog/*.implog`: 4 Datalog/ReBAC rules (recursive cycle fixpoint, diamond DAG transitive closure, multi-hop ReBAC resource access, multi-seed lanes).
   - `queries/impk/*.impk`: 8 GraphBLAS & multi-lane array DSL scripts (identity SpMV, ring Laplacian, PageRank, Afforest connected components, 64-lane SpMM + quorum, 64-lane greedy set cover, upper-triangular DAG shortest path, rectangular bipartite projection).
   - `queries/impscm/*.impscm`: 4 Homoiconic S-Expression IR programs verifying 1:1 equivalence with frontend lowerings.
   - `queries/expected/*.impscm` & `queries/query_manifest.json`: Canonical lowered S-expressions and ground-truth target domain dense node IDs, cardinalities, and scalar reductions.
