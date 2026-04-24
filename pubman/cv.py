from __future__ import annotations

import re
from pathlib import Path

from .config import CVConfig


def _cv_section_bounds(lines: list, section_name: str):
    """Return (header_idx, insert_idx, end_idx, max_num), or None if section not found."""
    header_re = re.compile(r"\\cvsection\{" + re.escape(section_name) + r"\}")
    boundary_re = re.compile(r"\\cvsection\{|\\end\{longtable\}")

    header_idx = next((i for i, ln in enumerate(lines) if header_re.search(ln)), None)
    if header_idx is None:
        return None

    end_idx = next(
        (i for i, ln in enumerate(lines[header_idx + 1:], header_idx + 1)
         if boundary_re.search(ln)),
        len(lines),
    )

    section_text = "".join(lines[header_idx:end_idx])
    numbers = [int(n) for n in re.findall(r"\\pubentry\{(\d+)\}", section_text)]
    max_num = max(numbers, default=0)

    # Publications has an extra \\ spacer line immediately after the header; skip it.
    lookahead = lines[header_idx + 1] if header_idx + 1 < len(lines) else ""
    insert_idx = header_idx + 2 if re.match(r"\s*\\\\\s*$", lookahead) else header_idx + 1

    return header_idx, insert_idx, end_idx, max_num


def _entry_indent(lines: list, start: int, end: int) -> str:
    for ln in lines[start:end]:
        if r"\pubentry" in ln:
            return re.match(r"^(\s*)", ln).group(1)
    return "\t\t\t\t\t\t\t\t"


def update_cv_tex(key: str, category: str, config: CVConfig, root: Path) -> None:
    r"""Insert a \pubentry line for key into the mapped LaTeX CV section."""
    section_name = config.section_map.get(category)
    if not section_name:
        print(f"  No CV section mapped for category '{category}'; skipping CV update.")
        return

    lines = config.tex.read_text().splitlines(keepends=True)
    result = _cv_section_bounds(lines, section_name)
    if result is None:
        print(f"  Warning: \\cvsection{{{section_name}}} not found in {config.tex.name}.")
        return

    header_idx, insert_idx, end_idx, max_num = result
    next_num = max_num + 1
    indent = _entry_indent(lines, insert_idx, end_idx)

    if category == "peer-reviewed":
        new_line = f"{indent}\\pubgraphic{{{key}}}\t& \\pubentry{{{next_num}}}{{{key}}}\n\n"
    else:
        new_line = f"{indent}& \\pubentry{{{next_num}}}{{{key}}}\n"

    lines.insert(insert_idx, new_line)
    config.tex.write_text("".join(lines))
    print(f"  → {config.tex.relative_to(root)}  (\\pubentry{{{next_num}}}{{{key}}} in {section_name})")
