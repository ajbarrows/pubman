from __future__ import annotations

import yaml

from ..config import GeneratorConfig

_SPECIAL = str.maketrans({"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_"})


def _esc(text: str) -> str:
    return text.translate(_SPECIAL)


def _period(p: str) -> str:
    return p.replace("–", "--").replace("—", "---")


def generate(manifest: list, gen_config: GeneratorConfig) -> str:
    source = gen_config.root / gen_config.extra["source_yaml"]
    entries = yaml.safe_load(source.read_text())

    lines = []
    prev_group = None

    for entry in entries:
        group = entry.get("group", "")

        if prev_group is not None and group != prev_group:
            lines.append("\t\t\t\t\t\t&\\\\")
            lines.append("")

        position = _esc(entry["position"])
        org = entry["organization"]
        url = entry.get("organization_url", "")
        period = _period(entry.get("period", ""))

        org_str = rf"\href{{{url}}}{{{_esc(org)}}}" if url else _esc(org)

        lines.append(f"\t\t\t\t\t\t& {position}, {org_str} & {period}\\\\")
        prev_group = group

    lines.append("\t\t\t\t\t\t&\\\\")
    lines.append("")
    return "\n".join(lines)
