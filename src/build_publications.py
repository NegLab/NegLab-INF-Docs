#!/usr/bin/env python3
"""Build the NegLab INF GitHub Pages project catalogue from BibTeX files."""

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


def read_bibtex_file(*, path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        raise FileNotFoundError(f"BibTeX file not found: {path}")
    entries = parse_bibtex(text=path.read_text(encoding="utf-8"), source=str(path))
    seen: set[str] = set()
    for entry in entries:
        bib_key = str(entry["bib_key"])
        if bib_key in seen:
            raise ValueError(f"Duplicate BibTeX key {bib_key!r} in {path}")
        seen.add(bib_key)
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


def filename_for_key(*, bib_key: str) -> str:
    ascii_key = unicodedata.normalize("NFKD", bib_key).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_key.lower()).strip("-") or "project"
    digest = hashlib.sha256(bib_key.encode("utf-8")).hexdigest()[:10]
    return f"{slug}-{digest}.html"


def _normalise_doi(*, doi: str) -> str:
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip(), flags=re.IGNORECASE)


def _valid_web_url(*, url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _entry_to_catalogue_entry(*, entry: dict[str, object]) -> dict[str, object]:
    fields = entry["fields"]
    if not isinstance(fields, dict):
        raise TypeError("BibTeX fields must be a dictionary")
    text_fields = {str(key): str(value) for key, value in fields.items()}
    entry_type = str(entry["entry_type"])
    title = _latex_to_text(value=text_fields.get("title", text_fields.get("name", "Untitled entry")))
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
    projectlink = text_fields.get("projectlink", "").strip()
    if not _valid_web_url(url=projectlink):
        projectlink = ""
    documentation = text_fields.get("documentation", "").strip()
    if not _valid_web_url(url=documentation):
        documentation = ""
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
        "project": "Project",
        "techreport": "Technical report",
        "tool": "Tool",
        "unpublished": "Preprint",
    }
    note = _latex_to_text(value=text_fields.get("note", text_fields.get("pubstate", "")))
    status = _latex_to_text(value=text_fields.get("status", ""))
    if entry_type == "tool" and not status:
        status = note
    return {
        "bib_key": str(entry["bib_key"]),
        "entry_type": entry_type,
        "type_label": type_labels.get(entry_type, entry_type.replace("_", " ").title()),
        "title": title,
        "subtitle": subtitle,
        "authors": _author_names(value=text_fields.get("author", text_fields.get("editor", ""))),
        "maintainers": _author_names(value=text_fields.get("maintainer", "")),
        "year": _latex_to_text(value=text_fields.get("year", "Undated")),
        "venue": venue,
        "institution": _latex_to_text(value=text_fields.get("institution", "")),
        "volume": _latex_to_text(value=text_fields.get("volume", "")),
        "number": _latex_to_text(value=text_fields.get("number", "")),
        "pages": _latex_to_text(value=text_fields.get("pages", "")),
        "publisher": _latex_to_text(value=text_fields.get("publisher", "")),
        "address": _latex_to_text(value=text_fields.get("address", text_fields.get("location", ""))),
        "note": note,
        "tooltype": _latex_to_text(value=text_fields.get("tooltype", "")).casefold(),
        "documentation": documentation,
        "access": _latex_to_text(value=text_fields.get("access", "")),
        "status": status.casefold(),
        "license": _latex_to_text(value=text_fields.get("license", "")),
        "related": [
            _latex_to_text(value=item.strip())
            for item in re.split(r"[,;]", text_fields.get("related", ""))
            if item.strip()
        ],
        "abstract": _latex_to_text(value=text_fields.get("abstract", "")),
        "keywords": keywords,
        "doi": doi,
        "url": url,
        "pdf": pdf,
        "projectlink": projectlink,
        "raw_bibtex": str(entry["raw_bibtex"]),
        "source": str(entry["source"]),
        "filename": filename_for_key(bib_key=str(entry["bib_key"])),
    }


def _escape(*, value: object) -> str:
    return html.escape(str(value), quote=True)


def load_inf_project_data(*, path: Path) -> dict[str, object]:
    """Load and validate the editable homepage data."""
    if not path.is_file():
        raise FileNotFoundError(f"INF project data file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    for field in ("title", "subtitle"):
        if not isinstance(data.get(field), str) or not str(data[field]).strip():
            raise ValueError(f"{path}: {field!r} must be a non-empty string")
    for field in ("description", "services", "research_areas", "related_links", "people"):
        if not isinstance(data.get(field), list):
            raise ValueError(f"{path}: {field!r} must be a JSON array")
    for position, person in enumerate(data["people"]):
        if not isinstance(person, dict):
            raise ValueError(f"{path}: people[{position}] must be an object")
        for field in ("name", "role"):
            if not isinstance(person.get(field), str) or not str(person[field]).strip():
                raise ValueError(f"{path}: people[{position}].{field} must be a non-empty string")
    return data


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


def _page_shell(
    *,
    title: str,
    description: str,
    body: str,
    asset_prefix: str,
    asset_version: str,
    project_name: str,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{_escape(value=description)}">
  <meta name="theme-color" content="#006d96">
  <title>{_escape(value=title)}</title>
  <link rel="stylesheet" href="{asset_prefix}assets/site.css?v={_escape(value=asset_version)}">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to content</a>
  <header class="site-header">
    <a class="brand" href="{asset_prefix}index.html" aria-label="{_escape(value=project_name)} home">
      <span class="brand-mark">INF</span>
      <span><strong>{_escape(value=project_name)}</strong><small>Information Infrastructure</small></span>
    </a>
    <nav aria-label="Main navigation"><a href="{asset_prefix}index.html#about">About</a><a href="{asset_prefix}index.html#people">People</a><a href="{asset_prefix}index.html#tools">Tools &amp; Services</a><a href="{asset_prefix}index.html#projects">Projects &amp; Publications</a></nav>
  </header>
  <main id="main-content">{body}</main>
  <footer><div><strong>{_escape(value=project_name)}</strong><p>Tools, projects, publications, and information infrastructure for collaborative negation research.</p></div><p>CRC 1629 · Goethe University Frankfurt</p></footer>
</body>
</html>
"""


def _format_author_list(*, authors: list[str]) -> str:
    return ", ".join(_escape(value=author) for author in authors) if authors else "Unknown authors"


def _render_catalogue_card(*, entry: dict[str, object]) -> str:
    authors = entry["authors"] if isinstance(entry["authors"], list) else []
    keywords = entry["keywords"] if isinstance(entry["keywords"], list) else []
    searchable = " ".join(
        [
            str(entry["title"]),
            str(entry["subtitle"]),
            str(entry["abstract"]),
            *[str(author) for author in authors],
            str(entry["venue"]),
            *[str(keyword) for keyword in keywords],
        ]
    ).lower()
    venue = f'<p class="venue">{_escape(value=entry["venue"])}</p>' if entry["venue"] else ""
    author_line = f'<p class="authors">{_format_author_list(authors=authors)}</p>' if authors else ""
    note = f'<span class="status-chip">{_escape(value=entry["note"])}</span>' if entry["note"] else ""
    return f"""<article class="publication-card" data-year="{_escape(value=entry['year'])}" data-type="{_escape(value=entry['entry_type'])}" data-search="{_escape(value=searchable)}">
  <div class="card-year"><span>{_escape(value=entry['year'])}</span><small>{_escape(value=entry['type_label'])}</small></div>
  <div class="card-content">
    <div class="card-heading"><h3><a href="publications/{_escape(value=entry['filename'])}">{_escape(value=entry['title'])}</a></h3>{note}</div>{author_line}{venue}
  </div>
  <a class="card-arrow" href="publications/{_escape(value=entry['filename'])}" aria-label="View {_escape(value=entry['title'])}">{_icon(name='arrow')}</a>
</article>"""


def _render_tool_card(*, entry: dict[str, object]) -> str:
    maintainers = entry["maintainers"] if isinstance(entry["maintainers"], list) else []
    keywords = entry["keywords"] if isinstance(entry["keywords"], list) else []
    searchable = " ".join(
        [
            str(entry["title"]),
            str(entry["subtitle"]),
            str(entry["abstract"]),
            *[str(maintainer) for maintainer in maintainers],
            *[str(keyword) for keyword in keywords],
            str(entry["tooltype"]),
        ]
    ).lower()
    subtitle = str(entry["subtitle"]) or str(entry["abstract"])
    maintainer_line = (
        f'<p class="tool-maintainers"><strong>Maintained by</strong> {_format_author_list(authors=maintainers)}</p>'
        if maintainers
        else ""
    )
    keyword_html = "".join(f'<span>{_escape(value=keyword)}</span>' for keyword in keywords[:4])
    keyword_line = f'<div class="tool-keywords">{keyword_html}</div>' if keyword_html else ""
    tooltype = str(entry["tooltype"])
    status = str(entry["status"])
    status_chip = f'<span class="status-chip">{_escape(value=status.title())}</span>' if status else ""
    return f"""<article class="publication-card tool-card" data-tooltype="{_escape(value=tooltype)}" data-status="{_escape(value=status)}" data-search="{_escape(value=searchable)}">
  <div class="card-year tool-meta"><span>{_escape(value=tooltype.title() or 'Tool')}</span><small>{_escape(value=status.title() or 'Status not specified')}</small></div>
  <div class="card-content">
    <div class="card-heading"><h3><a href="publications/{_escape(value=entry['filename'])}">{_escape(value=entry['title'])}</a></h3>{status_chip}</div>
    <p class="tool-summary">{_escape(value=subtitle)}</p>{maintainer_line}{keyword_line}
  </div>
  <a class="card-arrow" href="publications/{_escape(value=entry['filename'])}" aria-label="View {_escape(value=entry['title'])}">{_icon(name='arrow')}</a>
</article>"""


def _person_initials(*, name: str) -> str:
    title_words = {"prof", "prof.", "dr", "dr.", "apl", "apl."}
    words = [word for word in name.split() if word.casefold() not in title_words]
    selected = words[-2:] if len(words) > 1 else words
    return "".join(word[0].upper() for word in selected if word) or "INF"


def _render_inf_overview(*, project_data: dict[str, object]) -> str:
    descriptions = project_data["description"] if isinstance(project_data["description"], list) else []
    description_html = "".join(f'<p>{_escape(value=paragraph)}</p>' for paragraph in descriptions if isinstance(paragraph, str))

    research_areas = project_data["research_areas"] if isinstance(project_data["research_areas"], list) else []
    area_html = "".join(f'<span>{_escape(value=area)}</span>' for area in research_areas if isinstance(area, str))

    services = project_data["services"] if isinstance(project_data["services"], list) else []
    service_cards: list[str] = []
    for service in services:
        if not isinstance(service, dict):
            continue
        name = str(service.get("name", "Service"))
        items = service.get("items", [])
        item_html = "".join(f'<li>{_escape(value=item)}</li>' for item in items if isinstance(item, str)) if isinstance(items, list) else ""
        service_cards.append(f'<article class="service-card"><h3>{_escape(value=name)}</h3><ul>{item_html}</ul></article>')

    related_links = project_data["related_links"] if isinstance(project_data["related_links"], list) else []
    link_html = "".join(
        f'<a href="{_escape(value=link.get("url", ""))}" rel="noopener noreferrer">{_escape(value=link.get("label", "Related research"))} {_icon(name="external")}</a>'
        for link in related_links
        if isinstance(link, dict) and _valid_web_url(url=str(link.get("url", "")))
    )
    source = project_data.get("source", {})
    source_url = str(source.get("url", "")) if isinstance(source, dict) else ""
    source_link = (
        f'<a class="source-link" href="{_escape(value=source_url)}" rel="noopener noreferrer">Official INF project page {_icon(name="external")}</a>'
        if _valid_web_url(url=source_url)
        else ""
    )

    people = project_data["people"] if isinstance(project_data["people"], list) else []
    role_groups: dict[str, list[dict[str, object]]] = {}
    for person in people:
        if isinstance(person, dict):
            role_groups.setdefault(str(person["role"]), []).append(person)
    people_groups: list[str] = []
    for role, members in role_groups.items():
        cards: list[str] = []
        for person in members:
            name = str(person["name"])
            affiliation = str(person.get("affiliation", "")).strip()
            profile_url = str(person.get("profile_url", "")).strip()
            name_html = _escape(value=name)
            if _valid_web_url(url=profile_url):
                name_html = f'<a href="{_escape(value=profile_url)}" rel="noopener noreferrer">{name_html} {_icon(name="external")}</a>'
            affiliation_html = f'<p>{_escape(value=affiliation)}</p>' if affiliation else ""
            cards.append(
                f'<article class="person-card"><div class="person-initials" aria-hidden="true">{_escape(value=_person_initials(name=name))}</div>'
                f'<div><span>{_escape(value=role)}</span><h3>{name_html}</h3>{affiliation_html}</div></article>'
            )
        people_groups.append(f'<div class="people-group"><h3>{_escape(value=role)}</h3><div class="people-grid">{"".join(cards)}</div></div>')

    contact = str(project_data.get("contact", "")).strip()
    contact_html = f'<p class="contact-note">{_escape(value=contact)}</p>' if contact else ""
    return f"""
<section class="about-section" id="about">
  <div class="section-heading"><div><span class="eyebrow">About the subproject</span><h2>{_escape(value=project_data['title'])}</h2></div><p>{_escape(value=project_data['subtitle'])}</p></div>
  <div class="about-grid">
    <div class="about-copy">{description_html}<div class="related-links">{link_html}</div>{source_link}</div>
    <aside class="research-areas"><span class="eyebrow">Research areas</span><div>{area_html}</div></aside>
  </div>
  <div class="services-grid">{"".join(service_cards)}</div>{contact_html}
</section>
<section class="people-section" id="people">
  <div class="section-heading"><div><span class="eyebrow">The INF team</span><h2>People</h2></div><p>Project leadership and scientific staff supporting research across the CRC.</p></div>
  {''.join(people_groups)}
</section>
"""


def render_index(
    *,
    entries: list[dict[str, object]],
    project_name: str,
    project_subtitle: str,
    asset_version: str,
    project_data: dict[str, object],
) -> str:
    tools = [entry for entry in entries if entry["entry_type"] == "tool"]
    catalogue_entries = [entry for entry in entries if entry["entry_type"] != "tool"]
    years = sorted({str(entry["year"]) for entry in catalogue_entries}, reverse=True)
    types = sorted(
        {(str(entry["entry_type"]), str(entry["type_label"])) for entry in catalogue_entries},
        key=lambda item: item[1],
    )
    year_options = "".join(f'<option value="{_escape(value=year)}">{_escape(value=year)}</option>' for year in years)
    type_options = "".join(f'<option value="{_escape(value=key)}">{_escape(value=label)}</option>' for key, label in types)
    tooltype_options = "".join(
        f'<option value="{value}">{label}</option>'
        for value, label in (
            ("software", "Software"),
            ("service", "Service"),
            ("infrastructure", "Infrastructure"),
            ("workflow", "Workflow"),
        )
    )
    tool_status_options = "".join(
        f'<option value="{value}">{label}</option>'
        for value, label in (
            ("active", "Active"),
            ("beta", "Beta"),
            ("maintenance", "Maintenance"),
            ("retired", "Retired"),
        )
    )
    tool_cards = "\n".join(_render_tool_card(entry=entry) for entry in tools)
    catalogue_cards = "\n".join(_render_catalogue_card(entry=entry) for entry in catalogue_entries)
    people = project_data["people"] if isinstance(project_data["people"], list) else []
    people_count = sum(isinstance(person, dict) for person in people)
    tool_count = sum(entry["entry_type"] == "tool" for entry in entries)
    project_count = sum(entry["entry_type"] == "project" for entry in entries)
    publication_count = sum(entry["entry_type"] not in {"project", "tool"} for entry in entries)
    body = f"""
<section class="hero">
  <div class="hero-copy">
    <div class="eyebrow">CRC 1629 · Negation in Language and Beyond</div>
    <h1>{_escape(value=project_subtitle)}</h1>
    <p>Tools, services, projects, and research outputs from the INF subproject, building sustainable infrastructure and methods for collaborative research on negation.</p>
  </div>
  <nav class="section-navigation" aria-label="Explore the INF website">
    <a class="section-panel" href="#about">
      <span class="panel-icon">{_icon(name='book')}</span>
      <span class="panel-number">01</span>
      <h2>About INF</h2>
      <p>Learn how INF supports sustainable data, infrastructure, and collaborative research across the CRC.</p>
      <span class="panel-footer"><span>Project overview</span>{_icon(name='arrow')}</span>
    </a>
    <a class="section-panel" href="#people">
      <span class="panel-icon">{_icon(name='users')}</span>
      <span class="panel-number">02</span>
      <h2>People</h2>
      <p>Meet the project leadership and scientific staff behind INF’s services and research support.</p>
      <span class="panel-footer"><span class="panel-stat"><strong>{people_count}</strong><span>Team members</span></span>{_icon(name='arrow')}</span>
    </a>
    <a class="section-panel" href="#tools">
      <span class="panel-icon">{_icon(name='code')}</span>
      <span class="panel-number">03</span>
      <h2>Tools &amp; Services</h2>
      <p>Browse reusable software, hosted services, infrastructure resources, and workflows provided by INF.</p>
      <span class="panel-footer"><span class="panel-stat"><strong>{tool_count}</strong><span>Tools</span></span>{_icon(name='arrow')}</span>
    </a>
    <a class="section-panel" href="#projects">
      <span class="panel-icon">{_icon(name='file')}</span>
      <span class="panel-number">04</span>
      <h2>Projects &amp; Publications</h2>
      <p>Explore INF collaborations, development activities, articles, conference papers, and reports.</p>
      <span class="panel-footer"><span class="panel-stat"><strong>{project_count}</strong><span>Projects</span><strong>{publication_count}</strong><span>Publications</span></span>{_icon(name='arrow')}</span>
    </a>
  </nav>
</section>
{_render_inf_overview(project_data=project_data)}
<section class="publication-section tool-section" id="tools">
  <div class="section-heading"><div><span class="eyebrow">Reusable INF resources</span><h2>Tools &amp; Services</h2></div><p>Discover software, hosted services, infrastructure, and workflows maintained or provided by INF.</p></div>
  <div class="filters tool-filters" role="search" aria-label="Filter tools and services">
    <label class="search-field">{_icon(name='search')}<span class="sr-only">Search tools</span><input id="tool-search" type="search" placeholder="Search tools…" autocomplete="off"></label>
    <label><span class="sr-only">Filter by tool type</span><select id="tool-type-filter"><option value="">All tool types</option>{tooltype_options}</select></label>
    <label><span class="sr-only">Filter by tool status</span><select id="tool-status-filter"><option value="">All statuses</option>{tool_status_options}</select></label>
  </div>
  <div class="result-bar"><span id="tool-result-count">{tool_count} tools</span><button id="tool-clear-filters" type="button" hidden>Clear filters</button></div>
  <div class="publication-list tool-list" id="tool-list">{tool_cards}</div>
  <div class="empty-state" id="tool-empty-state" hidden><span>{_icon(name='search')}</span><h3>No tools found</h3><p>Try another search or clear the filters.</p></div>
</section>
<section class="publication-section" id="projects">
  <div class="section-heading"><div><span class="eyebrow">INF research catalogue</span><h2>Projects &amp; Publications</h2></div><p>Explore INF collaborations, research and development activities, articles, conference papers, and technical reports.</p></div>
  <div class="filters" role="search" aria-label="Filter projects and publications">
    <label class="search-field">{_icon(name='search')}<span class="sr-only">Search projects and publications</span><input id="catalogue-search" type="search" placeholder="Search project, publication, author, venue, or keyword…" autocomplete="off"></label>
    <label><span class="sr-only">Filter by year</span><select id="catalogue-year-filter"><option value="">All years</option>{year_options}</select></label>
    <label><span class="sr-only">Filter by entry type</span><select id="catalogue-type-filter"><option value="">All types</option>{type_options}</select></label>
  </div>
  <div class="result-bar"><span id="catalogue-result-count">{len(catalogue_entries)} entries</span><button id="catalogue-clear-filters" type="button" hidden>Clear filters</button></div>
  <div class="publication-list" id="catalogue-list">{catalogue_cards}</div>
  <div class="empty-state" id="catalogue-empty-state" hidden><span>{_icon(name='search')}</span><h3>No projects or publications found</h3><p>Try another search or clear the filters.</p></div>
</section>
<script src="assets/site.js?v={_escape(value=asset_version)}" defer></script>
"""
    return _page_shell(
        title=f"{project_name} · Catalogue",
        description="Tools, services, projects, publications, and research outputs of the NegLab CRC 1629 INF subproject.",
        body=body,
        asset_prefix="",
        asset_version=asset_version,
        project_name=project_name,
    )


def render_repository_link(*, url: str) -> str:
    if url:
        return f'<a class="button button-secondary" href="{_escape(value=url)}" rel="noopener noreferrer">{_icon(name="github")} Code &amp; archive</a>'
    return f'<span class="button button-secondary button-disabled" aria-disabled="true" title="No code or archive link has been added yet">{_icon(name="github")} Code &amp; archive</span>'


def _detail_rows(*, entry: dict[str, object]) -> str:
    if entry["entry_type"] == "tool":
        maintainers = entry["maintainers"] if isinstance(entry["maintainers"], list) else []
        related = entry["related"] if isinstance(entry["related"], list) else []
        values = [
            ("Tool type", str(entry["tooltype"]).title()),
            ("Status", str(entry["status"]).title()),
            ("Maintainer", ", ".join(str(maintainer) for maintainer in maintainers)),
            ("Access", entry["access"]),
            ("Year", entry["year"]),
            ("Institution", entry["institution"]),
            ("License", entry["license"]),
            ("Related entries", ", ".join(str(bib_key) for bib_key in related)),
            ("BibTeX key", entry["bib_key"]),
        ]
    else:
        values = [
            ("Entry type", entry["type_label"]),
            ("Year", entry["year"]),
            ("Venue", entry["venue"]),
            ("Volume", entry["volume"]),
            ("Issue / number", entry["number"]),
            ("Pages", entry["pages"]),
            ("Publisher", entry["publisher"]),
            ("Location", entry["address"]),
            ("DOI", entry["doi"]),
            ("BibTeX key", entry["bib_key"]),
        ]
    return "".join(
        f'<div><dt>{_escape(value=label)}</dt><dd>{_escape(value=value)}</dd></div>' for label, value in values if value
    )


def render_detail(*, entry: dict[str, object], project_name: str, asset_version: str) -> str:
    authors = entry["authors"] if isinstance(entry["authors"], list) else []
    maintainers = entry["maintainers"] if isinstance(entry["maintainers"], list) else []
    keywords = entry["keywords"] if isinstance(entry["keywords"], list) else []
    title = str(entry["title"])
    subtitle = f'<p class="subtitle">{_escape(value=entry["subtitle"])}</p>' if entry["subtitle"] else ""
    entry_type = entry["entry_type"]
    is_project = entry_type == "project"
    is_tool = entry_type == "tool"
    is_publication = not is_project and not is_tool
    if is_tool:
        venue = f'<p class="detail-venue">{_escape(value=str(entry["tooltype"]).title())}</p>' if entry["tooltype"] else ""
    else:
        venue = f'<p class="detail-venue">{_escape(value=entry["venue"])} · {_escape(value=entry["year"])}</p>' if entry["venue"] else f'<p class="detail-venue">{_escape(value=entry["year"])}</p>'
    lifecycle = entry["status"] if is_tool else entry["note"]
    note = f'<span class="status-chip">{_escape(value=str(lifecycle).title())}</span>' if lifecycle else ""
    author_line = f'<p class="detail-authors">{_format_author_list(authors=authors)}</p>' if authors else ""
    if is_tool:
        author_line = (
            f'<p class="detail-authors"><strong>Maintained by</strong> {_format_author_list(authors=maintainers)}</p>'
            if maintainers
            else ""
        )
        if authors:
            author_line += f'<p class="tool-authors"><strong>Developed by</strong> {_format_author_list(authors=authors)}</p>'
    actions: list[str] = []
    if entry["url"]:
        if is_tool:
            action_label = "Open tool"
        elif is_project:
            action_label = "Visit project"
        elif is_publication:
            action_label = "View publication"
        actions.append(f'<a class="button button-primary" href="{_escape(value=entry["url"])}" rel="noopener noreferrer">{_icon(name="external")} {action_label}</a>')
    if is_tool and entry["documentation"]:
        actions.append(f'<a class="button button-secondary" href="{_escape(value=entry["documentation"])}" rel="noopener noreferrer">{_icon(name="book")} Documentation</a>')
    if entry["pdf"]:
        actions.append(f'<a class="button button-secondary" href="{_escape(value=entry["pdf"])}" rel="noopener noreferrer">{_icon(name="file")} PDF</a>')
    actions.append(render_repository_link(url=str(entry["projectlink"])))
    abstract = str(entry["abstract"])
    about_heading = "About this tool" if is_tool else "Abstract"
    missing_about = "No description is available in the bibliography." if is_tool else "No abstract is available in the bibliography."
    abstract_section = f'<section class="paper-section"><h2>{about_heading}</h2><p class="abstract">{_escape(value=abstract)}</p></section>' if abstract else f'<section class="paper-section muted-section"><h2>{about_heading}</h2><p>{missing_about}</p></section>'
    keyword_html = "".join(f'<span>{_escape(value=keyword)}</span>' for keyword in keywords)
    keyword_section = f'<section class="paper-section"><h2>Keywords</h2><div class="keyword-list">{keyword_html}</div></section>' if keywords else ""
    back_target = "tools" if is_tool else "projects"
    back_label = "Tools &amp; Services" if is_tool else "Projects &amp; Publications"
    if is_tool:
        facts_heading = "Tool details"
        entry_kind = "Tool"
    elif is_project:
        facts_heading = "Project details"
        entry_kind = "Project"
    elif is_publication:
        facts_heading = "Publication details"
        entry_kind = "Publication"
    type_icon = "code" if is_tool else "book"
    body = f"""
<div class="detail-back"><a href="../index.html#{back_target}">← Back to {back_label}</a></div>
<article class="paper">
  <header class="paper-header">
    <div class="paper-type">{_icon(name=type_icon)} {_escape(value=entry['type_label'])}{note}</div>
    <h1>{_escape(value=title)}</h1>{subtitle}
    {author_line}{venue}
    <div class="paper-actions">{''.join(actions)}</div>
  </header>
  <div class="paper-layout">
    <div>{abstract_section}{keyword_section}
      <section class="paper-section citation-section"><div class="section-title-row"><h2>BibTeX</h2><button class="copy-button" type="button" data-copy-bib>{_icon(name='copy')} Copy</button></div><pre><code id="bibtex-entry">{_escape(value=entry['raw_bibtex'])}</code></pre></section>
    </div>
    <aside class="paper-facts"><h2>{facts_heading}</h2><dl>{_detail_rows(entry=entry)}</dl></aside>
  </div>
</article>
<script src="../assets/site.js?v={_escape(value=asset_version)}" defer></script>
"""
    page = _page_shell(
        title=f"{title} · {project_name}",
        description=abstract[:155] if abstract else f"{entry_kind} details for {title}.",
        body=body,
        asset_prefix="../",
        asset_version=asset_version,
        project_name=project_name,
    )
    return page.replace("<meta name=\"theme-color\"", f'<meta name="bib-key" content="{_escape(value=entry["bib_key"])}">\n  <meta name="theme-color"', 1)


def _sort_entries(*, entries: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    def sort_key(entry: dict[str, object]) -> tuple[int, str, str]:
        year = str(entry["year"])
        numeric_year = int(year) if year.isdigit() else -1
        return (-numeric_year, str(entry["title"]).casefold(), str(entry["bib_key"]).casefold())

    return sorted(entries, key=sort_key)


def _write_assets(*, docs_dir: Path, logo_path: Path, source_root: Path) -> None:
    assets_dir = docs_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for name in ("site.css", "site.js"):
        source = source_root / "site_assets" / name
        if not source.exists():
            raise FileNotFoundError(f"Required site asset is missing: {source}")
        shutil.copyfile(source, assets_dir / name)
    if not logo_path.is_file():
        raise FileNotFoundError(f"INF logo is missing: {logo_path}")
    shutil.copyfile(logo_path, assets_dir / "inf_logo.svg")


def _asset_version(*, source_root: Path) -> str:
    digest = hashlib.sha256()
    for name in ("site.css", "site.js"):
        source = source_root / "site_assets" / name
        if not source.is_file():
            raise FileNotFoundError(f"Required site asset is missing: {source}")
        digest.update(source.read_bytes())
    return digest.hexdigest()[:12]


def generate_site_from_entries(
    *,
    entries: Sequence[dict[str, object]],
    docs_dir: Path,
    allowed_entry_types: frozenset[str],
    project_name: str,
    project_subtitle: str,
    project_data_path: Path,
    logo_path: Path,
    source_root: Path,
) -> dict[str, int]:
    """Rebuild the complete site from parsed BibTeX entries and homepage data."""
    catalogue_entries = _sort_entries(
        entries=(
            _entry_to_catalogue_entry(entry=entry)
            for entry in entries
            if str(entry["entry_type"]) in allowed_entry_types
        )
    )
    if docs_dir.exists():
        if not docs_dir.is_dir():
            raise NotADirectoryError(f"Site output path is not a directory: {docs_dir}")
        shutil.rmtree(docs_dir)
    publication_dir = docs_dir / "publications"
    publication_dir.mkdir(parents=True)

    asset_version = _asset_version(source_root=source_root)
    project_data = load_inf_project_data(path=project_data_path)
    _write_assets(docs_dir=docs_dir, logo_path=logo_path, source_root=source_root)
    for entry in catalogue_entries:
        target = publication_dir / str(entry["filename"])
        rendered_page = render_detail(
            entry=entry,
            project_name=project_name,
            asset_version=asset_version,
        )
        target.write_text(rendered_page, encoding="utf-8")

    (docs_dir / "index.html").write_text(
        render_index(
            entries=catalogue_entries,
            project_name=project_name,
            project_subtitle=project_subtitle,
            asset_version=asset_version,
            project_data=project_data,
        ),
        encoding="utf-8",
    )
    manifest = {
        "publications": [
            {
                "bib_key": entry["bib_key"],
                "filename": entry["filename"],
                "title": entry["title"],
                "year": entry["year"],
                "entry_type": entry["entry_type"],
            }
            for entry in catalogue_entries
        ]
    }
    (publication_dir / "index.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (docs_dir / ".nojekyll").touch()
    return {
        "generated": len(catalogue_entries),
        "total": len(catalogue_entries),
        "tools": sum(entry["entry_type"] == "tool" for entry in catalogue_entries),
        "projects": sum(entry["entry_type"] == "project" for entry in catalogue_entries),
        "publications": sum(entry["entry_type"] not in {"project", "tool"} for entry in catalogue_entries),
        "ignored": len(entries) - len(catalogue_entries),
    }


def build_site(
    *,
    bib_path: Path,
    docs_dir: Path,
    allowed_entry_types: frozenset[str],
    project_name: str,
    project_subtitle: str,
    project_data_path: Path,
    logo_path: Path,
    source_root: Path,
) -> dict[str, int]:
    """Read one BibTeX file and rebuild the complete project catalogue."""
    return generate_site_from_entries(
        entries=read_bibtex_file(path=bib_path),
        docs_dir=docs_dir,
        allowed_entry_types=allowed_entry_types,
        project_name=project_name,
        project_subtitle=project_subtitle,
        project_data_path=project_data_path,
        logo_path=logo_path,
        source_root=source_root,
    )


def supported_entry_types(*, include_projects: bool = True) -> frozenset[str]:
    entry_types = {
        "article",
        "book",
        "booklet",
        "inbook",
        "incollection",
        "inproceedings",
        "manual",
        "mastersthesis",
        "misc",
        "phdthesis",
        "proceedings",
        "techreport",
        "unpublished",
    }
    if include_projects:
        entry_types.add("project")
        entry_types.add("tool")
    return frozenset(entry_types)


def _argument_parser(
    *,
    default_docs_dir: Path,
    default_bib_path: Path,
    default_project_data_path: Path,
    default_logo_path: Path,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild the GitHub Pages project catalogue from one BibTeX file and the INF project JSON.")
    parser.add_argument("bib_file", nargs="?", type=Path, default=default_bib_path, help=f"authoritative BibTeX input (default: {default_bib_path})")
    parser.add_argument("--docs-dir", type=Path, default=default_docs_dir, help=f"site output directory (default: {default_docs_dir})")
    parser.add_argument("--project-data", type=Path, default=default_project_data_path, help=f"editable INF homepage JSON (default: {default_project_data_path})")
    parser.add_argument("--logo", type=Path, default=default_logo_path, help=f"INF logo SVG (default: {default_logo_path})")
    parser.add_argument("--project-name", default="NegLab INF", help="short project name shown in the site header")
    parser.add_argument("--project-subtitle", default="Infrastructure for research on negation", help="main heading shown on the project index")
    return parser


def main(*, argv: Sequence[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parent.parent
    parser = _argument_parser(
        default_docs_dir=project_root / "docs",
        default_bib_path=project_root / "data" / "neglab-inf.bib",
        default_project_data_path=project_root / "data" / "inf-project.json",
        default_logo_path=project_root / "data" / "inf_logo.svg",
    )
    arguments = parser.parse_args(argv)
    allowed_entry_types = supported_entry_types(include_projects=True)
    result = build_site(
        bib_path=arguments.bib_file,
        docs_dir=arguments.docs_dir,
        allowed_entry_types=allowed_entry_types,
        project_name=arguments.project_name,
        project_subtitle=arguments.project_subtitle,
        project_data_path=arguments.project_data,
        logo_path=arguments.logo,
        source_root=Path(__file__).resolve().parent,
    )
    print(
        f"Rebuilt site from {arguments.bib_file}: {result['total']} catalogue entries "
        f"({result['tools']} tools, {result['projects']} projects, {result['publications']} publications), "
        f"{result['generated']} detail pages written, "
        f"{result['ignored']} unsupported entries ignored."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=None))
