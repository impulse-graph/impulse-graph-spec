# Impulse Graph Specifications & Test Vectors (v0.9.0)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

This repository contains the canonical, normative specifications and shared compliance test vectors for the **Impulse Graph Engine** ecosystem. It serves as the single source of truth for all implementations (C++, Java 25, Rust, Python, Go, C#) of both the binary snapshot format and the register-based virtual machine query engine.

---

## Directory Structure

- **`docs/`**: Normative specifications (concise, formal specification language):
  - [`FORMAT_SPECIFICATION.md`](docs/FORMAT_SPECIFICATION.md): The normative C-ABI Binary Snapshot Specification layout, header flags, alignment, domain key types, CSR topology rules, and SoA attribute type system.
  - [`VM_SPECIFICATION.md`](docs/VM_SPECIFICATION.md): The normative register-based virtual machine specification, registers, type tagging invariants, execution state layouts, status flags, and the `impOps` instruction set directory.
  - [`SCHEMA_SPECIFICATION.md`](docs/SCHEMA_SPECIFICATION.md): The normative specification for declarative graph schemas (`.imps.schema.yaml`).
- **`spec/`**: Declarative schema definitions (e.g., [`v0.9.0.yaml`](spec/v0.9.0.yaml)) of the format used for automated C++ and Java FFM class code generation.
- **`test-vectors/`**: Shared compliance test vectors for cross-language verification:
  - `tc01_` to `tc36_`: Binary snapshot files (`*.imps`, `*.bin`) covering edge cases, alignments, keys, encodings, and corruptions.
  - [`vm-impas/`](test-vectors/vm-impas/): Self-contained ImpulseVM assembly unit test scripts (`*.impas`) organized by category (scalars, control flow, errors, graphs, and extended algorithms).
- **`tools/`**: Specification validation and code generation utilities:
  - [`codegen.py`](tools/codegen.py): Emitter for C++ headers and Java FFM layout files compiled from specification schemas (`--cpp-dir`, `--java-dir`).
  - [`run_vm_asm_suite.py`](tools/run_vm_asm_suite.py): Standalone `.impas` assembly validator and 100% opcode coverage verifier (with optional `--lib <path>` / `IMPULSE_LIB_PATH` native FFI execution mode).

---

## Running the Assembly Compliance & Opcode Coverage Suite

`impulse-graph-spec` has **zero downstream dependencies**. By default, `run_vm_asm_suite.py` parses all `.impas` assembly test vectors and verifies 100% opcode coverage and multi-file appearance thresholds statically:

```bash
python3 tools/run_vm_asm_suite.py
```

To additionally execute every `.impas` vector against a compiled C-ABI shared library:

```bash
python3 tools/run_vm_asm_suite.py --lib /path/to/libimpulse_graph.dylib
```

For cross-engine four-way polyglot validation (C++ `-O3`, C++ `-O0`, Java 25, and OCaml) and contract-guided differential fuzzing, see [`impulse-verification`](https://github.com/impulse-graph/impulse-verification).
