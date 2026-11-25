#!/usr/bin/env python3
"""
ImpAsm v0.11.0 Two-Pass Assembler, Disassembler, Fixture Parser & `.impb` v11 Codec.

Driven directly from `v0.11-refactor/isa_v0_11.yaml` via `tools/v11_isa_loader.py`
(zero duplicated opcode tables). Implements `IMPAS_SPECIFICATION_v0_11.md`:
  - Header `; {{EXPECT: ...}}` compliance pragmas
  - Host-bound `.data` and `.const_pool` fixture directives
  - Two-pass `.code` assembly (labels, PC-relative branches, automatic morsel offsets)
  - Strict register bank & lexical morsel alias enforcement (`MF0..MF7`, `M0..M7`)
  - Canonical pseudo-instruction lowering (`SCALAR_3VL.cmp_gt/ge_*`, `SCALAR_INT_ALU.*.imm`)
  - 128-bit `FLAG_EXTENDED` + `0xFF OP_EXTENSION_PAYLOAD` encoding/decoding
  - Lossless disassembler and `.impb` v11 binary container pack/unpack
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from v11_isa_loader import DEFAULT_ISA_PATH, load_isa, valid_subop_mask

# Modifier flag nibble masks (high nibble of Byte 1)
FLAG_MASK = 0x1
FLAG_SCALAR = 0x2
FLAG_ACCUM = 0x4
FLAG_EXT = 0x8

MODIFIER_MAP = {
    "mask": FLAG_MASK,
    "scalar": FLAG_SCALAR,
    "accum": FLAG_ACCUM,
    "ext": FLAG_EXT,
}
MODIFIER_ORDER = [("accum", FLAG_ACCUM), ("scalar", FLAG_SCALAR), ("mask", FLAG_MASK), ("ext", FLAG_EXT)]

SCALAR_TYPE_NAMES = {
    "null": 0,
    "unset": 0,
    "i64": 1,
    "u64": 2,
    "f64": 3,
    "bool": 4,
    "bool_3vl": 4,
    "str": 5,
    "str_handle": 5,
    "f32": 6,
    "f32_raw": 6,
}

# Canonical pseudo-instruction commute table (IMPAS_SPECIFICATION_v0_11.md §4.3)
SCALAR_3VL_COMMUTE = {
    "cmp_gt_i64": "cmp_lt_i64",
    "cmp_ge_i64": "cmp_le_i64",
    "cmp_gt_u64": "cmp_lt_u64",
    "cmp_ge_u64": "cmp_le_u64",
    "cmp_gt_f64": "cmp_lt_f64",
    "cmp_ge_f64": "cmp_le_f64",
}

EXPECT_RE = re.compile(r"^\s*;\s*\{\{EXPECT:\s*(.+?)\s*\}\}\s*$")
REG_RE = re.compile(r"^(MF|M|R|F|V)([0-9]+)$")

# Opcodes where s3 is purely a mask register (must be 0 when FLAG_MASK is unset)
MASK_S3_ONLY_CODES = frozenset({
    0x30, 0x31, 0x33, 0x35, 0x37, 0x3B,
    0x41, 0x42, 0x43, 0x45, 0x46, 0x47,
    0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4F,
    0x52, 0x53, 0x57, 0x69, 0x6A,
})


class AsmError(ValueError):
    def __init__(self, message: str, line_no: int | None = None):
        self.line_no = line_no
        prefix = f"Line {line_no}: " if line_no is not None else ""
        super().__init__(f"{prefix}{message}")


@dataclass
class ParsedProgram:
    expectations: list[dict[str, Any]] = field(default_factory=list)
    data_directives: list[dict[str, Any]] = field(default_factory=list)
    const_pool: list[dict[str, Any]] = field(default_factory=list)
    words: list[int] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)


def encode_word(
    code: int, flags: int, subop: int, dst: int, s1: int, s2: int, s3: int, imm32: int
) -> int:
    b0 = code & 0xFF
    b1 = ((flags & 0xF) << 4) | (subop & 0xF)
    b2 = ((dst & 0xF) << 4) | (s1 & 0xF)
    b3 = ((s2 & 0xF) << 4) | (s3 & 0xF)
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24) | ((imm32 & 0xFFFFFFFF) << 32)


def encode_extension_word(imm32_hi: int) -> int:
    return 0xFF | ((imm32_hi & 0xFFFFFFFF) << 32)


def decode_word_fields(w: int) -> tuple[int, int, int, int, int, int, int, int]:
    code = w & 0xFF
    subop = (w >> 8) & 0xF
    flags = (w >> 12) & 0xF
    s1 = (w >> 16) & 0xF
    dst = (w >> 20) & 0xF
    s3 = (w >> 24) & 0xF
    s2 = (w >> 28) & 0xF
    imm32 = (w >> 32) & 0xFFFFFFFF
    return code, flags, subop, dst, s1, s2, s3, imm32


def u32_to_i32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def pack_impb(words: list[int], magic: int = 0x494D5042, version: int = 11) -> bytes:
    header = struct.pack("<IHHII", magic, version, 0, len(words), 0)
    body = struct.pack(f"<{len(words)}Q", *(w & 0xFFFFFFFFFFFFFFFF for w in words)) if words else b""
    return header + body


def unpack_impb(blob: bytes, expected_magic: int = 0x494D5042, expected_version: int = 11) -> list[int]:
    if len(blob) < 16:
        raise AsmError(f"Truncated .impb header ({len(blob)} bytes)")
    magic, version, _flags, word_count, reserved = struct.unpack("<IHHII", blob[:16])
    if magic != expected_magic:
        raise AsmError(f"Invalid .impb magic: 0x{magic:08X} (expected 0x{expected_magic:08X})")
    if version != expected_version:
        raise AsmError(f"Unsupported .impb version: {version} (expected {expected_version})")
    if reserved != 0:
        raise AsmError(f"Non-zero reserved field in .impb header: 0x{reserved:08X}")
    expected_len = 16 + word_count * 8
    if len(blob) != expected_len:
        raise AsmError(f".impb size mismatch: got {len(blob)} bytes, expected {expected_len}")
    if word_count == 0:
        return []
    return list(struct.unpack(f"<{word_count}Q", blob[16:]))


def resolve_banks(op: dict[str, Any], subop: int, flags: int) -> dict[str, str]:
    """Resolve concrete expected bank for each of (dst, s1, s2, s3).

    Returns values from: 'NONE', 'R', 'F', 'V', 'OPT_R', 'OPT_F', 'OPT_V',
    'STRIDE_IMM', 'IMM_MODE_TAG'.
    """
    code = op["code"]
    raw = dict(op["banks"])
    has_scalar = (flags & FLAG_SCALAR) != 0
    has_mask = (flags & FLAG_MASK) != 0

    def _default_slot(slot: str, spec: str) -> str:
        if spec == "MASK_F":
            return "F" if has_mask else "NONE"
        if spec == "V_OR_R":
            return "R" if has_scalar else "V"
        if spec == "OPT_V_OR_R":
            return "OPT_R" if has_scalar else "OPT_V"
        return spec

    res = {k: _default_slot(k, v) for k, v in raw.items()}

    # Exact subop-dependent bank resolution matching isa_v0_11.yaml & OPCODE_CATALOG_v0_11.md
    if code == 0x03:  # THROW
        res["s1"] = "R" if subop == 1 else "NONE"
    elif code == 0x04:  # ASSERT
        if subop in (0, 6, 7):
            res["s1"] = "R"
        elif subop in (1, 2):
            res["s1"] = "F"
        else:
            res["s1"] = "NONE"
    elif code == 0x06:  # LOAD_CONST_POOL
        res["dst"] = {0: "V", 1: "F", 2: "R"}[subop]
    elif code == 0x07:  # LOAD_PARAM
        res["dst"] = {0: "R", 1: "F", 2: "V"}[subop]
    elif code == 0x08:  # MOV
        if subop == 0:
            res["dst"], res["s1"] = "R", "R"
        elif subop == 1:
            res["dst"], res["s1"] = "F", "F"
        elif subop == 2:
            res["dst"], res["s1"] = "V", "V"
        elif subop == 3:
            res["dst"], res["s1"] = "R", "NONE"
        elif subop == 4:
            res["dst"], res["s1"] = "F", "NONE"
        elif subop == 5:
            res["dst"], res["s1"] = "V", "NONE"
    elif code == 0x09:  # SWAP
        bank = {0: "R", 1: "F", 2: "V"}[subop]
        res["dst"], res["s1"] = bank, bank
    elif code == 0x0A:  # SPILL
        res["s1"] = {0: "R", 1: "F", 2: "V"}[subop]
    elif code == 0x0B:  # RELOAD
        res["dst"] = {0: "R", 1: "F", 2: "V"}[subop]
    elif code == 0x0C:  # SCALAR_INT_ALU
        if subop == 10:  # not (unary)
            res["s2"] = "NONE"
            res["s3"] = "NONE"
        else:
            res["s2"] = "OPT_R"
            res["s3"] = "IMM_MODE_TAG"
    elif code == 0x10:  # JCC
        if subop in (6, 7):
            res["s1"] = "R"
        elif subop in (8, 9):
            res["s1"] = "F"
        else:
            res["s1"] = "NONE"
    elif code == 0x12:  # CALL
        if subop == 1:  # full16
            res["s1"] = res["s2"] = res["s3"] = "NONE"
    elif code == 0x14:  # SET_MAX_DOP
        res["s1"] = "R" if subop == 1 else "NONE"
    elif code == 0x20:  # FSEED
        res["s1"] = "R" if subop in (2, 3, 4) else "NONE"
    elif code == 0x26:  # SET_CONVERT
        if subop == 0:  # f2v_ids
            res["dst"], res["s1"] = "V", "F"
        elif subop == 1:  # v2f_ids
            res["dst"], res["s1"] = "F", "V"
        elif subop == 2:  # b2f
            res["dst"], res["s1"] = "F", "V"
        elif subop == 3:  # f2b
            res["dst"], res["s1"] = "V", "F"
    elif code == 0x27:  # STABLE_CHECK
        if subop == 0:  # frontier_eq
            res["dst"], res["s1"], res["s2"], res["s3"] = "NONE", "F", "F", "NONE"
        else:  # vec_l1
            res["dst"], res["s1"], res["s2"], res["s3"] = "R", "V", "V", "OPT_R"
    elif code == 0x33:  # DEGREE
        if subop in (0, 1):
            res["dst"], res["s1"] = "R", "F"
        elif subop in (2, 3):
            res["dst"], res["s1"] = "V", "NONE"
        else:
            res["dst"], res["s1"] = "R", "R"
    elif code == 0x34:  # SPMV
        if subop == 7:  # fwd_first_src
            res["s2"] = "NONE"
    elif code == 0x37:  # MORSEL_COMMIT
        if subop == 0:  # yield_frontier
            res["dst"], res["s1"], res["s2"] = "F", "V", "NONE"
        elif subop == 1:  # yield_lane_or
            res["dst"], res["s1"] = "F", "V"
        elif subop == 8:  # count_add_r
            res["dst"], res["s1"], res["s2"] = "R", "NONE", "NONE"
        else:
            res["dst"], res["s1"] = "V", "V"
    elif code == 0x39:  # SAMPLE_NEIGHBORS
        if subop == 0:  # frontier_wor
            res["dst"], res["s1"] = "F", "F"
        else:
            res["dst"], res["s1"] = "V", "V"
    elif code == 0x3B:  # GRAPH_KERNEL
        if subop in (0, 1, 4):
            res["dst"] = "V"
        elif subop == 2:
            res["dst"] = "F"
        elif subop == 3:
            res["dst"] = "R"
    elif code == 0x41:  # GATHER_NODE_ATTR
        if subop == 0:
            res["dst"], res["s1"] = "V", "V"
        elif subop == 1:
            res["dst"], res["s1"] = "V", "F"
        else:
            res["dst"], res["s1"] = "R", "R"
    elif code == 0x42:  # GATHER_EDGE_ATTR
        if subop == 0:
            res["dst"], res["s1"] = "V", "V"
        else:
            res["dst"], res["s1"] = "R", "R"
    elif code == 0x45:  # VEC_CMP
        if subop == 6:  # between
            res["s2"] = "R" if has_scalar else "V"
            res["s3"] = "R" if has_scalar else "V"
        elif subop == 7:  # in_set
            res["s2"] = "F"
            res["s3"] = "F" if has_mask else "NONE"
        else:
            res["s2"] = "R" if has_scalar else "V"
            res["s3"] = "F" if has_mask else "NONE"
    elif code == 0x46:  # VEC_3VL_OP
        if subop == 11:  # assert_finite
            res["dst"], res["s2"] = "NONE", "NONE"
        elif subop not in (0, 1, 3):  # unary 3VL/IEEE predicates
            res["s2"] = "NONE"
    elif code == 0x48 and subop >= 8:  # VEC_MATH_ARITH unary
        res["s2"] = "NONE"
    elif code == 0x49 and subop not in (8, 10):  # VEC_MATH_EXP_LOG unary
        res["s2"] = "NONE"
    elif code == 0x4A and subop != 6:  # VEC_MATH_TRIG_HYP unary
        res["s2"] = "NONE"
    elif code == 0x4B and subop != 1:  # VEC_MATH_ACT unary
        res["s2"] = "NONE"
    elif code == 0x4C and subop in (3, 10, 11, 12, 13):  # VEC_INT_BITWISE unary
        res["s2"] = "NONE"
    elif code == 0x4D:  # VEC_TERNARY
        if subop in (0, 2, 4, 6):
            res["s3"] = "V"
        else:  # *_r, time_valid_at_r, mul_div_i64_r
            res["s3"] = "R"
    elif code == 0x4E:  # VEC_BLEND
        res["s3"] = "V" if subop in (0, 2) else "R"
    elif code == 0x51:  # VEC_POINT
        if subop == 0:  # vec_get
            res["dst"], res["s1"], res["s2"] = "R", "V", "R"
        elif subop == 1:  # vec_set
            res["dst"], res["s1"], res["s2"] = "V", "R", "R"
        elif subop == 2:  # vec_cast
            res["dst"], res["s1"], res["s2"] = "V", "V", "NONE"
        elif subop == 3:  # vec_len
            res["dst"], res["s1"], res["s2"] = "R", "V", "NONE"
    elif code == 0x55:  # MAP_KEYS_TO_DENSE
        if subop == 0:  # param_to_f
            res["dst"], res["s1"] = "F", "NONE"
        elif subop in (1, 4):  # vec_to_v, v_to_v
            res["dst"], res["s1"] = "V", "V"
        elif subop == 2:  # scalar_to_r
            res["dst"], res["s1"] = "R", "R"
        elif subop == 3:  # f_to_f
            res["dst"], res["s1"] = "F", "F"
    elif code == 0x56:  # MAP_DENSE_TO_KEYS
        if subop == 0:
            res["dst"], res["s1"] = "V", "V"
        elif subop == 1:
            res["dst"], res["s1"] = "V", "F"
        else:
            res["dst"], res["s1"] = "R", "R"
    elif code == 0x57:  # COLLECT
        if subop in (0, 1):
            res["s1"] = "F"
        elif subop in (2, 4):
            res["s1"] = "V"
        else:
            res["s1"] = "R"
    elif code == 0x63:  # LANE_WALK
        if subop == 8:
            res["s2"] = "NONE"
    elif code == 0x64:  # LANE_BITWISE
        if subop in (0, 1):  # prune_mask, keep_mask
            res["s2"] = "R" if has_scalar else "OPT_R"
        elif subop == 2:  # and_not_lanes
            res["s2"] = "F"
        else:  # extract_lane
            res["s2"] = "R" if has_scalar else "NONE"
    elif code == 0x6D:  # LANE_STATE_OP
        if subop in (3, 4):  # to_lane_frontier, to_quorum_frontier
            res["dst"] = "F"
        else:
            res["dst"] = "V"
    elif code == 0x6E:  # LANE_STATE_REDUCE
        res["s1"] = "V"
    elif code == 0x6F:  # VECTOR_POOL
        if subop == 0:  # load_node
            res["s1"] = "R"
        elif subop in (1, 2):  # mean_pool, sum_pool
            res["s1"] = "F"
        else:  # l2_norm
            res["s1"] = "V"

    return res


def validate_word_semantics(
    op: dict[str, Any],
    flags: int,
    subop: int,
    dst: int,
    s1: int,
    s2: int,
    s3: int,
    imm32: int,
    line_no: int | None = None,
) -> None:
    """Enforce opcode-specific flag coupling and MBZ invariants matching OCaml V11_isa.decode_word."""
    code = op["code"]
    imm16_lo = imm32 & 0xFFFF
    imm16_hi = (imm32 >> 16) & 0xFFFF
    has_ext = (flags & FLAG_EXT) != 0
    has_accum = (flags & FLAG_ACCUM) != 0
    has_scalar = (flags & FLAG_SCALAR) != 0
    has_mask = (flags & FLAG_MASK) != 0

    if (valid_subop_mask(op) & (1 << subop)) == 0:
        raise AsmError(f"{op['mnemonic']}: invalid subop {subop}", line_no)
    if (flags & (~op["allowed_flags"] & 0xF)) != 0:
        raise AsmError(
            f"{op['mnemonic']}: disallowed modifier flags 0x{flags:X} (allowed 0x{op['allowed_flags']:X})",
            line_no,
        )

    if code in (0x00, 0x01, 0x13):  # HALT, NOP, RET
        if dst or s1 or s2 or s3 or imm32:
            raise AsmError(f"{op['mnemonic']}: non-zero MBZ operand field", line_no)
    elif code == 0xFF:  # EXTENSION_PAYLOAD
        if flags or subop or dst or s1 or s2 or s3:
            raise AsmError("OP_EXTENSION_PAYLOAD: ext_meta24 must be zero", line_no)
    elif code == 0x05:  # LOAD_CONST
        is_ext_subop = 4 <= subop <= 6
        if is_ext_subop != has_ext:
            raise AsmError(
                f"LOAD_CONST.{op['subops'][subop]}: FLAG_EXTENDED mismatch (requires_ext={is_ext_subop})",
                line_no,
            )
        if subop == 7 and imm32 != 0:
            raise AsmError("LOAD_CONST.null: imm32 must be 0", line_no)
        if s1 or s2 or s3:
            raise AsmError("LOAD_CONST: s1/s2/s3 must be 0", line_no)
    elif code in (0x0A, 0x0B):  # SPILL, RELOAD
        if imm16_lo >= 16 or imm16_hi != 0:
            raise AsmError(f"{op['mnemonic']}: spill slot must be 0..15 with imm16_hi=0", line_no)
    elif code == 0x0F:  # JMP
        if dst or s1 or s2 or s3:
            raise AsmError("JMP: dst/s1/s2/s3 must be 0", line_no)
    elif code == 0x34:  # SPMV
        if subop >= 7 and has_accum:
            raise AsmError("SPMV: subop >= 7 forbids .accum", line_no)
        if not has_mask and s3 != 0:
            raise AsmError("SPMV: s3 must be 0 without .mask", line_no)
    elif code == 0x45 and subop == 6:  # VEC_CMP.between
        if has_mask or imm32 != 0:
            raise AsmError("VEC_CMP.between: forbids .mask and requires imm32=0", line_no)
    elif code == 0x45 and subop == 7:  # VEC_CMP.in_set
        if has_scalar or (not has_mask and s3 != 0):
            raise AsmError("VEC_CMP.in_set: forbids .scalar and requires s3=0 without .mask", line_no)
    elif code == 0x4D and subop == 8:  # VEC_TERNARY.time_valid_at_r
        if has_scalar:
            raise AsmError("VEC_TERNARY.time_valid_at_r: forbids .scalar", line_no)
    elif code == 0x50:  # VEC_INIT
        if s1 != 0:
            raise AsmError("VEC_INIT: s1 must be 0", line_no)
    elif code == 0x63:  # LANE_WALK
        if (subop == 8 and s2 != 0) or (not has_mask and s3 != 0):
            raise AsmError("LANE_WALK: invalid s2/s3 MBZ field", line_no)
    elif code == 0x6C:  # LANE_STATE_WALK
        if subop in (3, 8) and has_scalar:
            raise AsmError("LANE_STATE_WALK.*_sum_mul: forbids .scalar", line_no)
        if not has_mask and s3 != 0:
            raise AsmError("LANE_STATE_WALK: s3 must be 0 without .mask", line_no)
    elif code in MASK_S3_ONLY_CODES:
        if not has_mask and s3 != 0:
            raise AsmError(f"{op['mnemonic']}: s3 must be 0 without .mask", line_no)


def _strip_asm_comment(line: str) -> str:
    in_str = False
    escaped = False
    for i, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_str:
            escaped = True
            continue
        if ch == '"':
            in_str = not in_str
        elif ch == ";" and not in_str:
            return line[:i]
    return line


def _split_operands(text: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    in_str = False
    escaped = False
    for ch in text:
        if escaped:
            cur.append(ch)
            escaped = False
            continue
        if ch == "\\" and in_str:
            cur.append(ch)
            escaped = True
            continue
        if ch == '"':
            in_str = not in_str
            cur.append(ch)
        elif not in_str:
            if ch in "[{(":
                depth += 1
                cur.append(ch)
            elif ch in "]})":
                depth -= 1
                cur.append(ch)
            elif ch == "," and depth == 0:
                tok = "".join(cur).strip()
                if tok:
                    out.append(tok)
                cur = []
            else:
                cur.append(ch)
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        out.append(tail)
    return out


def _parse_data_value(val: str) -> Any:
    s = val.strip()
    if s == "null":
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_data_value(item) for item in _split_operands(inner)]
    if re.fullmatch(r"-?0[xX][0-9a-fA-F]+", s):
        return int(s, 16)
    if re.fullmatch(r"-?[0-9]+", s):
        return int(s, 10)
    if re.fullmatch(r"-?[0-9]+\.[0-9]+([eE][+-]?[0-9]+)?", s):
        return float(s)
    return s


def _parse_directive(line: str, line_no: int) -> dict[str, Any]:
    # Tokenize respecting quotes and brackets
    tokens: list[str] = []
    cur: list[str] = []
    depth = 0
    in_str = False
    escaped = False
    for ch in line.strip():
        if escaped:
            cur.append(ch)
            escaped = False
            continue
        if ch == "\\" and in_str:
            cur.append(ch)
            escaped = True
            continue
        if ch == '"':
            in_str = not in_str
            cur.append(ch)
        elif not in_str:
            if ch in "[{(":
                depth += 1
                cur.append(ch)
            elif ch in "]})":
                depth -= 1
                cur.append(ch)
            elif ch.isspace() and depth == 0:
                if cur:
                    tokens.append("".join(cur))
                    cur = []
            else:
                cur.append(ch)
        else:
            cur.append(ch)
    if cur:
        tokens.append("".join(cur))
    if not tokens or not tokens[0].startswith("."):
        raise AsmError(f"Invalid directive: {line!r}", line_no)
    entry: dict[str, Any] = {"directive": tokens[0], "args": [], "kv": {}}
    for tok in tokens[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            entry["kv"][k] = _parse_data_value(v)
        else:
            entry["args"].append(_parse_data_value(tok))
    return entry


def _parse_int_or_float_bits(raw: str, mode: str, line_no: int) -> int:
    s = raw.strip()
    if mode == "f32":
        if re.fullmatch(r"0[xX][0-9a-fA-F]+", s):
            return int(s, 16) & 0xFFFFFFFF
        return struct.unpack("<I", struct.pack("<f", float(s)))[0]
    if mode == "f64":
        if re.fullmatch(r"0[xX][0-9a-fA-F]+", s):
            return int(s, 16) & 0xFFFFFFFFFFFFFFFF
        return struct.unpack("<Q", struct.pack("<d", float(s)))[0]
    if s.lower() == "none":
        return 0xFFFF
    if s in SCALAR_TYPE_NAMES:
        return SCALAR_TYPE_NAMES[s]
    try:
        return int(s, 0)
    except ValueError as exc:
        raise AsmError(f"Expected integer literal, got {raw!r}", line_no) from exc


class ImpAsmV11:
    def __init__(self, isa_path: Path | str = DEFAULT_ISA_PATH):
        self.isa = load_isa(isa_path)
        self.by_code: dict[int, dict[str, Any]] = {op["code"]: op for op in self.isa["opcodes"]}
        self.by_mnemonic: dict[str, dict[str, Any]] = {}
        for op in self.isa["opcodes"]:
            self.by_mnemonic[op["mnemonic"].upper()] = op
            self.by_mnemonic[op["name"].upper()] = op

    def _parse_reg(self, tok: str, expected_bank: str, in_morsel: bool, line_no: int) -> int:
        m = REG_RE.fullmatch(tok.upper())
        if not m:
            raise AsmError(f"Expected register in bank {expected_bank}, got {tok!r}", line_no)
        prefix, idx_s = m.group(1), m.group(2)
        idx = int(idx_s)
        base_bank = expected_bank.replace("OPT_", "")

        if prefix == "R":
            if not (0 <= idx <= 15):
                raise AsmError(f"Register {tok} out of range R0..R15", line_no)
            actual_bank, encoded = "R", idx
        elif prefix == "F":
            if not (0 <= idx <= 15):
                raise AsmError(f"Register {tok} out of range F0..F15", line_no)
            if in_morsel and idx >= 8:
                raise AsmError(
                    f"Inside a morsel block, write MF{idx - 8} instead of {tok}", line_no
                )
            actual_bank, encoded = "F", idx
        elif prefix == "V":
            if not (0 <= idx <= 15):
                raise AsmError(f"Register {tok} out of range V0..V15", line_no)
            if in_morsel and idx >= 8:
                raise AsmError(
                    f"Inside a morsel block, write M{idx - 8} instead of {tok}", line_no
                )
            actual_bank, encoded = "V", idx
        elif prefix == "MF":
            if not in_morsel:
                raise AsmError(f"Morsel mask {tok} is only legal inside a morsel block", line_no)
            if not (0 <= idx <= 7):
                raise AsmError(f"Morsel mask {tok} out of range MF0..MF7", line_no)
            actual_bank, encoded = "F", idx + 8
        elif prefix == "M":
            if not in_morsel:
                raise AsmError(f"Morsel vector {tok} is only legal inside a morsel block", line_no)
            if not (0 <= idx <= 7):
                raise AsmError(f"Morsel vector {tok} out of range M0..M7", line_no)
            actual_bank, encoded = "V", idx + 8
        else:
            raise AsmError(f"Unknown register token {tok!r}", line_no)

        if actual_bank != base_bank:
            raise AsmError(
                f"Register bank mismatch: expected {base_bank}, got {tok} ({actual_bank})", line_no
            )
        return encoded

    def _parse_head(self, head: str, line_no: int) -> tuple[dict[str, Any], int, int, str | None, bool]:
        """Parse MNEMONIC[.subop][.mod]* -> (op, subop_id, flags, pseudo_commute, is_int_imm)."""
        parts = head.split(".")
        mnem_raw = parts[0].upper()
        if mnem_raw not in self.by_mnemonic:
            raise AsmError(f"Unknown opcode mnemonic {parts[0]!r}", line_no)
        op = self.by_mnemonic[mnem_raw]
        if op["code"] == 0xFF:
            raise AsmError("OP_EXTENSION_PAYLOAD (0xFF) cannot be written directly in .code", line_no)

        subop_by_name = {v: k for k, v in op["subops"].items()}
        subop_id: int | None = None
        flags = 0
        seen_mods: set[str] = set()
        pseudo_commute: str | None = None
        is_int_imm = False

        for suffix in parts[1:]:
            sl = suffix.lower()
            if subop_id is None and op["code"] == 0x0E and sl in SCALAR_3VL_COMMUTE:
                pseudo_commute = sl
                subop_id = subop_by_name[SCALAR_3VL_COMMUTE[sl]]
            elif subop_id is None and sl in subop_by_name:
                subop_id = subop_by_name[sl]
            elif sl in MODIFIER_MAP:
                if sl in seen_mods:
                    raise AsmError(f"Duplicate modifier '.{sl}' on {op['mnemonic']}", line_no)
                seen_mods.add(sl)
                flags |= MODIFIER_MAP[sl]
            elif sl == "imm" and op["code"] == 0x0C:
                if is_int_imm:
                    raise AsmError("Duplicate '.imm' suffix on SCALAR_INT_ALU", line_no)
                is_int_imm = True
            elif sl in subop_by_name or (op["code"] == 0x0E and sl in SCALAR_3VL_COMMUTE):
                raise AsmError(f"Multiple subops specified on {op['mnemonic']}", line_no)
            else:
                raise AsmError(f"{op['mnemonic']}: unknown subop or modifier '.{suffix}'", line_no)

        if subop_id is None:
            if 0 in op["subops"]:
                subop_id = 0
            else:
                raise AsmError(f"{op['mnemonic']}: missing required subop", line_no)

        return op, subop_id, flags, pseudo_commute, is_int_imm

    def assemble(self, source: str) -> ParsedProgram:
        prog = ParsedProgram()
        section = "code"
        raw_code_items: list[tuple[int, str]] = []

        for line_no, raw_line in enumerate(source.splitlines(), start=1):
            m_exp = EXPECT_RE.match(raw_line)
            if m_exp:
                expr = m_exp.group(1)
                if "=" in expr:
                    k, v = expr.split("=", 1)
                    prog.expectations.append({"key": k.strip(), "value": v.strip(), "line": line_no})
                else:
                    prog.expectations.append({"raw": expr.strip(), "line": line_no})
                continue

            cleaned = _strip_asm_comment(raw_line).strip()
            if not cleaned:
                continue

            if cleaned == ".data":
                section = "data"
                continue
            if cleaned == ".const_pool":
                section = "const_pool"
                continue
            if cleaned == ".code":
                section = "code"
                continue

            if section == "data":
                prog.data_directives.append(_parse_directive(cleaned, line_no))
            elif section == "const_pool":
                prog.const_pool.append(_parse_directive(cleaned, line_no))
            else:
                raw_code_items.append((line_no, cleaned))

        # Pass 1: collect labels, track morsel spans, and compute PC offsets
        parsed_insts: list[dict[str, Any]] = []
        pc = 0
        morsel_stack: list[dict[str, Any]] = []

        for line_no, text in raw_code_items:
            while ":" in text:
                before, after = text.split(":", 1)
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", before.strip()):
                    lbl = before.strip()
                    if lbl in prog.labels:
                        raise AsmError(f"Duplicate label '{lbl}'", line_no)
                    prog.labels[lbl] = pc
                    text = after.strip()
                else:
                    break
            if not text:
                continue

            parts = text.split(None, 1)
            head = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            op, subop_id, flags, pseudo_commute, is_int_imm = self._parse_head(head, line_no)

            in_morsel = len(morsel_stack) > 0
            role = op["morsel_role"]
            morsel_info: dict[str, Any] | None = None

            if role == "header":
                if in_morsel:
                    raise AsmError("Nested morsel blocks are forbidden", line_no)
                morsel_info = {"hdr_pc": pc, "end_pc": None, "hdr_idx": len(parsed_insts)}
                morsel_stack.append(morsel_info)
            elif role == "end_only":
                if not in_morsel:
                    raise AsmError("MORSEL_END outside of morsel block", line_no)
                morsel_info = morsel_stack.pop()
                morsel_info["end_pc"] = pc
            elif in_morsel:
                if role == "forbidden":
                    raise AsmError(f"{op['mnemonic']} is forbidden inside a morsel block", line_no)
                if role == "body_v_only" and subop_id != 2:
                    raise AsmError(f"{op['mnemonic']}: only .v is allowed inside a morsel block", line_no)
                if role == "body_cast_only" and subop_id != 2:
                    raise AsmError("VEC_POINT: only .vec_cast is allowed inside a morsel block", line_no)
                if role == "body_pair_only" and subop_id < 4:
                    raise AsmError("VECTOR_RERANK: only .pair_* subops are allowed inside a morsel block", line_no)
                morsel_info = morsel_stack[-1]
            else:
                if role == "commit_only":
                    raise AsmError("MORSEL_COMMIT is only legal inside a morsel block", line_no)

            word_len = 2 if (flags & FLAG_EXT) else 1
            parsed_insts.append({
                "line_no": line_no,
                "pc": pc,
                "op": op,
                "subop": subop_id,
                "flags": flags,
                "pseudo_commute": pseudo_commute,
                "is_int_imm": is_int_imm,
                "rest": rest,
                "in_morsel": in_morsel and role != "header" and role != "end_only",
                "morsel_info": morsel_info,
            })
            pc += word_len

        if morsel_stack:
            raise AsmError("Unclosed morsel block (missing MORSEL_END)", parsed_insts[morsel_stack[-1]["hdr_idx"]]["line_no"])

        # Pass 2: encode every instruction
        words: list[int] = []
        for item in parsed_insts:
            line_no = item["line_no"]
            op = item["op"]
            code = op["code"]
            subop = item["subop"]
            flags = item["flags"]
            in_morsel = item["in_morsel"]
            operands = _split_operands(item["rest"]) if item["rest"] else []

            pos_tokens: list[str] = []
            kv_tokens: dict[str, str] = {}
            for tok in operands:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    kv_tokens[k.strip().lower()] = v.strip()
                else:
                    pos_tokens.append(tok)

            banks = resolve_banks(op, subop, flags)
            dst = s1 = s2 = s3 = 0
            imm32 = 0
            imm32_hi: int | None = None

            # Parse positional register operands
            p_idx = 0
            if code == 0x12:  # CALL (s1=r_stride, s2=f_stride, s3=v_stride)
                if subop == 0:
                    s1 = int(kv_tokens.pop("r_stride", "0"), 0) & 0xF
                    s2 = int(kv_tokens.pop("f_stride", "0"), 0) & 0xF
                    s3 = int(kv_tokens.pop("v_stride", "0"), 0) & 0xF
            else:
                for slot in ("dst", "s1", "s2", "s3"):
                    bspec = banks[slot]
                    if bspec in ("NONE", "IMM_MODE_TAG"):
                        continue
                    is_opt = bspec.startswith("OPT_")
                    if p_idx < len(pos_tokens) and REG_RE.fullmatch(pos_tokens[p_idx].upper()):
                        # Inside SCALAR_INT_ALU.imm, s2 is unused (0) and the remaining positional is imm32
                        if code == 0x0C and slot == "s2" and item["is_int_imm"]:
                            continue
                        val = self._parse_reg(pos_tokens[p_idx], bspec, in_morsel, line_no)
                        p_idx += 1
                        if slot == "dst":
                            dst = val
                        elif slot == "s1":
                            s1 = val
                        elif slot == "s2":
                            s2 = val
                        elif slot == "s3":
                            s3 = val
                    elif not is_opt:
                        raise AsmError(
                            f"{op['mnemonic']}.{op['subops'][subop]}: missing required {slot} ({bspec}) register",
                            line_no,
                        )

            if item["pseudo_commute"] is not None:
                s1, s2 = s2, s1

            if code == 0x0C and item["is_int_imm"]:
                s3 = 1

            # Remaining bare positional tokens (immediates or branch targets)
            rem_pos = pos_tokens[p_idx:]
            imm_layout = op["imm_layout"]

            if imm_layout == "NONE":
                if rem_pos or kv_tokens:
                    raise AsmError(f"{op['mnemonic']}: unexpected immediate operands {rem_pos} {kv_tokens}", line_no)
            elif imm_layout == "REL_PC_I32":
                target_tok = kv_tokens.pop("target", None) or (rem_pos.pop(0) if rem_pos else None)
                if target_tok is None:
                    raise AsmError(f"{op['mnemonic']}: missing branch target", line_no)
                if target_tok in prog.labels:
                    rel_off = prog.labels[target_tok] - item["pc"]
                else:
                    rel_off = int(target_tok, 0)
                if in_morsel:
                    m_info = item["morsel_info"]
                    target_pc = item["pc"] + rel_off
                    if rel_off <= 0 or target_pc > m_info["end_pc"]:
                        raise AsmError(
                            f"{op['mnemonic']}: inside morsel, jump must be strictly forward and <= MORSEL_END",
                            line_no,
                        )
                imm32 = rel_off & 0xFFFFFFFF
            elif imm_layout == "CONST_PAYLOAD":
                val_tok = kv_tokens.pop("imm", None) or (rem_pos.pop(0) if rem_pos else None)
                if subop == 7:  # null
                    if val_tok is not None and val_tok.lower() not in ("null", "0"):
                        raise AsmError("LOAD_CONST.null does not take a non-zero value", line_no)
                    imm32 = 0
                else:
                    if val_tok is None:
                        raise AsmError(f"LOAD_CONST.{op['subops'][subop]}: missing constant literal", line_no)
                    if subop in (2, 3):  # f32, f32_raw
                        imm32 = _parse_int_or_float_bits(val_tok, "f32", line_no)
                    elif subop in (4, 5, 6):  # i64, u64, f64 (128-bit)
                        mode = "f64" if subop == 6 else "int"
                        u64 = _parse_int_or_float_bits(val_tok, mode, line_no) & 0xFFFFFFFFFFFFFFFF
                        imm32 = u64 & 0xFFFFFFFF
                        imm32_hi = (u64 >> 32) & 0xFFFFFFFF
                    else:  # i32, u32
                        imm32 = _parse_int_or_float_bits(val_tok, "int", line_no) & 0xFFFFFFFF
            elif imm_layout == "POOL_DESC":
                if subop == 1:  # frontier: pool -> lo, dom -> hi
                    lo = _parse_int_or_float_bits(kv_tokens.pop("pool", kv_tokens.pop("lo", "0")), "int", line_no)
                    hi = _parse_int_or_float_bits(kv_tokens.pop("dom", kv_tokens.pop("hi", "0")), "int", line_no)
                    imm32 = (lo & 0xFFFF) | ((hi & 0xFFFF) << 16)
                else:
                    raw_pool = kv_tokens.pop("pool", None) or kv_tokens.pop("imm", None) or (rem_pos.pop(0) if rem_pos else "0")
                    imm32 = _parse_int_or_float_bits(raw_pool, "int", line_no) & 0xFFFFFFFF
            elif imm_layout in ("U32", "OPT_U32", "OPT_I32"):
                raw_imm = kv_tokens.pop("imm", None) or kv_tokens.pop("code", None) or (rem_pos.pop(0) if rem_pos else None)
                if raw_imm is not None:
                    imm32 = _parse_int_or_float_bits(raw_imm, "int", line_no) & 0xFFFFFFFF
                elif "lo" in kv_tokens or "hi" in kv_tokens:
                    lo = _parse_int_or_float_bits(kv_tokens.pop("lo", "0"), "int", line_no)
                    hi = _parse_int_or_float_bits(kv_tokens.pop("hi", "0"), "int", line_no)
                    imm32 = (lo & 0xFFFF) | ((hi & 0xFFFF) << 16)
            elif imm_layout in ("U16_LO", "OPT_U16_LO", "OPT_DOMAIN_U16", "LEN_OR_DOM"):
                if code == 0x38:  # MORSEL_END: auto-fill hdr_word_distance unless explicit
                    if "hdr_dist" in kv_tokens or "lo" in kv_tokens or rem_pos:
                        raw_lo = kv_tokens.pop("hdr_dist", kv_tokens.pop("lo", None)) or rem_pos.pop(0)
                        lo = _parse_int_or_float_bits(raw_lo, "int", line_no)
                    else:
                        lo = item["pc"] - item["morsel_info"]["hdr_pc"]
                    imm32 = lo & 0xFFFF
                else:
                    lo_key = next(
                        (k for k in ("dom", "rel", "slot", "k", "len", "lane", "type", "lo", "imm") if k in kv_tokens),
                        None,
                    )
                    if lo_key is not None:
                        lo = _parse_int_or_float_bits(kv_tokens.pop(lo_key), "int", line_no)
                    elif rem_pos:
                        lo = _parse_int_or_float_bits(rem_pos.pop(0), "int", line_no)
                    else:
                        lo = 0
                    imm32 = lo & 0xFFFF
            elif imm_layout == "U16_HI":
                if code == 0x36:  # FILTER_MORSEL: auto-fill end_word_offset in imm16_hi
                    if "end_off" in kv_tokens or "hi" in kv_tokens or rem_pos:
                        raw_hi = kv_tokens.pop("end_off", kv_tokens.pop("hi", None)) or rem_pos.pop(0)
                        hi = _parse_int_or_float_bits(raw_hi, "int", line_no)
                    else:
                        hi = item["morsel_info"]["end_pc"] - item["pc"]
                    imm32 = (hi & 0xFFFF) << 16
                elif code == 0x38:  # MORSEL_END: auto-fill hdr_word_distance in imm16_hi
                    if "hdr_dist" in kv_tokens or "hdr" in kv_tokens or "hi" in kv_tokens or rem_pos:
                        raw_hi = kv_tokens.pop("hdr_dist", kv_tokens.pop("hdr", kv_tokens.pop("hi", None))) or rem_pos.pop(0)
                        hi = _parse_int_or_float_bits(raw_hi, "int", line_no)
                    else:
                        hi = item["pc"] - item["morsel_info"]["hdr_pc"]
                    imm32 = (hi & 0xFFFF) << 16
                else:
                    hi_key = next((k for k in ("hi", "attr", "imm") if k in kv_tokens), None)
                    hi = _parse_int_or_float_bits(kv_tokens.pop(hi_key), "int", line_no) if hi_key else (
                        _parse_int_or_float_bits(rem_pos.pop(0), "int", line_no) if rem_pos else 0
                    )
                    imm32 = (hi & 0xFFFF) << 16
            elif imm_layout == "U16_PAIR":
                lo, hi = 0, 0
                if code == 0x35:  # WALK_MORSEL: rel -> lo, end_word_offset -> hi (auto)
                    lo = _parse_int_or_float_bits(kv_tokens.pop("rel", kv_tokens.pop("lo", "0")), "int", line_no)
                    if "end_off" in kv_tokens or "hi" in kv_tokens:
                        hi = _parse_int_or_float_bits(kv_tokens.pop("end_off", kv_tokens.pop("hi", "0")), "int", line_no)
                    else:
                        hi = item["morsel_info"]["end_pc"] - item["pc"]
                elif code == 0x07:  # LOAD_PARAM: param -> lo, dom/type -> hi
                    lo = _parse_int_or_float_bits(kv_tokens.pop("param", kv_tokens.pop("lo", "0")), "int", line_no)
                    hi_key = next((k for k in ("dom", "type", "hi") if k in kv_tokens), None)
                    hi = _parse_int_or_float_bits(kv_tokens.pop(hi_key), "int", line_no) if hi_key else 0
                elif code == 0x20:  # FSEED: node_id/lo -> lo, dom -> hi
                    lo_key = next((k for k in ("node", "id", "lo") if k in kv_tokens), None)
                    if lo_key:
                        lo = _parse_int_or_float_bits(kv_tokens.pop(lo_key), "int", line_no)
                    elif rem_pos:
                        lo = _parse_int_or_float_bits(rem_pos.pop(0), "int", line_no)
                    hi = _parse_int_or_float_bits(kv_tokens.pop("dom", kv_tokens.pop("hi", "0")), "int", line_no)
                elif code == 0x55:  # MAP_KEYS_TO_DENSE: dom -> lo, param -> hi
                    lo = _parse_int_or_float_bits(kv_tokens.pop("dom", kv_tokens.pop("lo", "0")), "int", line_no)
                    hi = _parse_int_or_float_bits(kv_tokens.pop("param", kv_tokens.pop("hi", "0")), "int", line_no)
                elif code == 0x57:  # COLLECT: out/batch -> lo, col -> hi
                    lo_key = next((k for k in ("out", "batch", "lo") if k in kv_tokens), None)
                    lo = _parse_int_or_float_bits(kv_tokens.pop(lo_key), "int", line_no) if lo_key else 0
                    hi_key = next((k for k in ("col", "hi") if k in kv_tokens), None)
                    hi = _parse_int_or_float_bits(kv_tokens.pop(hi_key), "int", line_no) if hi_key else 0
                else:
                    lo_key = next((k for k in ("rel", "dom", "lo") if k in kv_tokens), None)
                    hi_key = next((k for k in ("attr", "k", "idx", "hi") if k in kv_tokens), None)
                    if lo_key:
                        lo = _parse_int_or_float_bits(kv_tokens.pop(lo_key), "int", line_no)
                    if hi_key:
                        hi = _parse_int_or_float_bits(kv_tokens.pop(hi_key), "int", line_no)
                    if "imm" in kv_tokens:
                        imm32 = _parse_int_or_float_bits(kv_tokens.pop("imm"), "int", line_no) & 0xFFFFFFFF
                        lo = imm32 & 0xFFFF
                        hi = (imm32 >> 16) & 0xFFFF
                imm32 = (lo & 0xFFFF) | ((hi & 0xFFFF) << 16)

            if rem_pos or kv_tokens:
                raise AsmError(
                    f"{op['mnemonic']}: unconsumed operands pos={rem_pos} kv={kv_tokens}", line_no
                )

            validate_word_semantics(op, flags, subop, dst, s1, s2, s3, imm32, line_no)
            words.append(encode_word(code, flags, subop, dst, s1, s2, s3, imm32))
            if flags & FLAG_EXT:
                words.append(encode_extension_word(imm32_hi if imm32_hi is not None else 0))

        prog.words = words
        return prog

    def _fmt_reg(self, bank: str, idx: int, in_morsel: bool) -> str:
        base = bank.replace("OPT_", "")
        if base == "F" and in_morsel and idx >= 8:
            return f"MF{idx - 8}"
        if base == "V" and in_morsel and idx >= 8:
            return f"M{idx - 8}"
        return f"{base}{idx}"

    def disassemble(self, words: list[int]) -> str:
        lines: list[str] = [".code"]
        i = 0
        in_morsel = False

        while i < len(words):
            w = words[i]
            code, flags, subop, dst, s1, s2, s3, imm32 = decode_word_fields(w)
            if code not in self.by_code:
                raise AsmError(f"Word {i}: unassigned opcode 0x{code:02X}")
            if code == 0xFF:
                raise AsmError(f"Word {i}: standalone OP_EXTENSION_PAYLOAD (0xFF) without preceding FLAG_EXTENDED")
            op = self.by_code[code]
            validate_word_semantics(op, flags, subop, dst, s1, s2, s3, imm32)

            ext_hi: int | None = None
            if flags & FLAG_EXT:
                if i + 1 >= len(words):
                    raise AsmError(f"Word {i}: FLAG_EXTENDED truncated before Word 2")
                w2 = words[i + 1]
                c2, f2, so2, d2, a2, b2, c3_2, hi2 = decode_word_fields(w2)
                if c2 != 0xFF or f2 or so2 or d2 or a2 or b2 or c3_2:
                    raise AsmError(f"Word {i + 1}: invalid OP_EXTENSION_PAYLOAD guard word 0x{w2:016X}")
                ext_hi = hi2
                i += 2
            else:
                i += 1

            role = op["morsel_role"]
            if role == "end_only":
                in_morsel = False

            subop_name = op["subops"][subop]
            head = f"{op['mnemonic']}.{subop_name}"
            if code == 0x0C and s3 == 1:
                head += ".imm"
            for mod_name, mod_bit in MODIFIER_ORDER:
                if flags & mod_bit:
                    head += f".{mod_name}"

            banks = resolve_banks(op, subop, flags)
            ops_out: list[str] = []
            reg_in_morsel = in_morsel and role != "header"

            if code == 0x12:  # CALL
                if subop == 0:
                    if s1:
                        ops_out.append(f"r_stride={s1}")
                    if s2:
                        ops_out.append(f"f_stride={s2}")
                    if s3:
                        ops_out.append(f"v_stride={s3}")
            else:
                for slot, val in (("dst", dst), ("s1", s1), ("s2", s2), ("s3", s3)):
                    bspec = banks[slot]
                    if bspec in ("NONE", "IMM_MODE_TAG"):
                        continue
                    if code == 0x0C and slot == "s2" and s3 == 1:
                        continue
                    if bspec.startswith("OPT_") and val == 0:
                        # Still emit if a later positional register is present or always emit for lossless clarity
                        ops_out.append(self._fmt_reg(bspec, val, reg_in_morsel))
                    else:
                        ops_out.append(self._fmt_reg(bspec, val, reg_in_morsel))

            imm_layout = op["imm_layout"]
            lo = imm32 & 0xFFFF
            hi = (imm32 >> 16) & 0xFFFF

            if imm_layout == "REL_PC_I32":
                ops_out.append(str(u32_to_i32(imm32)))
            elif imm_layout == "CONST_PAYLOAD":
                if subop == 7:
                    pass
                elif subop in (4, 5, 6):
                    full64 = (imm32 & 0xFFFFFFFF) | (((ext_hi or 0) & 0xFFFFFFFF) << 32)
                    ops_out.append(f"0x{full64:016X}")
                elif subop in (2, 3):
                    ops_out.append(f"0x{imm32:08X}")
                else:
                    ops_out.append(str(u32_to_i32(imm32) if subop == 0 else imm32))
            elif imm_layout == "POOL_DESC":
                if subop == 1:
                    ops_out.append(f"pool={lo}")
                    ops_out.append(f"dom={hi}")
                else:
                    ops_out.append(f"pool={imm32}")
            elif imm_layout in ("U32", "OPT_U32"):
                if imm32 != 0 or imm_layout == "U32":
                    ops_out.append(f"imm={imm32}")
            elif imm_layout == "OPT_I32":
                if imm32 != 0 or (code == 0x0C and s3 == 1):
                    ops_out.append(f"imm={u32_to_i32(imm32)}")
            elif imm_layout in ("U16_LO", "OPT_U16_LO", "OPT_DOMAIN_U16", "LEN_OR_DOM"):
                if code == 0x38:
                    ops_out.append(f"hdr_dist={lo}")
                elif lo != 0 or imm_layout == "U16_LO":
                    ops_out.append(f"lo={lo}")
            elif imm_layout == "U16_HI":
                if code == 0x36:
                    ops_out.append(f"end_off={hi}")
                elif code == 0x38:
                    ops_out.append(f"hdr_dist={hi}")
                elif hi != 0 or imm_layout == "U16_HI":
                    ops_out.append(f"hi={hi}")
            elif imm_layout == "U16_PAIR":
                if code == 0x35:
                    ops_out.append(f"rel={lo}")
                    ops_out.append(f"end_off={hi}")
                else:
                    ops_out.append(f"lo={lo}")
                    ops_out.append(f"hi={hi}")

            indent = "    " if reg_in_morsel else "  "
            line_str = f"{indent}{head}" + (f" {', '.join(ops_out)}" if ops_out else "")
            lines.append(line_str)

            if role == "header":
                in_morsel = True

        return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="ImpAsm v0.11.0 Assembler & Disassembler")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_asm = sub.add_parser("assemble", help="Assemble .impas file to .impb")
    p_asm.add_argument("input", type=Path)
    p_asm.add_argument("-o", "--output", type=Path, required=True)

    p_dis = sub.add_parser("disassemble", help="Disassemble .impb file to ImpAsm text")
    p_dis.add_argument("input", type=Path)

    p_rt = sub.add_parser("roundtrip", help="Verify assemble -> disassemble -> re-assemble identity")
    p_rt.add_argument("input", type=Path)

    p_fx = sub.add_parser("parse-fixture", help="Dump parsed .data/.const_pool/EXPECT JSON")
    p_fx.add_argument("input", type=Path)

    args = parser.parse_args()
    asm = ImpAsmV11()

    if args.cmd == "assemble":
        prog = asm.assemble(args.input.read_text(encoding="utf-8"))
        args.output.write_bytes(pack_impb(prog.words))
        print(f"Assembled {len(prog.words)} words -> {args.output}")
    elif args.cmd == "disassemble":
        words = unpack_impb(args.input.read_bytes())
        print(asm.disassemble(words), end="")
    elif args.cmd == "roundtrip":
        prog1 = asm.assemble(args.input.read_text(encoding="utf-8"))
        text = asm.disassemble(prog1.words)
        prog2 = asm.assemble(text)
        if prog1.words != prog2.words:
            print("ROUNDTRIP MISMATCH", file=sys.stderr)
            return 1
        print(f"OK: {len(prog1.words)} words roundtripped losslessly")
    elif args.cmd == "parse-fixture":
        prog = asm.assemble(args.input.read_text(encoding="utf-8"))
        print(json.dumps({
            "expectations": prog.expectations,
            "data_directives": prog.data_directives,
            "const_pool": prog.const_pool,
            "word_count": len(prog.words),
            "words_hex": [f"0x{w:016X}" for w in prog.words],
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
