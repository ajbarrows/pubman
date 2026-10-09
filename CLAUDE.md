# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -e .           # Install in editable mode
pip install -e ".[docs]"   # Also install mkdocs for documentation

pubman --doi <DOI>          # Add publication by DOI (fetches from CrossRef)
pubman --bib <FILE>         # Add publication from a BibTeX file
pubman --orcid <ORCID_ID>   # Bulk-import all works from an ORCID profile
pubman --regenerate         # Regenerate all outputs without adding new entries
pubman --fix-dois           # Strip doi.org URL prefixes from existing DOIs, then regenerate
pubman --config <FILE>      # Override config path (default: walks up from cwd)
pubman --category <CAT>     # Override inferred category

mkdocs serve               # Preview docs at http://127.0.0.1:8000
```

There are no automated tests.

## Architecture

**pubman** is a Python 3.9+ CLI tool that maintains a single YAML manifest (`publications.yaml`) as the source of truth for a researcher's publications, then regenerates multiple output formats from it.

### Data flow

```
CrossRef API / ORCID API / .bib file
    → fetch.py         (normalize raw metadata)
    → manifest.py      (dedup, generate citation key, insert into YAML)
    → bib.py           (regenerate .bib output)
    → cv.py            (insert \pubentry lines into LaTeX CV)
    → generators/      (pluggable: astro_md, typescript, custom)
```

### Modules

| File | Responsibility |
|---|---|
| `cli.py` | Argument parsing, orchestrates all layers |
| `config.py` | Loads `pubman.toml`; walks up from cwd to find it |
| `manifest.py` | Load/save YAML, duplicate detection, citation key generation, entry normalization |
| `fetch.py` | CrossRef API, ORCID API, BibTeX file parsing |
| `bib.py` | BibTeX output (supports bolding author's own name) |
| `cv.py` | LaTeX CV integration — inserts `\pubentry` lines into a `.tex` file |
| `generators/astro_md.py` | Creates one Markdown file per publication for Astro content collections |
| `generators/typescript.py` | Exports featured publications as a TypeScript object |

### Configuration (`pubman.toml`)

Found by walking up from the working directory. Key sections:

```toml
[manifest]
path = "publications.yaml"      # YAML source of truth

[bib]
output = "publications.bib"
my_last_name = "Smith"          # Used for author name bolding in BibTeX

[cv]
tex = "cv.tex"
figures_dir = "assets/figures"
section_map = { "peer-reviewed" = "Publications", "invited-talk" = "Invited Talks" }

[[generators]]
module = "pubman.generators.astro_md"
output = "src/content/publications/.pubman-sync.log"
categories = ["peer-reviewed"]
```

Custom generators can be pointed to any Python module that exports a `generate(manifest, config)` function.

### Citation key algorithm

Keys follow the pattern `BaWe26` (first two letters of first author's last name + first two of second + two-digit year). `manifest.py:generate_key()` handles collision avoidance.

### Valid categories

`peer-reviewed`, `invited-talk`, `selected-talk`, `conference` — determines which LaTeX CV section each entry is inserted into.

### Manifest entry structure

```yaml
- key: "SmJo24"
  type: article          # article | inproceedings | misc | ...
  category: peer-reviewed
  title: "..."
  authors:
    - first: "John"
      last: "Smith"
  year: 2024
  featured: false        # Set true to include in TypeScript/featured outputs
  image: "/assets/figures/SmJo24.jpg"   # Suggested path, place file manually
  doi: "10.xxxx/..."
  journal: "Nature"
  abstract: "..."
```
