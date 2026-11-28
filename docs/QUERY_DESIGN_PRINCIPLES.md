# Query Language & Compiler Frontend Design Principles

> **Scope**: Normative architectural principles governing all query frontends (`openCypher`, `ImpK`, `ImpLog`, Fluent SDKs, and future declarative dialects) that compile into `ImpScheme` and execute on `ImpulseVM`.

---

## 1. Set-First Frontier Semantics by Default

Graph traversal engines that default to **bag (multiset) semantics**—tracking every distinct walk/path as an independent traverser object—suffer from silent exponential blowups on dense graphs whenever users omit explicit deduplication.

* **Principle**: Every `ImpulseVM` traversal step operates on a **deduplicated node frontier set** (`ImpulseBitSet` / sparse dense-ID set) by default.
* **Explicit Multiplicity & Path State**: When a query genuinely requires path counts, shortest-path distances, probabilities, or weights, it must opt into **explicit monoidic state propagation** (`(S, ⊕, ⊗)` via `OP_SPMV`, `OP_WALK_MORSEL`, or `OP_LANE_STATE_WALK`).
* **Bounded Path Reconstruction**: Arbitrary unbounded all-simple-paths enumeration is out of scope for the core VM; path reconstruction is bounded to deterministic shortest-path / predecessor-trace queries (`0x6C` + `0x6E`).

---

## 2. Strict Static Per-Domain Typing

Untyped, dynamically polymorphic streams—where a single traversal step can emit a heterogeneous mix of nodes from different domains, raw scalars, or edges—prevent static register allocation, break SIMD vectorization, and force runtime type dispatch on every element.

* **Per-Domain Dense ID Space**: There is no global unified node ID space. Every query must anchor to an explicit domain (`Domain`), and every frontier register `F[i]` is statically bound to a single `dom_id` at compile time.
* **Typed Relation Walks**: Every hop must name one or more explicit relations whose target domains agree. Anonymous untyped walks (`-->`) and heterogeneous mixed-domain unions (e.g., merging a `Company` frontier and a `City` frontier into a single untyped stream) are rejected at compile time.
* **Compile-Time Width & Schema Binding**: Integer ID widths (`u16` / `u32` / `u64`) and attribute column types are resolved against the `.imps` schema during compilation, never via per-element runtime reflection.

---

## 3. Canonical Compiler IR Separate from Frontend Syntax

Optimizing directly on frontend ASTs or live fluent step chains via ad-hoc rewrite passes leads to fragile pattern-matching rules that must be duplicated across every query language and SDK.

* **Single Optimization Substrate (`ImpScheme`)**: All frontends—declarative query languages (`openCypher`, `ImpLog`), array/vector DSLs (`ImpK`), and host-language fluent builders (`Traversal<T>`)—must lower to the canonical `ImpScheme` S-Expression IR before optimization and bytecode emission.
* **Frontend-Agnostic Passes**: Common subexpression elimination (CSE), partition/predicate pushdown, CSR/CSC direction selection, multi-anchor DAG scheduling, and register allocation live strictly in the `ImpScheme` pipeline so every frontend inherits them automatically.

---

## 4. No Host-Language Lambdas or Callbacks in Query Pipelines

Allowing arbitrary host-language closures (Java lambdas, Python callbacks, embedded scripting hooks) inside traversal steps breaks four core engine invariants:

1. **Cross-Language Portability**: Queries containing host closures cannot execute identically across C++, Rust, Java, Python, C#, and OCaml engines.
2. **Determinism & Vectorization**: Arbitrary host callbacks break 4-way `ICTX` determinism, morsel thread-safety, and SIMD batching (creating an N+1 FFI/callback cliff).
3. **Optimization Opacity**: The compiler cannot inspect, reorder, or push down opaque host code.
4. **Security**: Embedded scripting/closure evaluation in query strings introduces remote code execution (RCE) and injection attack surfaces.

* **Sanctioned Alternatives**:
  * **Sandboxed Predicates**: Express row/edge filters and projections via pure, side-effect-free CEL / `ImpScheme` expressions lowered to native `impOps` bytecode.
  * **Live External Data**: Bind mutable external attributes zero-copy via `OP_LOAD_PARAM.vec` external column overlays (`OP_COALESCE` for sparse overrides), or use 2-phase batched host queries.

---

## 5. Composable, IR-Backed Combinators in Fluent SDKs

Fluent host APIs (`Traversal<T>`) should be **lazy, immutable DAG builders** that expose expressive set, loop, and state combinators without leaking VM register mechanics to callers:

* **Set & Semi-Join Combinators**: `union`, `intersect`, `difference`, `where(...)` (semi-join), `whereNot(...)` (anti-join), and `coalesce(...)` (fallback).
* **Explicit Loop Control**: Distinguish exact-$k$ hops (`repeat(k, step)`), cumulative depth-$0..k$ expansion (`emit()`), predicate-gated termination (`until(predicate)`), and bounded fixpoint convergence (`repeatUntilStable(step, maxHops)`).
* **First-Class Monoidic State**: Explicit state initialization (`withState`) and branch/hop state reduction (`combineState` / `Reducer`) lowered directly to vector/semiring VM ops.

---

## 6. Immutable Storage & Layered Freshness

In-place mutable graph storage (page splits, B-tree locking, MVCC, WAL recovery inside the query kernel) is incompatible with lock-free `mmap` execution and 128-byte aligned CSR/CSC layouts.

* **Base Snapshot Immutability**: `.imps` files remain strictly immutable and read-only.
* **Layered Freshness Model** (when sub-second write visibility is required): Combine an immutable base `.imps` snapshot with:
  1. Zero-copy external column overlays (`OP_LOAD_PARAM.vec`) for live attribute mutations,
  2. Live node and edge tombstone bitmasks for instant revocations,
  3. Small L0 delta `.imps` micro-snapshots mounted via `FederatedSnapshotView`, and
  4. Background streaming compaction into a new base `.imps` swapped atomically via `SnapshotSwapManager`.
