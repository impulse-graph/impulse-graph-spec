#!/usr/bin/env python3
"""
GFM (GitHub Flavored Markdown) Linter for ImpulseVM v0.11.0 specification docs.

Checks all `v0.11-refactor/*.md` files for:
  1. Balanced fenced code blocks (``` / ````)
  2. Consistent column counts in Markdown tables (header, separator, body)
  3. Valid relative internal file links (no broken links)
  4. Valid heading formatting (no empty headings)
  5. No trailing unclosed inline LaTeX `$` pairs on prose lines
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SPEC_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = SPEC_ROOT / "v0.11-refactor"

LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")


def _split_table_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells: list[str] = []
    cur: list[str] = []
    escaped = False
    in_code = False
    for ch in s:
        if escaped:
            cur.append(ch)
            escaped = False
            continue
        if ch == "\\":
            cur.append(ch)
            escaped = True
            continue
        if ch == "`":
            in_code = not in_code
            cur.append(ch)
            continue
        if ch == "|" and not in_code:
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    cells.append("".join(cur).strip())
    return cells


def _is_table_sep(line: str) -> bool:
    cells = _split_table_cells(line)
    if not cells:
        return False
    return all(re.fullmatch(r":?-{3,}:?", c) is not None for c in cells)


def _strip_inline_code(line: str) -> str:
    return re.sub(r"`[^`]*`", "", line)


def lint_file(path: Path) -> list[str]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    in_fence = False
    fence_char = ""
    fence_len = 0
    fence_start_line = 0

    table_cols: int | None = None

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # 1. Code fence tracking
        m_fence = re.match(r"^(`{3,}|~{3,})", stripped)
        if m_fence:
            marker = m_fence.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
                fence_len = len(marker)
                fence_start_line = idx
                table_cols = None
            elif marker[0] == fence_char and len(marker) >= fence_len and stripped == marker:
                in_fence = False
            continue

        if in_fence:
            continue

        # 2. Table column consistency
        if stripped.startswith("|") and stripped.endswith("|") and len(stripped) >= 2:
            cols = len(_split_table_cells(stripped))
            if table_cols is None:
                # Start of a table; check next line if it's a separator
                if idx < len(lines) and _is_table_sep(lines[idx].strip()):
                    sep_cols = len(_split_table_cells(lines[idx].strip()))
                    if sep_cols != cols:
                        errors.append(
                            f"{path.name}:{idx + 1}: table separator has {sep_cols} cols, header has {cols}"
                        )
                    table_cols = cols
            else:
                if cols != table_cols:
                    errors.append(
                        f"{path.name}:{idx}: table row has {cols} cols, expected {table_cols}"
                    )
        else:
            table_cols = None

        # 3. Heading check
        if re.match(r"^#{1,6}\s*$", stripped):
            errors.append(f"{path.name}:{idx}: empty Markdown heading")

        # 4. Relative link check
        for _, target in LINK_RE.findall(_strip_inline_code(line)):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            file_part = target.split("#", 1)[0].strip()
            if not file_part:
                continue
            resolved = (path.parent / file_part).resolve()
            if not resolved.exists():
                errors.append(f"{path.name}:{idx}: broken relative link '{target}'")

        # 5. Unescaped inline '$' parity check outside inline code
        prose = _strip_inline_code(line)
        # Remove display math $$...$$ and escaped \$
        prose = prose.replace("\\$", "")
        prose = re.sub(r"\$\$", "", prose)
        if prose.count("$") % 2 != 0:
            errors.append(f"{path.name}:{idx}: unbalanced inline LaTeX '$' delimiter")

    if in_fence:
        errors.append(f"{path.name}:{fence_start_line}: unclosed code fence")

    return errors


def lint_directory(target_dir: Path = DEFAULT_DIR) -> list[str]:
    all_errors: list[str] = []
    md_files = sorted(target_dir.glob("*.md"))
    if not md_files:
        all_errors.append(f"No .md files found in {target_dir}")
        return all_errors
    for md in md_files:
        all_errors.extend(lint_file(md))
    return all_errors


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    errors = lint_directory(target)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        print(f"GFM lint FAILED with {len(errors)} error(s).", file=sys.stderr)
        return 1
    md_count = len(list(target.glob("*.md")))
    print(f"OK: GFM lint passed across {md_count} Markdown files in {target.name}/ (0 errors).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
