#!/usr/bin/env python3
"""Store a project's code/archive link in the BibTeX database and rebuild docs."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

from build_publications import (
    filename_for_key,
    generate_site_from_entries,
    read_bibtex_file,
    render_bibtex_entry,
    supported_entry_types,
    write_bibtex_database,
)


def _validate_url(*, url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("The project link must be an absolute http:// or https:// URL")


def update_publication_link(
    *,
    database_path: Path,
    docs_dir: Path,
    bib_key: str,
    url: str | None,
    project_name: str,
    project_subtitle: str,
    source_root: Path,
) -> Path:
    """Set projectlink in the database and regenerate the corresponding docs page."""
    if url is not None:
        _validate_url(url=url)
    entries = read_bibtex_file(path=database_path)
    matching_position = next(
        (position for position, entry in enumerate(entries) if entry["bib_key"] == bib_key),
        None,
    )
    if matching_position is None:
        raise KeyError(f"No database entry has BibTeX key {bib_key!r}")

    entry = dict(entries[matching_position])
    raw_fields = entry.get("fields")
    if not isinstance(raw_fields, dict):
        raise TypeError(f"BibTeX fields for {bib_key!r} must be a dictionary")
    fields = {str(name): str(value) for name, value in raw_fields.items()}
    if url is None:
        fields.pop("projectlink", None)
    else:
        fields["projectlink"] = url
    entry["fields"] = fields
    entry["raw_bibtex"] = render_bibtex_entry(entry=entry)
    entries[matching_position] = entry
    write_bibtex_database(path=database_path, entries=entries)

    generate_site_from_entries(
        entries=entries,
        docs_dir=docs_dir,
        full_rebuild=False,
        allowed_entry_types=supported_entry_types(include_projects=True),
        project_name=project_name,
        project_subtitle=project_subtitle,
        source_root=source_root,
    )
    return docs_dir / "publications" / filename_for_key(bib_key=bib_key)


def _argument_parser(*, default_database_path: Path, default_docs_dir: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Store a project or publication code/archive URL in the BibTeX database and rebuild the docs."
    )
    parser.add_argument("bib_key", help="exact BibTeX key from the authoritative database")
    parser.add_argument("url", nargs="?", help="GitHub or archival-service URL")
    parser.add_argument("--remove", action="store_true", help="remove projectlink and restore the empty placeholder")
    parser.add_argument("--database", type=Path, default=default_database_path, help=f"authoritative BibTeX database (default: {default_database_path})")
    parser.add_argument("--docs-dir", type=Path, default=default_docs_dir, help=f"generated site directory (default: {default_docs_dir})")
    parser.add_argument("--project-name", default="NegLab INF", help="short project name shown in the site header")
    parser.add_argument("--project-subtitle", default="Infrastructure for research on negation", help="main heading shown on the project index")
    return parser


def main(*, argv: Sequence[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parent.parent
    parser = _argument_parser(
        default_database_path=project_root / "data" / "neglab-inf.bib",
        default_docs_dir=project_root / "docs",
    )
    arguments = parser.parse_args(argv)
    if arguments.remove and arguments.url:
        parser.error("URL cannot be used together with --remove")
    if not arguments.remove and not arguments.url:
        parser.error("URL is required unless --remove is used")
    page_path = update_publication_link(
        database_path=arguments.database,
        docs_dir=arguments.docs_dir,
        bib_key=arguments.bib_key,
        url=None if arguments.remove else arguments.url,
        project_name=arguments.project_name,
        project_subtitle=arguments.project_subtitle,
        source_root=Path(__file__).resolve().parent,
    )
    action = "Removed projectlink and regenerated" if arguments.remove else "Stored projectlink and regenerated"
    print(f"{action} {page_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=None))
