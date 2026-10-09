from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

import yaml

MONTH_ABBR = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
    7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec",
}
MONTH_NUM = {v: k for k, v in MONTH_ABBR.items()}

VALID_CATEGORIES = ("peer-reviewed", "invited-talk", "selected-talk", "conference")


def load(path: Path) -> list:
    """Load YAML manifest, returning [] if the file does not exist."""
    if not path.exists():
        return []
    with open(path) as f:
        return yaml.safe_load(f) or []


def save(entries: list, path: Path) -> None:
    """Write entries to path as YAML."""
    with open(path, "w") as f:
        yaml.dump(entries, f, allow_unicode=True, sort_keys=False,
                  default_flow_style=False, width=120)


def normalize_doi(doi: str | None) -> str | None:
    """Strip whitespace, a doi.org URL prefix, a "doi:" prefix and trailing slashes."""
    if not doi:
        return None
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", doi.strip(), flags=re.I)
    return doi.strip().rstrip("/") or None


def _normalize(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", title.lower())).strip()


def find_duplicate(manifest: list, doi=None, title=None):
    """Return (entry, reason_str) if duplicate found, else (None, None)."""
    doi = normalize_doi(doi)
    for entry in manifest:
        if doi:
            existing = normalize_doi(entry.get("doi"))
            if existing and existing.lower() == doi.lower():
                return entry, "DOI match"
        if title:
            ratio = SequenceMatcher(None, _normalize(title), _normalize(entry["title"])).ratio()
            if ratio > 0.95:
                return entry, f"title similarity {ratio:.0%}"
    return None, None


def generate_key(authors: list, year: int, manifest: list, entry_type: str = "article") -> str:
    """
    Articles:    First2ofLast1 + First2ofLast2 + YY  (e.g. BaWe26)
    Single-auth: First4ofLast + YY
    Misc:        FullLast1 + YY
    Appends a/b/c... on collision.
    """
    year_str = str(year)[-2:]
    lasts = [a["last"] for a in authors]

    if entry_type == "article":
        base = (lasts[0][:2] + lasts[1][:2] if len(lasts) >= 2 else lasts[0][:4]) + year_str
    else:
        base = lasts[0] + year_str

    existing = {e["key"] for e in manifest}
    if base not in existing:
        return base
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        candidate = base + suffix
        if candidate not in existing:
            return candidate
    raise RuntimeError(f"Cannot generate unique key from base '{base}'")


def build_entry(raw: dict, key: str, category: str,
                image_prefix: str = "/assets/images/figures") -> dict:
    """Build a normalized manifest entry; peer-reviewed entries are featured by default."""
    featured = category == "peer-reviewed"
    entry = {
        "key": key,
        "type": raw["type"],
        "category": category,
        "title": raw["title"],
        "authors": raw["authors"],
        "year": raw["year"],
        "featured": featured,
        "image": f"{image_prefix}/{key}.jpg" if featured else None,
    }
    for f in ("month", "journal", "volume", "number", "pages", "doi", "abstract"):
        if raw.get(f):
            entry[f] = raw[f]
    return entry
