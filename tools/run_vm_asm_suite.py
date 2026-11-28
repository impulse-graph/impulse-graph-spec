#!/usr/bin/env python3
"""
ImpulseVM v0.11.0 Metamorphic Compliance & Multi-Dimensional Coverage Suite Runner.

Executes `.impas` v0.11 test vectors under `test-vectors/vm-impas/` against the
OCaml Reference Oracle (`impulse-ocaml --vm-fixture-batch`) across metamorphic
geometry profiles (P0, P1, P2, P3), verifies all `; {{EXPECT: ...}}` assertions,
checks lossless assembler roundtrip, enforces `ICTX v2` `logical_hash` invariance,
and gates 100% `(opcode x subop x flag)` coverage from `v0.11-refactor/isa_v0_11.yaml`.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shlex
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
SPEC_ROOT = TOOLS_DIR.parent
DEFAULT_VECTORS_DIR = SPEC_ROOT / "test-vectors" / "vm-impas"
DEFAULT_OCAML_BIN = SPEC_ROOT.parent / "impulse-ocaml" / "_build" / "default" / "bin" / "main.exe"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from impas_assembler import (
    AsmError,
    FLAG_ACCUM,
    FLAG_EXT,
    FLAG_MASK,
    FLAG_SCALAR,
    ImpAsm,
    SCALAR_TYPE_NAMES,
    decode_word_fields,
)
from isa_loader import load_isa

RAW_WORDS_RE = re.compile(r"^\s*;\s*\{\{RAW_WORDS:\s*(.+?)\s*\}\}\s*$")
EXPECT_LINE_RE = re.compile(r"^\s*;\s*\{\{EXPECT:\s*(.+?)\s*\}\}\s*$")
COV_TAG_RE = re.compile(r"^\s*;\s*\{\{COVERS_NEG:\s*(.+?)\s*\}\}\s*$")


class BatchEngineClient:
    """Persistent stdin/stdout JSONL client for a v0.11 VM engine (`impulse-ocaml` or Java)."""

    def __init__(self, cmd: list[str], label: str = "engine"):
        self.label = label
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def run_fixture(
        self, payload: dict[str, Any], profile: str = "P0", max_steps: int | None = None
    ) -> dict[str, Any]:
        assert self.proc.stdin is not None and self.proc.stdout is not None
        ms = str(max_steps) if max_steps is not None else "-"
        line = f"{profile}\t{ms}\t{json.dumps(payload, separators=(',', ':'))}\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()
        resp = self.proc.stdout.readline()
        if not resp:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"{self.label} batch process terminated unexpectedly: {err}")
        return json.loads(resp)

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.wait(timeout=5)


class OcamlBatchClient(BatchEngineClient):
    """Persistent stdin/stdout JSONL client for `impulse-ocaml --vm-fixture-batch`."""

    def __init__(self, ocaml_bin: Path):
        if not ocaml_bin.exists():
            raise FileNotFoundError(f"OCaml oracle binary not found: {ocaml_bin}")
        super().__init__([str(ocaml_bin), "--vm-fixture-batch"], label="OCaml")


def _u64_to_i64(u: int) -> int:
    u &= 0xFFFFFFFFFFFFFFFF
    return u - 0x10000000000000000 if u >= 0x8000000000000000 else u


def _f64_to_i64_bits(f: float) -> int:
    return _u64_to_i64(struct.unpack("<Q", struct.pack("<d", f))[0])


def _parse_expect_scalar(raw: str) -> tuple[str, Any]:
    s = raw.strip()
    if s.upper() == "NULL":
        return ("null", None)
    if s.startswith('"') and s.endswith('"'):
        return ("str", s[1:-1])
    if s.lower() in ("+inf", "inf"):
        return ("f64_bits", _f64_to_i64_bits(math.inf))
    if s.lower() == "-inf":
        return ("f64_bits", _f64_to_i64_bits(-math.inf))
    if s.lower() in ("-0.0", "+0.0"):
        return ("f64_bits", _f64_to_i64_bits(float(s)))
    if re.fullmatch(r"-?0[xX][0-9a-fA-F]+", s):
        return ("int64", _u64_to_i64(int(s, 16)))
    if re.fullmatch(r"-?[0-9]+", s):
        return ("int64", _u64_to_i64(int(s, 10)))
    if re.fullmatch(r"-?[0-9]+\.[0-9]+([eE][+-]?[0-9]+)?", s):
        return ("f64_bits", _f64_to_i64_bits(float(s)))
    return ("raw", s)


def _parse_expectations(src: str) -> tuple[list[tuple[str, str]], list[int] | None, list[str]]:
    expects: list[tuple[str, str]] = []
    raw_words: list[int] | None = None
    cov_neg_tags: list[str] = []
    for line in src.splitlines():
        m_raw = RAW_WORDS_RE.match(line)
        if m_raw:
            toks = [t.strip() for t in m_raw.group(1).split(",") if t.strip()]
            raw_words = [int(t, 0) & 0xFFFFFFFFFFFFFFFF for t in toks]
            continue
        m_cov = COV_TAG_RE.match(line)
        if m_cov:
            cov_neg_tags.extend(t.strip() for t in m_cov.group(1).split(",") if t.strip())
            continue
        m_exp = EXPECT_LINE_RE.match(line)
        if m_exp:
            body = m_exp.group(1)
            # Support comma-separated flag clauses like "ZF = 0, ST = 1, NF = 0"
            if "=" in body:
                k0 = body.split("=", 1)[0].strip().upper()
                if k0 in ("ZF", "ST", "NF") and "," in body:
                    for part in body.split(","):
                        if "=" in part:
                            pk, pv = part.split("=", 1)
                            expects.append((pk.strip().upper(), pv.strip()))
                    continue
                k, v = body.split("=", 1)
                expects.append((k.strip().upper(), v.strip()))
    return expects, raw_words, cov_neg_tags


def _check_expectations(
    expects: list[tuple[str, str]], res: dict[str, Any], profile: str
) -> list[str]:
    errs: list[str] = []
    for k, v in expects:
        if k in ("MAX_STEPS", "ASM_ERROR"):
            continue
        if k == "STATUS":
            if res.get("status") != v:
                errs.append(f"[{profile}] STATUS expected {v}, got {res.get('status')}")
        elif k == "LOGICAL_HASH":
            if res.get("logical_hash", "").lower() != v.lower():
                errs.append(f"[{profile}] LOGICAL_HASH expected {v}, got {res.get('logical_hash')}")
        elif k == "PHYSICAL_HASH":
            if profile == "P0" and res.get("physical_hash", "").lower() != v.lower():
                errs.append(f"[{profile}] PHYSICAL_HASH expected {v}, got {res.get('physical_hash')}")
        elif k == "PC":
            if res.get("pc") != int(v, 0):
                errs.append(f"[{profile}] PC expected {v}, got {res.get('pc')}")
        elif k == "MAX_DOP":
            if res.get("max_dop") != int(v, 0):
                errs.append(f"[{profile}] MAX_DOP expected {v}, got {res.get('max_dop')}")
        elif k == "USER_THROW_CODE":
            if res.get("user_throw_code") != int(v, 0):
                errs.append(
                    f"[{profile}] USER_THROW_CODE expected {v}, got {res.get('user_throw_code')}"
                )
        elif k in ("ZF", "ST", "NF"):
            want = bool(int(v, 0))
            got = bool(res.get("flags", {}).get(k.lower(), False))
            if got != want:
                errs.append(f"[{profile}] {k} expected {int(want)}, got {int(got)}")
        elif k == "R_VALID_MASK":
            if res.get("r_valid_mask") != int(v, 0):
                errs.append(
                    f"[{profile}] R_VALID_MASK expected {v}, got 0x{res.get('r_valid_mask', 0):04x}"
                )
        elif k == "R_TYPE_WORD":
            if res.get("r_type_word", "").lower() != v.lower():
                errs.append(f"[{profile}] R_TYPE_WORD expected {v}, got {res.get('r_type_word')}")
        elif re.fullmatch(r"R([0-9]|1[0-5])_TYPE", k):
            rname = k[:-5]
            want_ty = SCALAR_TYPE_NAMES.get(v.lower(), int(v, 0) if v.isdigit() else -1)
            got_ty = res.get("r_types", {}).get(rname)
            if got_ty != want_ty:
                errs.append(f"[{profile}] {k} expected {want_ty}, got {got_ty}")
        elif re.fullmatch(r"R([0-9]|1[0-5])", k):
            kind, want_val = _parse_expect_scalar(v)
            got_val = res.get("r_regs", {}).get(k)
            if kind == "null":
                if got_val is not None:
                    errs.append(f"[{profile}] {k} expected NULL, got {got_val!r}")
            elif kind == "str":
                if got_val != want_val:
                    errs.append(f"[{profile}] {k} expected {want_val!r}, got {got_val!r}")
            elif kind in ("int64", "f64_bits"):
                if not isinstance(got_val, int) or _u64_to_i64(got_val) != want_val:
                    errs.append(
                        f"[{profile}] {k} expected {want_val} (0x{want_val & 0xFFFFFFFFFFFFFFFF:016x}), "
                        f"got {got_val!r}"
                    )
        elif re.fullmatch(r"F([0-9]|1[0-5])", k):
            got_f = res.get("f_regs", {}).get(k)
            if v.upper() == "NULL":
                if got_f is not None:
                    errs.append(f"[{profile}] {k} expected NULL, got {got_f}")
            else:
                m_f = re.fullmatch(r"\[(.*?)\]\s*(?:\(dom=([0-9]+)\))?", v)
                if not m_f:
                    errs.append(f"[{profile}] malformed frontier expectation {k}={v}")
                elif got_f is None:
                    errs.append(f"[{profile}] {k} expected {v}, got NULL")
                else:
                    inner = m_f.group(1).strip()
                    want_nodes = [int(x.strip(), 0) for x in inner.split(",") if x.strip()] if inner else []
                    if got_f.get("nodes") != want_nodes:
                        errs.append(f"[{profile}] {k}.nodes expected {want_nodes}, got {got_f.get('nodes')}")
                    if m_f.group(2) is not None and got_f.get("domain_id") != int(m_f.group(2)):
                        errs.append(
                            f"[{profile}] {k}.domain_id expected {m_f.group(2)}, got {got_f.get('domain_id')}"
                        )
        elif re.fullmatch(r"COLLECT_[0-9]+", k):
            slot = k.split("_", 1)[1]
            got_out = res.get("outputs", {}).get(slot)
            want_out = json.loads(v)
            if got_out != want_out:
                errs.append(f"[{profile}] {k} expected {want_out}, got {got_out}")
    return errs


def _record_words_coverage(
    words: list[int],
    is_positive: bool,
    vec_file: Path,
    op_pos_files: dict[int, set[str]],
    op_neg_files: dict[int, set[str]],
    subop_pos: dict[tuple[int, int], set[str]],
    subop_neg: dict[tuple[int, int], set[str]],
    flag_pos: dict[tuple[int, int], set[str]],
    flag_neg: dict[tuple[int, int], set[str]],
    by_code: dict[int, dict[str, Any]],
) -> None:
    fname = str(vec_file)
    i = 0
    while i < len(words):
        code, flags, subop, _dst, _s1, _s2, _s3, _imm = decode_word_fields(words[i])
        if code in by_code:
            op = by_code[code]
            allowed = op["allowed_flags"]
            if is_positive:
                op_pos_files[code].add(fname)
                subop_pos[(code, subop)].add(fname)
                for bit in (FLAG_MASK, FLAG_SCALAR, FLAG_ACCUM, FLAG_EXT):
                    if flags & bit:
                        flag_pos[(code, bit)].add(fname)
            else:
                op_neg_files[code].add(fname)
                if subop in op["subops"]:
                    subop_neg[(code, subop)].add(fname)
                disallowed = flags & (~allowed & 0xF)
                for bit in (FLAG_MASK, FLAG_SCALAR, FLAG_ACCUM, FLAG_EXT):
                    if disallowed & bit:
                        flag_neg[(code, bit)].add(fname)
        if (flags & FLAG_EXT) and i + 1 < len(words):
            i += 2
        else:
            i += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ImpulseVM v0.11.0 Compliance & Coverage Runner")
    parser.add_argument("--vectors-dir", type=Path, default=DEFAULT_VECTORS_DIR)
    parser.add_argument("--ocaml-bin", type=Path, default=DEFAULT_OCAML_BIN)
    parser.add_argument("--java-cmd", type=str, default=None,
                        help="Command line (shlex-split) to launch Java VmFixtureBatchMain for 2-way OCaml parity")
    parser.add_argument("--pillar", type=int, choices=[1, 2, 3, 4, 5], default=None)
    parser.add_argument("--profiles", type=str, default="P0,P1,P2,P3")
    parser.add_argument("--filter", type=str, default=None)
    parser.add_argument("--check-coverage", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    isa = load_isa()
    by_code = {op["code"]: op for op in isa["opcodes"]}
    asm = ImpAsm()
    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]

    if args.pillar is not None:
        pillar_dirs = sorted(args.vectors_dir.glob(f"0{args.pillar}_*"))
        files = sorted(p for d in pillar_dirs for p in d.rglob("*.impas"))
    else:
        files = sorted(args.vectors_dir.rglob("*.impas"))

    if args.filter:
        files = [f for f in files if args.filter in str(f)]

    if not files:
        print(f"No .impas test vectors found in {args.vectors_dir}", file=sys.stderr)
        return 1

    op_pos_files: dict[int, set[str]] = defaultdict(set)
    op_neg_files: dict[int, set[str]] = defaultdict(set)
    subop_pos: dict[tuple[int, int], set[str]] = defaultdict(set)
    subop_neg: dict[tuple[int, int], set[str]] = defaultdict(set)
    flag_pos: dict[tuple[int, int], set[str]] = defaultdict(set)
    flag_neg: dict[tuple[int, int], set[str]] = defaultdict(set)

    client = OcamlBatchClient(args.ocaml_bin)
    java_client = (
        BatchEngineClient(shlex.split(args.java_cmd), label="Java")
        if args.java_cmd
        else None
    )
    passed = 0
    failed = 0
    metamorphic_checks = 0
    java_parity_checks = 0

    try:
        for vec_file in files:
            src = vec_file.read_text(encoding="utf-8")
            expects, raw_words, cov_neg_tags = _parse_expectations(src)
            exp_dict = dict(expects)
            max_steps = int(exp_dict["MAX_STEPS"], 0) if "MAX_STEPS" in exp_dict else None
            rel_name = vec_file.relative_to(args.vectors_dir)

            # 1. Assembler-rejection negative vector
            if "ASM_ERROR" in exp_dict:
                want_sub = exp_dict["ASM_ERROR"]
                try:
                    asm.assemble(src)
                    print(f"FAIL {rel_name}: expected AsmError containing {want_sub!r}, but assembled cleanly")
                    failed += 1
                    continue
                except AsmError as exc:
                    if want_sub.lower() not in str(exc).lower():
                        print(f"FAIL {rel_name}: AsmError {str(exc)!r} did not match {want_sub!r}")
                        failed += 1
                        continue
                # Record negative coverage from COVERS_NEG tags (e.g. "0x05:subop=4", "0x01:flag=0x4")
                for tag in cov_neg_tags:
                    m_op = re.fullmatch(r"(0x[0-9a-fA-F]+)(?::subop=([0-9]+))?(?::flag=(0x[0-9a-fA-F]+))?", tag)
                    if m_op:
                        c = int(m_op.group(1), 16)
                        op_neg_files[c].add(str(vec_file))
                        if m_op.group(2) is not None:
                            subop_neg[(c, int(m_op.group(2)))].add(str(vec_file))
                        if m_op.group(3) is not None:
                            flag_neg[(c, int(m_op.group(3), 16))].add(str(vec_file))
                passed += 1
                if args.verbose:
                    print(f"PASS {rel_name} (ASM_ERROR)")
                continue

            # 2. Raw bytecode validator-rejection negative vector OR assembled vector
            if raw_words is not None:
                words = raw_words
                data_directives: list[dict[str, Any]] = []
                const_pool: list[dict[str, Any]] = []
                is_positive = exp_dict.get("STATUS", "IMPULSE_VM_OK") == "IMPULSE_VM_OK"
            else:
                try:
                    prog = asm.assemble(src)
                except AsmError as exc:
                    print(f"FAIL {rel_name}: unexpected AsmError: {exc}")
                    failed += 1
                    continue
                words = prog.words
                data_directives = prog.data_directives
                const_pool = prog.const_pool
                is_positive = exp_dict.get("STATUS", "IMPULSE_VM_OK") == "IMPULSE_VM_OK"

                # Lossless roundtrip check on positive vectors
                if is_positive:
                    try:
                        dis = asm.disassemble(words)
                        prog2 = asm.assemble(dis)
                        if prog2.words != words:
                            print(f"FAIL {rel_name}: assembler roundtrip mismatch")
                            failed += 1
                            continue
                    except Exception as exc:
                        print(f"FAIL {rel_name}: assembler roundtrip error: {exc}")
                        failed += 1
                        continue

            has_pinned_tiers = any(d.get("directive") == ".tier_thresholds" for d in data_directives)
            run_profiles = ["P0"] if (has_pinned_tiers or not is_positive) else profiles

            fixture_payload = {
                "data_directives": data_directives,
                "const_pool": const_pool,
                "words_hex": [f"0x{w:016X}" for w in words],
            }

            vec_errs: list[str] = []
            logical_hashes: dict[str, str] = {}
            java_logical_hashes: dict[str, str] = {}
            has_transcendental = any(
                (w & 0xFF) in (0x49, 0x4A, 0x4B) for w in words
            )
            for prof in run_profiles:
                res = client.run_fixture(fixture_payload, profile=prof, max_steps=max_steps)
                vec_errs.extend(_check_expectations(expects, res, prof))
                logical_hashes[prof] = res.get("logical_hash", "")

                if java_client is not None:
                    jres = java_client.run_fixture(fixture_payload, profile=prof, max_steps=max_steps)
                    java_parity_checks += 1
                    vec_errs.extend(
                        f"Java {e}" for e in _check_expectations(expects, jres, prof)
                    )
                    java_logical_hashes[prof] = jres.get("logical_hash", "")
                    if jres.get("status") != res.get("status"):
                        vec_errs.append(
                            f"[{prof}] Java vs OCaml STATUS mismatch: Java={jres.get('status')} OCaml={res.get('status')}"
                        )
                    elif jres.get("pc") != res.get("pc"):
                        vec_errs.append(
                            f"[{prof}] Java vs OCaml PC mismatch: Java={jres.get('pc')} OCaml={res.get('pc')}"
                        )
                    elif not has_transcendental and jres.get("logical_hash", "").lower() != res.get("logical_hash", "").lower():
                        vec_errs.append(
                            f"[{prof}] Java vs OCaml ICTX v2 logical_hash mismatch: "
                            f"Java={jres.get('logical_hash')} OCaml={res.get('logical_hash')}"
                        )

            if is_positive and len(logical_hashes) > 1:
                metamorphic_checks += 1
                uniq = set(logical_hashes.values())
                if len(uniq) != 1:
                    vec_errs.append(f"Metamorphic logical_hash divergence across profiles: {logical_hashes}")
                if java_client is not None and not has_transcendental:
                    juniq = set(java_logical_hashes.values())
                    if len(juniq) != 1:
                        vec_errs.append(f"Java metamorphic logical_hash divergence across profiles: {java_logical_hashes}")

            if vec_errs:
                failed += 1
                print(f"FAIL {rel_name}:")
                for e in vec_errs:
                    print(f"  - {e}")
            else:
                passed += 1
                if args.verbose:
                    print(f"PASS {rel_name} ({','.join(run_profiles)} -> {logical_hashes.get('P0', '')})")
                _record_words_coverage(
                    words,
                    is_positive,
                    vec_file,
                    op_pos_files,
                    op_neg_files,
                    subop_pos,
                    subop_neg,
                    flag_pos,
                    flag_neg,
                    by_code,
                )
                for tag in cov_neg_tags:
                    m_op = re.fullmatch(r"(0x[0-9a-fA-F]+)(?::subop=([0-9]+))?(?::flag=(0x[0-9a-fA-F]+))?", tag)
                    if m_op:
                        c = int(m_op.group(1), 16)
                        op_neg_files[c].add(str(vec_file))
                        if m_op.group(2) is not None:
                            subop_neg[(c, int(m_op.group(2)))].add(str(vec_file))
                        if m_op.group(3) is not None:
                            flag_neg[(c, int(m_op.group(3), 16))].add(str(vec_file))
    finally:
        client.close()
        if java_client is not None:
            java_client.close()

    java_suffix = f", {java_parity_checks} Java≡OCaml ICTX v2 checks" if java_client is not None else ""
    print(
        f"\nSummary: {passed}/{passed + failed} vectors passed "
        f"({metamorphic_checks} metamorphic P0..P3 invariance checks{java_suffix})."
    )
    if failed > 0:
        return 1

    if args.check_coverage:
        target_ops = [
            op
            for op in isa["opcodes"]
            if op["code"] != 0xFF and (args.pillar is None or op["pillar"] == args.pillar)
        ]
        cov_errors: list[str] = []
        tot_subops = 0
        cov_subops_pos = 0
        cov_subops_neg = 0
        for op in target_ops:
            c = op["code"]
            mnem = op["mnemonic"]
            if len(op_pos_files[c]) < 2:
                cov_errors.append(f"0x{c:02X} {mnem}: only {len(op_pos_files[c])} positive files (need >= 2)")
            if len(op_neg_files[c]) < 2:
                cov_errors.append(f"0x{c:02X} {mnem}: only {len(op_neg_files[c])} negative files (need >= 2)")
            for so, sname in sorted(op["subops"].items()):
                tot_subops += 1
                p_cnt = len(subop_pos[(c, so)])
                n_cnt = len(subop_neg[(c, so)])
                if p_cnt >= 2:
                    cov_subops_pos += 1
                else:
                    cov_errors.append(
                        f"0x{c:02X} {mnem}.{sname} (subop {so}): {p_cnt} positive files (need >= 2)"
                    )
                if n_cnt >= 1:
                    cov_subops_neg += 1
                else:
                    cov_errors.append(
                        f"0x{c:02X} {mnem}.{sname} (subop {so}): {n_cnt} negative files (need >= 1)"
                    )
            allowed = op["allowed_flags"]
            for bit in (FLAG_MASK, FLAG_SCALAR, FLAG_ACCUM, FLAG_EXT):
                if allowed & bit:
                    if len(flag_pos[(c, bit)]) < 1:
                        cov_errors.append(f"0x{c:02X} {mnem}: allowed flag 0x{bit:X} untested in positive vectors")
        print(
            f"Coverage (pillar={args.pillar or 'ALL'}): {len(target_ops)} opcodes, "
            f"{cov_subops_pos}/{tot_subops} subops >=2 pos, {cov_subops_neg}/{tot_subops} subops >=1 neg."
        )
        if cov_errors:
            print(f"Coverage gate FAILED ({len(cov_errors)} gaps):", file=sys.stderr)
            for e in cov_errors[:40]:
                print(f"  - {e}", file=sys.stderr)
            if len(cov_errors) > 40:
                print(f"  ... and {len(cov_errors) - 40} more.", file=sys.stderr)
            return 1
        print("Coverage gate PASSED 100%!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
