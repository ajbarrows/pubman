from __future__ import annotations

from .manifest import MONTH_ABBR


def _bib_escape(text: str) -> str:
    return text.replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")


def _bib_author(a: dict, my_last_name: str) -> str:
    name = f"{a['last']}, {a['first']}".rstrip(", ")
    return "\\textbf{" + name + "}" if a["last"].lower() == my_last_name.lower() else name


def _bib_entry(entry: dict, my_last_name: str) -> str:
    key = entry["key"]
    btype = entry.get("type", "article")
    lines = [f"@{btype}{{{key},"]

    def field(k, v, braces=True):
        lines.append(f"\t{k} = {{{v}}}," if braces else f"\t{k} = {v},")

    field("title", _bib_escape(entry["title"]))
    field("author", " and\n\t\t".join(_bib_author(a, my_last_name) for a in entry["authors"]))
    field("year", str(entry["year"]))

    if entry.get("month"):
        field("month", MONTH_ABBR.get(entry["month"], str(entry["month"])), braces=False)

    if btype == "article":
        for f in ("volume", "number", "pages"):
            if entry.get(f):
                field(f, str(entry[f]))
        if entry.get("journal"):
            field("journal", _bib_escape(entry["journal"]))
    else:
        if entry.get("journal"):
            field("howpublished", _bib_escape(entry["journal"]))

    if entry.get("doi"):
        field("doi", entry["doi"])
    if entry.get("abstract"):
        field("abstract", entry["abstract"])

    lines.append("}")
    return "\n".join(lines)


def generate(manifest: list, my_last_name: str) -> str:
    """Render manifest as BibTeX; the author matching my_last_name is typeset in bold."""
    return "\n\n".join(_bib_entry(e, my_last_name) for e in manifest) + "\n"
