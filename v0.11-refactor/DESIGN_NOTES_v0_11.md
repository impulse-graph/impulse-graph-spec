# ImpulseVM v0.11.0 Architectural Design Notes

> **Status**: Living design rationale for v0.11.0 → v1.0 ISA freeze (uncommitted working notes).

---

## 1. Live External Data Augmentation (No Host Callback Opcodes)

- **Decision**: Do **not** add an in-VM C-ABI callback opcode (`OP_CALL_HOST_FN`). Host callbacks break 4-way determinism (`ICTX v2`), morsel thread-safety, zero-allocation guarantees, and SIMD vectorization (N+1 FFI/RPC cliff).
- **Sanctioned Pattern — Zero-Copy External Column Overlays**:
  - For static `.imps` topology + fast-changing live attributes (60Hz PMU telemetry, live traffic weights, inventory, fraud scores), the caller maintains an off-heap/shared-memory `f32[N_d]` / `i64[N_d]` array and binds it zero-copy via **`0x07 OP_LOAD_PARAM.vec`**.
  - Inside `OP_WALK_MORSEL`, **`0x43 OP_GATHER_VEC`** reads the live overlay at native SIMD speed; **`0x4F OP_COALESCE(V_live, V_imps_base)`** handles sparse overrides.
- **External DB Augmentation (Postgres / Redis)**:
  - Use 2-phase batched orchestration: VM Query 1 returns candidate IDs (`OP_COLLECT`) → host runs 1 batched `IN (...)` query → host binds results via `OP_LOAD_PARAM.vec` into VM Query 2.

---

## 2. Multi-Anchor / Multi-Domain Subqueries in Fluent APIs

- **VM / ISA Capability**: ImpulseVM v0.11 already supports arbitrary multi-anchor DAGs natively in **one single `.impb` program** — multiple `0x07 OP_LOAD_PARAM.frontier` calls bind `F0`, `F1`, ... on different starting domains, walk independently into a common central domain, combine via `0x22 OP_SET_OP` (and `0x48` for state vectors), and march into a third domain with zero client round-trips.
- **Fluent API Patterns (Lazy DAG `Traversal<D>`)**:
  1. **Composable Lazy Values + Combinators (Primary)**:
     ```java
     var fromUsers    = snap.domain("User").traverse(uSeeds).out("EXPRESSED_IN");      // Traversal<Gene>
     var fromDiseases = snap.domain("Disease").traverse(dSeeds).in("ASSOCIATED_WITH"); // Traversal<Gene>
     var drugs = fromUsers.intersect(fromDiseases).out("TARGETED_BY").collect();
     ```
     With state combination: `fromUsers.join(fromDiseases, (a, b) -> a.score + b.score)`.
  2. **Inline Subquery Lambda** (`whereIn` / `whereNotIn`):
     ```java
     snap.domain("User").traverse(uSeeds)
         .out("EXPRESSED_IN")
         .whereIn(q -> q.domain("Disease").traverse(dSeeds).in("ASSOCIATED_WITH"))
         .out("TARGETED_BY")
         .collect();
     ```
  3. **$N$-Way Fan-In**: `Traversal.intersect(t1, t2, t3).out("TARGETED_BY").collect()`.
- **Compilation**: Because `Traversal<D>` nodes are lazy immutable DAGs, `.compile()` / `.collect()` topologically sorts the DAG, deduplicates shared sub-traversals (CSE), allocates `F0..F15` / `V0..V15`, and emits a single `.impb` program.

---

## 3. Geospatial Graph Analytics (EPSG:4326 / WGS84)

- **Zero New Opcodes Needed**:
  - **Earth Distance**: Haversine (spherical, ~0.3% max error), local equirectangular (`0x49.hypot` + `0x4A.cos`), and Andoyer-Lambert (closed-form WGS84 ellipsoidal correction, ~10 m global accuracy) all lower cleanly to `0x48`/`0x49`/`0x4A`/`0x4D` inside `OP_WALK_MORSEL` (exposed as `ImpK`/`ImpScheme` macros).
  - **Multi-Origin Isochrones & Routing**: `0x6C OP_LANE_STATE_WALK.fwd_min_plus` (16 origins/pass, $\Delta$-stepping) + `0x6D.prune_cutoff` + `0x4D.time_valid_at_r`.
  - **H3 / S2 Spatial Grids**: `k`-ring expansion via $k$-hop `0x30 OP_WALK` + exact distance filtering in `OP_WALK_MORSEL`.
  - **Geographic $k$-NN & Radius Search**: Store 3D ECEF unit-sphere vectors `(cos φ cos λ, cos φ sin λ, sin φ)` as `f32[3]` embeddings and query directly via `0x69 OP_VECTOR_ANN_SEARCH` (`.ids` / `.radius`).
- **Known Boundary**: Arbitrary variable-length point-in-polygon ray casting over jagged polygon rings is not a native VM primitive; use H3 cell-set polyfill (`0x22.inter` / `0x45.in_set`) for pre-filtering.

---

## 4. Frontend Implications (Cypher, ImpK, ImpLog)

- **openCypher (RO Subset)**: Native Kleene 3VL (`0x0E`/`0x45`/`0x46`), arbitrary `WHERE` over `(a)-[r]->(b)` via `OP_WALK_MORSEL` (+ morsel `OP_SPILL.v`), `IN` via `0x45.in_set`, `shortestPath` via `0x6C.fwd_min_plus` + `0x6E.trace_path`, and `ORDER BY ... LIMIT k` via `0x53 OP_TOP_K`. Out-of-scope by design: write clauses, dynamic high-cardinality string `GROUP BY` on non-domain columns, full-table multi-key sort without `LIMIT`, and unbounded Cartesian / all-simple-paths enumeration.
- **ImpK**: Direct lowering to `0x34 OP_SPMV` (CSC Pull), `0x6C OP_LANE_STATE_WALK` (16-lane AoS SpMM), `0x6F OP_VECTOR_POOL` + `0x6A.pair_*`, and explicit `r_type_word` scalar tags.
- **ImpLog**: Semi-naive fixpoints collapse into `0x30 OP_WALK.mask` (`F_visited` in `s3`) + `0x22.union` + `0x27 OP_STABLE_CHECK`; stratified negation maps to `0x23`/`0x22.diff`; 64-lane ReBAC consensus maps to `0x63`/`0x65`/`0x66`.

---

## 5. Temporal Handling, CEL Datetime & Timezone Policy

- **VM Representation**: All timestamps inside ImpulseVM are `i64` UTC epochs (seconds/ms/ns).
  - Point-in-time / bitemporal validity (`valid_from <= T < valid_to`): `0x4D OP_VEC_TERNARY.time_valid_at_r`.
  - Time-respecting / causal paths (`edge.ts >= arrival[u]`): `0x35 OP_WALK_MORSEL` + `OP_MORSEL_COMMIT.scatter_min`.
- **CEL Datetime Functions (Zero New Opcodes)**:
  - `getHours` / `getMinutes` / `getSeconds` / `getDayOfWeek` (UTC or fixed offset) lower to 2–3 `i64` `div`/`rem` ops (`0x48`/`0x0C`).
  - `getFullYear` / `getMonth` / `getDate` lower via Howard Hinnant's branchless `civil_from_days` algorithm (~12 integer ops in `0x48`).
- **IANA `tzdata` / DST Policy**: Strictly excluded from the core VM kernel (prevents `tzdata` version drift across OS/JDKs from breaking 4-way `ICTX v2` determinism and preserves zero runtime dependencies). Convert query anchors to UTC `i64` in the host before `OP_LOAD_PARAM.scalar`, or precompute `utc_offset_sec` / `local_hour` attributes in `.imps` at build time.

---

## 6. Fixed-Point Financial Decimals (`DECIMAL(P, S)`)

- **`.imps` Schema Layer**: `DECIMAL(P, S)` ($1 \le P \le 18$, $0 \le S \le P$) is stored physically as an 8-byte-aligned `int64_t[]` column scaled by $10^S$ (identical to Apache Parquet `DECIMAL64`), with `(DECIMAL64, precision, scale)` recorded in `.imps` attribute metadata / schema manifest (zero binary layout change).
- **ImpulseVM Layer**: No new register bank or vector element type; loaded as standard `i64`. `add`/`sub`/`cmp`/`sum`/`min`/`max`/`scatter_add` execute as exact `i64` ops (zero binary FP drift).
- **Overflow-Safe Multiply/Divide**: `0x4D OP_VEC_TERNARY` `subop 9 = .mul_div_i64_r` computes `(i128(V[s1]) * i128(s2)) / i128(R[s3])` with deterministic half-even (banker's) rounding (returning Kleene `NULL` on `R[s3] == 0` or final `i64` overflow), preventing intermediate 64-bit overflow during decimal scale normalization.

---

## 7. `.imps` Format v1.0 Alignment (Summary)

See [FORMAT_SPECIFICATION_v1_0_DELTA.md](FORMAT_SPECIFICATION_v1_0_DELTA.md) for the byte-level `.imps` v0.9.0 → v1.0 delta:
1. Optional `cscEdgePerm[]` (`IMP_REL_FEATURE_CSC_EDGE_PERM`) for $O(1)$ weighted Pull-CSC in `0x34 OP_SPMV` and `0x6C OP_LANE_STATE_WALK`.
2. Explicit `SrcNodeIDWidth` in `RelationDirectoryEntry.Reserved1[0]` for mixed-width cross-domain relations.
3. Distinct unsigned base codes `0x0F..0x12` (`UINT8..UINT64`), signed `int64_t` `TIMESTAMP_MS`/`NS`, `0x13 DECIMAL64` (`Reserved1=scale`, `Reserved2=precision`), `0x14 BOOL`, and optional 64-bit `VAR_STRING` offsets (`> 4 GB` text blobs).
4. `IndexType = 0x08` (`IMP_INDEX_VECTOR_ANN`) packing `MetricType`, `IndexAlgo`, `GraphM`, `Dimension`, and `EfDefault` into `IndexDescriptor.ReservedPadding`.
5. Replace stale v0.10 `0x19`–`0x20` references in §4.4 with `0x3A OP_HAS_TOPOLOGY`.

---

## 8. JSON Attributes, Build-Time Shredding & DocumentDB-Style Indexing

- **Core Rule**: Do **not** embed a JSON parser inside ImpulseVM (preserves SIMD vectorization, zero-allocation, zero runtime deps, and 4-way `ICTX v2` parity).
- **Three-Tier JSON Strategy (Zero New Opcodes)**:
  1. **Build-Time Subcolumn Shredding (`impulse-cli`)**: Shred hot JSON paths (`meta:$.tier,$.risk_score`) into native nullable 128B-aligned SoA `.imps` columns + `0x54 OP_INDEX_SCAN` for numeric/date ranges; rewrite `json_get(...)` in CEL/ImpScheme directly to the shredded column.
  2. **Bipartite Inverted `(JsonTerm)-[:MATCHES]->(Doc)` Graph**: Key unique `(path, value)` leaf tokens (`"$.tags[]=vip"`) in Section 2 Key Catalog. Containment queries (`@>`) execute exact, zero-MVCC, zero-recheck intersections via `0x55 OP_MAP_KEYS_TO_DENSE` + `0x30 OP_WALK` + `0x22.inter` (or single-pass 64-predicate `AND` / quorum via `0x63` + `0x65`/`0x66`).
  3. **Host-Side Extraction**: Narrow candidates in-VM, `OP_COLLECT` raw `VAR_STRING` JSON blobs, and extract long-tail fields in the host (`simdjson` / Jackson).

### 8.1 `simdjson` Ingestion & `.imps` vs. Apache Lucene Segments
- **`simdjson` Role**: Keep outside `impulse-core`/`ImpulseVM` (zero-dep rule); use in `impulse-cli` for 2–4 GB/s NDJSON ingestion and `--shred-json` build-time shredding. Its `vpshufb` SIMD UTF-8 validation is directly applicable to `.imps` Section 2 string-pool validation.
- **Structural Parallel with Apache Lucene Segments**:

| Lucene Segment (Elasticsearch) | Impulse `.imps` Snapshot |
| :--- | :--- |
| Immutable `mmap` segment (`docID` `0..maxDoc-1`) | Immutable 128B-aligned `mmap` snapshot (`nodeID` `0..N_d-1`) |
| DocValues (columnar per-field arrays) | Section 3 SoA Attributes |
| Inverted Posting Lists (`Term -> [docIDs]`) | CSR Relation `(Term)-[:IN_DOC]->(Doc)` |
| BKD-Tree / HNSW `KnnVectors` | Secondary Index Directory (`ZoneMap`, `0x08 VectorANN`) |
| `MultiReader` across immutable segments | `FederatedSnapshotView` + `0x55.f_to_f` |
| `.liv` live-docs tombstone bitset | `FLAG_MASKED_S3` (`F_deleted` exclusion mask) |

- **What ES/Lucene Still Owns**: Text analysis (stemmers/tokenizers), phrase positions, fuzzy FST automata, Block-Max WAND early-terminated BM25, and 1-second NRT LSM segment compaction.
- **Where ES / Search / RAG Teams Care**: Multi-hop graph + vector + filtered-document queries (GraphRAG, SIEM/threat-hunting, entity resolution), where Elasticsearch cannot do native multi-hop joins without leaving the engine.

### 8.2 Elasticsearch / OpenSearch Plugin POC Strategy (No Core Fork Needed)
- **Why a Plugin Beats Forking**: Both Elasticsearch and OpenSearch run on Java 21+/25 JVMs and expose a clean `SearchPlugin` API (`QueryBuilder` + `Weight` + `Scorer` returning a Lucene `DocIdSetIterator` / `BitSetIterator`). Forking a multi-million-LOC Gradle monorepo isn't needed; a **~500–800 LOC plugin** embeds `impulse-graph-java` (`V11Workspace` + `V11MethodHandleCompiler`) directly inside the search node JVM over `mmap`'d `.imps` snapshots.
- **Zero-Hop Hybrid Execution**: Lucene intersects the `BitSetIterator` produced by ImpulseVM's multi-hop graph traversal directly with Lucene's BM25 full-text and `knn` scorers inside the same segment loop (mapping `.imps` `nodeID -> Lucene docID` via a cached per-`LeafReaderContext` `int[]` built once on segment open).
- **Target**: Build against **OpenSearch** first (Apache 2.0, clean JDK 21/25 plugin SDK), then mirror to Elasticsearch (`org.opensearch.*` → `org.elasticsearch.*`). Ideal benchmark showcase: single-request hybrid BM25 + 3-hop graph traversal vs. multi-round-trip ES/Neo4j pipelines.
- **Maintenance & Lifecycle (Two Tiers, Zero Core Fork)**:
  - *Tier 1 (Sidecar / Out-of-Band)*: `impulse-cli` / `impulse-platform` builds `.imps` out-of-band and atomically swaps it via `SnapshotSwapManager`.
  - *Tier 2 (Native Lucene `Codec`)*: Custom `org.apache.lucene.codecs.Codec` writes `_N.imps` on segment flush, streams-merges `_*.imps` in `Codec.merge()` via `SnapshotWriter`, registers `_N.imps` in `SegmentInfo` (inheriting shard replication and S3 snapshot backup automatically), mounts active segments via `FederatedSnapshotView` (with `docBase` offset sharing across segments of the same index), and applies `.liv` deletions via `FLAG_MASKED_S3`.
- **Headroom & Packaging**: Typical Lucene shards hold ~20–50 active segments (`TieredMergePolicy`), well within v0.11 limits (`65,536` logical domains/relations; `1,024` mounted `.imps` files in `imp_str_handle_t`). Distributed as a standard pure-Java `.zip` plugin (~1–2 MB, zero native JNI binaries) installed via `opensearch-plugin install` / `elasticsearch-plugin install`.
