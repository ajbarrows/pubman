from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        sys.exit("Python 3.11+ required, or: pip install tomli")


@dataclass
class BibConfig:
    output: Path
    my_last_name: str = "Barrows"


@dataclass
class CVConfig:
    tex: Path
    figures_dir: Path
    section_map: dict[str, str] = field(default_factory=dict)
    build_cmd: Optional[str] = None


@dataclass
class GeneratorConfig:
    name: str
    module: str
    output: Path
    extra: dict = field(default_factory=dict)
    root: Optional[Path] = None


@dataclass
class Config:
    root: Path
    manifest_path: Path
    bib: Optional[BibConfig] = None
    cv: Optional[CVConfig] = None
    generators: list[GeneratorConfig] = field(default_factory=list)


def find_config(start: Path = Path.cwd()) -> Path:
    """Walk up from start searching for pubman.toml."""
    for directory in [start, *start.parents]:
        candidate = directory / "pubman.toml"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "pubman.toml not found. Run from the portfolio root or create pubman.toml."
    )


def load_config(path: Optional[Path] = None) -> Config:
    """Load pubman.toml; if path is None, walks up from cwd via find_config."""
    if path is None:
        path = find_config()
    root = path.parent

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    manifest_path = root / raw["manifest"]["path"]

    bib = None
    if "bib" in raw:
        b = raw["bib"]
        bib = BibConfig(
            output=root / b["output"],
            my_last_name=b.get("my_last_name", "Barrows"),
        )

    cv = None
    if "cv" in raw:
        c = raw["cv"]
        cv = CVConfig(
            tex=root / c["tex"],
            figures_dir=root / c["figures_dir"],
            section_map=c.get("section_map", {}),
            build_cmd=c.get("build_cmd"),
        )

    generators = []
    for g in raw.get("generators", []):
        extra = {k: v for k, v in g.items() if k not in ("name", "module", "output")}
        generators.append(GeneratorConfig(
            name=g["name"],
            module=g["module"],
            output=root / g["output"],
            extra=extra,
            root=root,
        ))

    return Config(
        root=root,
        manifest_path=manifest_path,
        bib=bib,
        cv=cv,
        generators=generators,
    )
