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
    for entry in entries:
        degree = _esc(entry["degree"])
        institution = entry["institution"]
        url = entry.get("institution_url", "")
        location = entry.get("location", "")
        period = _period(entry.get("period", ""))
        thesis = entry.get("thesis", "")
        thesis_label = entry.get("thesis_label", "Thesis")

        if url:
            degree_str = rf"\href{{{url}}}{{\textbf{{{degree}}}}}"
            inst_str = rf"\href{{{url}}}{{{_esc(institution)}}}"
        else:
            degree_str = rf"\textbf{{{degree}}}"
            inst_str = _esc(institution)

        if location:
            inst_str += f", {_esc(location)}"

        lines.append(f"\t\t\t\t\t\t& {degree_str} & {period} \\\\")
        lines.append(f"\t\t\t\t\t\t& {inst_str} \\\\")

        if thesis:
            lines.append(
                f"\t\t\t\t\t\t& \\quad {_esc(thesis_label)}: \\textit{{{_esc(thesis)}}} \\\\"
            )

        lines.append("\t\t\t\t\t\t&\\\\")
        lines.append("")

    return "\n".join(lines)
