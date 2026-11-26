# Impulse Graph Specifications & Test Vectors (v0.11.0)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

This repository contains the canonical, normative specifications, ISA tables, and shared compliance test vectors for the **Impulse Graph Engine** ecosystem. It serves as the single source of truth for all implementations (C++, Java 25, OCaml, Rust, Python, Go, Node.js, C#) of both the `.imps` binary snapshot format and the `ImpulseVM` v0.11 register-based virtual machine.

---

## Directory Structure

- **`docs/`**: Normative specifications:
  - [`FORMAT_SPECIFICATION.md`](docs/FORMAT_SPECIFICATION.md): C-ABI Binary Snapshot Specification layout (`.imps` v0.11 `0x000B`, 192B relation directory entries with dedicated 128B-aligned COO arrays, backward-compatible with v0.9/v0.10).
  - [`VM_SPECIFICATION.md`](docs/VM_SPECIFICATION.md): `ImpulseVM` v0.11 register-based virtual machine specification (256B hot frame, 3-bank `R0..R15`/`F0..F15`/`V0..V15`, 2-buffer caller-owned lifecycle, Dual ICTX v2).
  - [`SCHEMA_SPECIFICATION.md`](docs/SCHEMA_SPECIFICATION.md): Declarative graph schemas (`.imps.schema.yaml`).
- **`v0.11-refactor/`**: Canonical v0.11 ISA YAML (`isa_v0_11.yaml`, 78 active opcodes + `0xFF` extension payload, 452 subops) and generated polyglot ISA tables (`generated/{ImpulseIsaTables.java,impulse_vm_isa.hpp,impulse_isa_tables.ml,impulse_isa_tables.rs}`).
- **`test-vectors/`**: Shared compliance test vectors for cross-language verification:
  - `tc01_` to `tc38_`: Binary snapshot files (`*.imps`) covering edge cases, alignments, keys, encodings, and corruptions.
  - [`vm-impas/`](test-vectors/vm-impas/): 682 self-contained `ImpulseVM` v0.11 assembly compliance vectors across Pillars 1–5 and metamorphic geometry profiles `P0..P3`.
- **`tools/`**: Engine-agnostic specification validation, assembler, and table generation utilities:
  - [`isa_loader.py`](tools/isa_loader.py) & [`gen_isa_tables.py`](tools/gen_isa_tables.py): Single-source-of-truth ISA loader and C++/Java/OCaml/Rust codegen.
  - [`impas_assembler.py`](tools/impas_assembler.py): Canonical `.impas` → `.impb` v11 assembler.
  - [`run_vm_asm_suite.py`](tools/run_vm_asm_suite.py): Standalone `.impas` compliance runner with `--check-coverage` (enforcing 78/78 opcodes and 452/452 subops) and `--profiles P0,P1,P2,P3`.

---

## Running the Assembly Compliance & Opcode Coverage Suite

`impulse-graph-spec` has **zero downstream dependencies**. Run the full compliance and 100% opcode/subop coverage suite:

```bash
python3 tools/run_vm_asm_suite.py --check-coverage --profiles P0,P1,P2,P3
```

For four-way polyglot validation (C++ `-O3`, C++ `-O0`, Java 25, and OCaml), metamorphic testing, and contract-guided differential fuzzing, see [`impulse-verification`](https://github.com/impulse-graph/impulse-verification).
