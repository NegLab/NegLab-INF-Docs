#!/usr/bin/env python3
"""Build the NegLab INF GitHub Pages publication site from BibTeX files."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urlparse


def _read_balanced(*, text: str, start: int, opening: str, closing: str) -> tuple[str, int]:
    depth = 0
    quoted = False
    escaped = False
    for position in range(start, len(text)):
        character = text[position]
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
            continue
        if quoted:
            continue
        if character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return text[start + 1 : position], position + 1
    raise ValueError(f"Unclosed BibTeX entry beginning at character {start}")


def _split_top_level(*, text: str, separator: str) -> list[str]:
    parts: list[str] = []
    start = 0
    brace_depth = 0
    quoted = False
    escaped = False
    for position, character in enumerate(text):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
        elif not quoted and character == "{":
            brace_depth += 1
        elif not quoted and character == "}":
            brace_depth -= 1
        elif not quoted and brace_depth == 0 and character == separator:
            parts.append(text[start:position])
            start = position + 1
    parts.append(text[start:])
    return parts


def _unwrap_value(*, value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == "{" and value[-1] == "}") or (value[0] == '"' and value[-1] == '"')):
        return value[1:-1]
    return value


def _parse_fields(*, body: str) -> tuple[str, dict[str, str]]:
    key_and_fields = _split_top_level(text=body, separator=",")
    bib_key = key_and_fields[0].strip()
    if not bib_key:
        raise ValueError("A BibTeX entry has no key")

    fields: dict[str, str] = {}
    for part in key_and_fields[1:]:
        if not part.strip():
            continue
        name_and_value = part.split("=", maxsplit=1)
        if len(name_and_value) != 2:
            raise ValueError(f"Malformed field in BibTeX entry {bib_key!r}: {part.strip()!r}")
        name, raw_value = name_and_value
        value_parts = _split_top_level(text=raw_value, separator="#")
        fields[name.strip().lower()] = "".join(_unwrap_value(value=value) for value in value_parts).strip()
    return bib_key, fields


def parse_bibtex(*, text: str, source: str) -> list[dict[str, object]]:
    """Parse standard braced/quoted BibTeX entries without third-party packages."""
    entries: list[dict[str, object]] = []
    position = 0
    entry_pattern = re.compile(r"@\s*([A-Za-z]+)\s*([({])")
    while match := entry_pattern.search(text, position):
        entry_type = match.group(1).lower()
        opening = match.group(2)
        closing = "}" if opening == "{" else ")"
        body, end = _read_balanced(text=text, start=match.end() - 1, opening=opening, closing=closing)
        raw = text[match.start() : end].strip()
        position = end
        if entry_type in {"comment", "preamble", "string"}:
            continue
        bib_key, fields = _parse_fields(body=body)
        entries.append(
            {
                "bib_key": bib_key,
                "entry_type": entry_type,
                "fields": fields,
                "raw_bibtex": raw,
                "source": source,
            }
        )
    return entries


def _latex_to_text(*, value: str) -> str:
    replacements = {
        r"\&": "&",
        r"\%": "%",
        r"\_": "_",
        r"\#": "#",
        r"\textendash": "–",
        r"\textemdash": "—",
        "``": "“",
        "''": "”",
        "~": " ",
    }
    accent_replacements = {
        r'\"a': "ä", r'\"o': "ö", r'\"u': "ü", r'\"A': "Ä", r'\"O': "Ö", r'\"U': "Ü",
        r"\'a": "á", r"\'e": "é", r"\'i": "í", r"\'o": "ó", r"\'u": "ú",
        r"\`a": "à", r"\`e": "è", r"\`i": "ì", r"\`o": "ò", r"\`u": "ù",
        r"\ss": "ß", r"\ae": "æ", r"\AE": "Æ", r"\o": "ø", r"\O": "Ø",
    }
    result = value
    for source, target in replacements.items():
        result = result.replace(source, target)
    for command, target in accent_replacements.items():
        result = re.sub(r"\{?" + re.escape(command) + r"\}?", target, result)
    command_pattern = re.compile(r"\\(?:textit|textbf|emph|mathrm|mathbf|textrm)\s*\{([^{}]*)\}")
    while command_pattern.search(result):
        result = command_pattern.sub(r"\1", result)
    result = re.sub(r"\\[A-Za-z]+\s*", "", result)
    result = result.replace("{", "").replace("}", "")
    result = result.replace("---", "—").replace("--", "–")
    return " ".join(result.split())


def _author_names(*, value: str) -> list[str]:
    authors: list[str] = []
    for author in re.split(r"\s+and\s+", value.strip()):
        author = _latex_to_text(value=author.strip())
        if "," in author:
            pieces = [piece.strip() for piece in author.split(",") if piece.strip()]
            author = " ".join(reversed(pieces))
        if author:
            authors.append(author)
    return authors


def _filename_for_key(*, bib_key: str) -> str:
    ascii_key = unicodedata.normalize("NFKD", bib_key).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_key.lower()).strip("-") or "publication"
    digest = hashlib.sha256(bib_key.encode("utf-8")).hexdigest()[:10]
    return f"{slug}-{digest}.html"


def _normalise_doi(*, doi: str) -> str:
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip(), flags=re.IGNORECASE)


def _valid_web_url(*, url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _entry_to_publication(*, entry: dict[str, object]) -> dict[str, object]:
    fields = entry["fields"]
    if not isinstance(fields, dict):
        raise TypeError("BibTeX fields must be a dictionary")
    text_fields = {str(key): str(value) for key, value in fields.items()}
    entry_type = str(entry["entry_type"])
    title = _latex_to_text(value=text_fields.get("title", text_fields.get("name", "Untitled publication")))
    subtitle = _latex_to_text(value=text_fields.get("subtitle", ""))
    venue = _latex_to_text(
        value=text_fields.get("journal", text_fields.get("booktitle", text_fields.get("institution", "")))
    )
    doi = _normalise_doi(doi=text_fields.get("doi", ""))
    url = text_fields.get("url", "").strip()
    if not _valid_web_url(url=url):
        url = f"https://doi.org/{doi}" if doi else ""
    pdf = text_fields.get("pdf", "").strip()
    if not _valid_web_url(url=pdf):
        pdf = ""
    keywords = [
        _latex_to_text(value=item.strip())
        for item in re.split(r"[,;]", text_fields.get("keywords", ""))
        if item.strip()
    ]
    type_labels = {
        "article": "Journal article",
        "inbook": "Book chapter",
        "incollection": "Book chapter",
        "inproceedings": "Conference paper",
        "mastersthesis": "Master's thesis",
        "misc": "Publication",
        "phdthesis": "Doctoral thesis",
        "proceedings": "Proceedings",
        "techreport": "Technical report",
        "unpublished": "Preprint",
    }
    return {
        "bib_key": str(entry["bib_key"]),
        "entry_type": entry_type,
        "type_label": type_labels.get(entry_type, entry_type.replace("_", " ").title()),
        "title": title,
        "subtitle": subtitle,
        "authors": _author_names(value=text_fields.get("author", text_fields.get("editor", ""))),
        "year": _latex_to_text(value=text_fields.get("year", "Undated")),
        "venue": venue,
        "volume": _latex_to_text(value=text_fields.get("volume", "")),
        "number": _latex_to_text(value=text_fields.get("number", "")),
        "pages": _latex_to_text(value=text_fields.get("pages", "")),
        "publisher": _latex_to_text(value=text_fields.get("publisher", "")),
        "address": _latex_to_text(value=text_fields.get("address", text_fields.get("location", ""))),
        "note": _latex_to_text(value=text_fields.get("note", text_fields.get("pubstate", ""))),
        "abstract": _latex_to_text(value=text_fields.get("abstract", "")),
        "keywords": keywords,
        "doi": doi,
        "url": url,
        "pdf": pdf,
        "raw_bibtex": str(entry["raw_bibtex"]),
        "source": str(entry["source"]),
        "filename": _filename_for_key(bib_key=str(entry["bib_key"])),
    }


def _escape(*, value: object) -> str:
    return html.escape(str(value), quote=True)


def _icon(*, name: str) -> str:
    paths = {
        "arrow": '<path d="m9 18 6-6-6-6"/>',
        "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/>',
        "code": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
        "copy": '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
        "external": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
        "file": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/>',
        "github": '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3.3-.4 6.8-1.6 6.8-7A5.4 5.4 0 0 0 19.4 4 5 5 0 0 0 19.3.5S18.2.1 15 1.8a13.4 13.4 0 0 0-7 0C4.8.1 3.7.5 3.7.5A5 5 0 0 0 3.6 4a5.4 5.4 0 0 0-1.4 3.7c0 5.4 3.5 6.6 6.8 7A4.8 4.8 0 0 0 8 18v4"/><path d="M8 19c-3 .9-3-1.5-4-2"/>',
        "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
        "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    }
    return f'<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'


def _page_shell(*, title: str, description: str, body: str, asset_prefix: str, project_name: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{_escape(value=description)}">
  <meta name="theme-color" content="#102a2a">
  <title>{_escape(value=title)}</title>
  <link rel="stylesheet" href="{asset_prefix}assets/site.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to content</a>
  <header class="site-header">
    <a class="brand" href="{asset_prefix}index.html" aria-label="{_escape(value=project_name)} home">
      <span class="brand-mark">INF</span>
      <span><strong>{_escape(value=project_name)}</strong><small>Information Infrastructure</small></span>
    </a>
    <nav aria-label="Main navigation"><a href="{asset_prefix}index.html#publications">Publications</a><a href="https://www.neglab.de/" rel="noopener noreferrer">NegLaB {_icon(name='external')}</a></nav>
  </header>
  <main id="main-content">{body}</main>
  <footer><div><strong>{_escape(value=project_name)}</strong><p>Information infrastructure for collaborative negation research.</p></div><p>CRC 1629 · Goethe University Frankfurt</p></footer>
</body>
</html>
"""


def _format_author_list(*, authors: list[str]) -> str:
    return ", ".join(_escape(value=author) for author in authors) if authors else "Unknown authors"


def _render_index_card(*, publication: dict[str, object]) -> str:
    authors = publication["authors"] if isinstance(publication["authors"], list) else []
    keywords = publication["keywords"] if isinstance(publication["keywords"], list) else []
    searchable = " ".join(
        [str(publication["title"]), *[str(author) for author in authors], str(publication["venue"]), *[str(k) for k in keywords]]
    ).lower()
    venue = f'<p class="venue">{_escape(value=publication["venue"])}</p>' if publication["venue"] else ""
    note = f'<span class="status-chip">{_escape(value=publication["note"])}</span>' if publication["note"] else ""
    return f"""<article class="publication-card" data-year="{_escape(value=publication['year'])}" data-type="{_escape(value=publication['entry_type'])}" data-search="{_escape(value=searchable)}">
  <div class="card-year"><span>{_escape(value=publication['year'])}</span><small>{_escape(value=publication['type_label'])}</small></div>
  <div class="card-content">
    <div class="card-heading"><h3><a href="publications/{_escape(value=publication['filename'])}">{_escape(value=publication['title'])}</a></h3>{note}</div>
    <p class="authors">{_format_author_list(authors=authors)}</p>{venue}
  </div>
  <a class="card-arrow" href="publications/{_escape(value=publication['filename'])}" aria-label="View {_escape(value=publication['title'])}">{_icon(name='arrow')}</a>
</article>"""


def render_index(*, publications: list[dict[str, object]], project_name: str, project_subtitle: str) -> str:
    years = sorted({str(publication["year"]) for publication in publications}, reverse=True)
    types = sorted({(str(publication["entry_type"]), str(publication["type_label"])) for publication in publications}, key=lambda item: item[1])
    year_options = "".join(f'<option value="{_escape(value=year)}">{_escape(value=year)}</option>' for year in years)
    type_options = "".join(f'<option value="{_escape(value=key)}">{_escape(value=label)}</option>' for key, label in types)
    cards = "\n".join(_render_index_card(publication=publication) for publication in publications)
    author_count = len({author for publication in publications for author in publication["authors"] if isinstance(author, str)})
    body = f"""
<section class="hero">
  <div class="eyebrow">CRC 1629 · Negation in Language and Beyond</div>
  <h1>{_escape(value=project_subtitle)}</h1>
  <p>Research outputs from the INF subproject, building sustainable data, tools, and methods for collaborative research on negation.</p>
  <a class="button button-primary" href="#publications">Browse publications {_icon(name='arrow')}</a>
  <div class="hero-orbit" aria-hidden="true"><span></span><span></span><span></span></div>
</section>
<section class="stats" aria-label="Publication statistics">
  <div><strong>{len(publications)}</strong><span>Publications</span></div>
  <div><strong>{author_count}</strong><span>Contributors</span></div>
  <div><strong>{len(years)}</strong><span>Publication years</span></div>
</section>
<section class="publication-section" id="publications">
  <div class="section-heading"><div><span class="eyebrow">Research library</span><h2>Publications</h2></div><p>Explore the INF subproject’s articles, conference papers, and technical reports.</p></div>
  <div class="filters" role="search">
    <label class="search-field">{_icon(name='search')}<span class="sr-only">Search publications</span><input id="publication-search" type="search" placeholder="Search title, author, venue, or keyword…" autocomplete="off"></label>
    <label><span class="sr-only">Filter by year</span><select id="year-filter"><option value="">All years</option>{year_options}</select></label>
    <label><span class="sr-only">Filter by publication type</span><select id="type-filter"><option value="">All types</option>{type_options}</select></label>
  </div>
  <div class="result-bar"><span id="result-count">{len(publications)} publications</span><button id="clear-filters" type="button" hidden>Clear filters</button></div>
  <div class="publication-list" id="publication-list">{cards}</div>
  <div class="empty-state" id="empty-state" hidden><span>{_icon(name='search')}</span><h3>No publications found</h3><p>Try another search or clear the filters.</p></div>
</section>
<script src="assets/site.js" defer></script>
"""
    return _page_shell(
        title=f"{project_name} · Publications",
        description="Publications and research outputs of the NegLab CRC 1629 INF subproject.",
        body=body,
        asset_prefix="",
        project_name=project_name,
    )


def render_repository_link(*, url: str) -> str:
    if url:
        return f'<a class="button button-secondary" href="{_escape(value=url)}" rel="noopener noreferrer">{_icon(name="github")} Code &amp; archive</a>'
    return f'<span class="button button-secondary button-disabled" aria-disabled="true" title="No code or archive link has been added yet">{_icon(name="github")} Code &amp; archive</span>'


def _detail_rows(*, publication: dict[str, object]) -> str:
    values = [
        ("Publication type", publication["type_label"]),
        ("Published", publication["year"]),
        ("Venue", publication["venue"]),
        ("Volume", publication["volume"]),
        ("Issue / number", publication["number"]),
        ("Pages", publication["pages"]),
        ("Publisher", publication["publisher"]),
        ("Location", publication["address"]),
        ("DOI", publication["doi"]),
        ("BibTeX key", publication["bib_key"]),
    ]
    return "".join(
        f'<div><dt>{_escape(value=label)}</dt><dd>{_escape(value=value)}</dd></div>' for label, value in values if value
    )


def render_detail(*, publication: dict[str, object], repository_url: str, project_name: str) -> str:
    authors = publication["authors"] if isinstance(publication["authors"], list) else []
    keywords = publication["keywords"] if isinstance(publication["keywords"], list) else []
    title = str(publication["title"])
    subtitle = f'<p class="subtitle">{_escape(value=publication["subtitle"])}</p>' if publication["subtitle"] else ""
    venue = f'<p class="detail-venue">{_escape(value=publication["venue"])} · {_escape(value=publication["year"])}</p>' if publication["venue"] else f'<p class="detail-venue">{_escape(value=publication["year"])}</p>'
    note = f'<span class="status-chip">{_escape(value=publication["note"])}</span>' if publication["note"] else ""
    actions: list[str] = []
    if publication["url"]:
        actions.append(f'<a class="button button-primary" href="{_escape(value=publication["url"])}" rel="noopener noreferrer">{_icon(name="external")} View publication</a>')
    if publication["pdf"]:
        actions.append(f'<a class="button button-secondary" href="{_escape(value=publication["pdf"])}" rel="noopener noreferrer">{_icon(name="file")} PDF</a>')
    actions.append(f'<!-- PUBLICATION_LINK_START -->{render_repository_link(url=repository_url)}<!-- PUBLICATION_LINK_END -->')
    abstract = str(publication["abstract"])
    abstract_section = f'<section class="paper-section"><h2>Abstract</h2><p class="abstract">{_escape(value=abstract)}</p></section>' if abstract else '<section class="paper-section muted-section"><h2>Abstract</h2><p>No abstract is available in the bibliography.</p></section>'
    keyword_html = "".join(f'<span>{_escape(value=keyword)}</span>' for keyword in keywords)
    keyword_section = f'<section class="paper-section"><h2>Keywords</h2><div class="keyword-list">{keyword_html}</div></section>' if keywords else ""
    body = f"""
<div class="detail-back"><a href="../index.html#publications">← Back to all publications</a></div>
<article class="paper">
  <header class="paper-header">
    <div class="paper-type">{_icon(name='book')} {_escape(value=publication['type_label'])}{note}</div>
    <h1>{_escape(value=title)}</h1>{subtitle}
    <p class="detail-authors">{_format_author_list(authors=authors)}</p>{venue}
    <div class="paper-actions">{''.join(actions)}</div>
  </header>
  <div class="paper-layout">
    <div>{abstract_section}{keyword_section}
      <section class="paper-section citation-section"><div class="section-title-row"><h2>BibTeX</h2><button class="copy-button" type="button" data-copy-bib>{_icon(name='copy')} Copy</button></div><pre><code id="bibtex-entry">{_escape(value=publication['raw_bibtex'])}</code></pre></section>
    </div>
    <aside class="paper-facts"><h2>Publication details</h2><dl>{_detail_rows(publication=publication)}</dl></aside>
  </div>
</article>
<script src="../assets/site.js" defer></script>
"""
    page = _page_shell(
        title=f"{title} · {project_name}",
        description=abstract[:155] if abstract else f"Publication details for {title}.",
        body=body,
        asset_prefix="../",
        project_name=project_name,
    )
    return page.replace("<meta name=\"theme-color\"", f'<meta name="bib-key" content="{_escape(value=publication["bib_key"])}">\n  <meta name="theme-color"', 1)


def _load_links(*, path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in data.items()):
        raise ValueError(f"{path} must contain a JSON object mapping BibTeX keys to URLs")
    return data


def _sort_publications(*, publications: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    def sort_key(publication: dict[str, object]) -> tuple[int, str, str]:
        year = str(publication["year"])
        numeric_year = int(year) if year.isdigit() else -1
        return (-numeric_year, str(publication["title"]).casefold(), str(publication["bib_key"]).casefold())

    return sorted(publications, key=sort_key)


def _write_assets(*, docs_dir: Path, source_root: Path) -> None:
    assets_dir = docs_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for name in ("site.css", "site.js"):
        source = source_root / "site_assets" / name
        if not source.exists():
            raise FileNotFoundError(f"Required site asset is missing: {source}")
        shutil.copyfile(source, assets_dir / name)


def build_site(
    *,
    bib_paths: Sequence[Path],
    docs_dir: Path,
    full_rebuild: bool,
    allowed_entry_types: frozenset[str],
    project_name: str,
    project_subtitle: str,
    source_root: Path,
) -> dict[str, int]:
    """Build publication pages and return counts for generated/skipped entries."""
    all_entries: list[dict[str, object]] = []
    for bib_path in bib_paths:
        if not bib_path.is_file():
            raise FileNotFoundError(f"BibTeX file not found: {bib_path}")
        all_entries.extend(parse_bibtex(text=bib_path.read_text(encoding="utf-8"), source=str(bib_path)))

    seen: set[str] = set()
    publications: list[dict[str, object]] = []
    for entry in all_entries:
        bib_key = str(entry["bib_key"])
        if bib_key in seen:
            raise ValueError(f"Duplicate BibTeX key: {bib_key}")
        seen.add(bib_key)
        if str(entry["entry_type"]) in allowed_entry_types:
            publications.append(_entry_to_publication(entry=entry))
    publications = _sort_publications(publications=publications)

    publication_dir = docs_dir / "publications"
    publication_dir.mkdir(parents=True, exist_ok=True)
    links_path = publication_dir / "links.json"
    links = _load_links(path=links_path)

    if full_rebuild:
        for generated_page in publication_dir.glob("*.html"):
            if '<meta name="bib-key"' in generated_page.read_text(encoding="utf-8"):
                generated_page.unlink()

    generated = 0
    skipped = 0
    for publication in publications:
        target = publication_dir / str(publication["filename"])
        if target.exists() and not full_rebuild:
            skipped += 1
            continue
        target.write_text(
            render_detail(
                publication=publication,
                repository_url=links.get(str(publication["bib_key"]), ""),
                project_name=project_name,
            ),
            encoding="utf-8",
        )
        generated += 1

    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "index.html").write_text(
        render_index(publications=publications, project_name=project_name, project_subtitle=project_subtitle),
        encoding="utf-8",
    )
    manifest = {
        "publications": [
            {
                "bib_key": publication["bib_key"],
                "filename": publication["filename"],
                "title": publication["title"],
                "year": publication["year"],
                "entry_type": publication["entry_type"],
            }
            for publication in publications
        ]
    }
    (publication_dir / "index.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not links_path.exists():
        links_path.write_text("{}\n", encoding="utf-8")
    (docs_dir / ".nojekyll").touch()
    _write_assets(docs_dir=docs_dir, source_root=source_root)
    return {"generated": generated, "skipped": skipped, "total": len(publications), "ignored": len(all_entries) - len(publications)}


def _argument_parser(*, default_docs_dir: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a GitHub Pages publication site from one or more BibTeX files.")
    parser.add_argument("bib_files", nargs="+", type=Path, help="BibTeX file(s) to import")
    parser.add_argument("--docs-dir", type=Path, default=default_docs_dir, help=f"site output directory (default: {default_docs_dir})")
    parser.add_argument("--full-rebuild", action="store_true", help="replace every generated publication page and remove orphaned publication HTML files")
    parser.add_argument("--project-name", default="NegLab INF", help="short project name shown in the site header")
    parser.add_argument("--project-subtitle", default="Infrastructure for research on negation", help="main heading shown on the publication index")
    return parser


def main(*, argv: Sequence[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parent.parent
    parser = _argument_parser(default_docs_dir=project_root / "docs")
    arguments = parser.parse_args(argv)
    allowed_entry_types = frozenset(
        {"article", "book", "booklet", "inbook", "incollection", "inproceedings", "manual", "mastersthesis", "misc", "phdthesis", "proceedings", "techreport", "unpublished"}
    )
    result = build_site(
        bib_paths=arguments.bib_files,
        docs_dir=arguments.docs_dir,
        full_rebuild=arguments.full_rebuild,
        allowed_entry_types=allowed_entry_types,
        project_name=arguments.project_name,
        project_subtitle=arguments.project_subtitle,
        source_root=Path(__file__).resolve().parent,
    )
    print(
        f"Imported {result['total']} publications: {result['generated']} generated, "
        f"{result['skipped']} already present, {result['ignored']} unsupported entries ignored."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=None))
