#!/usr/bin/env python3
"""Add, replace, or remove a project's code/archive link by BibTeX key."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

from build_publications import render_repository_link


def _load_json_object(*, path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"Required project metadata does not exist: {path}. Run build_publications.py first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def _filename_from_manifest(*, manifest_path: Path, bib_key: str) -> str:
    manifest = _load_json_object(path=manifest_path)
    publications = manifest.get("publications")
    if not isinstance(publications, list):
        raise ValueError(f"Expected a publications list in {manifest_path}")
    for publication in publications:
        if isinstance(publication, dict) and publication.get("bib_key") == bib_key:
            filename = publication.get("filename")
            if isinstance(filename, str):
                return filename
    raise KeyError(f"No generated project or output has BibTeX key {bib_key!r}")


def _validate_url(*, url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("The project link must be an absolute http:// or https:// URL")


def update_publication_link(*, docs_dir: Path, bib_key: str, url: str | None) -> Path:
    """Update one generated page and its persistent BibTeX-key-to-URL mapping."""
    publication_dir = docs_dir / "publications"
    filename = _filename_from_manifest(manifest_path=publication_dir / "index.json", bib_key=bib_key)
    page_path = publication_dir / filename
    if not page_path.is_file():
        raise FileNotFoundError(f"The project page listed for {bib_key!r} is missing: {page_path}")
    if url is not None:
        _validate_url(url=url)

    links_path = publication_dir / "links.json"
    links_data = _load_json_object(path=links_path) if links_path.exists() else {}
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in links_data.items()):
        raise ValueError(f"{links_path} must map BibTeX keys to URL strings")
    links = {str(key): str(value) for key, value in links_data.items()}
    if url is None:
        links.pop(bib_key, None)
    else:
        links[bib_key] = url

    page = page_path.read_text(encoding="utf-8")
    replacement = f"<!-- PUBLICATION_LINK_START -->{render_repository_link(url=url or '')}<!-- PUBLICATION_LINK_END -->"
    updated_page, replacements = re.subn(
        r"<!-- PUBLICATION_LINK_START -->.*?<!-- PUBLICATION_LINK_END -->",
        lambda _: replacement,
        page,
        count=1,
        flags=re.DOTALL,
    )
    if replacements != 1:
        raise ValueError(f"Could not find the code/archive placeholder in {page_path}")

    page_path.write_text(updated_page, encoding="utf-8")
    links_path.write_text(json.dumps(dict(sorted(links.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return page_path


def _argument_parser(*, default_docs_dir: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Set a project or publication code/archive URL using its BibTeX key.")
    parser.add_argument("bib_key", help="exact BibTeX key from the imported bibliography")
    parser.add_argument("url", nargs="?", help="GitHub or archival-service URL")
    parser.add_argument("--remove", action="store_true", help="remove the stored link and restore the empty placeholder")
    parser.add_argument("--docs-dir", type=Path, default=default_docs_dir, help=f"generated site directory (default: {default_docs_dir})")
    return parser


def main(*, argv: Sequence[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parent.parent
    parser = _argument_parser(default_docs_dir=project_root / "docs")
    arguments = parser.parse_args(argv)
    if arguments.remove and arguments.url:
        parser.error("URL cannot be used together with --remove")
    if not arguments.remove and not arguments.url:
        parser.error("URL is required unless --remove is used")
    page_path = update_publication_link(
        docs_dir=arguments.docs_dir,
        bib_key=arguments.bib_key,
        url=None if arguments.remove else arguments.url,
    )
    action = "Removed link from" if arguments.remove else "Updated"
    print(f"{action} {page_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=None))
