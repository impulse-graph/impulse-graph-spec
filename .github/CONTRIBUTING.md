# Contributing to Impulse Graph Specification & Test Vectors

Thank you for your interest in contributing to the **Impulse Graph Engine** binary format specification and VM test harness.

---

## 1. Repository Overview & Scope

The `impulse-graph-spec` repository is the canonical reference source for:
- **Impulse Binary Snapshot Format (`.imps`)**: C-ABI binary layout, page headers, 128-byte alignment rules, and Section directories.
- **Impulse VM Instruction Set Architecture (`impOps`)**: Register-based opcode semantics (`0x01`..`0x6A`), instruction encodings, and operand constraints.
- **Compliance Test Vectors**: Cross-language conformance test suite (`tc01`..`tc36` and `vm-impas/`).
- **Specification Schema**: Machine-readable specification definitions (`spec/v0.9.0.yaml`).
- **Verification Harnesses**: Python test verification suite (`tools/run_vm_asm_suite.py`).

---

## 2. Specification Governance & Contribution Policies

### 2.1 Test-First Opcode Specification & Coverage Mandate
When introducing a new opcode, modifying opcode semantics, or proposing ISA extensions:
1. **Test Vectors Must Accompany the Spec**: Test vectors in `test-vectors/vm-impas/` must be defined alongside the specification change.
2. **Positive & Negative Test Vectors**:
   - **Positive Vectors**: Verify expected status `IMPULSE_VM_OK`, correct register outputs, and status flags.
   - **Negative Vectors**: Verify graceful error status codes, bounds checking, or `OP_THROW` / `OP_ASSERT` trap conditions.
3. **100% Opcode Coverage Rule**:
   Every opcode (`0x00`..`0x72`) must appear in **at least 2 distinct test files** in `test-vectors/vm-impas/`. The test suite (`run_vm_asm_suite.py`) enforces this rule in CI.

### 2.2 Dedicated Feature Branching
- All changes must be developed on dedicated feature branches (`git checkout -b feat/<feature-name>`).
- Direct pushes to `main` are prohibited.

---

## 3. Local Development & Verification

### Prerequisites
- Python 3.10+
- `pyyaml`, `pytest`

### Running the Test Suite
```bash
# 1. Install dependencies
pip install -r requirements.txt # or: pip install pyyaml pytest

# 2. Run the full VM assembly and opcode coverage test suite
python tools/run_vm_asm_suite.py

# 3. Verify specification YAML syntax
python -c "import yaml; yaml.safe_load(open('spec/v0.9.0.yaml'))"
```

---

## 4. Submitting a Pull Request

1. **Open an Issue / RFC First**: For non-trivial changes to the binary layout or new opcodes, submit a **Specification Change Proposal** or **Opcode Proposal** issue first.
2. **Ensure All Checks Pass**:
   - Spec YAML parses cleanly.
   - `python tools/run_vm_asm_suite.py` reports 100% opcode coverage and zero test failures.
3. **Submit PR**: Target the `main` branch with a clear summary of changes and rationale.
