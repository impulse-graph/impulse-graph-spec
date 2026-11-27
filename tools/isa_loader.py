#!/usr/bin/env python3
"""
Zero-dependency loader and strict schema validator for ImpulseVM v0.11.0 ISA YAML
(`v0.11-refactor/isa_v0_11.yaml`).

Uses `yaml.safe_load` when PyYAML is available, and falls back to an exact stdlib
YAML subset parser so all M0 tools run out-of-the-box with Python 3 stdlib only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

SPEC_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ISA_PATH = SPEC_ROOT / "v0.11-refactor" / "isa_v0_11.yaml"

VALID_MORSEL_ROLES = frozenset({
    "forbidden",
    "body_ok",
    "body_cast_only",
    "body_v_only",
    "body_pair_only",
    "fwd_jump_only",
    "header",
    "commit_only",
    "end_only",
})

VALID_IMM_LAYOUTS = frozenset({
    "NONE",
    "U32",
    "OPT_U32",
    "OPT_I32",
    "REL_PC_I32",
    "U16_LO",
    "U16_HI",
    "OPT_U16_LO",
    "U16_PAIR",
    "OPT_U16_PAIR",
    "OPT_DOMAIN_U16",
    "LEN_OR_DOM",
    "CONST_PAYLOAD",
    "POOL_DESC",
    "EXT_WORD_2",
})

VALID_VM_FLAGS = frozenset({"ZF", "ST", "NF"})


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for i, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_double:
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i].rstrip()
    return line.rstrip()


def _parse_scalar(text: str) -> Any:
    s = text.strip()
    if s == "":
        return ""
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        inner = s[1:-1]
        if s.startswith('"'):
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    if s == "true":
        return True
    if s == "false":
        return False
    if s in ("null", "~"):
        return None
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", s):
        return int(s, 16)
    if re.fullmatch(r"-?[0-9]+", s):
        return int(s, 10)
    if re.fullmatch(r"-?[0-9]+\.[0-9]+", s):
        return float(s)
    return s


def _split_flow_items(s: str) -> list[str]:
    items: list[str] = []
    cur: list[str] = []
    depth = 0
    in_single = False
    in_double = False
    escaped = False
    for ch in s:
        if escaped:
            cur.append(ch)
            escaped = False
            continue
        if ch == "\\" and in_double:
            cur.append(ch)
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            cur.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            cur.append(ch)
        elif not in_single and not in_double:
            if ch in "{[":
                depth += 1
                cur.append(ch)
            elif ch in "}]":
                depth -= 1
                cur.append(ch)
            elif ch == "," and depth == 0:
                item = "".join(cur).strip()
                if item:
                    items.append(item)
                cur = []
            else:
                cur.append(ch)
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        items.append(tail)
    return items


def _find_colon_outside_quotes(s: str) -> int:
    in_single = False
    in_double = False
    depth = 0
    escaped = False
    for i, ch in enumerate(s):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_double:
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
            elif ch == ":" and depth == 0:
                if i + 1 == len(s) or s[i + 1] in (" ", "\t"):
                    return i
    return -1


def _parse_flow(text: str) -> Any:
    s = text.strip()
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1].strip()
        out: dict[Any, Any] = {}
        if not inner:
            return out
        for item in _split_flow_items(inner):
            idx = _find_colon_outside_quotes(item)
            if idx < 0:
                raise ValueError(f"Invalid flow mapping entry: {item!r}")
            k = _parse_scalar(item[:idx])
            v = _parse_value(item[idx + 1 :])
            out[k] = v
        return out
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(item) for item in _split_flow_items(inner)]
    return _parse_scalar(s)


def _parse_value(text: str) -> Any:
    s = text.strip()
    if s.startswith("{") or s.startswith("["):
        return _parse_flow(s)
    return _parse_scalar(s)


def _parse_yaml_stdlib(raw: str) -> dict[Any, Any]:
    tokens: list[tuple[int, str]] = []
    for raw_line in raw.splitlines():
        cleaned = _strip_comment(raw_line)
        if not cleaned.strip():
            continue
        indent = len(cleaned) - len(cleaned.lstrip(" "))
        tokens.append((indent, cleaned.lstrip(" ")))

    def parse_block(idx: int, min_indent: int) -> tuple[Any, int]:
        if idx >= len(tokens):
            return {}, idx
        indent, text = tokens[idx]
        if text.startswith("- "):
            return parse_seq(idx, indent)
        return parse_map(idx, indent)

    def parse_seq(idx: int, seq_indent: int) -> tuple[list[Any], int]:
        out: list[Any] = []
        while idx < len(tokens):
            indent, text = tokens[idx]
            if indent < seq_indent:
                break
            if indent > seq_indent or not text.startswith("- "):
                break
            rest = text[2:].strip()
            idx += 1
            if not rest:
                val, idx = parse_block(idx, seq_indent + 1)
                out.append(val)
                continue
            colon_i = _find_colon_outside_quotes(rest)
            if colon_i >= 0:
                item_map: dict[Any, Any] = {}
                k = _parse_scalar(rest[:colon_i])
                v_str = rest[colon_i + 1 :].strip()
                if v_str:
                    item_map[k] = _parse_value(v_str)
                else:
                    item_map[k], idx = parse_block(idx, seq_indent + 2)
                if idx < len(tokens) and tokens[idx][0] > seq_indent:
                    sub_map, idx = parse_map(idx, tokens[idx][0])
                    item_map.update(sub_map)
                out.append(item_map)
            else:
                out.append(_parse_value(rest))
        return out, idx

    def parse_map(idx: int, map_indent: int) -> tuple[dict[Any, Any], int]:
        out: dict[Any, Any] = {}
        while idx < len(tokens):
            indent, text = tokens[idx]
            if indent < map_indent:
                break
            if indent > map_indent:
                raise ValueError(f"Unexpected indentation at line: {text!r}")
            if text.startswith("- "):
                break
            colon_i = _find_colon_outside_quotes(text)
            if colon_i < 0:
                raise ValueError(f"Expected 'key: value' at line: {text!r}")
            k = _parse_scalar(text[:colon_i])
            v_str = text[colon_i + 1 :].strip()
            idx += 1
            if v_str:
                out[k] = _parse_value(v_str)
            else:
                if idx < len(tokens) and tokens[idx][0] > map_indent:
                    val, idx = parse_block(idx, map_indent + 1)
                    out[k] = val
                else:
                    out[k] = None
        return out, idx

    root, end_idx = parse_block(0, 0)
    if end_idx != len(tokens):
        raise ValueError(f"Unparsed YAML trailing tokens at index {end_idx}: {tokens[end_idx]}")
    if not isinstance(root, dict):
        raise ValueError("ISA YAML root must be a mapping")
    return root


def load_isa(path: Path | str = DEFAULT_ISA_PATH) -> dict[str, Any]:
    isa_path = Path(path)
    raw = isa_path.read_text(encoding="utf-8")
    parsed_stdlib = _parse_yaml_stdlib(raw)
    try:
        import yaml  # type: ignore

        parsed_pyyaml = yaml.safe_load(raw)
        if parsed_pyyaml != parsed_stdlib:
            raise ValueError("Stdlib YAML parser diverged from PyYAML safe_load!")
        data = parsed_pyyaml
    except ModuleNotFoundError:
        data = parsed_stdlib
    validate_isa(data)
    return data


def validate_isa(data: dict[str, Any]) -> None:
    if data.get("schema_version") != 1:
        raise ValueError(f"Expected schema_version == 1, got {data.get('schema_version')!r}")
    if data.get("isa_name") != "impOps":
        raise ValueError(f"Expected isa_name == 'impOps', got {data.get('isa_name')!r}")
    if data.get("impb_magic") != 0x494D5042:
        raise ValueError(f"Expected impb_magic == 0x494D5042, got {data.get('impb_magic')!r}")
    if data.get("impb_version_u16") != 11:
        raise ValueError(f"Expected impb_version_u16 == 11, got {data.get('impb_version_u16')!r}")

    opcodes = data.get("opcodes")
    if not isinstance(opcodes, list):
        raise ValueError("Missing or invalid 'opcodes' list")

    active_count = 0
    ext_count = 0
    seen_codes: set[int] = set()
    seen_names: set[str] = set()
    seen_mnemonics: set[str] = set()

    for op in opcodes:
        code = op["code"]
        name = op["name"]
        mnemonic = op["mnemonic"]
        pillar = op["pillar"]
        allowed_flags = op["allowed_flags"]
        morsel_role = op["morsel_role"]
        banks = op["banks"]
        imm_layout = op["imm_layout"]
        sets_vm_flags = op["sets_vm_flags"]
        subops = op["subops"]

        if not isinstance(code, int) or not (0 <= code <= 0xFF):
            raise ValueError(f"Invalid opcode byte {code!r} for {name}")
        if code in seen_codes:
            raise ValueError(f"Duplicate opcode code 0x{code:02X}")
        seen_codes.add(code)

        if name in seen_names:
            raise ValueError(f"Duplicate opcode name {name}")
        seen_names.add(name)

        if mnemonic in seen_mnemonics:
            raise ValueError(f"Duplicate mnemonic {mnemonic}")
        seen_mnemonics.add(mnemonic)

        if code == 0xFF:
            if name != "OP_EXTENSION_PAYLOAD" or pillar != 0:
                raise ValueError("0xFF must be OP_EXTENSION_PAYLOAD with pillar 0")
            ext_count += 1
        else:
            if pillar not in (1, 2, 3, 4, 5):
                raise ValueError(f"{name}: invalid pillar {pillar!r}")
            active_count += 1

        if not isinstance(allowed_flags, int) or not (0 <= allowed_flags <= 0xF):
            raise ValueError(f"{name}: allowed_flags out of 0x0..0xF: {allowed_flags!r}")

        if morsel_role not in VALID_MORSEL_ROLES:
            raise ValueError(f"{name}: invalid morsel_role {morsel_role!r}")

        if set(banks.keys()) != {"dst", "s1", "s2", "s3"}:
            raise ValueError(f"{name}: banks must have keys dst,s1,s2,s3, got {banks.keys()}")

        if imm_layout not in VALID_IMM_LAYOUTS:
            raise ValueError(f"{name}: invalid imm_layout {imm_layout!r}")

        if not isinstance(sets_vm_flags, list) or not set(sets_vm_flags).issubset(VALID_VM_FLAGS):
            raise ValueError(f"{name}: invalid sets_vm_flags {sets_vm_flags!r}")

        if not isinstance(subops, dict) or not subops:
            raise ValueError(f"{name}: subops must be a non-empty mapping")

        seen_subop_names: set[str] = set()
        for sid, sname in subops.items():
            if not isinstance(sid, int) or not (0 <= sid <= 15):
                raise ValueError(f"{name}: subop id {sid!r} out of 0..15")
            if not isinstance(sname, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", sname):
                raise ValueError(f"{name}: invalid subop name {sname!r}")
            if sname in seen_subop_names:
                raise ValueError(f"{name}: duplicate subop name {sname!r}")
            seen_subop_names.add(sname)

    if active_count != 80 or ext_count != 1:
        raise ValueError(
            f"Expected 80 active opcodes + 1 extension (0xFF), got {active_count} + {ext_count}"
        )


def valid_subop_mask(op: dict[str, Any]) -> int:
    mask = 0
    for sid in op["subops"].keys():
        mask |= 1 << int(sid)
    return mask


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ISA_PATH
    isa = load_isa(path)
    total_subops = sum(len(op["subops"]) for op in isa["opcodes"])
    print(
        f"OK: {path.name} validated ({len(isa['opcodes']) - 1} active opcodes + 0xFF, "
        f"{total_subops} total subops, impb v{isa['impb_version_u16']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
