## Description

Briefly describe the specification amendment, opcode addition, or test vector update introduced by this pull request.

## Related Issues

Closes #[issue number]

## Type of Change

- [ ] 📜 Format Specification Amendment (`docs/FORMAT_SPECIFICATION.md`)
- [ ] ⚡ ImpOps Opcode / ISA Definition or Modification
- [ ] 🧪 Conformance Test Vector Addition / Fix (`test-vectors/`)
- [ ] 🛠️ Harness & Verification Tooling Update (`tools/`)
- [ ] 📝 Documentation / Typo Fix

---

## Contributor Checklist

- [ ] **Normative Specification Updated**: Any format or opcode change is documented in `docs/FORMAT_SPECIFICATION.md`.
- [ ] **Schema Updated**: `spec/v0.9.0.yaml` has been updated if binary fields, layout, or opcode enumerations changed.
- [ ] **Positive & Negative Test Vectors**: Every new/modified opcode has both expected-success and bounds/trap error test vectors in `test-vectors/vm-impas/`.
- [ ] **100% Opcode Coverage**: Every defined opcode appears in at least **2 distinct test files** in `test-vectors/vm-impas/`.
- [ ] **Local Verification Passed**: Ran `python tools/run_vm_asm_suite.py` with 0 failures.
- [ ] **YAML Validation**: Executed `python -c "import yaml; yaml.safe_load(open('spec/v0.9.0.yaml'))"` successfully.
