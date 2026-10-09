# pubman

Manifest-driven publication manager for academics. Pulls metadata from CrossRef, ORCID, or BibTeX files; maintains a single YAML manifest; and regenerates BibTeX, TypeScript, Astro Markdown, and LaTeX CV sections on each update.

## Installation

```bash
pip install -e .

# With docs dependencies
pip install -e ".[docs]"
mkdocs serve   # preview at http://127.0.0.1:8000
```

## Configuration

Create `pubman.toml` at the root of your portfolio/CV repo:

```toml
[manifest]
path = "publications.yaml"

[bib]
output = "publications.bib"
my_last_name = "Smith"

# Optional: LaTeX CV integration
[cv]
tex = "cv.tex"
figures_dir = "assets/figures"
section_map = { "peer-reviewed" = "Publications", "invited-talk" = "Invited Talks", "selected-talk" = "Selected Talks", "conference" = "Abstracts" }

# Optional: one or more output generators
[[generators]]
name = "typescript"
module = "pubman.generators.typescript"
output = "src/content.ts"
page_title = "Papers"
page_description = "My publications"
ts_export_name = "papersContent"

[[generators]]
name = "astro_md"
module = "pubman.generators.astro_md"
output = "src/content/publications/.pubman-sync.log"
categories = ["peer-reviewed"]
figures_url_prefix = "/assets/images/figures"
figures_dir = "public/assets/images/figures"
```

## Usage

```bash
# Add a publication by DOI
pubman --doi 10.1038/s41586-024-00001-0

# Add from a BibTeX file
pubman --bib paper.bib

# Bulk-import all works from an ORCID profile
pubman --orcid 0000-0000-0000-0000

# Override the inferred category
pubman --doi 10.1234/example --category invited-talk

# Regenerate all outputs without adding anything new
pubman --regenerate

# Strip doi.org URL prefixes from existing DOIs, then regenerate
pubman --fix-dois
```

After adding an entry, pubman prints the generated key (e.g. `SmJo24`) and tells you where to drop the figure file. Set `featured: true` in `publications.yaml` to include an entry on your website.

## Categories

| Value | CV section (default) |
|---|---|
| `peer-reviewed` | Publications |
| `invited-talk` | Invited Talks |
| `selected-talk` | Selected Talks |
| `conference` | Abstracts |

## Custom generators

Point `module` at any Python module that exposes a `generate(manifest, config)` function, or use `module:function` syntax for a non-default name.
