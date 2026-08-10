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
- **`tools/`**: Verification and code generation utilities:
  - [`codegen.py`](tools/codegen.py): Emitter for C++ headers and Java FFM layout files compiled from specification schemas.
  - [`run_vm_asm_suite.py`](tools/run_vm_asm_suite.py): FFI-based test runner that executes the `.impas` unit tests against a compiled native engine library and verifies coverage.

---

## Running the Assembly Compliance Suite

To verify that a compiled native engine implementation conforms to the virtual machine specification, execute the polyglot assembly test runner:

```bash
python3 tools/run_vm_asm_suite.py
```

### Requirements
- Python 3.8+
- A compiled native library (`libimpulse_graph.dylib`, `libimpulse_graph.so`, or `impulse_graph.dll`) located in `../impulse-graph-core/impulse-cpp/build/`.
- 100% instruction set opcode coverage: The test suite verifies that every defined opcode is covered in at least two distinct `.impas` files.
