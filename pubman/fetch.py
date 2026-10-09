from __future__ import annotations

import re
import sys
from pathlib import Path

import requests

from .manifest import MONTH_NUM, normalize_doi

CROSSREF_URL = "https://api.crossref.org/works/{doi}"
ORCID_BASE = "https://pub.orcid.org/v3.0"

# Maps ORCID work types to (bibtex_type, pubman_category)
_ORCID_TYPE_MAP: dict[str, tuple[str, str]] = {
    "journal-article":      ("article", "peer-reviewed"),
    "conference-paper":     ("misc",    "conference"),
    "conference-abstract":  ("misc",    "conference"),
    "conference-poster":    ("misc",    "conference"),
    "lecture-speech":       ("misc",    "invited-talk"),
    "dissertation":         ("misc",    "conference"),
    "working-paper":        ("misc",    "conference"),
    "preprint":             ("misc",    "conference"),
    "other":                ("misc",    "conference"),
}


def fetch_crossref(doi: str, user_agent: str = "pubman/1.0") -> dict:
    """Fetch and normalize metadata from the CrossRef REST API."""
    doi = normalize_doi(doi) or ""
    r = requests.get(
        CROSSREF_URL.format(doi=doi),
        headers={"User-Agent": user_agent},
        timeout=15,
    )
    r.raise_for_status()
    msg = r.json()["message"]

    authors = [
        {"first": a.get("given", ""), "last": a.get("family", "")}
        for a in msg.get("author", [])
    ]

    title = re.sub(r"<[^>]+>", "", (msg.get("title") or [""])[0])

    date = (msg.get("published") or msg.get("published-print")
            or msg.get("published-online") or msg.get("issued") or {})
    parts = date.get("date-parts", [[None]])[0]
    year = parts[0]
    month = parts[1] if len(parts) > 1 else None

    journal = (msg.get("container-title") or [None])[0]
    pages = (msg.get("page") or "").replace("-", "--") or None
    abstract = re.sub(r"<[^>]+>", "", msg.get("abstract", "")).strip() or None

    return {
        "type": "article",
        "title": title,
        "authors": authors,
        "year": year,
        "month": month,
        "journal": journal,
        "volume": msg.get("volume") or None,
        "number": msg.get("issue") or None,
        "pages": pages,
        "doi": doi,
        "abstract": abstract,
    }


def _strip_latex(text: str) -> str:
    text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\text(?:bf|it|rm)\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\emph\{([^}]*)\}", r"\1", text)
    text = re.sub(r"[{}]", "", text)
    return text.strip()


def _parse_author_string(raw: str) -> dict | None:
    raw = _strip_latex(raw).strip()
    if not raw:
        return None
    if "," in raw:
        last, first = raw.split(",", 1)
    else:
        parts = raw.split()
        last, first = (parts[-1], " ".join(parts[:-1])) if len(parts) > 1 else (parts[0], "")
    return {"first": first.strip(), "last": last.strip()}


def _orcid_get(url: str, user_agent: str) -> dict:
    r = requests.get(
        url,
        headers={"Accept": "application/json", "User-Agent": user_agent},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _extract_doi(external_ids: dict | None) -> str | None:
    for eid in (external_ids or {}).get("external-id") or []:
        if eid.get("external-id-type") == "doi":
            return normalize_doi(eid.get("external-id-value"))
    return None


def _parse_orcid_author(contributor: dict) -> dict | None:
    name = ((contributor.get("credit-name") or {}).get("value") or "").strip()
    if not name:
        return None
    if "," in name:
        last, first = name.split(",", 1)
        return {"first": first.strip(), "last": last.strip()}
    parts = name.split()
    return {"first": " ".join(parts[:-1]), "last": parts[-1]} if len(parts) > 1 else {"first": "", "last": name}


def _parse_orcid_work(work: dict) -> dict:
    """Normalize a full ORCID work record into a raw metadata dict."""
    title = ((work.get("title") or {}).get("title") or {}).get("value", "")
    work_type = work.get("type", "other")
    bib_type, category = _ORCID_TYPE_MAP.get(work_type, ("misc", "conference"))

    pub_date = work.get("publication-date") or {}
    year_node = pub_date.get("year") or {}
    month_node = pub_date.get("month") or {}
    year = int(year_node["value"]) if year_node.get("value") else None
    month = int(month_node["value"]) if month_node.get("value") else None

    journal = ((work.get("journal-title") or {}).get("value") or "")
    doi = _extract_doi(work.get("external-ids"))

    authors = [
        a for c in ((work.get("contributors") or {}).get("contributor") or [])
        if (a := _parse_orcid_author(c))
    ]

    return {
        "type": bib_type,
        "_category": category,
        "title": title,
        "authors": authors,
        "year": year,
        "month": month,
        "journal": journal,
        "doi": doi,
    }


def fetch_orcid_works(orcid_id: str, user_agent: str = "pubman/1.0") -> list[dict]:
    """
    Fetch all works for an ORCID author ID.

    For each work with a DOI, CrossRef is used to obtain clean metadata and the
    full author list. Works without a DOI fall back to ORCID metadata directly.
    Each returned dict has a '_category' key with the inferred pubman category.
    """
    base = f"{ORCID_BASE}/{orcid_id}"

    # Step 1: works summary — one put-code + DOI per group (de-duplicated works)
    data = _orcid_get(f"{base}/works", user_agent)
    groups = data.get("group") or []

    preferred: list[tuple[int, str | None]] = []  # (put_code, doi_or_None)
    for group in groups:
        group_doi = _extract_doi(group.get("external-ids"))
        summaries = group.get("work-summary") or []
        if not summaries:
            continue
        summary = summaries[0]
        put_code = summary["put-code"]
        doi = group_doi or _extract_doi(summary.get("external-ids"))
        preferred.append((put_code, doi))

    if not preferred:
        return []

    # Step 2: batch-fetch full records for works that need ORCID metadata
    #         (those without a DOI, since CrossRef won't be available)
    no_doi_codes = [pc for pc, doi in preferred if not doi]
    full_records: dict[int, dict] = {}
    _BATCH = 50
    for i in range(0, len(no_doi_codes), _BATCH):
        batch = no_doi_codes[i : i + _BATCH]
        codes_str = ",".join(str(c) for c in batch)
        bulk = _orcid_get(f"{base}/works/{codes_str}", user_agent)
        for item in bulk.get("bulk") or []:
            work = item.get("work") or {}
            pc = work.get("put-code")
            if pc:
                full_records[pc] = work

    # Step 3: enrich and normalize
    results: list[dict] = []
    for put_code, doi in preferred:
        raw: dict | None = None

        if doi:
            try:
                raw = fetch_crossref(doi, user_agent=user_agent)
                raw["_category"] = "peer-reviewed"
            except Exception:
                pass  # fall through to ORCID metadata below

        if raw is None:
            work = full_records.get(put_code, {})
            raw = _parse_orcid_work(work)
            if not raw.get("title"):
                continue

        results.append(raw)

    return results


def parse_bibtex(path: Path) -> list:
    """Parse a BibTeX file; return list of normalized field dicts."""
    try:
        import bibtexparser
    except ImportError:
        sys.exit("Missing dependency: pip install 'bibtexparser<2'")

    with open(path) as f:
        db = bibtexparser.load(f)

    results = []
    for e in db.entries:
        authors = [
            a for part in re.split(r"\s+and\s+", e.get("author", ""), flags=re.I)
            if (a := _parse_author_string(part))
        ]

        raw_month = e.get("month", "")
        if isinstance(raw_month, str) and raw_month:
            month = MONTH_NUM.get(raw_month.strip().lower()[:3]) or (
                int(raw_month) if raw_month.isdigit() else None
            )
        else:
            month = int(raw_month) if raw_month else None

        doi = normalize_doi(e.get("doi"))

        results.append({
            "type": e.get("ENTRYTYPE", "article"),
            "title": _strip_latex(e.get("title", "")),
            "authors": authors,
            "year": int(e["year"]) if e.get("year") else None,
            "month": month,
            "journal": _strip_latex(e.get("journal") or e.get("howpublished") or ""),
            "volume": e.get("volume") or None,
            "number": e.get("number") or None,
            "pages": (e.get("pages") or "").strip() or None,
            "doi": doi,
            "abstract": _strip_latex(e.get("abstract", "")) or None,
        })
    return results
