# ImpAsm v0.11.0 Assembly Language & Test Vector Specification (`.impas`)

> **Normative Draft (`v0.11.0-ISA-Refactor`)**
> Specifies the human-readable text assembly language (`ImpAsm` v0.11), lexical register & morsel mnemonics, modifier suffixes, host-bound `.data` fixture directives (replacing all v0.10 bytecode mock opcodes), `.const_pool` literal declarations, and compliance expectation pragmas.

---

## 1. Design Principles & Key Changes from v0.10.0

1. **Typed Bank Register Tokens (`R`, `F`, `V`, `MF`, `M`)**:
   - Replaces untyped `R0..R63` with `R0..R15` (Scalar), `F0..F15` (Frontier), `V0..F15`/`V0..V15` (Vector), and inside lexical morsels `MF0..MF7` (`F8..F15`) and `M0..M7` (`V8..V15`).
   - Assembler catches bank mismatches at parse time (e.g., passing `R1` where `F[s1]` is expected without `.scalar` fails assembly immediately with line/column diagnostics).
2. **Dot-Qualified Subop & Modifier Suffixes**:
   - Every instruction follows `MNEMONIC[.subop][.accum][.scalar][.mask][.ext] operands...`, mapping 1:1 onto `[opcode:8 | flags:4 | subop:4]`.
3. **Zero Mock Opcodes in `.code`**:
   - Test graph topologies, node/edge attributes, parameters, and tier geometry overrides live exclusively in `.data` directives parsed by the test harness to construct an off-heap `VmQueryContext` + in-memory `.imps` fixture *before* `pc = 0`. The assembled `.impb` bytecode contains **only** pure production `impOps` instructions.
4. **Automatic Lexical Morsel & Branch Offset Resolution**:
   - `WALK_MORSEL` / `FILTER_MORSEL` blocks automatically compute `end_word_offset` and `MORSEL_END` `hdr_word_distance` without manual instruction counting.

---

## 2. File Structure & Section Grammar

An `.impas` v0.11 file consists of three optional declarative sections followed by `.code`, plus header expectation comments:

```impas
; {{EXPECT: STATUS = IMPULSE_VM_OK}}
; {{EXPECT: R0 = 3}}
; {{EXPECT: LOGICAL_HASH = 0x8a91f042d31c77e1}}

.data
  .domain 0 name="User" count=5 width=u32
  .domain 1 name="Item" count=4 width=u32
  .relation 0 name="PURCHASED" src_dom=0 tgt_dom=1
  .csr_inline rel=0 offsets=[0, 2, 3, 5, 5, 6] targets=[0, 1, 2, 1, 3, 3]
  .edge_attr rel=0 attr=0 name="amount" type=f64 values=[15.0, 120.0, null, 250.0, 80.0, 99.5]
  .param 0 type=frontier dom=0 values=[0, 2]
  .param 1 type=f64 value=100.0

.const_pool
  .pool 0 type=str value="ACTIVE"
  .pool 1 type=i64_vec values=[10, 20, 30]

.code
  LOAD_PARAM.frontier           F0, param=0, dom=0
  LOAD_PARAM.scalar             R1, param=1, type=f64
  WALK_FILTERED.gt              F1, F0, R1, rel=0, attr=0
  SET_CARDINALITY.card_1bit     R0, F1
  COLLECT.frontier_ids          F1, out=0
  HALT
```

---

## 3. Register Tokens & Lexical Morsel Scoping Rules

| Token Family | Encoded Nibble (`0..15`) | Legal Scope | Description |
| :--- | :--- | :--- | :--- |
| `R0` .. `R15` | `0` .. `15` | Everywhere (read-only `R0..R15` inside morsels; `dst` `R0..R7` allowed on `MORSEL_COMMIT.count_add_r`) | 64-bit scalar registers + `r_valid_mask`. |
| `F0` .. `F15` | `0` .. `15` | Outside morsels (`F0..F7` legal as read-only / `MORSEL_COMMIT` `dst` inside morsels) | Domain-bound 1-bit or multi-lane frontiers. |
| `V0` .. `V15` | `0` .. `15` | Outside morsels (`V0..F7` / `V0..V7` legal as read-only / `MORSEL_COMMIT` `dst` inside morsels) | Typed columnar / scratch vectors. |
| `MF0` .. `MF7` | `8` .. `15` (`F` bank) | **Strictly inside** `WALK_MORSEL` / `FILTER_MORSEL .. MORSEL_END` | Thread-private L1 morsel active masks (`MF0` pre-bound to `[0..L)`). |
| `M0` .. `M7` | `8` .. `15` (`V` bank) | **Strictly inside** `WALK_MORSEL` / `FILTER_MORSEL .. MORSEL_END` | Thread-private L1 morsel vectors (`M0=src_id`/`node_id`, `M1=tgt_id`, `M2=edge_idx`, `M3=lane_mask`). |

> [!WARNING]
> **Assembler Strict Alias Enforcement**: Inside a morsel block, writing raw `F8..F15` or `V8..V15` is rejected by the assembler with a diagnostic instructing the author to write `MF0..MF7` or `M0..M7`. Conversely, writing `MF0..MF7` or `M0..M7` *outside* a morsel block is a syntax error. This makes thread-private vs domain-global scope visually unmistakable in `.impas` source.

---

## 4. Instruction Syntax, Operands & Modifier Suffixes

### 4.1 Opcode, Subop & Modifier Ordering

```ebnf
Instruction ::= OPCODE ( "." SUBOP )? ( "." MODIFIER )* OperandList?
MODIFIER    ::= "accum"   (* 0x4: FLAG_ACCUM     *)
              | "scalar"  (* 0x2: FLAG_SCALAR_RHS *)
              | "mask"    (* 0x1: FLAG_MASKED_S3  *)
              | "ext"     (* 0x8: FLAG_EXTENDED   *)
```

Modifiers may appear in any order after `.subop` and are ORed into `flags:4` (duplicate modifiers in the same instruction are rejected as a syntax error).

### 4.2 Positional Register Order & Keyword Immediates

To prevent transposition bugs on multi-immediate instructions (`rel_id` vs `attr_id` vs `domain_id`), register operands are positional (`dst, s1, s2, s3` omitting unused positions) while immediate halves use explicit `key=value` tags (or bare signed/unsigned literals on single-immediate instructions like `LOAD_CONST`, `JMP`, `TRAP`, `THROW`, `ASSERT`, `LOOP_DECR`):

| Immediate Tag | Target Field | Used By |
| :--- | :--- | :--- |
| `dom=<u16>` | `imm16_lo` (or `imm16_hi` on `FSEED`, `LOAD_PARAM.frontier`, `LOAD_CONST_POOL.frontier`) | Domain-anchored ops |
| `rel=<u16>` / `rel1=<u16>` | `imm16_lo` | `WALK*`, `DEGREE`, `SPMV`, `WALK_MORSEL`, `GATHER_EDGE_ATTR`, `LANE_*`, `GRAPH_KERNEL` |
| `rel2=<u16>` | `imm16_hi` | `WALK_2HOP` |
| `attr=<u16>` | `imm16_hi` | `WALK_FILTERED`, `SPMV` (`attr=none` $\to$ `0xFFFF`), `LOAD_COLUMN`, `GATHER_*`, `NODE_FILTER`, `INDEX_SCAN`, `VECTOR_RERANK` |
| `param=<u16>` | `imm16_lo` (`imm16_hi` on `MAP_KEYS_TO_DENSE.param_to_f`) | `LOAD_PARAM`, `MAP_KEYS_TO_DENSE` |
| `pool=<u32>` | `imm32` (`imm16_lo` on `.frontier`) | `LOAD_CONST_POOL` |
| `k=<u16>` | `imm16_lo` (`imm16_hi` on `WALK.fwd_bounded`, `SAMPLE_NEIGHBORS`, `GRAPH_KERNEL.kcore_frontier`) | `TOP_K`, `LANE_FILTER_QUORUM`, `LANE_SET_COVER`, `SAMPLE_NEIGHBORS`, `WALK.fwd_bounded` |
| `slot=<u16>` | `imm16_lo` | `SPILL`, `RELOAD` |
| `out=<u16>` / `batch=<u16>`, `col=<u16>` | `imm16_lo`, `imm16_hi` | `COLLECT` |
| `idx=<u16>` | `imm16_hi` | `VECTOR_ANN_SEARCH` |

### 4.3 Canonical Assembler Pseudo-Instructions (Zero Extra Opcodes)

The assembler lowers the following ergonomic aliases directly to canonical v0.11 opcodes:

| ImpAsm Alias | Canonical Lowering | Reason |
| :--- | :--- | :--- |
| `SCALAR_3VL.cmp_gt_i64 Rd, Ra, Rb` | `SCALAR_3VL.cmp_lt_i64 Rd, Rb, Ra` | Commutes `(s1, s2)` to fit all int/uint/f64 comparators + 3VL logic in 16 subops. |
| `SCALAR_3VL.cmp_ge_i64 Rd, Ra, Rb` | `SCALAR_3VL.cmp_le_i64 Rd, Rb, Ra` | Commutes `(s1, s2)`. |
| `SCALAR_3VL.cmp_gt_u64 Rd, Ra, Rb` | `SCALAR_3VL.cmp_lt_u64 Rd, Rb, Ra` | Commutes `(s1, s2)`. |
| `SCALAR_3VL.cmp_ge_u64 Rd, Ra, Rb` | `SCALAR_3VL.cmp_le_u64 Rd, Rb, Ra` | Commutes `(s1, s2)`. |
| `SCALAR_3VL.cmp_gt_f64 Rd, Ra, Rb` | `SCALAR_3VL.cmp_lt_f64 Rd, Rb, Ra` | Commutes `(s1, s2)`. |
| `SCALAR_3VL.cmp_ge_f64 Rd, Ra, Rb` | `SCALAR_3VL.cmp_le_f64 Rd, Rb, Ra` | Commutes `(s1, s2)`. |
| `SCALAR_INT_ALU.<op>.imm Rd, Rs1, <i32>` | `SCALAR_INT_ALU.<op>` with `s3 = 1, imm32 = <i32>` | Selects immediate RHS mode cleanly. |

---

## 5. Host-Bound `.data` Section Directives (Test & Benchmark Harness)

All `.data` directives are evaluated by the test runner (`run_vm_asm_suite_v11.py` / `impas_v11_loader`) to build an immutable in-memory `.imps` v0.9.0 snapshot + `VmQueryContext` **before** invoking `impulse_vm_execute_v11`:

| Directive | Syntax & Parameters | Purpose |
| :--- | :--- | :--- |
| **`.domain`** | `.domain <id> name="<str>" count=<N> [width=u16\|u32\|u64]` | Declares node domain `<id>` with cardinality $N_d$ and physical ID width (`AGENTS.md` §3.14). |
| **`.relation`** | `.relation <id> name="<str>" src_dom=<d0> tgt_dom=<d1>` | Declares directed relation `<id>` mapping `src_dom` $\to$ `tgt_dom`. |
| **`.csr_inline`** | `.csr_inline rel=<id> offsets=[...] targets=[...]` | Populates forward CSR arrays for `rel` (validates `len(offsets) == N_src + 1` and `targets[i] < N_tgt`). |
| **`.csc_inline`** | `.csc_inline rel=<id> offsets=[...] sources=[...] [edge_perm=[...]]` | Populates reverse CSC arrays (if omitted, `auto_csc=true` may build CSC when testing push/pull). |
| **`.coo_inline`** | `.coo_inline rel=<id> sources=[...] targets=[...]` | Populates COO-only or hybrid relation layout for testing layout-independent `OP_WALK` / `OP_SPMV`. |
| **`.dense_inline`** | `.dense_inline rel=<id> rows=[[...], ...]` | Populates Dense BitMatrix layout for `rel`. |
| **`.node_attr`** | `.node_attr dom=<id> attr=<aid> [name="<str>"] type=<T> values=[v0, null, ...]` | Builds `.imps` columnar node attribute + Arrow nullability bitmap (`T` $\in$ `i8..i64, u8..u64, f32, f64, bool, str, f32_emb[D]`). |
| **`.edge_attr`** | `.edge_attr rel=<id> attr=<aid> [name="<str>"] type=<T> values=[...]` | Builds `.imps` columnar edge attribute + Arrow nullability bitmap. |
| **`.key_catalog`** | `.key_catalog dom=<id> type=str\|u64 keys=["alice", "bob", ...]` | Populates Section 2 external Key Catalog for `OP_MAP_KEYS_*` tests. |
| **`.index`** | `.index dom=<id> attr=<aid> kind=sorted\|hash\|hnsw [metric=cosine]` | Builds secondary or ANN index section in the fixture snapshot. |
| **`.param`** | `.param <pid> type=<T> [dom=<id>] value=<v> \| values=[...]` | Binds host query parameter `<pid>` in `VmQueryContext` (supports `value=null`!). |
| **`.tier_thresholds`** | `.tier_thresholds tier0_max=<n> page_shift=<p> tier2_ratio=<r> morsel_max=<m> [max_dop=<d>]` | Overrides `VmContextPool` tier promotion & morsel geometry for deterministic boundary testing on tiny graphs! |

---

## 6. Compliance Assertion Pragmas (`; {{EXPECT: ...}}`)

Test vectors declare normative post-execution assertions in leading line comments:

| Assertion Key | Example | Verified Condition |
| :--- | :--- | :--- |
| `STATUS` | `; {{EXPECT: STATUS = IMPULSE_VM_OK}}` (or `IMPULSE_VM_ERR_DOMAIN_MISMATCH`) | Exact `impulse_vm_status_v11_t` return code (or static `impulse_vm_validate` rejection code). |
| `LOGICAL_HASH` | `; {{EXPECT: LOGICAL_HASH = 0x9c21004ef812a301}}` | 64-bit `ICTX v2` tier-invariant logical digest (must match across OCaml, C++ ON/OFF, Rust, Java 25, and **all** `.tier_thresholds` profiles!). |
| `PHYSICAL_HASH` | `; {{EXPECT: PHYSICAL_HASH = 0x44b19a00cc1209ef}}` | 64-bit `ICTX v2` tier-variant digest (verified across C++, Rust, and Java 25 when executed under identical `.tier_thresholds`). |
| `R<0..15>` | `; {{EXPECT: R0 = 42}}` / `; {{EXPECT: R1 = NULL}}` / `; {{EXPECT: R2 = 0.85}}` | Post-halt scalar value and `r_valid_mask` bit. |
| `FLAGS` | `; {{EXPECT: ZF = 0, ST = 1, NF = 0}}` | Post-halt `vm_flags` bits. |
| `F<0..15>` | `; {{EXPECT: F1 = [1, 3, 4] (dom=1)}}` | Logical sorted active node IDs (or `(node:lane_hex)` pairs for multi-lane frontiers) and `domain_id`. |
| `COLLECT_<slot>` | `; {{EXPECT: COLLECT_0 = [1, 3]}}` | Terminal `OP_COLLECT` output slot content. |
