from __future__ import annotations

from pathlib import Path

import yaml

from ..config import GeneratorConfig

MANAGED_MARKER = "pubman_managed"
INCLUDE_CATEGORIES = ("peer-reviewed",)


def _format_author(a: dict) -> str:
    first = (a.get("first") or "").strip()
    last = (a.get("last") or "").strip()
    if first and last:
        return f"{last}, {first}"
    return last or first


def _entry_to_frontmatter(entry: dict) -> dict:
    authors = [_format_author(a) for a in entry.get("authors", [])]
    doi = (entry.get("doi") or "").strip()
    url = f"https://doi.org/{doi}" if doi else ""

    fm: dict = {
        "title": entry["title"],
        "authors": authors,
        "year": entry["year"],
        "venue": entry.get("journal") or "",
        "type": "paper",
        MANAGED_MARKER: True,
        "featured": bool(entry.get("featured", False)),
    }
    if url:
        fm["links"] = {"website": url}
    image = (entry.get("image") or "").strip() or None
    if image:
        fm["figure"] = image
    groups = entry.get("groups") or None
    if groups:
        fm["groups"] = groups
    return fm


def _render_md(entry: dict) -> str:
    fm = _entry_to_frontmatter(entry)
    fm_str = yaml.dump(fm, allow_unicode=True, sort_keys=False,
                       default_flow_style=False, width=120)
    abstract = (entry.get("abstract") or "").strip()
    body = f"\n{abstract}\n" if abstract else ""
    return f"---\n{fm_str}---\n{body}"


def generate(manifest: list, config: GeneratorConfig) -> str:
    """Write one Markdown file per included entry; removes previously managed files first.

    config.output should point to a log file inside the target content directory,
    e.g. src/content/publications/.pubman-sync.log.
    """
    # output should point to a log file inside the target content directory,
    # e.g. src/content/publications/.pubman-sync.log
    content_dir = config.output.parent
    content_dir.mkdir(parents=True, exist_ok=True)

    categories: list[str] = config.extra.get("categories", list(INCLUDE_CATEGORIES))
    if isinstance(categories, str):
        categories = [categories]

    # Remove previously managed files
    removed = 0
    for f in content_dir.glob("*.md"):
        if f"{MANAGED_MARKER}: true" in f.read_text():
            f.unlink()
            removed += 1

    # Write one file per included entry
    written = 0
    for entry in manifest:
        if entry.get("category") not in categories:
            continue
        key = entry["key"]
        (content_dir / f"{key}.md").write_text(_render_md(entry))
        written += 1

    summary = f"astro_md: wrote {written} files, removed {removed} stale ({content_dir})\n"
    return summary
