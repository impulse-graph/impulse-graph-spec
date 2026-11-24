# ImpScheme v0.11.0 Normative IR Specification (`.impscm`)

> **Normative Draft (`v0.11.0-ISA-Refactor`)**
> Specifies the canonical, ISA-agnostic, storage-layout-agnostic S-Expression Intermediate Representation (`ImpScheme` v0.11) shared by all query frontends (`ImpK`, `ImpLog`, `openCypher`, language SDK builders) and all `ImpulseVM` compiler backends (C++, Java 25, Rust, OCaml).

---

## 1. Normative Design Invariants

Every conforming `ImpScheme` v0.11 parser, validator, optimizer, and backend **MUST** uphold the following five invariants:

1. **Zero Physical Storage Leakage**:
   - `ImpScheme` expresses **logical** graph operations only. Physical edge layouts (`CSR`, `CSC`, `COO`, `Dense BitMatrix`), push/pull direction switching, 3-tier frontier promotions (`Tier 0/1/2`), and secondary-index vs. BRIN scan selection are strictly backend/VM decisions.
   - Surface forms MUST NOT encode physical layouts (e.g., `(walk :fwd "FOLLOWS" ...)` instead of `(csr-walk "FOLLOWS")`; `(collect :frontier-ids ...)` instead of `(collect-bitset)`).
2. **Zero VM/ISA Leakage**:
   - `ImpScheme` MUST NOT expose register bank indices (`R0`, `F1`, `V2`, `M0`), opcode numbers, `subop` selectors, `flags:4` modifiers, or integer constant-pool/parameter slot IDs.
   - Values are bound lexically via SSA `let` bindings; host inputs are referenced by symbolic name (`$param_name`).
3. **Strict Per-Domain Static Typing (`AGENTS.md` §3.14)**:
   - There is no global node ID space. Every `Frontier<D>`, `LaneFrontier<D>`, and domain-aligned `Vector<D, T>` carries a static domain `D` resolved against `GraphCatalog`.
   - Operations combining frontiers or vectors from incompatible domains MUST be rejected at IR validation time (before codegen).
4. **Kleene Three-Valued Logic (3VL) & Canonical `NaN`**:
   - All scalar, vector, and predicate expressions obey Kleene 3VL (`true`, `false`, `null`).
   - IEEE-754 `NaN` produced by any floating-point operation canonicalizes to `null`.
   - Filtering (`node-filter`, `where`) and conditional branching (`if`) accept **only** Kleene `true` (`false` and `null` both take the non-matching / `else` path).
5. **Deterministic Semantics & Optimization Equivalence**:
   - Every well-typed `.impscm` program defines a single deterministic mathematical result independent of compiler optimization level (`opt-ON` $\equiv$ `opt-OFF`), compiler implementation (`C++` $\equiv$ `Java`), physical `.imps` layout (`CSR` vs. `CSC` vs. `COO`), and `max_dop`.

---

## 2. Lexical Structure & Concrete Grammar

### 2.1 Lexical Tokens

```ebnf
Comment     ::= ";" [^\n]* "\n"
Keyword     ::= ":" [a-z][a-z0-9_-]*
ParamRef    ::= "$" [a-zA-Z_][a-zA-Z0-9_]*
Symbol      ::= [a-zA-Z_+\-*/%<>=!?][a-zA-Z0-9_+\-*/%<>=!?.:-]*
String      ::= '"' ( [^"\\] | '\\' ["\\nrt] )* '"'
IntLit      ::= "-"? [0-9]+ ( "u" )?          (* i64 by default; suffix u -> u64 *)
FloatLit    ::= "-"? [0-9]+ "." [0-9]+ ( [eE] [+-]? [0-9]+ )? ( "f" )?  (* f64; f -> f32 *)
BoolLit     ::= "#t" | "#f"
NullLit     ::= "null"
```

### 2.2 S-Expression Grammar

```ebnf
Program     ::= "(query" ParamDecl* BodyExpr* CollectForm+ ")"
ParamDecl   ::= "(param" ParamRef TypeExpr ")"
BodyExpr    ::= LetForm | AssertForm | ThrowForm | DefineFnForm
LetForm     ::= "(let" "(" Binding+ ")" Expr+ ")"
Binding     ::= "[" Symbol Expr "]"
DefineFnForm::= "(define-fn" "(" Symbol TypedArg* ")" Expr ")"
TypedArg    ::= "[" Symbol ":" TypeExpr "]"
CollectForm ::= "(collect" CollectKind String Expr MaskOpt? ")"
CollectKind ::= ":frontier-ids" | ":frontier-bitset" | ":vec" | ":scalar" | ":table-col"
```

* **Lexical Scoping & Immutability**: Bindings introduced by `let` are immutable SSA values. Shadowing in nested `let` blocks is permitted; mutable `set!` is **not** part of `ImpScheme` v0.11 (iteration state is carried explicitly by `fixpoint` and `repeat` loop variables).

---

## 3. Static Type & Domain System

### 3.1 Type Universe

| Type Syntax | Category | Description |
| :--- | :--- | :--- |
| `i64`, `u64`, `i32`, `u32`, `f64`, `f32`, `bool`, `str`, `(decimal P S)` | **Scalar** | Nullable Kleene scalar value (maps to `R` bank). `(decimal P S)` ($1 \le P \le 18$, $0 \le S \le P$) is a fixed-point decimal lowered to scaled `i64` ($\times 10^S$). |
| `(frontier "Dom")` | **1-Bit Frontier** | Unordered set of dense node IDs in domain `"Dom"` (maps to `F` bank, $W=1$). |
| `(lane-frontier "Dom")` | **Multi-Lane Frontier** | Bit-sliced multi-lane frontier ($\le 64$ lanes) in domain `"Dom"` (maps to `F` bank, $W \in \{8..64\}$). |
| `(lane-state "Dom" T W)` | **Multi-Lane State Slab** | Cache-line-capped 2D AoS numeric state slab (`T ∈ {f32, f64}`, $W \le 64\text{ B/node}$; maps to `V` bank). |
| `(vec "Dom" T)` | **Domain-Aligned Vector** | Columnar vector of length $N_{\text{Dom}}$ and element type `T` (maps to `V` bank). |
| `(list T)` | **Compact / Ordered Vector** | Variable-length ordered vector of type `T` (e.g., top-$k$ IDs, ANN results, query embeddings; maps to `V` bank). |
| `(id "Dom")` | **Domain Node ID** | Scalar dense node ID bound to domain `"Dom"` (`u64` runtime representation). |

### 3.2 Domain Inference Rules

1. **Explicit Anchors**: `param`, `domain-all`, `seed`, `key->dense`, `index-scan`, `ids->frontier`, `lane-init-seeds`, `lane-init-groups`, and `ann-search` MUST name their target domain `"Dom"` explicitly.
2. **Relation Transitions**: Given relation `R` in `GraphCatalog` with `(src_dom, tgt_dom)`:
   - `(walk :fwd "R" f ...)` requires `f : (frontier src_dom)` and yields `(frontier tgt_dom)`.
   - `(walk :rev "R" f ...)` requires `f : (frontier tgt_dom)` and yields `(frontier src_dom)`.
   - `(walk :both "R" f ...)` and transitive forms (`:transitive+`, `:transitive*`, `:hops k`) require `src_dom == tgt_dom`.
3. **In-Domain Endomorphisms**: `set-union`, `set-intersect`, `set-diff`, `set-sym-diff`, `node-filter`, `spmv` (`:mask`), and `walk` (`:exclude`) require matching domain types on all participating frontiers/vectors.
4. **Numeric Promotion**: Implicit `int` $\leftrightarrow$ `float` coercion is **forbidden**; compilers reject mixed integer/float operands unless explicitly cast via `(cast expr T)`.

---

## 4. Control Flow, Iteration & Subroutines

| Form | Syntax | Semantics |
| :--- | :--- | :--- |
| **Conditional** | `(if cond then-expr else-expr)` | Evaluates `then-expr` iff scalar `cond` is Kleene `true` (`false` and `null` take `else-expr`). Both branches MUST have identical static types. |
| **Fixpoint Loop** | `(fixpoint ([s0 init0] ...) (:until stop-cond [:max-iters n]) body-tuple)` | Repeatedly evaluates `body-tuple` to produce next state `(s0', ...)` until `stop-cond` is `true` (typically `(frontier-eq? next prev)` or `(<= (vec-l1 next prev) eps)`) or `max-iters` is reached. Returns final state tuple. |
| **Counted Loop** | `(repeat n ([s0 init0] ...) body-tuple)` | Executes `body-tuple` `n` times (`n : i64`; `n <= 0` executes 0 times and returns `(init0, ...)`). |
| **Subroutine** | `(define-fn (f [x : T1] ...) body)` / `(call f a1 ...)` | Pure typed subroutine; backend may inline or lower to windowed `OP_CALL`/`OP_RET`. |
| **Assertions & Errors** | `(assert cond tag)` / `(throw code [detail])` | Traps with `ERR_ASSERTION_FAILED` if `cond` is not `true`, or raises deterministic `ERR_USER_THROW` with `code`. |

---

## 5. Canonical Operator Catalog

### 5.1 Anchors, Metadata & Key Mapping

| Form | Signature / Syntax | Semantics |
| :--- | :--- | :--- |
| **`domain-all`** | `(domain-all "Dom")` | Virtual full-domain frontier `[0, N_Dom)` of type `(frontier "Dom")`. |
| **`seed`** | `(seed "Dom" id-expr ...)` | Constructs `(frontier "Dom")` from 0 or more scalar node IDs (or empty if 0 args). |
| **`key->dense`** | `(key->dense "Dom" expr)` | Translates external key(s) (`str`/`u64` scalar, list, or param) via Section 2 Key Catalog to `(id "Dom")`, `(list (id "Dom"))`, or `(frontier "Dom")`. Missing keys yield `null` (scalar/list) or are omitted (frontier). |
| **`dense->key`** | `(dense->key "Dom" expr)` | Translates dense ID(s) (`id`, `list`, or `frontier`) back to external keys; preserves rank order on `list` and ascending ID order on `frontier`. |
| **`index-scan`** | `(index-scan "Dom" "attr" op val [hi])` | Secondary-index point/range query (`=`, `<`, `<=`, `>`, `>=`, `between-cc`, `between-co`) returning `(frontier "Dom")`. Transparently falls back to full-domain filter if no physical index exists. |
| **`domain-card`** | `(domain-card "Dom")` | Exact node count $N_{\text{Dom}}$ (`u64`). |
| **`rel-edges`** | `(rel-edges "REL")` | Exact edge count $M_{\text{REL}}$ (`u64`). |
| **`has-capability?`** | `(has-capability? :key-cat\|:node-attr\|:edge-attr\|:index name [attr])` | Snapshot schema capability probe (`bool`). |

### 5.2 Frontier & Set Algebra

| Form | Syntax | Semantics |
| :--- | :--- | :--- |
| **`set-union` / `set-intersect` / `set-diff` / `set-sym-diff`** | `(set-op f1 f2)` | Binary set algebra over same-domain `Frontier<D>` or `LaneFrontier<D>` (bitwise per-node on multi-lane). |
| **`set-complement`** | `(set-complement f)` | Domain-bounded complement `[0, N_D) \ f` for 1-bit `Frontier<D>`. |
| **`cardinality`** | `(cardinality f)` | Exact `u64` cardinality of 1-bit `f` (for multi-lane, use `lane-card`). |
| **`contains?`** | `(contains? f node-id)` | Scalar `bool` membership test (`null` if `node-id` is `null`). |
| **`frontier-eq?`** | `(frontier-eq? f1 f2)` | Logical membership equality (`bool`), independent of physical tier. |
| **`frontier->ids`** | `(frontier->ids f)` | Extracts ascending dense IDs into `(list (id D))`. |
| **`ids->frontier`** | `(ids->frontier "Dom" id-list)` | Scatters valid IDs from `(list ...)` into `(frontier "Dom")`. |

### 5.3 Graph Traversal, Semirings & Sampling

| Form | Syntax | Semantics |
| :--- | :--- | :--- |
| **`walk`** | `(walk dir "REL" f [:exclude excl] [:where edge-pred] [:hops k \| :transitive+ \| :transitive*])` | `dir` $\in$ `{:fwd, :rev, :both}`. Expands `f` along `"REL"`, optionally excluding `excl` at every hop and filtering edges by `edge-pred`. Backend selects `OP_WALK`, `OP_WALK_FILTERED`, or `OP_WALK_MORSEL` automatically. |
| **`degree`** | `(degree :fwd\|:rev "REL" target [:mask m])` | If `target` is `Frontier`: exact edge volume sum (`u64`). If `target` is `(id D)`: single-node degree (`u64`). If `target` is `:all`: domain-aligned degree `(vec D u64)`. |
| **`spmv`** | `(spmv :fwd\|:rev semiring "REL" f rhs [:edge-attr "w"] [:mask m] [:accum init])` | GraphBLAS semiring propagation along logical edge direction (`:fwd` = $Src \to Tgt$, `:rev` = $Tgt \to Src$). `semiring` $\in$ `{:plus-times, :min-plus, :max-plus, :max-times, :min-max, :sum-edge, :min-edge, :max-edge, :first-src, :argmin-plus}`. Deterministic under all `max_dop`. |
| **`sample-neighbors`** | `(sample-neighbors :wor\|:wr\|:rw-step\|:rw-stay "REL" seeds k seed-u64)` | Deterministic SplitMix64 + Floyd's $O(k)$ neighbor sampling / random-walk step. |
| **`graph-kernel`** | `(graph-kernel kind "REL" [:mask f] [:k k])` | `kind` $\in$ `{:cc, :kcore-nums, :kcore-frontier, :tri-count-total, :tri-count-vec}`. `:cc` canonicalizes every component label to its minimum dense node ID. |

### 5.4 Declarative Edge & Node Streams (Morsel Abstraction)

Instead of exposing VM morsel registers (`MF0..MF7`, `M0..M7`), `ImpScheme` provides two declarative stream forms. Backends lower simple single-attribute predicates to `OP_NODE_FILTER` / `OP_WALK_FILTERED` and complex multi-attribute / multi-sink expressions to `OP_WALK_MORSEL` / `OP_FILTER_MORSEL` + `OP_MORSEL_COMMIT`:

* **Node Filtering & Projection**:
  ```scheme
  (node-filter f (lambda (u) (and (> (attr u "age") 21) (str-starts-with? (attr u "email") "admin"))))
  (node-project f (lambda (u) (* (attr u "price") (- 1.0 (attr u "discount")))))
  ```
* **Multi-Sink Edge Stream (`edge-stream`)**:
  ```scheme
  (edge-stream :fwd "TRANSFER" f [:exclude visited]
    (lambda (src tgt edge)
      (where (and (> (edge-attr edge "amount") $min_amt)
                  (time-valid-at? (edge-attr edge "valid_from") (edge-attr edge "valid_to") $now)))
      (yield-frontier out_f tgt)
      (scatter-min    out_dist tgt (+ (vec-at dist src) (edge-attr edge "cost")) :accum dist)
      (count-add      out_cnt)))
  ```
  - Inside `edge-stream` / `node-filter` / `node-project`, `src`, `tgt`, `edge`, and `u` are lexical cursor variables (never raw indices).
  - Attribute reads `(attr u "name")`, `(edge-attr edge "name")`, and outer vector reads `(vec-at V u)` are pure expressions that compose arbitrarily with all §5.5 operators.

### 5.5 Polymorphic Scalar & Vector Expressions

All expression operators below work uniformly over scalars, domain-aligned vectors, lists, and stream-cursor expressions (scalar broadcasting is automatic when mixing a vector/cursor with a scalar):

* **Arithmetic**: `+`, `-`, `*`, `/`, `%`, `min`, `max`, `copysign`, `neg`, `abs`, `sqrt`, `rsqrt`, `floor`, `ceil`, `trunc`, `round` (half away from zero), `fma`, `lerp`, `clamp`, `safe-div`, `mul-div-i64` (exact 128-bit intermediate `(a * b) / c` for `(decimal P S)` scale alignment)
* **Exponential / Log / Special**: `exp`, `exp2`, `exp10`, `expm1`, `log`, `log2`, `log10`, `log1p`, `pow`, `cbrt`, `hypot`, `erf`, `erfc`, `lgamma`
* **Trig / Hyperbolic**: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `sinc`, `sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh`
* **Activations**: `relu`, `leaky-relu`, `sigmoid`, `gelu`, `silu`, `softplus`
* **Integer Bitwise**: `bit-and`, `bit-or`, `bit-xor`, `bit-not`, `bit-and-not`, `shl`, `shr-u`, `shr-s`, `rotl`, `rotr`, `popcount`, `clz`, `ctz`, `bswap`
* **Comparisons & Kleene 3VL**: `=`, `!=`, `<`, `<=`, `>`, `>=`, `between`, `in`, `and`, `or`, `not`, `xor`, `is-null?`, `is-not-null?`, `is-true?`, `is-false?`, `is-nan?`, `is-inf?`, `is-finite?`, `assert-finite!`, `coalesce`, `select` (Kleene ternary: `null` cond $\to$ `null`), `case-when` (SQL `CASE`: `false`/`null` $\to$ `else`), `time-valid-at?`
* **Strings (UTF-8 bytewise)**: `str-starts-with?`, `str-ends-with?`, `str-contains?`, `str-len` (plus `=`, `!=`, `<`, `<=`, `>`, `>=` on `str`)
* **Explicit Cast**: `(cast expr T)` (`i64`, `u64`, `i32`, `u32`, `f64`, `f32`)

### 5.6 Columnar Vectors, Reductions & Ranking

| Form | Syntax | Semantics |
| :--- | :--- | :--- |
| **`load-node-attr`** | `(load-node-attr "Dom" "attr")` | Zero-copy domain-aligned `(vec "Dom" T)`. |
| **`vec-fill`** | `(vec-fill "Dom" T val)` / `(vec-fill-len len T val)` | Allocates vector filled with `val` (supports `null`). |
| **`vec-get` / `vec-set`** | `(vec-get v idx)` / `(vec-set v idx val)` | Point read / functional COW point update (seed setup & scalar extraction only). |
| **`vec-len`** | `(vec-len v)` | $O(1)$ total length (`u64`). |
| **`gather`** | `(gather data-vec idx-vec)` | Indirect gather `out[i] = data-vec[idx-vec[i]]`. |
| **`reduce`** | `(reduce op v [:mask f])` | Deterministic reduction (`:sum`, `:min`, `:max`, `:count-valid`, `:mean`, `:l1-norm`, `:l2-norm-sq`, `:argmin`, `:argmax`, `:any-true`, `:all-true`). Lowest index breaks ties on `:argmin`/`:argmax`. |
| **`vec-l1`** | `(vec-l1 v1 v2)` | Deterministic $L_1$ distance $\sum \lvert v_1[i] - v_2[i] \rvert$ (`f64`). |
| **`top-k`** | `(top-k :desc\|:asc k scores [:mask f] [:return :ids\|:scores])` | Deterministic bounded top-$k$ (`(list ...)`). Equal scores break ties by ascending index; `null` lanes excluded. |

### 5.7 Multi-Lane Bit-Sliced & Vector ANN

| Form | Syntax | Semantics |
| :--- | :--- | :--- |
| **`lane-init-seeds`** | `(lane-init-seeds "Dom" seed-list)` | Initializes `(lane-frontier "Dom")` with $\le 64$ seeds (one lane per element). |
| **`lane-init-groups`** | `(lane-init-groups "Dom" node-list group-list)` | Initializes `(lane-frontier "Dom")` mapping each node to cohort lane `0..63`. |
| **`lane-walk`** | `(lane-walk :fwd\|:rev\|:both "REL" lanes [:exclude excl] [:edge-mask mask-vec] [:transitive+ \| :transitive*])` | Bit-sliced multi-lane propagation across up to 64 lanes simultaneously. |
| **`lane-bitwise`** | `(lane-bitwise :prune\|:keep lanes mask-u64)` / `(lane-bitwise :extract lanes k)` | Per-lane mask filtering or single-lane extraction to 1-bit `(frontier "Dom")`. |
| **`lane-quorum`** | `(lane-quorum :at-least\|:exact\|:at-most-nonzero k lanes)` | Collapses multi-lane frontier into 1-bit `(frontier "Dom")` by per-node lane popcount. |
| **`lane-reduce-and`** | `(lane-reduce-and lanes [:mask mask-u64])` | 1-bit `(frontier "Dom")` of nodes active in all required lanes (`EMPTY` if 0 active lanes). |
| **`lane-reduce-attr`** | `(lane-reduce-attr :sum\|:min\|:max\|:count lanes vec)` | Per-lane reduction returning a $K$-element `(list ...)`. |
| **`lane-card`** | `(lane-card :pop-sum\|:any-nodes\|:all-nodes\|:single-lane lanes [lane-k])` | Multi-lane cardinality metric (`u64`). |
| **`lane-state-init`** | `(lane-state-init "Dom" T W :zero\|:inf [:seeds f val] [:witness #t])` | Allocates 2D AoS `(lane-state "Dom" T W)` ($\le 64\text{ B/node}$) with optional witness parent tracking. |
| **`lane-state-walk`** | `(lane-state-walk :fwd\|:rev semiring "REL" state [:edge-attr "w"] [:fixpoint] [:delta d] [:mask f])` | Multi-lane semiring relaxation (`:min-plus`, `:max-plus`, `:max-mul`, `:sum-mul`, `:min-max`) with schedule-invariant witness tie-breaking. |
| **`lane-state-op`** | `(lane-state-op :project-affine\|:prune-cutoff\|:prune-hub-quorum\|:to-lane-frontier\|:to-quorum-frontier state ...)` | In-domain multi-lane state damping, cutoff/hub-quorum pruning, and frontier bridging. |
| **`lane-state-reduce`** | `(lane-state-reduce :min\|:max\|:sum\|:mean\|:argmin\|:argmax\|:trace-path state ...)` | Per-lane / cross-lane reduction (lowest index wins ties) or deterministic witness path reconstruction. |
| **`ann-search`** | `(ann-search "Dom" "idx" query-vec k-or-radius [:radius] [:ef ef] [:mask f])` | Queries HNSW/DiskANN index (top-$k$ or `:radius` threshold) returning rank-ordered `(list (id "Dom"))`. Ties broken by ascending dense ID. |
| **`vector-rerank`** | `(vector-rerank :dot\|:cosine\|:neg-l2-sq\|:l2-sq\|:pair-dot\|:pair-cosine\|:pair-neg-l2-sq\|:pair-l2-sq "Dom" "attr" ids rhs)` | Exact query-vs-candidate or pairwise node-to-node (also valid inside `edge-stream`) similarity scoring returning `(list f32)`. |
| **`vector-pool`** | `(vector-pool :load-node\|:mean-pool\|:sum-pool\|:l2-norm "Dom" "attr" target)` | Loads a single node's `[D]` embedding, pools a frontier centroid/sum, or L2-normalizes a vector into `(list f32)`. |

### 5.8 Terminal Collection (`collect`)

```scheme
(collect :frontier-ids    "reachable_users" f1)
(collect :frontier-bitset "mask"            f1)
(collect :vec             "scores"          v0 :mask f1)
(collect :scalar          "total"           r0)
(collect :table-col       "results.id"      ids)
(collect :table-col       "results.score"   scores :mask f1)
```

---

## 6. Canonical Examples

### 6.1 ReBAC Transitive Reachability
```scheme
(query
  (param $user     (id "User"))
  (param $resource (id "Resource"))
  (let ([groups (walk :fwd "MEMBER_OF" (seed "User" $user))]
        [all_g  (walk :fwd "GROUP_INCLUDES" groups :transitive*)]
        [res    (walk :fwd "CAN_ACCESS" all_g)])
    (collect :scalar "allowed" (contains? res $resource))))
```

### 6.2 PageRank (20 Iterations, Top-10 Results)
```scheme
(query
  (let ([all     (domain-all "Page")]
        [n_f64   (cast (domain-card "Page") f64)]
        [damping 0.85]
        [base    (/ (- 1.0 damping) n_f64)]
        [deg     (cast (degree :fwd "LINKS" :all) f64)]
        [rank0   (vec-fill "Page" f64 (/ 1.0 n_f64))]
        [final_r (repeat 20 ([r rank0])
                   (let ([contrib (safe-div r deg 0.0)]
                         [pulled  (spmv :fwd :plus-times "LINKS" all contrib)])
                     (+ (* pulled damping) base)))]
        [top10   (top-k :desc 10 final_r :return :ids)])
    (collect :vec "top_pages" (dense->key "Page" top10))))
```

### 6.3 Hybrid GraphRAG (2-Hop Neighborhood + Filtered ANN + Cosine Rerank)
```scheme
(query
  (param $anchor (id "Entity"))
  (param $q_emb  (list f32))
  (let ([hop1  (walk :fwd "RELATED" (seed "Entity" $anchor))]
        [hop2  (walk :fwd "RELATED" hop1 :exclude hop1)]
        [cand  (ann-search "Entity" "emb_idx" $q_emb 200 :mask hop2)]
        [score (vector-rerank :cosine "Entity" "embedding" cand $q_emb)]
        [pos   (top-k :desc 10 score :return :ids)]
        [top10 (gather cand pos)])
    (collect :vec "top_entities" top10)))
```

---

## 7. Compiler Lowering & E2E Test Fixture Contract

### 7.1 Required Validation Errors
Conforming `ImpScheme` validators MUST reject the following statically before bytecode generation:
* Unknown domain, relation, attribute, index, or parameter name.
* Domain mismatch on `walk`, `set-*`, `spmv`, `node-filter`, or `:mask`/`:exclude`.
* Implicit integer/float mixing without `(cast ...)`.
* Non-endo relation passed to `:both`, `:transitive+`, `:transitive*`, `:hops`, or `graph-kernel`.
* Unbound lexical symbol or arity mismatch.

### 7.2 E2E Fixture Verification (`impscm` → Compile → Execute)
E2E `.impscm` test fixtures in `impulse-graph-spec` MUST verify **semantic collected outputs**—never golden `.impas` assembly text diffs:

```scheme
; {{EXPECT: STATUS = IMPULSE_VM_OK}}
; {{EXPECT: COLLECT "allowed" = true}}
```

Every `.impscm` E2E fixture MUST pass three parity checks in `impulse-verification`:
1. **Ground-Truth Match**: Collected output matches `{{EXPECT: COLLECT ...}}`.
2. **Optimizer Soundness**: `compile(opt-ON)` and `compile(opt-OFF)` produce identical collected outputs.
3. **Cross-Compiler Parity**: C++ compiler and Java 25 compiler produce identical collected outputs (each executed on the verified v0.11 VM).

### 7.3 Deprecated v0.10 Surface Aliases (Migration Window Only)
To ease migration of existing `.impscm` scripts, parsers MAY accept the following deprecated v0.10 forms during the v0.10 $\to$ v0.11 transition and normalize them immediately during parsing:
* `(csr-walk "REL")` $\to$ `(walk :fwd "REL" ...)`
* `(csc-walk "REL")` $\to$ `(walk :rev "REL" ...)`
* `(lane-walk-csr "REL")` $\to$ `(lane-walk :fwd "REL" ...)`
* `(collect-bitset)` $\to$ `(collect :frontier-bitset "result" ...)`
* `(vector-rerank-dot ...)` $\to$ `(vector-rerank :dot ...)`
