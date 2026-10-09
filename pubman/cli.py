from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import bib as bib_mod
from . import cv as cv_mod
from .config import Config, load_config
from .fetch import fetch_crossref, fetch_orcid_works, parse_bibtex
from .generators import load_generator
from .manifest import (
    VALID_CATEGORIES,
    build_entry,
    find_duplicate,
    generate_key,
    load,
    normalize_doi,
    save,
)

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

USER_AGENT = "pubman/1.0"


def _figures_url_prefix(config: Config) -> str:
    for g in config.generators:
        prefix = g.extra.get("figures_url_prefix")
        if prefix:
            return prefix
    return "/assets/images/figures"


def _print_figure_paths(key: str, config: Config) -> None:
    print(f"\n  Place figure (named by key, .jpg or .png):")
    for g in config.generators:
        fd = g.extra.get("figures_dir")
        if fd:
            fpath = config.root / fd / (key + ".jpg")
            print(f"    {g.name:12}: {fpath.relative_to(config.root)}")
    if config.cv:
        fpath = config.cv.figures_dir / (key + ".jpg")
        print(f"    {'cv':12}: {fpath.relative_to(config.root)}")


def _rebuild_cv(config: Config) -> None:
    if not (config.cv and config.cv.build_cmd):
        return
    print("  Rebuilding CV PDF ...")
    result = subprocess.run(
        config.cv.build_cmd,
        shell=True,
        cwd=config.cv.tex.parent,
        capture_output=True,
    )
    if result.returncode == 0:
        pdf = config.cv.tex.with_suffix(".pdf")
        print(f"  → {pdf.relative_to(config.root)}")
        return

    # pdflatex writes errors to stdout; extract the actionable lines
    print(f"\n  CV build failed (exit {result.returncode}).")
    stdout_lines = result.stdout.decode(errors="replace").splitlines()
    error_block: list[str] = []
    for i, ln in enumerate(stdout_lines):
        if ln.startswith("!"):
            # include the error line plus the "l.NN ..." source location that follows
            error_block.append(ln)
            for j in range(i + 1, min(i + 4, len(stdout_lines))):
                if stdout_lines[j].startswith("l.") or stdout_lines[j].strip():
                    error_block.append("  " + stdout_lines[j])
                else:
                    break
    if error_block:
        print()
        for ln in error_block:
            print(f"    {ln}")
    log = config.cv.tex.with_suffix(".log")
    print(f"\n  Full log: {log}")


def _regenerate(manifest: list, config: Config) -> None:
    if config.bib:
        content = bib_mod.generate(manifest, config.bib.my_last_name)
        config.bib.output.write_text(content)
        print(f"  → {config.bib.output.relative_to(config.root)}")

    for gen_config in config.generators:
        generate = load_generator(gen_config)
        content = generate(manifest, gen_config)
        gen_config.output.write_text(content)
        print(f"  → {gen_config.output.relative_to(config.root)}")


def cmd_bulk_add(args, manifest: list, config: Config) -> None:
    print(f"Fetching works for ORCID {args.orcid} ...")
    try:
        works = fetch_orcid_works(args.orcid, user_agent=USER_AGENT)
    except requests.HTTPError as exc:
        sys.exit(f"ORCID error: {exc}")

    if not works:
        print("No works found.")
        return

    print(f"Found {len(works)} works. Checking for duplicates ...\n")

    image_prefix = _figures_url_prefix(config)
    added: list[tuple[str, dict]] = []
    skipped: list[tuple[dict, str, str]] = []

    for raw in works:
        category = raw.pop("_category", "conference")

        if not raw.get("title"):
            continue
        if not raw.get("authors"):
            print(f"  Skipping (no author info): {raw.get('title', '')[:70]}")
            continue

        dup, reason = find_duplicate(manifest, doi=raw.get("doi"), title=raw["title"])
        if dup:
            skipped.append((raw, reason, dup["key"]))
            continue

        key = generate_key(raw["authors"], raw.get("year") or 0, manifest, raw["type"])
        entry = build_entry(raw, key, category, image_prefix=image_prefix)
        manifest.insert(0, entry)
        added.append((key, entry))

    if not added:
        print(f"Nothing to add — all {len(skipped)} works already in manifest.")
        return

    save(manifest, config.manifest_path)
    print(f"Added {len(added)}, skipped {len(skipped)} duplicate(s).\n")

    print("Updating outputs ...")
    _regenerate(manifest, config)

    if config.cv:
        for key, entry in added:
            cv_mod.update_cv_tex(key, entry["category"], config.cv, config.root)

    _rebuild_cv(config)

    print("\nAdded:")
    for key, entry in added:
        source = "(CrossRef)" if entry.get("doi") else "(ORCID)"
        print(f"  {key:20} [{entry['category']:15}] {source}  {entry['title'][:55]}")

    if skipped:
        print(f"\nSkipped {len(skipped)} duplicate(s):")
        for raw, reason, existing_key in skipped:
            print(f"  {existing_key:20} ({reason})")


def cmd_add(args, manifest: list, config: Config) -> None:
    if args.doi:
        print(f"Fetching {args.doi!r} from CrossRef ...")
        try:
            raw = fetch_crossref(args.doi, user_agent=USER_AGENT)
        except requests.HTTPError as exc:
            sys.exit(f"CrossRef error: {exc}")
        default_category = "peer-reviewed"
    else:
        raws = parse_bibtex(Path(args.bib))
        if not raws:
            sys.exit("No entries found in BibTeX file.")
        raw = raws[0]
        if len(raws) > 1:
            print(f"Warning: {len(raws)} entries found; using only the first.")
        default_category = "peer-reviewed" if raw["type"] == "article" else "conference"

    category = args.category or default_category

    dup, reason = find_duplicate(manifest, doi=raw.get("doi"), title=raw["title"])
    if dup:
        sys.exit(f"Duplicate ({reason}): key={dup['key']!r}\n  {dup['title'][:80]}")

    key = generate_key(raw["authors"], raw["year"], manifest, raw["type"])
    entry = build_entry(raw, key, category, image_prefix=_figures_url_prefix(config))

    manifest.insert(0, entry)
    save(manifest, config.manifest_path)

    title_preview = entry["title"][:70] + ("..." if len(entry["title"]) > 70 else "")
    print(f"\nAdded:    {key}")
    print(f"Title:    {title_preview}")
    print(f"Category: {category}  |  Featured: {entry['featured']}")
    print(f"\nUpdating outputs ...")
    _regenerate(manifest, config)

    if config.cv:
        cv_mod.update_cv_tex(key, category, config.cv, config.root)

    _rebuild_cv(config)

    _print_figure_paths(key, config)

    if not entry.get("featured"):
        print(f"\n  Entry is not featured on the website.")
        print(f"  Set `featured: true` in publications.yaml to include it.")


def cmd_fix_dois(manifest: list, config: Config) -> None:
    fixed = []
    for entry in manifest:
        doi = entry.get("doi")
        if doi and normalize_doi(doi) != doi:
            entry["doi"] = normalize_doi(doi)
            fixed.append((entry["key"], doi, entry["doi"]))

    if not fixed:
        print("All DOIs already normalized.")
        return

    save(manifest, config.manifest_path)
    print(f"Normalized {len(fixed)} DOI(s):")
    for key, old, new in fixed:
        print(f"  {key:20} {old}  →  {new}")

    print("\nUpdating outputs ...")
    _regenerate(manifest, config)
    _rebuild_cv(config)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a publication to the manifest and regenerate outputs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", metavar="FILE", type=Path,
        help="Path to pubman.toml (default: searches up from cwd)",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--doi", metavar="DOI", help="DOI to look up via CrossRef")
    src.add_argument("--bib", metavar="FILE", help="BibTeX file (first entry is used)")
    src.add_argument(
        "--orcid", metavar="ORCID_ID",
        help="ORCID author ID (e.g. 0000-0000-0000-0000); exhaustively adds all works, "
             "enriching via CrossRef where DOIs are available",
    )
    src.add_argument("--regenerate", action="store_true",
                     help="Regenerate outputs without adding a new entry")
    src.add_argument("--fix-dois", action="store_true",
                     help="Normalize existing DOIs (strip doi.org URL prefixes) and regenerate outputs")
    parser.add_argument(
        "--category", choices=VALID_CATEGORIES,
        help="Override inferred category for --doi/--bib (ignored for --orcid). "
             "CV sections: peer-reviewed→Publications, invited-talk→Invited Talks, "
             "selected-talk→Selected Talks, conference→Abstracts.",
    )

    args = parser.parse_args()
    config = load_config(args.config)
    manifest = load(config.manifest_path)

    if args.regenerate:
        print("Regenerating outputs from manifest ...")
        _regenerate(manifest, config)
        _rebuild_cv(config)
    elif args.fix_dois:
        cmd_fix_dois(manifest, config)
    elif args.orcid:
        cmd_bulk_add(args, manifest, config)
    else:
        cmd_add(args, manifest, config)


if __name__ == "__main__":
    main()
