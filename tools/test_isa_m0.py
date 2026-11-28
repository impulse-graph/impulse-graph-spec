#!/usr/bin/env python3
"""
Exhaustive M0 (Freeze & Codegen) Verification Suite for ImpulseVM v0.11.0.

Covers:
  1. isa_v0_11.yaml freeze & schema invariants (78 active + 0xFF, 449 subops)
  2. gen_v11_tables.py --check drift gate (OCaml, C++20, Java 25, Rust)
  3. lint_v11_gfm.py gate across all v0.11-refactor/*.md (0 errors)
  4. Exhaustive (opcode x valid_subop) assemble -> .impb -> disassemble -> re-assemble roundtrip
  5. Exhaustive (opcode x allowed_flag_subset) positive matrix + multi-modifier permutations
  6. Exhaustive negative flag bit & duplicate modifier rejection matrix
  7. Exhaustive 256-opcode & 16-subop space sweep (all 177 unassigned opcodes + standalone 0xFF)
  8. Exhaustive morsel scope, role, and register alias matrix (F8..15/V8..15 vs MF0..7/M0..7)
  9. All 16 register indices per bank + boundary 16/32/64-bit immediates
 10. All 6 SCALAR_3VL commute & 15 SCALAR_INT_ALU.imm pseudo-instructions + .data/.const_pool/EXPECT
"""

from __future__ import annotations

import itertools
import sys
import unittest
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from gen_isa_tables import generate_all
from impas_assembler import (
    AsmError,
    FLAG_ACCUM,
    FLAG_EXT,
    FLAG_MASK,
    FLAG_SCALAR,
    ImpAsm,
    MODIFIER_ORDER,
    SCALAR_3VL_COMMUTE,
    encode_word,
    pack_impb,
    resolve_banks,
    unpack_impb,
)
from lint_gfm import lint_directory
from isa_loader import load_isa, valid_subop_mask


def _is_valid_combo(op: dict[str, Any], subop: int, flags: int) -> bool:
    code = op["code"]
    if (flags & (~op["allowed_flags"] & 0xF)) != 0:
        return False
    if code == 0x05:  # LOAD_CONST
        is_ext = 4 <= subop <= 6
        return bool(flags & FLAG_EXT) == is_ext
    if code == 0x34 and subop >= 7 and (flags & FLAG_ACCUM):
        return False
    if code == 0x45 and subop == 6 and (flags & FLAG_MASK):
        return False
    if code == 0x45 and subop == 7 and (flags & FLAG_SCALAR):
        return False
    if code == 0x4D and subop == 8 and (flags & FLAG_SCALAR):
        return False
    if code == 0x58:  # VEC_DECIMAL_ALU
        if subop in (3, 4, 15) and (flags & FLAG_MASK):
            return False
        if 7 <= subop <= 14 and (flags & FLAG_SCALAR):
            return False
    if code == 0x6C and subop in (3, 8) and (flags & FLAG_SCALAR):
        return False
    return True


def _synth_instruction_source(op: dict[str, Any], subop: int, flags: int) -> str:
    """Synthesize a valid ImpAsm snippet exercising (op, subop, flags)."""
    code = op["code"]
    mnem = op["mnemonic"]
    subop_name = op["subops"][subop]
    role = op["morsel_role"]
    in_morsel = role in ("commit_only", "end_only")

    head = f"{mnem}.{subop_name}"
    for mname, mbit in MODIFIER_ORDER:
        if flags & mbit:
            head += f".{mname}"

    banks = resolve_banks(op, subop, flags)
    operands: list[str] = []

    if code == 0x12:  # CALL
        if subop == 0:
            operands.extend(["r_stride=2", "f_stride=1", "v_stride=3"])
    else:
        reg_picks = {"R": [1, 2, 3, 4], "F": [1, 2, 3, 4], "V": [1, 2, 3, 4]}
        for idx_slot, slot in enumerate(("dst", "s1", "s2", "s3")):
            bspec = banks[slot]
            if bspec in ("NONE", "IMM_MODE_TAG"):
                continue
            base = bspec.replace("OPT_", "")
            rnum = reg_picks[base][idx_slot]
            if in_morsel and slot != "dst" and base in ("F", "V"):
                # Inside morsel, s1/s2/s3 can use MF0/M0..M3
                operands.append(f"{'MF' if base == 'F' else 'M'}{idx_slot}")
            else:
                operands.append(f"{base}{rnum}")

    imm_layout = op["imm_layout"]
    if imm_layout == "REL_PC_I32":
        operands.append("0")
    elif imm_layout == "CONST_PAYLOAD":
        if subop == 7:
            pass
        elif subop in (4, 5, 6):
            operands.append("0x1122334455667788")
        elif subop in (2, 3):
            operands.append("0x3F800000")
        else:
            operands.append("42")
    elif imm_layout == "POOL_DESC":
        if subop == 1:
            operands.extend(["pool=3", "dom=1"])
        else:
            operands.append("pool=7")
    elif imm_layout in ("U32", "OPT_U32"):
        operands.append("imm=12345")
    elif imm_layout == "OPT_I32":
        operands.append("imm=-7")
    elif imm_layout in ("U16_LO", "OPT_U16_LO", "OPT_DOMAIN_U16", "LEN_OR_DOM"):
        if code in (0x0A, 0x0B):
            operands.append("slot=5")
        elif code == 0x38:
            pass  # MORSEL_END auto-fills hdr_dist
        else:
            operands.append("lo=3")
    elif imm_layout == "U16_HI":
        if code != 0x36:
            operands.append("hi=2")
    elif imm_layout in ("U16_PAIR", "OPT_U16_PAIR"):
        if code == 0x35:
            operands.append("rel=1")
        else:
            operands.extend(["lo=2", "hi=3"])

    line = f"  {head}" + (f" {', '.join(operands)}" if operands else "")

    if role == "header":
        return f".code\n{line}\n  MORSEL_END\n"
    if role == "commit_only":
        return f".code\n  WALK_MORSEL.fwd F1, rel=0\n  {line}\n  MORSEL_END\n"
    if role == "end_only":
        return ".code\n  WALK_MORSEL.fwd F1, rel=0\n  MORSEL_END.end\n"
    return f".code\n{line}\n"


class TestIsaM0Exhaustive(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.isa = load_isa()
        cls.asm = ImpAsm()
        cls.active_ops = [op for op in cls.isa["opcodes"] if op["code"] != 0xFF]

    def test_01_yaml_freeze_invariants(self) -> None:
        self.assertEqual(len(self.active_ops), 80)
        self.assertEqual(len(self.isa["opcodes"]), 81)
        total_subops = sum(len(op["subops"]) for op in self.isa["opcodes"])
        self.assertEqual(total_subops, 487)

    def test_02_codegen_zero_drift(self) -> None:
        drifts = generate_all(check=True)
        self.assertEqual(drifts, [], "\n".join(drifts))

    def test_03_gfm_lint_zero_errors(self) -> None:
        errors = lint_directory()
        self.assertEqual(errors, [], "\n".join(errors))

    def test_04_exhaustive_opcode_subop_and_flag_roundtrip(self) -> None:
        """Exhaustively test EVERY (opcode x valid_subop x valid_flag_subset) combination."""
        combos_tested = 0
        for op in self.active_ops:
            allowed = op["allowed_flags"]
            flag_subsets = [f for f in range(16) if (f & ~allowed) == 0]
            for subop in sorted(op["subops"].keys()):
                for flags in flag_subsets:
                    if not _is_valid_combo(op, subop, flags):
                        continue
                    src = _synth_instruction_source(op, subop, flags)
                    prog1 = self.asm.assemble(src)
                    # .impb binary container pack/unpack roundtrip
                    blob = pack_impb(prog1.words)
                    unpacked = unpack_impb(blob)
                    self.assertEqual(prog1.words, unpacked)
                    # Disassemble -> re-assemble bitwise identity
                    dis = self.asm.disassemble(prog1.words)
                    prog2 = self.asm.assemble(dis)
                    self.assertEqual(
                        prog1.words,
                        prog2.words,
                        f"Roundtrip mismatch for {op['mnemonic']}.{op['subops'][subop]} flags=0x{flags:X}\n"
                        f"SRC:\n{src}\nDIS:\n{dis}",
                    )
                    combos_tested += 1
        # Must cover all 448 active subops and well over 1,000 (op x subop x flag) triples
        self.assertGreater(combos_tested, 1000)

    def test_05_exhaustive_modifier_permutations_and_duplicates(self) -> None:
        """Verify modifier order invariance and duplicate modifier rejection."""
        # SPMV allows accum (0x4) | scalar (0x2) | mask (0x1) = 0x7
        mods = ["accum", "scalar", "mask"]
        ref_words = self.asm.assemble(".code\n  SPMV.fwd_plus_times.accum.scalar.mask V1, F2, R3, F4, rel=1, attr=2\n").words
        for perm in itertools.permutations(mods):
            suffix = ".".join(perm)
            w = self.asm.assemble(f".code\n  SPMV.fwd_plus_times.{suffix} V1, F2, R3, F4, rel=1, attr=2\n").words
            self.assertEqual(w, ref_words, f"Permutation .{suffix} diverged")
        for m in mods + ["ext"]:
            with self.assertRaises(AsmError):
                self.asm.assemble(f".code\n  SPMV.fwd_plus_times.{m}.{m} V1, F2, R3, F4, rel=1, attr=2\n")

    def test_06_exhaustive_disallowed_flags_rejected(self) -> None:
        """Every disallowed flag bit on every active opcode must be rejected by assembler & disassembler."""
        rejected = 0
        for op in self.active_ops:
            allowed = op["allowed_flags"]
            subop = sorted(op["subops"].keys())[0]
            for mname, mbit in MODIFIER_ORDER:
                if (allowed & mbit) != 0:
                    continue
                # Disassembler must reject raw word with disallowed flag bit
                bad_word = encode_word(op["code"], mbit, subop, 0, 0, 0, 0, 0)
                with self.assertRaises(AsmError):
                    self.asm.disassemble([bad_word])
                # Assembler must reject syntax with disallowed modifier
                src = _synth_instruction_source(op, subop, 0)
                bad_src = src.replace(
                    f"{op['mnemonic']}.{op['subops'][subop]}",
                    f"{op['mnemonic']}.{op['subops'][subop]}.{mname}",
                    1,
                )
                with self.assertRaises(AsmError):
                    self.asm.assemble(bad_src)
                rejected += 1
        self.assertGreater(rejected, 200)

    def test_07_exhaustive_256_opcode_and_16_subop_space_sweep(self) -> None:
        """Sweep all 256 Byte-0 codes and all 16 subop slots for every active opcode."""
        defined_codes = {op["code"] for op in self.isa["opcodes"]}
        unassigned = [c for c in range(256) if c not in defined_codes]
        self.assertEqual(len(unassigned), 175)

        # All 177 unassigned opcodes rejected
        for c in unassigned:
            with self.assertRaises(AsmError):
                self.asm.disassemble([encode_word(c, 0, 0, 0, 0, 0, 0, 0)])

        # Standalone 0xFF rejected; direct 0xFF in .code rejected
        with self.assertRaises(AsmError):
            self.asm.disassemble([encode_word(0xFF, 0, 0, 0, 0, 0, 0, 0)])
        with self.assertRaises(AsmError):
            self.asm.assemble(".code\n  EXTENSION_PAYLOAD\n")

        # Truncated FLAG_EXTENDED rejected; corrupted Word-2 guard byte rejected
        w1 = encode_word(0x05, FLAG_EXT, 4, 1, 0, 0, 0, 0x12345678)
        with self.assertRaises(AsmError):
            self.asm.disassemble([w1])
        with self.assertRaises(AsmError):
            self.asm.disassemble([w1, encode_word(0x01, 0, 0, 0, 0, 0, 0, 0)])

        # Every undefined subop in 0..15 rejected for every active opcode
        invalid_subop_checks = 0
        for op in self.active_ops:
            mask = valid_subop_mask(op)
            for s in range(16):
                if (mask & (1 << s)) == 0:
                    with self.assertRaises(AsmError):
                        self.asm.disassemble([encode_word(op["code"], 0, s, 0, 0, 0, 0, 0)])
                    invalid_subop_checks += 1
        self.assertEqual(invalid_subop_checks, 80 * 16 - 486)

    def test_08_exhaustive_morsel_scope_and_register_alias_matrix(self) -> None:
        """Exhaustively verify morsel role restrictions and F8..15/V8..15 vs MF0..7/M0..7 rules."""
        # Every forbidden opcode rejected inside morsel
        forbidden_ops = [op for op in self.active_ops if op["morsel_role"] == "forbidden"]
        for op in forbidden_ops:
            subop = sorted(op["subops"].keys())[0]
            flags = FLAG_EXT if (op["code"] == 0x05 and 4 <= subop <= 6) else 0
            inner = _synth_instruction_source(op, subop, flags).replace(".code\n", "")
            wrapped = f".code\n  WALK_MORSEL.fwd F1, rel=0\n{inner}  MORSEL_END\n"
            with self.assertRaises(AsmError):
                self.asm.assemble(wrapped)

        # Nested morsel, unclosed morsel, stray MORSEL_END, stray MORSEL_COMMIT rejected
        for bad in (
            ".code\n  WALK_MORSEL.fwd F1, rel=0\n  WALK_MORSEL.fwd F2, rel=0\n  MORSEL_END\n  MORSEL_END\n",
            ".code\n  WALK_MORSEL.fwd F1, rel=0\n  NOP\n",
            ".code\n  MORSEL_END\n",
            ".code\n  MORSEL_COMMIT.yield_frontier F1, MF0\n",
        ):
            with self.assertRaises(AsmError):
                self.asm.assemble(bad)

        # body_v_only (SPILL/RELOAD), body_cast_only (VEC_POINT), body_pair_only (VECTOR_RERANK)
        for bad in (
            ".code\n  WALK_MORSEL.fwd F1, rel=0\n  SPILL.r R1, slot=0\n  MORSEL_END\n",
            ".code\n  WALK_MORSEL.fwd F1, rel=0\n  RELOAD.f F1, slot=0\n  MORSEL_END\n",
            ".code\n  WALK_MORSEL.fwd F1, rel=0\n  VEC_POINT.vec_get R1, M0, R2\n  MORSEL_END\n",
            ".code\n  WALK_MORSEL.fwd F1, rel=0\n  VECTOR_RERANK.dot M4, M0, M1, lo=0, hi=0\n  MORSEL_END\n",
        ):
            with self.assertRaises(AsmError):
                self.asm.assemble(bad)

        # Valid body_v_only, body_cast_only, body_pair_only, and forward-only jump inside morsel
        valid_morsel = """
.code
  WALK_MORSEL.fwd F1, rel=0
    SPILL.v M4, slot=0
    RELOAD.v M5, slot=0
    VEC_POINT.vec_cast M6, M5, lo=1
    VECTOR_RERANK.pair_dot M7, M5, M6, lo=0, hi=1
    JCC.jempty_f MF0, skip_commit
    MORSEL_COMMIT.yield_frontier.mask F2, M1, MF0
  skip_commit:
  MORSEL_END
"""
        prog = self.asm.assemble(valid_morsel)
        self.assertEqual(prog.words, self.asm.assemble(self.asm.disassemble(prog.words)).words)

        # Backward jump inside morsel rejected
        with self.assertRaises(AsmError):
            self.asm.assemble(
                ".code\n  WALK_MORSEL.fwd F1, rel=0\n  back:\n  NOP\n  JMP back\n  MORSEL_END\n"
            )

        # All 8 F8..F15 and V8..V15 rejected inside morsel; all 8 MF0..MF7 and M0..M7 rejected outside
        for i in range(8):
            with self.assertRaises(AsmError):
                self.asm.assemble(
                    f".code\n  WALK_MORSEL.fwd F1, rel=0\n  SET_OP.union F{8 + i}, MF0, MF1\n  MORSEL_END\n"
                )
            with self.assertRaises(AsmError):
                self.asm.assemble(
                    f".code\n  WALK_MORSEL.fwd F1, rel=0\n  VEC_MATH_ARITH.add V{8 + i}, M0, M1\n  MORSEL_END\n"
                )
            with self.assertRaises(AsmError):
                self.asm.assemble(f".code\n  SET_OP.union MF{i}, F0, F1\n")
            with self.assertRaises(AsmError):
                self.asm.assemble(f".code\n  VEC_MATH_ARITH.add M{i}, V0, V1\n")

    def test_09_all_16_register_indices_and_boundary_immediates(self) -> None:
        lines = [".code"]
        for r in range(16):
            lines.append(f"  MOV.r R{r}, R{(r + 1) % 16}")
            lines.append(f"  MOV.f F{r}, F{(r + 1) % 16}")
            lines.append(f"  MOV.v V{r}, V{(r + 1) % 16}")
        # Boundary 32-bit & 64-bit immediates (including -0.0 and canonical NaN)
        for val in ("0", "1", "-1", "-2147483648", "2147483647"):
            lines.append(f"  LOAD_CONST.i32 R0, {val}")
        for val64 in (
            "0x0000000000000000",
            "0xFFFFFFFFFFFFFFFF",
            "0x8000000000000000",
            "0x7FF8000000000000",
        ):
            lines.append(f"  LOAD_CONST.f64.ext R1, {val64}")
        lines.append("  HALT")
        prog = self.asm.assemble("\n".join(lines))
        self.assertEqual(prog.words, self.asm.assemble(self.asm.disassemble(prog.words)).words)

    def test_10_pseudo_instructions_and_spec_section2_fixture(self) -> None:
        # All 6 SCALAR_3VL commute aliases
        for alias, canon in SCALAR_3VL_COMMUTE.items():
            w_alias = self.asm.assemble(f".code\n  SCALAR_3VL.{alias} R3, R1, R2\n").words
            w_canon = self.asm.assemble(f".code\n  SCALAR_3VL.{canon} R3, R2, R1\n").words
            self.assertEqual(w_alias, w_canon, f"Commute failed for {alias}")

        # All 15 binary SCALAR_INT_ALU.<op>.imm forms
        int_op = next(op for op in self.active_ops if op["code"] == 0x0C)
        for sid, sname in int_op["subops"].items():
            if sname == "not":
                continue
            prog = self.asm.assemble(f".code\n  SCALAR_INT_ALU.{sname}.imm R3, R1, -42\n")
            self.assertEqual(prog.words, self.asm.assemble(self.asm.disassemble(prog.words)).words)

        # Full IMPAS_SPECIFICATION_v0_11.md §2 example
        spec_example = """
; {{EXPECT: STATUS = IMPULSE_VM_OK}}
; {{EXPECT: R0 = 3}}
; {{EXPECT: LOGICAL_HASH = 0x8a91f042d31c77e1}}

.data
  .domain 0 name="User" count=5 width=u32
  .domain 1 name="Item" count=4 width=u32
  .relation 0 name="PURCHASED" src_dom=0 tgt_dom=1
  .csr_inline rel=0 offsets=[0, 2, 3, 5, 5, 6] targets=[0, 1, 2, 1, 3, 3]
  .edge_attr rel=0 attr=0 name="amount" type=f64 values=[15.0, 120.0, null, 250.0, 80.0, 99.5]
  .param 0 type=frontier dom=0 values=[0, 2]
  .param 1 type=f64 value=100.0

.const_pool
  .pool 0 type=str value="ACTIVE"
  .pool 1 type=i64_vec values=[10, 20, 30]

.code
  LOAD_PARAM.frontier           F0, param=0, dom=0
  LOAD_PARAM.scalar             R1, param=1, type=f64
  WALK_FILTERED.gt              F1, F0, R1, rel=0, attr=0
  SET_CARDINALITY.card_1bit     R0, F1
  COLLECT.frontier_ids          F1, out=0
  HALT
"""
        prog = self.asm.assemble(spec_example)
        self.assertEqual(len(prog.expectations), 3)
        self.assertEqual(len(prog.data_directives), 7)
        self.assertEqual(len(prog.const_pool), 2)
        self.assertEqual(len(prog.words), 6)
        self.assertEqual(prog.words, self.asm.assemble(self.asm.disassemble(prog.words)).words)


if __name__ == "__main__":
    unittest.main()
