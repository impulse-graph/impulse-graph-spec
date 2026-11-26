# `.imps` Binary Snapshot Format Change Checklist (Standard Procedure)

This document is the normative multi-repository procedure for introducing any binary format change (minor version bump, directory entry expansion, new topology/attribute encoding, or feature flag) to the **Impulse Binary Snapshot Format (`.imps`)**.

Every `.imps` format change MUST complete all 8 stages below before merging to `main`.

---

## Stage 1 — Specification & Machine-Readable Schema (`impulse-graph-spec`)
- [ ] **Create new schema YAML** (`spec/v0.X.0.yaml`) derived from the previous version (`spec/v0.(X-1).0.yaml`):
  - Bump `version` packed integer (e.g., `0x000A` → `0x000B`).
  - Document exact `expected_size`, field byte offsets, alignment guarantees (128-byte section alignment for AVX-512 / GPUDirect / TPU tiles), and zero-filled reserved padding.
  - Define any new feature-flag bits (`required_features` / `section_features`) and enums.
  - Validate with `python3 -c "import yaml; yaml.safe_load(open('spec/v0.X.0.yaml'))"`.
- [ ] **Update normative prose** in `docs/FORMAT_SPECIFICATION.md` with byte-offset tables, backward-compatibility rules, and invariants.
- [ ] **Define backward-compatibility policy**:
  - Writers emit the new version `0x000X`.
  - Readers MUST continue to open all supported prior versions (`0x0009`, `0x000A`, ..., `0x000X`) without breaking existing snapshots.
- [ ] **Update `impulse-graph-spec/.github/workflows/ci.yml`** to validate the new `spec/v0.X.0.yaml`.

---

## Stage 2 — POD Struct Layouts & Compile-Time Size Assertions
- [ ] **C++20 (`impulse-graph-core/impulse-cpp/include/impulse_format_v0_X.h`)**:
  - Define `#pragma pack(push, 1)` C-ABI structs matching `spec/v0.X.0.yaml`.
  - Add `static_assert(sizeof(...) == expected_size)` and `offsetof` assertions for every modified struct.
  - Include from `include/impulse_graph.h` and update `IMPULSE_VERSION_MINOR` / `IMPULSE_VERSION_PACKED`.
- [ ] **Java 25 (`impulse-graph-java/impulse-spec/.../v0_X/ImpulseLayoutsV0_X.java`)**:
  - Define Java FFM `StructLayout`s matching exact byte offsets and field names.
  - Add JUnit test asserting `LAYOUT.byteSize() == expected_size` and exact `byteOffset(...)` parity with C++.
- [ ] **Rust (`impulse-graph-core/impulse-rust/src/spec.rs`)**:
  - Define `#[repr(C, packed)]` structs with `const _: () = assert!(core::mem::size_of::<...>() == expected_size);`.

---

## Stage 3 — Streaming Writers & Builders
- [ ] **C++20 (`impulse-graph-core/impulse-cpp/src/impulse_snapshot_writer.cpp`)**:
  - Emit new header `version` and new directory entry size.
  - Pad all new binary payload sections to **128-byte boundaries** (`O(chunk)` single-pass streaming, no random seeks).
  - Recompute CRC-16-CCITT header checksum (`0x00..0x3D`) and SHA-256 footer integrity hash.
- [ ] **Java 25 (`impulse-graph-java/impulse-storage/.../DefaultSnapshotBuilder.java` & `impulse-builder/.../StreamingSnapshotWriter.java`)**:
  - Emit identical v0.X header, directory entries, 128B-aligned payload sections, CRC-16, and SHA-256 footer.
- [ ] **Zero-filled reserved bytes**: All `reserved*` padding bytes MUST be written as `0x00`.

---

## Stage 4 — Backward-Compatible Readers & Security Hardening
- [ ] **C++20 (`impulse-graph-core/impulse-cpp/src/impulse_graph.cpp`)**:
  - Dispatch directory entry stride and field parsing on `header->version`.
  - Validate every new offset & byte size against `file_size` using overflow-safe arithmetic (`safe_mul` / `check_section_bounds`), 128-byte alignment, and valid enum ranges.
  - **Zero heap topology copies** (`engine_invariants.md`): readers MUST retain raw zero-copy pointers into `mmap_ptr`.
- [ ] **Java 25 (`impulse-graph-java/impulse-storage/.../BinarySnapshotLoader.java`)**:
  - Dispatch on `version`, validate all new bounds/alignment/enums upfront on `open()`, and slice zero-copy `MemorySegment`s directly from the mapped file segment.
- [ ] **Rust (`impulse-graph-core/impulse-rust/src/spec.rs`)**:
  - Dispatch on `version` and validate bounds cleanly without panicking on corrupt inputs.

---

## Stage 5 — VM Runtime Adapters (Zero-Copy)
- [ ] **C++20 (`impulse-graph-core/impulse-cpp/src/v11/v11_vm_dispatch.cpp`)**:
  - Bind new zero-copy pointers/metadata in `build_snapshot_view_from_imps(...)` (0 heap allocations, no topology synthesis).
- [ ] **Java 25 (`impulse-graph-java/impulse-vm/.../V11SnapshotAdapter.java`)**:
  - Bind new zero-copy `MemorySegment`s and metadata in `V11SnapshotAdapter.from(...)` (0 heap topology arrays).
- [ ] Run `python3 impulse-verification/tools/check_engine_invariants.py` — MUST report **0 violations**.

---

## Stage 6 — CLI & Developer Tooling (`impulse-cli`)
- [ ] Update `impulse-cli/src/commands/inspect.rs` to parse and print new v0.X directory fields without `BufferOverflow` or version rejection.
- [ ] Update `impulse-cli/src/commands/merge.rs` (and any other snapshot-reading subcommands) to preserve or handle v0.X entries cleanly.

---

## Stage 7 — Cross-Engine Round-Trip & Negative Compliance Verification
- [ ] **Positive cross-engine round-trip tests**:
  - C++ writes v0.X `.imps` → C++ opens & executes VM queries **AND** Java opens & executes identical bytecode with bitwise-identical output.
  - Java writes v0.X `.imps` → C++ opens & executes VM queries **AND** `impulse inspect` parses cleanly.
- [ ] **Backward-compatibility regression**:
  - Existing v0.9 / v0.10 snapshots (`tc01`..`tc37`, benchmark datasets) continue to open and execute identically in C++, Java, and Rust.
- [ ] **Negative / hardening tests**:
  - Truncated payload, misaligned offset, invalid enum value, integer-overflow byte count, and missing required topology all fail gracefully with explicit error status codes (no crash / UB / OOB read).
- [ ] **Full regression gates**:
  - `run_vm_asm_suite_v11.py --check-coverage` (100% pass).
  - `test_v11_morsel_stress.py` (3-way OCaml/Java/C++ pass).
  - `ctest` (C++), `mvn test` (Java), `cargo test` (Rust).

---

## Stage 8 — Submodule Bumps, Docs & Release Hygiene
- [ ] Bump `spec/` submodules in `impulse-graph-core`, `impulse-graph-java`, `impulse-ocaml`, and `impulse-verification` once `impulse-graph-spec` commits land.
- [ ] Update `impulse-website` format specification pages and root `AGENTS.md` if the canonical version number changes.
- [ ] Verify zero heavy `.imps` / `.tsv` / `.csv` files are staged in Git (`AGENTS.md` §3.6).
