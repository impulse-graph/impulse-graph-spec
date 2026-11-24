# ImpulseVM v0.11.0 → v1.0 Implementation Roadmap & AI-Assisted Execution Guide

> **Status**: Frozen ISA Design (`78` active opcodes + `0xFF`), ready for M0 implementation on branch `feat/v0.11.0-ISA-Refactor`.

---

## 1. Execution Milestones (M0–M5)

Execute strictly **spec-first, oracle-gated, pillar-by-pillar** (`AGENTS.md` §3.9, §3.13, §3.18) so every step maintains equal or higher quality than v0.10:

| Milestone | Target Repos | Scope | Hard Exit Gate |
| :--- | :--- | :--- | :--- |
| **M0 — Freeze & Codegen** | `impulse-graph-spec` | Freeze `isa_v0_11.yaml` (`78 + 1` ops). Build `tools/gen_v11_tables.py` (generates OCaml, C++20, Java 25, Rust opcode/subop/flag/morsel tables from YAML) and `tools/impas_v11_assembler.py`. | 0 manual table drift across languages; assembler roundtrips all 78 opcodes + `0xFF`; GFM lint = 0. |
| **M1 — OCaml Oracle + Test Vectors** | `impulse-ocaml`, `impulse-graph-spec` | Complete `V11_eval` across all 5 pillars in `impulse-ocaml`. Author $\ge 2$ positive + $\ge 2$ negative `.impas` vectors per opcode ($\ge 156$ files). | 100% opcode coverage; OCaml `ICTX v2` `logical_hash` invariant across metamorphic profiles `P0` (Tier0), `P1` (Tier1), `P2` (Tier2), `P3` (`morsel_max=1`). |
| **M2 — Java 25 Production VM + JIT** | `impulse-graph-java` | Expand `org.impulsegraph.vm.v11` pillar-by-pillar (P1 → P2 → P3 → P4 → P5) + `V11MethodHandleCompiler` against M1 vectors. | 100% `ICTX v2` match with OCaml; JFR `0 B/query` steady-state allocation gate; JIT ≡ Interpreter on all vectors. |
| **M3 — C++20 Kernel + 4-Way Fuzzing** | `impulse-graph-core`, `impulse-verification` | Implement C-ABI `impulse_workspace_init` / `plan_memory` / `validate` / `exec` with Google Highway (`opt-ON` + `opt-OFF`, ASan/UBSan clean). | `four_way_validation.py` 100% green (`C++ ON`, `C++ OFF`, `Java 25`, `OCaml`); `fuzz_vm_contracts.py` 100k+ random programs with 0 divergences; Java $\le 2\times$ C++ parity. |
| **M4 — `ImpScheme` Backend & E2E** | `impulse-graph-core`, `impulse-graph-java`, `impulse-benchmarks` | Retarget `ImpScheme` emitter from v0.10 → v0.11 (`ImpK`, `ImpLog`, `openCypher`, Fluent SDKs stay largely unchanged). | `cross_compiler_parity.py` (`C++` ≡ `Java`, `opt-ON` ≡ `opt-OFF`); Hetionet / PowerGrid / ReBAC / Twitter-2010 benchmarks pass with equal or better latency & memory vs v0.10. |
| **M5 — Cutover & v0.11 / v1.0-RC Release** | All repos | Archive v0.10 interpreters, promote `v0.11` modules to primary, wire FFI bindings (`python`/`node`/`go`/`dotnet`/`rust`), cut SLSA-L3 CI release. | Full multi-repo CI green; signed/notarized artifacts published. |

---

## 2. Concrete Work-Tracking & PR Strategy for AI-Assisted Implementation

**Avoid both extremes**: do **not** open 80+ micro-issues (overhead swamps progress), and do **not** accumulate a 40,000-LOC mega-PR per repo (unreviewable, breaks bisecting, causes AI context drift).

### 2.1 Issue Tracking: 6 Milestone Epic Issues (One Per Milestone)
Create **6 Milestone Epic Issues** in `impulse-graph-spec` (`M0` through `M5`), each with a concise Markdown checkbox list of **Pillar-sized work units** (typically 5–7 checkboxes per epic):
- Example (`M1` Epic):
  - `[ ] M1.1 — Pillar 1 (Control, Scalar, Windows, Spills) in OCaml + .impas vectors`
  - `[ ] M1.2 — Pillar 2 (3-Tier Frontiers & Set Algebra) in OCaml + .impas vectors`
  - `[ ] M1.3 — Pillar 3 (Walks, SpMV, Lexical Morsels, Kernels) in OCaml + .impas vectors`
  - `[ ] M1.4 — Pillar 4 (Vectors, 3VL, Math, DECIMAL64, Key Bridges) in OCaml + .impas vectors`
  - `[ ] M1.5 — Pillar 5 (Multi-Lane, MITra LANE_STATE, Vector ANN/Pool) in OCaml + .impas vectors`

### 2.2 Branching & PR Cadence: Small Pillar PRs into `feat/v0.11.0-ISA-Refactor`
- Keep **`main` untouched and shippable (`v0.10.0`)** throughout M0–M4.
- Keep **`feat/v0.11.0-ISA-Refactor`** as the long-lived v0.11 integration branch in each repo.
- Implement **one Pillar (or one subsystem) per feature branch/PR** (`feat/v11-m2-p3-morsels` → PR into `feat/v0.11.0-ISA-Refactor`), targeting **500–1,500 LOC per PR**.
- At **M5**, open one clean integration PR (`feat/v0.11.0-ISA-Refactor` → `main`) per repo once every M0–M4 gate is green.

### 2.3 AI Session Operating Rules (Preventing Context Rot & Drift)
1. **One Pillar = One Fresh AI Session**: Scope each agent session to a single checkbox item (e.g., *"Implement M2.3: Java Pillar 3 opcodes `0x30`–`0x3B` and pass all M1 Pillar 3 `.impas` vectors against OCaml `ICTX v2`"*).
2. **Codegen Before Code**: Never hand-edit opcode/subop constants in C++/Java/OCaml/Rust — always regenerate from `isa_v0_11.yaml` via `gen_v11_tables.py` and verify in CI.
3. **Mandatory Verification Before Closing Any Session**:
   - Every PR must run its milestone's exact exit command (`dune runtest`, `mvn test`, `four_way_validation.py`, or `jfr view allocation-by-site`) and report empirical pass/fail numbers.
   - Never merge a Pillar PR if `ICTX v2` `logical_hash` diverges on any vector or metamorphic profile (`P0`–`P3`).
4. **Update the Epic Checkbox Immediately**: Check off the Pillar item in the Milestone Epic as soon as its PR merges into `feat/v0.11.0-ISA-Refactor`, so the next AI session starts with an exact, unambiguous handoff.
