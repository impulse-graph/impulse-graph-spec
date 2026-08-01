# Impulse Graph C-ABI Binary Snapshot Specification (v2.4)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

This repository contains the canonical, normative specification and shared test vectors for the **Impulse Graph Engine C-ABI Binary Snapshot Specification (v2.4)**.

## Directory Structure

* `docs/FORMAT_SPECIFICATION.md`: The normative C-ABI Binary Snapshot Specification v2.4 layout, header flags, alignment directives, domain key types, CSR topology encodings, and compliance rules.
* `test-vectors/`: Shared binary snapshot test vectors for polyglot implementations (C++, Java, Rust, Python, Go, C#).

## Key Specification Highlights (v2.4)

- **Header Alignment**: 64-byte header magic `0x494D5053` (`IMPS`), version `0x0002` / `0x0004` (v2.4).
- **Hardware Boundary Alignment**: 128-byte section alignment for AVX-512, GPU GPUDirect (`cuFile`), and TPU vector units.
- **Page Alignment**: 4KB page alignment support for high-throughput zero-copy `mmap` IO.
- **Feature Bitmaps**: Dual 64-bit feature bitmasks for global and per-relation capability negotiation.
- **Topology Encodings**: Compressed CSR (`RAW_UINT32`, `RAW_UINT16`, `DELTA_VBYTE`, `SIMDCOMP`, `SLICED_ELLPACK`, `TPU_BCOO`, `RAW_UINT64`, `ROARING_BITMAP`).

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
