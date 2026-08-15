# Security Policy

## Supported Versions

The Impulse Graph specification and compliance test vectors are versioned according to Semantic Versioning (`vMAJOR.MINOR.PATCH`). Security and integrity patches are applied to the following active versions:

| Specification Version | Supported |
| :--- | :--- |
| **0.9.x** | :white_check_mark: |
| < 0.9.0 | :x: (Deprecated) |

---

## Reporting a Vulnerability

We take the security and integrity of the **Impulse Binary Snapshot Format (`.imps`)** and the **Impulse VM (`impOps`)** instruction set architecture seriously. Security vulnerabilities in binary formats, alignment guarantees, bounds-checking contracts, and verification harnesses can impact downstream implementations across multiple languages (C++, Java, Rust, Python, Go, C#).

### Private Disclosure Process

> [!IMPORTANT]
> **Please do not report security vulnerabilities through public GitHub issues or discussions.**

To report a vulnerability or critical specification ambiguity:

1. **GitHub Private Vulnerability Reporting (Preferred)**:
   Navigate to the [Security Advisories tab](https://github.com/impulse-graph/impulse-graph-spec/security/advisories) and click **"Report a vulnerability"**.
2. **Security Contact**:
   If private vulnerability reporting is unavailable, email the maintainers directly at `security@impulsegraph.io` with the subject tag `[SECURITY: SPEC]`.

### Information to Include

Please provide:
- Specification section, document, or test vector identifier (e.g., `docs/FORMAT_SPECIFICATION.md#Section-2`, `tc04_alignment`).
- Description of the vulnerability, ambiguity, or potential memory safety / out-of-bounds consequence for downstream engine implementations.
- Minimal reproduction steps or sample test vector (`.impas` or `.imps`) demonstrating the condition.
- Any proposed remediation or opcode specification adjustment.

### Response & Disclosure Timeline

- **Initial Acknowledgment**: Within 48 hours of receipt.
- **Triage & Assessment**: Within 5 business days with maintainers.
- **Remediation & Advisory Release**: Coordinated with core engine (`impulse-graph-core`, `impulse-graph-java`) releases.
