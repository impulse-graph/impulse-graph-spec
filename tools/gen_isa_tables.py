#!/usr/bin/env python3
"""
Polyglot ISA Table Code Generator for ImpulseVM v0.11.0 (`impOps` v0.11).

Reads `v0.11-refactor/isa_v0_11.yaml` as the single source of truth and emits
compile-ready, zero-drift opcode/subop/flag/morsel tables for:
  - OCaml   : impulse_isa_tables.ml       (impulse-ocaml reference oracle)
  - C++20   : impulse_vm_isa.hpp  (impulse-cpp kernel, incl. X-macros & nibble macros)
  - Java 25 : ImpulseIsaTables.java       (impulse-graph-java VM & JIT)
  - Rust    : impulse_isa_tables.rs       (impulse-cli assemble/disassemble/inspect & ffi.rs)

Use `--check` in CI to fail on any drift between YAML and generated artifacts.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from isa_loader import DEFAULT_ISA_PATH, SPEC_ROOT, load_isa, valid_subop_mask

DEFAULT_OUT_DIR = SPEC_ROOT / "v0.11-refactor" / "generated"

MORSEL_ROLE_ORDER = [
    "forbidden",
    "body_ok",
    "body_cast_only",
    "body_v_only",
    "body_pair_only",
    "fwd_jump_only",
    "header",
    "commit_only",
    "end_only",
]

MORSEL_ROLE_PASCAL = {
    "forbidden": "Forbidden",
    "body_ok": "BodyOk",
    "body_cast_only": "BodyCastOnly",
    "body_v_only": "BodyVOnly",
    "body_pair_only": "BodyPairOnly",
    "fwd_jump_only": "FwdJumpOnly",
    "header": "Header",
    "commit_only": "CommitOnly",
    "end_only": "EndOnly",
}

MORSEL_ROLE_OCAML = {r: f"Morsel_{r}" for r in MORSEL_ROLE_ORDER}


def _pascal_from_upper_snake(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_") if part)


def _header_banner(comment_prefix: str, isa: dict[str, Any]) -> str:
    return (
        f"{comment_prefix} DO NOT EDIT — Auto-generated from v0.11-refactor/isa_v0_11.yaml\n"
        f"{comment_prefix} by tools/gen_isa_tables.py (impOps v{isa['isa_version']}, "
        f"impb v{isa['impb_version_u16']}).\n"
    )


# ---------------------------------------------------------------------------
# 1. OCaml Generator (impulse_isa_tables.ml)
# ---------------------------------------------------------------------------

def gen_ocaml(isa: dict[str, Any]) -> str:
    opcodes: list[dict[str, Any]] = isa["opcodes"]
    lines: list[str] = [
        "(** DO NOT EDIT — Auto-generated from v0.11-refactor/isa_v0_11.yaml",
        f"    by tools/gen_isa_tables.py (impOps v{isa['isa_version']}, impb v{isa['impb_version_u16']}). *)",
        "",
        f"let impb_magic : int32 = 0x{isa['impb_magic']:08X}l",
        f"let impb_version_u16 : int = {isa['impb_version_u16']}",
        "",
        "(** 4-bit Global Modifier Flag nibble masks. *)",
        "let flag_masked_s3 : int = 0x1",
        "let flag_scalar_rhs : int = 0x2",
        "let flag_accum : int = 0x4",
        "let flag_extended : int = 0x8",
        "",
        "(** VM Condition Flag bitmasks. *)",
        "let vm_flag_zf : int = 0x0001",
        "let vm_flag_st : int = 0x0002",
        "let vm_flag_nf : int = 0x0004",
        "",
        "(** All 80 active opcodes (across 5 pillars) plus 0xFF OP_EXTENSION_PAYLOAD. *)",
        "type opcode =",
    ]
    for op in opcodes:
        lines.append(f"  | {op['name']}")
    lines.append("")

    lines.append("type morsel_role =")
    for role in MORSEL_ROLE_ORDER:
        lines.append(f"  | {MORSEL_ROLE_OCAML[role]}")
    lines.append("")

    lines.extend([
        "type opcode_meta = {",
        "  op               : opcode;",
        "  code             : int;",
        "  name             : string;",
        "  mnemonic         : string;",
        "  pillar           : int;",
        "  allowed_flags    : int;",
        "  valid_subop_mask : int;",
        "  morsel_role      : morsel_role;",
        "}",
        "",
        "let all_opcode_meta : opcode_meta list = [",
    ])
    for op in opcodes:
        mask = valid_subop_mask(op)
        role = MORSEL_ROLE_OCAML[op["morsel_role"]]
        lines.append(
            f"  {{ op = {op['name']}; code = 0x{op['code']:02X}; name = \"{op['name']}\"; "
            f"mnemonic = \"{op['mnemonic']}\"; pillar = {op['pillar']}; "
            f"allowed_flags = 0x{op['allowed_flags']:X}; valid_subop_mask = 0x{mask:04X}; "
            f"morsel_role = {role} }};"
        )
    lines.extend([
        "]",
        "",
        "let by_code_table : opcode_meta option array =",
        "  let tbl = Array.make 256 None in",
        "  List.iter (fun m -> tbl.(m.code) <- Some m) all_opcode_meta;",
        "  tbl",
        "",
        "let code_of_opcode : opcode -> int = function",
    ])
    for op in opcodes:
        lines.append(f"  | {op['name']} -> 0x{op['code']:02X}")
    lines.extend([
        "",
        "let meta_of_opcode (op : opcode) : opcode_meta =",
        "  match by_code_table.(code_of_opcode op) with",
        "  | Some m -> m",
        "  | None -> assert false",
        "",
        "(** Typed per-opcode subop sum types with exhaustive to_int / of_int codecs. *)",
        "module Subop = struct",
    ])
    for op in opcodes:
        mod_name = _pascal_from_upper_snake(op["mnemonic"])
        lines.append(f"  module {mod_name} = struct")
        lines.append("    type t =")
        for sid in sorted(op["subops"].keys()):
            ctor = _pascal_from_upper_snake(op["subops"][sid])
            lines.append(f"      | {ctor}")
        lines.append("")
        lines.append("    let to_int : t -> int = function")
        for sid in sorted(op["subops"].keys()):
            ctor = _pascal_from_upper_snake(op["subops"][sid])
            lines.append(f"      | {ctor} -> {sid}")
        lines.append("")
        lines.append("    let of_int : int -> t option = function")
        for sid in sorted(op["subops"].keys()):
            ctor = _pascal_from_upper_snake(op["subops"][sid])
            lines.append(f"      | {sid} -> Some {ctor}")
        lines.append("      | _ -> None")
        lines.append("  end")
        lines.append("")
    lines.extend([
        "end",
        "",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. C++20 Generator (impulse_vm_isa.hpp)
# ---------------------------------------------------------------------------

def gen_cpp(isa: dict[str, Any]) -> str:
    opcodes: list[dict[str, Any]] = isa["opcodes"]
    status_codes: dict[int, str] = isa["status_codes"]
    scalar_tags: dict[int, str] = isa["scalar_type_tags"]

    lines: list[str] = [
        _header_banner("//", isa).rstrip(),
        "#pragma once",
        "",
        "#include <array>",
        "#include <cstdint>",
        "#include <string_view>",
        "",
        "// =============================================================================",
        "// 1. SQLite-Style X-Macro Opcode Lists & Zero-Cost 64-Bit Nibble Macros",
        "// =============================================================================",
        "// X(NAME, CODE, MNEMONIC, PILLAR, ALLOWED_FLAGS, VALID_SUBOP_MASK, MORSEL_ROLE)",
        "#define IMPULSE_ACTIVE_OPCODE_LIST(X) \\",
    ]
    active_ops = [op for op in opcodes if op["code"] != 0xFF]
    for i, op in enumerate(active_ops):
        mask = valid_subop_mask(op)
        role = MORSEL_ROLE_PASCAL[op["morsel_role"]]
        cont = " \\" if i + 1 < len(active_ops) else ""
        lines.append(
            f"  X({op['name']}, 0x{op['code']:02X}, {op['mnemonic']}, {op['pillar']}, "
            f"0x{op['allowed_flags']:X}, 0x{mask:04X}, {role}){cont}"
        )

    ext_op = next(op for op in opcodes if op["code"] == 0xFF)
    lines.extend([
        "",
        "#define IMPULSE_OPCODE_LIST(X) \\",
        "  IMPULSE_ACTIVE_OPCODE_LIST(X) \\",
        f"  X({ext_op['name']}, 0xFF, {ext_op['mnemonic']}, 0, 0x0, 0x0001, Forbidden)",
        "",
        "// 64-bit instruction word field extraction macros (little-endian nibble layout):",
        "// [imm32:32 | s2:4 | s3:4 | dst:4 | s1:4 | flags:4 | subop:4 | opcode:8]",
        "#define IMP_OPCODE(w)    (static_cast<uint8_t>((static_cast<uint64_t>(w)) & 0xFFULL))",
        "#define IMP_SUBOP(w)     (static_cast<uint8_t>(((static_cast<uint64_t>(w)) >> 8) & 0xFULL))",
        "#define IMP_FLAGS(w)     (static_cast<uint8_t>(((static_cast<uint64_t>(w)) >> 12) & 0xFULL))",
        "#define IMP_S1(w)        (static_cast<uint8_t>(((static_cast<uint64_t>(w)) >> 16) & 0xFULL))",
        "#define IMP_DST(w)       (static_cast<uint8_t>(((static_cast<uint64_t>(w)) >> 20) & 0xFULL))",
        "#define IMP_S3(w)        (static_cast<uint8_t>(((static_cast<uint64_t>(w)) >> 24) & 0xFULL))",
        "#define IMP_S2(w)        (static_cast<uint8_t>(((static_cast<uint64_t>(w)) >> 28) & 0xFULL))",
        "#define IMP_IMM32(w)     (static_cast<uint32_t>(((static_cast<uint64_t>(w)) >> 32) & 0xFFFFFFFFULL))",
        "#define IMP_IMM32_S(w)   (static_cast<int32_t>(IMP_IMM32(w)))",
        "#define IMP_IMM16_LO(w)  (static_cast<uint16_t>(IMP_IMM32(w) & 0xFFFFu))",
        "#define IMP_IMM16_HI(w)  (static_cast<uint16_t>((IMP_IMM32(w) >> 16) & 0xFFFFu))",
        "",
        "namespace impulse::vm {",
        "",
        f"inline constexpr uint32_t kImpbMagic = 0x{isa['impb_magic']:08X}u;",
        f"inline constexpr uint16_t kImpbVersion = {isa['impb_version_u16']}u;",
        f"inline constexpr std::size_t kActiveOpcodeCount = {len(active_ops)}u;",
        "",
        "enum ModifierFlag : uint8_t {",
        "  FLAG_MASKED_S3  = 0x1u,",
        "  FLAG_SCALAR_RHS = 0x2u,",
        "  FLAG_ACCUM      = 0x4u,",
        "  FLAG_EXTENDED   = 0x8u,",
        "};",
        "",
        "enum VmConditionFlag : uint16_t {",
        "  VM_FLAG_ZF = 0x0001u,",
        "  VM_FLAG_ST = 0x0002u,",
        "  VM_FLAG_NF = 0x0004u,",
        "};",
        "",
        "enum class Status : uint32_t {",
    ])
    for code in sorted(status_codes.keys()):
        lines.append(f"  {status_codes[code]} = {code}u,")
    lines.extend([
        "};",
        "",
        "enum class ScalarType : uint8_t {",
    ])
    for code in sorted(scalar_tags.keys()):
        lines.append(f"  {scalar_tags[code]} = {code}u,")
    lines.extend([
        "};",
        "",
        "enum class MorselRole : uint8_t {",
    ])
    for idx, role in enumerate(MORSEL_ROLE_ORDER):
        lines.append(f"  {MORSEL_ROLE_PASCAL[role]} = {idx}u,")
    lines.extend([
        "};",
        "",
        "enum class Opcode : uint8_t {",
        "#define IMP_ENUM_ENTRY(NAME, CODE, MNEM, PILLAR, FLAGS, MASK, ROLE) NAME = CODE,",
        "  IMPULSE_OPCODE_LIST(IMP_ENUM_ENTRY)",
        "#undef IMP_ENUM_ENTRY",
        "};",
        "",
        "namespace subop {",
    ])
    for op in opcodes:
        mnem = op["mnemonic"]
        for sid in sorted(op["subops"].keys()):
            sname = op["subops"][sid].upper()
            lines.append(f"inline constexpr uint8_t k{mnem}_{sname} = {sid}u;")
    lines.extend([
        "}  // namespace subop",
        "",
        "struct OpcodeMeta {",
        "  bool defined;",
        "  uint8_t code;",
        "  uint8_t pillar;",
        "  uint8_t allowed_flags;",
        "  uint16_t valid_subop_mask;",
        "  MorselRole morsel_role;",
        "  std::string_view name;",
        "  std::string_view mnemonic;",
        "};",
        "",
        "inline constexpr std::array<OpcodeMeta, 256> kOpcodeMeta = []() constexpr {",
        "  std::array<OpcodeMeta, 256> tbl{};",
        "#define IMP_META_ENTRY(NAME, CODE, MNEM, PILLAR, FLAGS, MASK, ROLE) \\",
        "  tbl[CODE] = OpcodeMeta{true, CODE, PILLAR, FLAGS, MASK, MorselRole::ROLE, #NAME, #MNEM};",
        "  IMPULSE_OPCODE_LIST(IMP_META_ENTRY)",
        "#undef IMP_META_ENTRY",
        "  return tbl;",
        "}();",
        "",
        "[[nodiscard]] constexpr uint64_t encode_word(",
        "    Opcode op, uint8_t flags, uint8_t subop,",
        "    uint8_t dst, uint8_t s1, uint8_t s2, uint8_t s3, uint32_t imm32) noexcept {",
        "  const uint64_t b0 = static_cast<uint64_t>(op) & 0xFFULL;",
        "  const uint64_t b1 = ((static_cast<uint64_t>(flags) & 0xFULL) << 4) | (static_cast<uint64_t>(subop) & 0xFULL);",
        "  const uint64_t b2 = ((static_cast<uint64_t>(dst) & 0xFULL) << 4) | (static_cast<uint64_t>(s1) & 0xFULL);",
        "  const uint64_t b3 = ((static_cast<uint64_t>(s2) & 0xFULL) << 4) | (static_cast<uint64_t>(s3) & 0xFULL);",
        "  return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24) | (static_cast<uint64_t>(imm32) << 32);",
        "}",
        "",
        "[[nodiscard]] constexpr uint64_t encode_extension_word(uint32_t imm32_hi) noexcept {",
        "  return 0xFFULL | (static_cast<uint64_t>(imm32_hi) << 32);",
        "}",
        "",
        "}  // namespace impulse::vm",
        "",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. Java 25 Generator (ImpulseIsaTables.java)
# ---------------------------------------------------------------------------

def gen_java(isa: dict[str, Any]) -> str:
    opcodes: list[dict[str, Any]] = isa["opcodes"]
    status_codes: dict[int, str] = isa["status_codes"]
    scalar_tags: dict[int, str] = isa["scalar_type_tags"]

    lines: list[str] = [
        _header_banner("//", isa).rstrip(),
        "package org.impulsegraph.vm;",
        "",
        "/** Generated normative ISA constants and metadata tables for ImpulseVM v0.11.0. */",
        "public final class ImpulseIsaTables {",
        "",
        f"    public static final int IMPB_MAGIC = 0x{isa['impb_magic']:08X};",
        f"    public static final int IMPB_VERSION = {isa['impb_version_u16']};",
        f"    public static final int ACTIVE_OPCODE_COUNT = {len(opcodes) - 1};",
        "",
        "    // Global Modifier Flags (high nibble of Byte 1)",
        "    public static final int FLAG_MASKED_S3  = 0x1;",
        "    public static final int FLAG_SCALAR_RHS = 0x2;",
        "    public static final int FLAG_ACCUM      = 0x4;",
        "    public static final int FLAG_EXTENDED   = 0x8;",
        "",
        "    // VM Condition Flags",
        "    public static final int VM_FLAG_ZF = 0x0001;",
        "    public static final int VM_FLAG_ST = 0x0002;",
        "    public static final int VM_FLAG_NF = 0x0004;",
        "",
        "    // Status Codes",
    ]
    for code in sorted(status_codes.keys()):
        lines.append(f"    public static final int {status_codes[code]} = {code};")
    lines.extend(["", "    // Scalar Type Tags"])
    for code in sorted(scalar_tags.keys()):
        lines.append(f"    public static final int {scalar_tags[code]} = {code};")
    lines.extend(["", "    // Morsel Roles"])
    for idx, role in enumerate(MORSEL_ROLE_ORDER):
        lines.append(f"    public static final int MORSEL_{role.upper()} = {idx};")
    lines.extend(["", "    // Opcodes (80 active + 0xFF extension guard)"])
    for op in opcodes:
        lines.append(f"    public static final int {op['name']} = 0x{op['code']:02X};")
    lines.extend(["", "    // Subop Constants"])
    for op in opcodes:
        mnem = op["mnemonic"]
        for sid in sorted(op["subops"].keys()):
            sname = op["subops"][sid].upper()
            lines.append(f"    public static final int SUBOP_{mnem}_{sname} = {sid};")

    lines.extend([
        "",
        "    public static final boolean[] DEFINED = new boolean[256];",
        "    public static final int[] PILLAR = new int[256];",
        "    public static final int[] ALLOWED_FLAGS = new int[256];",
        "    public static final int[] VALID_SUBOP_MASK = new int[256];",
        "    public static final int[] MORSEL_ROLE = new int[256];",
        "    public static final String[] OPCODE_NAME = new String[256];",
        "    public static final String[] OPCODE_MNEMONIC = new String[256];",
        "",
        "    static {",
    ])
    for op in opcodes:
        mask = valid_subop_mask(op)
        role_const = f"MORSEL_{op['morsel_role'].upper()}"
        lines.append(
            f"        register({op['name']}, {op['pillar']}, 0x{op['allowed_flags']:X}, "
            f"0x{mask:04X}, {role_const}, \"{op['name']}\", \"{op['mnemonic']}\");"
        )
    lines.extend([
        "    }",
        "",
        "    private static void register(int code, int pillar, int allowedFlags, int subopMask,",
        "                                 int morselRole, String name, String mnemonic) {",
        "        DEFINED[code] = true;",
        "        PILLAR[code] = pillar;",
        "        ALLOWED_FLAGS[code] = allowedFlags;",
        "        VALID_SUBOP_MASK[code] = subopMask;",
        "        MORSEL_ROLE[code] = morselRole;",
        "        OPCODE_NAME[code] = name;",
        "        OPCODE_MNEMONIC[code] = mnemonic;",
        "    }",
        "",
        "    public static long encode(int op, int flags, int subop, int dst, int s1, int s2, int s3, int imm32) {",
        "        long b0 = op & 0xFFL;",
        "        long b1 = ((flags & 0xFL) << 4) | (subop & 0xFL);",
        "        long b2 = ((dst & 0xFL) << 4) | (s1 & 0xFL);",
        "        long b3 = ((s2 & 0xFL) << 4) | (s3 & 0xFL);",
        "        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24) | ((imm32 & 0xFFFFFFFFL) << 32);",
        "    }",
        "",
        "    public static long encodeExtensionWord(int imm32Hi) {",
        "        return 0xFFL | ((imm32Hi & 0xFFFFFFFFL) << 32);",
        "    }",
        "",
        "    private ImpulseIsaTables() {}",
        "}",
        "",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Rust Generator (impulse_isa_tables.rs — for impulse-cli & ffi.rs)
# ---------------------------------------------------------------------------

def gen_rust(isa: dict[str, Any]) -> str:
    opcodes: list[dict[str, Any]] = isa["opcodes"]
    status_codes: dict[int, str] = isa["status_codes"]
    scalar_tags: dict[int, str] = isa["scalar_type_tags"]

    lines: list[str] = [
        _header_banner("//", isa).rstrip(),
        "// Generated for impulse-cli (assemble/disassemble/inspect) and impulse-rust ffi.rs.",
        "#![allow(dead_code)]",
        "",
        f"pub const IMPB_MAGIC: u32 = 0x{isa['impb_magic']:08X};",
        f"pub const IMPB_VERSION: u16 = {isa['impb_version_u16']};",
        f"pub const ACTIVE_OPCODE_COUNT: usize = {len(opcodes) - 1};",
        "",
        "pub const FLAG_MASKED_S3: u8 = 0x1;",
        "pub const FLAG_SCALAR_RHS: u8 = 0x2;",
        "pub const FLAG_ACCUM: u8 = 0x4;",
        "pub const FLAG_EXTENDED: u8 = 0x8;",
        "",
        "pub const VM_FLAG_ZF: u16 = 0x0001;",
        "pub const VM_FLAG_ST: u16 = 0x0002;",
        "pub const VM_FLAG_NF: u16 = 0x0004;",
        "",
        "#[repr(u32)]",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]",
        "pub enum Status {",
    ]
    for code in sorted(status_codes.keys()):
        lines.append(f"    {_pascal_from_upper_snake(status_codes[code])} = {code},")
    lines.extend([
        "}",
        "",
        "#[repr(u8)]",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]",
        "pub enum ScalarType {",
    ])
    for code in sorted(scalar_tags.keys()):
        lines.append(f"    {_pascal_from_upper_snake(scalar_tags[code])} = {code},")
    lines.extend([
        "}",
        "",
        "#[repr(u8)]",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]",
        "pub enum MorselRole {",
    ])
    for idx, role in enumerate(MORSEL_ROLE_ORDER):
        lines.append(f"    {MORSEL_ROLE_PASCAL[role]} = {idx},")
    lines.extend([
        "}",
        "",
        "#[repr(u8)]",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]",
        "pub enum Opcode {",
    ])
    for op in opcodes:
        lines.append(f"    {_pascal_from_upper_snake(op['name'])} = 0x{op['code']:02X},")
    lines.extend([
        "}",
        "",
        "pub mod subop {",
    ])
    for op in opcodes:
        mnem = op["mnemonic"]
        for sid in sorted(op["subops"].keys()):
            sname = op["subops"][sid].upper()
            lines.append(f"    pub const {mnem}_{sname}: u8 = {sid};")
    lines.extend([
        "}",
        "",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub struct OpcodeMeta {",
        "    pub op: Opcode,",
        "    pub code: u8,",
        "    pub pillar: u8,",
        "    pub allowed_flags: u8,",
        "    pub valid_subop_mask: u16,",
        "    pub morsel_role: MorselRole,",
        "    pub name: &'static str,",
        "    pub mnemonic: &'static str,",
        "}",
        "",
        "pub const OPCODE_META: [Option<OpcodeMeta>; 256] = {",
        "    let mut tbl: [Option<OpcodeMeta>; 256] = [None; 256];",
    ])
    for op in opcodes:
        mask = valid_subop_mask(op)
        variant = _pascal_from_upper_snake(op["name"])
        role = MORSEL_ROLE_PASCAL[op["morsel_role"]]
        lines.append(
            f"    tbl[0x{op['code']:02X}] = Some(OpcodeMeta {{ "
            f"op: Opcode::{variant}, code: 0x{op['code']:02X}, pillar: {op['pillar']}, "
            f"allowed_flags: 0x{op['allowed_flags']:X}, valid_subop_mask: 0x{mask:04X}, "
            f"morsel_role: MorselRole::{role}, name: \"{op['name']}\", mnemonic: \"{op['mnemonic']}\" }});"
        )
    lines.extend([
        "    tbl",
        "};",
        "",
        "#[inline]",
        "pub const fn encode_word(",
        "    op: Opcode, flags: u8, subop: u8, dst: u8, s1: u8, s2: u8, s3: u8, imm32: u32,",
        ") -> u64 {",
        "    let b0 = (op as u64) & 0xFF;",
        "    let b1 = (((flags as u64) & 0xF) << 4) | ((subop as u64) & 0xF);",
        "    let b2 = (((dst as u64) & 0xF) << 4) | ((s1 as u64) & 0xF);",
        "    let b3 = (((s2 as u64) & 0xF) << 4) | ((s3 as u64) & 0xF);",
        "    b0 | (b1 << 8) | (b2 << 16) | (b3 << 24) | ((imm32 as u64) << 32)",
        "}",
        "",
        "#[inline]",
        "pub const fn encode_extension_word(imm32_hi: u32) -> u64 {",
        "    0xFF | ((imm32_hi as u64) << 32)",
        "}",
        "",
    ])
    return "\n".join(lines)


TARGETS = {
    "ocaml": ("impulse_isa_tables.ml", gen_ocaml),
    "cpp": ("impulse_vm_isa.hpp", gen_cpp),
    "java": ("ImpulseIsaTables.java", gen_java),
    "rust": ("impulse_isa_tables.rs", gen_rust),
}


def generate_all(
    isa_path: Path = DEFAULT_ISA_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    targets: list[str] | None = None,
    check: bool = False,
) -> list[str]:
    isa = load_isa(isa_path)
    selected = targets if targets else list(TARGETS.keys())
    drifts: list[str] = []

    if not check:
        out_dir.mkdir(parents=True, exist_ok=True)

    for t in selected:
        if t not in TARGETS:
            raise ValueError(f"Unknown target {t!r}; choose from {list(TARGETS.keys())}")
        fname, fn = TARGETS[t]
        rendered = fn(isa)
        dest = out_dir / fname
        if check:
            if not dest.exists():
                drifts.append(f"MISSING: {dest}")
            else:
                existing = dest.read_text(encoding="utf-8")
                if existing != rendered:
                    diff = "".join(
                        difflib.unified_diff(
                            existing.splitlines(keepends=True),
                            rendered.splitlines(keepends=True),
                            fromfile=str(dest),
                            tofile=f"{dest} (generated)",
                            n=2,
                        )
                    )
                    drifts.append(f"DRIFT in {dest}:\n{diff}")
        else:
            dest.write_text(rendered, encoding="utf-8")
    return drifts


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ImpulseVM v0.11.0 ISA tables from YAML")
    parser.add_argument("--isa", type=Path, default=DEFAULT_ISA_PATH, help="Path to isa_v0_11.yaml")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory")
    parser.add_argument(
        "--targets",
        type=str,
        default=",".join(TARGETS.keys()),
        help="Comma-separated subset of: ocaml,cpp,java,rust",
    )
    parser.add_argument("--check", action="store_true", help="Fail if generated files differ")
    args = parser.parse_args()

    selected = [t.strip() for t in args.targets.split(",") if t.strip()]
    drifts = generate_all(args.isa, args.out_dir, selected, check=args.check)
    if args.check:
        if drifts:
            for d in drifts:
                print(d, file=sys.stderr)
            return 1
        print(f"OK: 0 drift across {len(selected)} generated targets in {args.out_dir}")
        return 0

    print(f"Generated {len(selected)} ISA table files in {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
