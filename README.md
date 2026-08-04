# Impulse Graph C-ABI Binary Snapshot Specification (v0.9.0)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

This repository contains the canonical, normative specification and shared test vectors for the **Impulse Graph Engine C-ABI Binary Snapshot Specification (v0.9.0)**.

## Directory Structure

* `docs/FORMAT_SPECIFICATION.md`: The normative C-ABI Binary Snapshot Specification v0.9.0 layout, header flags, alignment directives, domain key types, CSR topology rules, SoA attribute type system, and compliance rules.
* `rework-notes.md`: Architectural rework notes, S3 streaming upload design, physical block layout, and type system specs.
* `test-vectors/`: Shared binary snapshot test vectors for polyglot implementations (C++, Java, Rust, Python, Go, C#).

## Key Specification Highlights (v0.9.0)

- **Header Alignment**: Fixed 4KB Page 0 with 64-byte active baseline, magic `0x494D5053` (`IMPS`), version `0x0009` (v0.9.0).
- **Single-Pass Cloud Ingestion**: Signatures, SHA-256 digests, metadata streams, and 16-byte trailer (`footer_length` + `"IMPS"`) sit at EOF for zero-staging S3 multi-part uploads.
- **Physical Block Layout**: 4KB page-aligned Relation Blocks positioned *before* Node Domain Blocks for instant sub-microsecond topology traversal.
- **Hardware Alignment**: 128-byte alignment across all internal matrix and SoA attribute arrays for AVX-512 vector units, GPU warp memory coalescing, and GPUDirect Storage (`cuFile`).
- **Structure of Arrays (SoA) & Bitwise Nullability**: Orthogonal `type_code` with Bit 7 (`0x80`) Nullability flag (128B-aligned Validity Bitmap array) and `dimension` attribute for 0.00µs zero-copy PyTorch/NumPy 2D Tensor mappings.
- **Standardized Topology**: Always standard uncompressed CSR (`ENCODING_RAW = 0x00`), optional CSC transpose index, and explicit reverse relations.

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
