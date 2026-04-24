from __future__ import annotations

from ..config import GeneratorConfig


def _ts_authors(authors: list) -> str:
    parts = [
        f"{a['last']} {a['first'][0]}".strip() if a.get("first") else a["last"]
        for a in authors
    ]
    return ", ".join(parts)


def _ts_citation(entry: dict) -> str:
    journal = entry.get("journal", "")
    vol = str(entry.get("volume") or "")
    num = str(entry.get("number") or "")
    year = entry.get("year", "")
    vol_part = vol + (f"({num})" if num else "")
    return ", ".join(p for p in [journal, vol_part, str(year)] if p)


def generate(manifest: list, config: GeneratorConfig) -> str:
    """Render featured manifest entries as a TypeScript export object."""
    page_title = config.extra.get("page_title", "Papers")
    page_description = config.extra.get("page_description", "Publications")
    export_name = config.extra.get("ts_export_name", "papersContent")
    section_title = config.extra.get("ts_section_title", "Papers")

    featured = [e for e in manifest if e.get("featured")]
    items = []
    for e in featured:
        doi = e.get("doi", "")
        href = f"https://doi.org/{doi}" if doi else ""
        title = e["title"].replace('"', '\\"')
        items.append(
            f'    {{\n'
            f'      title: "{title}",\n'
            f'      authors: "{_ts_authors(e["authors"])}",\n'
            f'      citation: "{_ts_citation(e)}",\n'
            f'      image: "{e.get("image") or ""}",\n'
            f'      href: "{href}",\n'
            f'    }}'
        )

    return (
        f"export const {export_name} = {{\n"
        f'  meta: {{\n'
        f'    title: "{page_title}",\n'
        f'    description: "{page_description}",\n'
        f"  }},\n"
        f'  title: "{section_title}",\n'
        f"  papers: [\n"
        + ",\n".join(items) + ",\n"
        "  ],\n"
        "};\n"
    )
