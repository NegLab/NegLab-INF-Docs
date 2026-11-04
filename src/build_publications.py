#!/usr/bin/env python3
"""Build the NegLab INF GitHub Pages catalogue from one BibTeX file.

Every catalogue entry is a ``@project`` entry. Its ``keywords`` field lists the
catalogue categories (tool, project, publication, collaboration) that decide
on which tab pages the entry appears.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urlparse

ENTRY_TYPE = "project"

CATEGORY_ORDER = ("tool", "project", "publication", "collaboration")
CATEGORY_ALIASES = {category: category for category in CATEGORY_ORDER} | {f"{category}s": category for category in CATEGORY_ORDER}
CATEGORY_LABELS = {"tool": "Tool", "project": "Project", "publication": "Publication", "collaboration": "Collaboration"}

PUBLICATION_TYPE_LABELS = {
    "article": "Journal article",
    "book": "Book",
    "booklet": "Booklet",
    "inbook": "Book chapter",
    "incollection": "Book chapter",
    "inproceedings": "Conference paper",
    "manual": "Manual",
    "mastersthesis": "Master's thesis",
    "misc": "Publication",
    "phdthesis": "Doctoral thesis",
    "proceedings": "Proceedings",
    "techreport": "Technical report",
    "unpublished": "Preprint",
}

# Catalogue-only fields that are dropped when a publication is exported as standard BibTeX.
CATALOGUE_ONLY_FIELDS = frozenset(
    {"keywords", "tags", "pubtype", "collaboration", "name", "maintainer", "tooltype", "status", "access", "documentation", "projectlink", "related", "license"}
)


@dataclass(frozen=True)
class Page:
    slug: str
    filename: str
    label: str
    icon: str
    eyebrow: str
    summary: str
    category: str | None = None
    stat_label: str = ""
    singular: str = ""
    plural: str = ""


PAGES = (
    Page(
        slug="about",
        filename="about.html",
        label="About",
        icon="info",
        eyebrow="About the subproject",
        summary="Learn how INF supports sustainable data, infrastructure, and collaborative research across the CRC.",
    ),
    Page(
        slug="people",
        filename="people.html",
        label="People",
        icon="users",
        eyebrow="The INF team",
        summary="Meet the project leadership and scientific staff behind INF’s services and research support.",
    ),
    Page(
        slug="tools",
        filename="tools.html",
        label="Tools & Services",
        icon="code",
        eyebrow="Reusable INF resources",
        summary="Browse reusable software, hosted services, infrastructure resources, and workflows provided by INF.",
        category="tool",
        stat_label="Tools",
        singular="tool",
        plural="tools",
    ),
    Page(
        slug="projects",
        filename="projects.html",
        label="Projects",
        icon="folder",
        eyebrow="INF activities",
        summary="Explore research, development, annotation, and infrastructure activities carried out by INF.",
        category="project",
        stat_label="Projects",
        singular="project",
        plural="projects",
    ),
    Page(
        slug="publications",
        filename="publications.html",
        label="Publications",
        icon="book",
        eyebrow="Research outputs",
        summary="Read journal articles, conference papers, and technical reports by INF members and partners.",
        category="publication",
        stat_label="Publications",
        singular="publication",
        plural="publications",
    ),
    Page(
        slug="collaborations",
        filename="collaborations.html",
        label="Collaborations",
        icon="link",
        eyebrow="Joint work across the CRC",
        summary="See the projects, tools, and publications INF has realised together with other CRC 1629 projects.",
        category="collaboration",
        stat_label="Collaborations",
        singular="collaboration",
        plural="collaborations",
    ),
)
PAGES_BY_SLUG = {page.slug: page for page in PAGES}
CATEGORY_PAGES = {page.category: page for page in PAGES if page.category}

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


def _split_list(*, value: str) -> list[str]:
    return [_latex_to_text(value=item.strip()) for item in re.split(r"[,;]", value) if item.strip()]


def _partner_projects(*, value: str) -> list[str]:
    """Return the CRC projects listed in ``collaboration``; codes like ``a02`` become ``A02``."""
    partners: list[str] = []
    for item in _split_list(value=value):
        partner = item.upper() if re.fullmatch(r"[A-Za-z]\d{2}", item) else item
        if partner not in partners:
            partners.append(partner)
    return partners


def parse_categories(*, bib_key: str, value: str) -> list[str]:
    """Return the catalogue categories listed in an entry's ``keywords`` field."""
    categories: list[str] = []
    for item in _split_list(value=value):
        category = CATEGORY_ALIASES.get(item.casefold())
        if category is None:
            allowed = ", ".join(CATEGORY_ORDER)
            raise ValueError(f"Entry {bib_key!r} has unknown category {item!r} in keywords; use {allowed}")
        if category not in categories:
            categories.append(category)
    if not categories:
        raise ValueError(
            f"Entry {bib_key!r} has no categories; add keywords = {{tool, project, publication, or collaboration}}"
        )
    return categories


def citation_bibtex(*, bib_key: str, pubtype: str, fields: dict[str, str]) -> str:
    """Convert a catalogue entry into standard BibTeX for citing a publication."""
    items: list[tuple[str, str]] = []
    if "title" not in fields and fields.get("name"):
        items.append(("title", fields["name"]))
    items.extend((name, value) for name, value in fields.items() if name not in CATALOGUE_ONLY_FIELDS)
    if fields.get("tags"):
        items.append(("keywords", fields["tags"]))
    items = [(name, " ".join(value.split())) for name, value in items if value.strip()]
    width = max((len(name) for name, _ in items), default=0)
    body = ",\n".join(f"  {name.ljust(width)} = {{{value}}}" for name, value in items)
    return f"@{pubtype}{{{bib_key},\n{body}\n}}"


def _entry_to_catalogue_entry(*, entry: dict[str, object]) -> dict[str, object]:
    fields = entry["fields"]
    if not isinstance(fields, dict):
        raise TypeError("BibTeX fields must be a dictionary")
    text_fields = {str(key): str(value) for key, value in fields.items()}
    bib_key = str(entry["bib_key"])
    entry_type = str(entry["entry_type"])
    if entry_type != ENTRY_TYPE:
        raise ValueError(
            f"Entry {bib_key!r} uses @{entry_type}; every catalogue entry must be @{ENTRY_TYPE} "
            "with its categories listed in keywords"
        )
    categories = parse_categories(bib_key=bib_key, value=text_fields.get("keywords", ""))
    is_publication = "publication" in categories
    pubtype = text_fields.get("pubtype", "").strip().casefold()
    if is_publication and not pubtype:
        pubtype = "misc"
    pubtype_label = PUBLICATION_TYPE_LABELS.get(pubtype, pubtype.replace("_", " ").title()) if pubtype else ""
    primary = categories[0]
    type_label = pubtype_label if primary == "publication" else CATEGORY_LABELS[primary]

    title = _latex_to_text(value=text_fields.get("title", text_fields.get("name", "Untitled entry")))
    venue = _latex_to_text(
        value=text_fields.get("journal", text_fields.get("booktitle", text_fields.get("institution", "")))
    )
    doi = _normalise_doi(doi=text_fields.get("doi", ""))
    links: dict[str, str] = {}
    for name in ("url", "pdf", "projectlink", "documentation"):
        link = text_fields.get(name, "").strip()
        links[name] = link if _valid_web_url(url=link) else ""
    if not links["url"] and doi:
        links["url"] = f"https://doi.org/{doi}"
    note = _latex_to_text(value=text_fields.get("note", text_fields.get("pubstate", "")))
    status = _latex_to_text(value=text_fields.get("status", "")) or note
    return {
        "bib_key": bib_key,
        "categories": categories,
        "primary_category": primary,
        "pubtype": pubtype,
        "pubtype_label": pubtype_label,
        "type_label": type_label,
        "title": title,
        "subtitle": _latex_to_text(value=text_fields.get("subtitle", "")),
        "authors": _author_names(value=text_fields.get("author", text_fields.get("editor", ""))),
        "maintainers": _author_names(value=text_fields.get("maintainer", "")),
        "year": _latex_to_text(value=text_fields.get("year", "")) or "Undated",
        "venue": venue,
        "institution": _latex_to_text(value=text_fields.get("institution", "")),
        "volume": _latex_to_text(value=text_fields.get("volume", "")),
        "number": _latex_to_text(value=text_fields.get("number", "")),
        "pages": _latex_to_text(value=text_fields.get("pages", "")),
        "publisher": _latex_to_text(value=text_fields.get("publisher", "")),
        "address": _latex_to_text(value=text_fields.get("address", text_fields.get("location", ""))),
        "tooltype": _latex_to_text(value=text_fields.get("tooltype", "")).casefold(),
        "access": _latex_to_text(value=text_fields.get("access", "")),
        "status": status.casefold(),
        "license": _latex_to_text(value=text_fields.get("license", "")),
        "related": _split_list(value=text_fields.get("related", "")),
        "abstract": _latex_to_text(value=text_fields.get("abstract", "")),
        "tags": _split_list(value=text_fields.get("tags", "")),
        "partners": _partner_projects(value=text_fields.get("collaboration", "")),
        "doi": doi,
        **links,
        "raw_bibtex": str(entry["raw_bibtex"]),
        "citation_bibtex": citation_bibtex(bib_key=bib_key, pubtype=pubtype, fields=text_fields) if is_publication else "",
        "source": str(entry["source"]),
        "filename": filename_for_key(bib_key=bib_key),
    }


def _link_related_entries(*, entries: list[dict[str, object]]) -> None:
    """Validate ``related`` keys and record links in both directions."""
    by_key = {str(entry["bib_key"]): entry for entry in entries}
    links: dict[str, list[str]] = {key: [] for key in by_key}
    for entry in entries:
        key = str(entry["bib_key"])
        for related_key in entry["related"]:
            if related_key not in by_key:
                raise ValueError(f"Entry {key!r} lists unknown related key {related_key!r}")
            for source, target in ((key, related_key), (related_key, key)):
                if target != source and target not in links[source]:
                    links[source].append(target)
    for entry in entries:
        entry["related_entries"] = [
            {"bib_key": key, "title": by_key[key]["title"], "filename": by_key[key]["filename"], "type_label": by_key[key]["type_label"]}
            for key in links[str(entry["bib_key"])]
        ]


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
        "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
        "github": '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3.3-.4 6.8-1.6 6.8-7A5.4 5.4 0 0 0 19.4 4 5 5 0 0 0 19.3.5S18.2.1 15 1.8a13.4 13.4 0 0 0-7 0C4.8.1 3.7.5 3.7.5A5 5 0 0 0 3.6 4a5.4 5.4 0 0 0-1.4 3.7c0 5.4 3.5 6.6 6.8 7A4.8 4.8 0 0 0 8 18v4"/><path d="M8 19c-3 .9-3-1.5-4-2"/>',
        "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
        "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
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
    active: str,
) -> str:
    current = ' aria-current="page"'
    nav_links = "".join(
        f'<a href="{asset_prefix}{page.filename}"{current if page.slug == active else ""}>{_escape(value=page.label)}</a>'
        for page in PAGES
    )
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
    <nav aria-label="Main navigation">{nav_links}</nav>
  </header>
  <main id="main-content">{body}</main>
  <footer><div><strong>{_escape(value=project_name)}</strong><p>Tools, projects, publications, and information infrastructure for collaborative negation research.</p></div><p>CRC 1629 · Goethe University Frankfurt</p></footer>
  <script src="{asset_prefix}assets/site.js?v={_escape(value=asset_version)}" defer></script>
</body>
</html>
"""


def _page_intro(*, page: Page) -> str:
    return f"""
<section class="page-hero">
  <div class="page-hero-inner"><span class="eyebrow">{_escape(value=page.eyebrow)}</span><h1>{_escape(value=page.label)}</h1><p>{_escape(value=page.summary)}</p></div>
</section>"""


def _format_author_list(*, authors: list[str]) -> str:
    return ", ".join(_escape(value=author) for author in authors) if authors else "Unknown authors"


def _card_attributes(*, entry: dict[str, object]) -> str:
    searchable = " ".join(
        [
            str(entry["title"]),
            str(entry["subtitle"]),
            str(entry["abstract"]),
            str(entry["venue"]),
            str(entry["tooltype"]),
            str(entry["type_label"]),
            *[str(author) for author in entry["authors"]],
            *[str(maintainer) for maintainer in entry["maintainers"]],
            *[str(tag) for tag in entry["tags"]],
            *[CATEGORY_LABELS[category] for category in entry["categories"]],
            *[str(partner) for partner in entry["partners"]],
        ]
    ).lower()
    attributes = {
        "year": entry["year"],
        "status": entry["status"],
        "tooltype": entry["tooltype"],
        "pubtype": entry["pubtype"],
        "categories": "|".join(entry["categories"]),
        "partners": "|".join(entry["partners"]),
        "search": searchable,
    }
    return " ".join(f'data-{name}="{_escape(value=value)}"' for name, value in attributes.items())


def _partner_line(*, entry: dict[str, object]) -> str:
    partners = entry["partners"]
    if not partners:
        return ""
    return f'<p class="partner-line"><strong>In collaboration with</strong> {_escape(value=", ".join(partners))}</p>'


def _render_catalogue_card(*, entry: dict[str, object], label: str) -> str:
    authors = entry["authors"]
    venue = f'<p class="venue">{_escape(value=entry["venue"])}</p>' if entry["venue"] else ""
    author_line = f'<p class="authors">{_format_author_list(authors=authors)}</p>' if authors else ""
    status = f'<span class="status-chip">{_escape(value=entry["status"])}</span>' if entry["status"] else ""
    return f"""<article class="publication-card" {_card_attributes(entry=entry)}>
  <div class="card-year"><span>{_escape(value=entry['year'])}</span><small>{_escape(value=label)}</small></div>
  <div class="card-content">
    <div class="card-heading"><h3><a href="publications/{_escape(value=entry['filename'])}">{_escape(value=entry['title'])}</a></h3>{status}</div>{author_line}{venue}{_partner_line(entry=entry)}
  </div>
  <a class="card-arrow" href="publications/{_escape(value=entry['filename'])}" aria-label="View {_escape(value=entry['title'])}">{_icon(name='arrow')}</a>
</article>"""


def _render_tool_card(*, entry: dict[str, object]) -> str:
    maintainers = entry["maintainers"]
    tags = entry["tags"]
    summary = str(entry["subtitle"]) or str(entry["abstract"])
    maintainer_line = (
        f'<p class="tool-maintainers"><strong>Maintained by</strong> {_format_author_list(authors=maintainers)}</p>'
        if maintainers
        else ""
    )
    tag_html = "".join(f'<span>{_escape(value=tag)}</span>' for tag in tags[:4])
    tag_line = f'<div class="tool-keywords">{tag_html}</div>' if tag_html else ""
    tooltype = str(entry["tooltype"])
    status = str(entry["status"])
    status_chip = f'<span class="status-chip">{_escape(value=status.title())}</span>' if status else ""
    return f"""<article class="publication-card tool-card" {_card_attributes(entry=entry)}>
  <div class="card-year tool-meta"><span>{_escape(value=tooltype.title() or 'Tool')}</span><small>{_escape(value=status.title() or 'Status not specified')}</small></div>
  <div class="card-content">
    <div class="card-heading"><h3><a href="publications/{_escape(value=entry['filename'])}">{_escape(value=entry['title'])}</a></h3>{status_chip}</div>
    <p class="tool-summary">{_escape(value=summary)}</p>{maintainer_line}{_partner_line(entry=entry)}{tag_line}
  </div>
  <a class="card-arrow" href="publications/{_escape(value=entry['filename'])}" aria-label="View {_escape(value=entry['title'])}">{_icon(name='arrow')}</a>
</article>"""


def _person_initials(*, name: str) -> str:
    title_words = {"prof", "prof.", "dr", "dr.", "apl", "apl."}
    words = [word for word in name.split() if word.casefold() not in title_words]
    selected = words[-2:] if len(words) > 1 else words
    return "".join(word[0].upper() for word in selected if word) or "INF"


def _people(*, project_data: dict[str, object]) -> list[dict[str, object]]:
    people = project_data["people"] if isinstance(project_data["people"], list) else []
    return [person for person in people if isinstance(person, dict)]


def render_about_page(*, project_data: dict[str, object], project_name: str, asset_version: str) -> str:
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
    contact = str(project_data.get("contact", "")).strip()
    contact_html = f'<p class="contact-note">{_escape(value=contact)}</p>' if contact else ""
    page = PAGES_BY_SLUG["about"]
    body = f"""{_page_intro(page=page)}
<section class="about-section">
  <div class="section-heading"><div><span class="eyebrow">{_escape(value=project_data['title'])}</span><h2>{_escape(value=project_data['subtitle'])}</h2></div></div>
  <div class="about-grid">
    <div class="about-copy">{description_html}<div class="related-links">{link_html}</div>{source_link}</div>
    <aside class="research-areas"><span class="eyebrow">Research areas</span><div>{area_html}</div></aside>
  </div>
  <div class="services-grid">{"".join(service_cards)}</div>{contact_html}
</section>
"""
    return _page_shell(
        title=f"{page.label} · {project_name}",
        description=page.summary,
        body=body,
        asset_prefix="",
        asset_version=asset_version,
        project_name=project_name,
        active=page.slug,
    )


def render_people_page(*, project_data: dict[str, object], project_name: str, asset_version: str) -> str:
    role_groups: dict[str, list[dict[str, object]]] = {}
    for person in _people(project_data=project_data):
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
        people_groups.append(f'<div class="people-group"><h2>{_escape(value=role)}</h2><div class="people-grid">{"".join(cards)}</div></div>')
    page = PAGES_BY_SLUG["people"]
    body = f"""{_page_intro(page=page)}
<section class="people-section">
  {''.join(people_groups)}
</section>
"""
    return _page_shell(
        title=f"{page.label} · {project_name}",
        description=page.summary,
        body=body,
        asset_prefix="",
        asset_version=asset_version,
        project_name=project_name,
        active=page.slug,
    )


def render_index(
    *,
    entries: list[dict[str, object]],
    project_name: str,
    project_subtitle: str,
    asset_version: str,
    project_data: dict[str, object],
) -> str:
    panels: list[str] = []
    for number, page in enumerate(PAGES, start=1):
        if page.slug == "about":
            stat = "<span>Project overview</span>"
        elif page.slug == "people":
            stat = f'<span class="panel-stat"><strong>{len(_people(project_data=project_data))}</strong><span>Team members</span></span>'
        else:
            count = sum(page.category in entry["categories"] for entry in entries)
            stat = f'<span class="panel-stat"><strong>{count}</strong><span>{_escape(value=page.stat_label)}</span></span>'
        panels.append(
            f"""    <a class="section-panel" href="{page.filename}">
      <span class="panel-icon">{_icon(name=page.icon)}</span>
      <span class="panel-number">{number:02d}</span>
      <h2>{_escape(value=page.label)}</h2>
      <p>{_escape(value=page.summary)}</p>
      <span class="panel-footer">{stat}{_icon(name='arrow')}</span>
    </a>"""
        )
    panel_html = "\n".join(panels)
    body = f"""
<section class="hero">
  <div class="hero-copy">
    <div class="eyebrow">CRC 1629 · Negation in Language and Beyond</div>
    <h1>{_escape(value=project_subtitle)}</h1>
    <p>Tools, services, projects, and research outputs from the INF subproject, building sustainable infrastructure and methods for collaborative research on negation.</p>
  </div>
  <nav class="section-navigation" aria-label="Explore the INF website">
{panel_html}
  </nav>
</section>
"""
    return _page_shell(
        title=f"{project_name} · Catalogue",
        description="Tools, services, projects, publications, and collaborations of the NegLab CRC 1629 INF subproject.",
        body=body,
        asset_prefix="",
        asset_version=asset_version,
        project_name=project_name,
        active="home",
    )


def _filter_select(*, name: str, label: str, all_label: str, options: Iterable[tuple[str, str]], token: bool = False) -> str:
    option_html = "".join(f'<option value="{_escape(value=value)}">{_escape(value=text)}</option>' for value, text in options)
    mode = ' data-filter-mode="token"' if token else ""
    return f'<label><span class="sr-only">{_escape(value=label)}</span><select data-filter="{name}"{mode}><option value="">{_escape(value=all_label)}</option>{option_html}</select></label>'


def _category_filters(*, category: str, entries: list[dict[str, object]]) -> list[str]:
    def distinct(field: str) -> list[str]:
        return sorted({str(entry[field]) for entry in entries if entry[field]})

    years = sorted({str(entry["year"]) for entry in entries}, reverse=True)
    year_filter = _filter_select(name="year", label="Filter by year", all_label="All years", options=((year, year) for year in years))
    status_filter = _filter_select(
        name="status", label="Filter by status", all_label="All statuses", options=((value, value.title()) for value in distinct("status"))
    )
    if category == "tool":
        return [
            _filter_select(
                name="tooltype", label="Filter by tool type", all_label="All tool types", options=((value, value.title()) for value in distinct("tooltype"))
            ),
            status_filter,
        ]
    if category == "publication":
        pubtypes = sorted({(str(entry["pubtype"]), str(entry["pubtype_label"])) for entry in entries}, key=lambda item: item[1])
        return [year_filter, _filter_select(name="pubtype", label="Filter by publication type", all_label="All publication types", options=pubtypes)]
    if category == "collaboration":
        present = [other for other in CATEGORY_ORDER if other != "collaboration" and any(other in entry["categories"] for entry in entries)]
        partners = sorted({str(partner) for entry in entries for partner in entry["partners"]}, key=str.casefold)
        return [
            year_filter,
            _filter_select(
                name="partners",
                label="Filter by partner project",
                all_label="All partner projects",
                options=((partner, partner) for partner in partners),
                token=True,
            ),
            _filter_select(
                name="categories",
                label="Filter by category",
                all_label="All categories",
                options=((other, CATEGORY_PAGES[other].stat_label) for other in present),
                token=True,
            ),
        ]
    return [year_filter, status_filter]


def render_category_page(
    *,
    page: Page,
    entries: list[dict[str, object]],
    project_name: str,
    asset_version: str,
) -> str:
    category = str(page.category)
    members = [entry for entry in entries if category in entry["categories"]]
    if category == "tool":
        cards = "\n".join(_render_tool_card(entry=entry) for entry in members)
    elif category == "publication":
        cards = "\n".join(_render_catalogue_card(entry=entry, label=str(entry["pubtype_label"])) for entry in members)
    else:
        cards = "\n".join(_render_catalogue_card(entry=entry, label=str(entry["type_label"])) for entry in members)
    count_label = page.singular if len(members) == 1 else page.plural
    body = f"""{_page_intro(page=page)}
<section class="publication-section" data-catalogue>
  <div class="filters" role="search" aria-label="Filter {_escape(value=page.plural)}">
    <label class="search-field">{_icon(name='search')}<span class="sr-only">Search {_escape(value=page.plural)}</span><input data-search-input type="search" placeholder="Search {_escape(value=page.plural)} by title, author, venue, or tag…" autocomplete="off"></label>
    {''.join(_category_filters(category=category, entries=members))}
  </div>
  <div class="result-bar"><span data-result-count data-singular="{_escape(value=page.singular)}" data-plural="{_escape(value=page.plural)}">{len(members)} {_escape(value=count_label)}</span><button data-clear type="button" hidden>Clear filters</button></div>
  <div class="publication-list" data-list>{cards}</div>
  <div class="empty-state" data-empty{'' if not members else ' hidden'}><span>{_icon(name='search')}</span><h3>No {_escape(value=page.plural)} found</h3><p>Try another search or clear the filters.</p></div>
</section>
"""
    return _page_shell(
        title=f"{page.label} · {project_name}",
        description=page.summary,
        body=body,
        asset_prefix="",
        asset_version=asset_version,
        project_name=project_name,
        active=page.slug,
    )


def render_repository_link(*, url: str) -> str:
    if url:
        return f'<a class="button button-secondary" href="{_escape(value=url)}" rel="noopener noreferrer">{_icon(name="github")} Code &amp; archive</a>'
    return f'<span class="button button-secondary button-disabled" aria-disabled="true" title="No code or archive link has been added yet">{_icon(name="github")} Code &amp; archive</span>'


def _detail_rows(*, entry: dict[str, object]) -> str:
    institution = entry["institution"] if entry["institution"] != entry["venue"] else ""
    values = [
        ("Publication type", entry["pubtype_label"]),
        ("Tool type", str(entry["tooltype"]).title()),
        ("Status", str(entry["status"]).title()),
        ("Maintainer", ", ".join(str(maintainer) for maintainer in entry["maintainers"])),
        ("Collaborating projects", ", ".join(str(partner) for partner in entry["partners"])),
        ("Access", entry["access"]),
        ("Year", entry["year"]),
        ("Venue", entry["venue"]),
        ("Institution", institution),
        ("Volume", entry["volume"]),
        ("Issue / number", entry["number"]),
        ("Pages", entry["pages"]),
        ("Publisher", entry["publisher"]),
        ("Location", entry["address"]),
        ("DOI", entry["doi"]),
        ("License", entry["license"]),
        ("BibTeX key", entry["bib_key"]),
    ]
    return "".join(
        f'<div><dt>{_escape(value=label)}</dt><dd>{_escape(value=value)}</dd></div>' for label, value in values if value
    )


def render_detail(*, entry: dict[str, object], project_name: str, asset_version: str) -> str:
    authors = entry["authors"]
    maintainers = entry["maintainers"]
    tags = entry["tags"]
    categories = entry["categories"]
    primary = str(entry["primary_category"])
    primary_page = CATEGORY_PAGES[primary]
    title = str(entry["title"])
    subtitle = f'<p class="subtitle">{_escape(value=entry["subtitle"])}</p>' if entry["subtitle"] else ""
    is_tool = primary == "tool"

    venue_parts = [str(entry["venue"]) or (str(entry["tooltype"]).title() if is_tool else ""), str(entry["year"])]
    venue = f'<p class="detail-venue">{_escape(value=" · ".join(part for part in venue_parts if part))}</p>'
    status = f'<span class="status-chip">{_escape(value=str(entry["status"]).title())}</span>' if entry["status"] else ""
    if is_tool and maintainers:
        author_line = f'<p class="detail-authors"><strong>Maintained by</strong> {_format_author_list(authors=maintainers)}</p>'
        if authors:
            author_line += f'<p class="tool-authors"><strong>Developed by</strong> {_format_author_list(authors=authors)}</p>'
    else:
        author_line = f'<p class="detail-authors">{_format_author_list(authors=authors)}</p>' if authors else ""
        if maintainers:
            author_line += f'<p class="tool-authors"><strong>Maintained by</strong> {_format_author_list(authors=maintainers)}</p>'
    category_links = "".join(
        f'<a href="../{CATEGORY_PAGES[category].filename}">{_escape(value=CATEGORY_PAGES[category].label)}</a>' for category in categories
    )

    actions: list[str] = []
    if entry["url"]:
        action_label = {"tool": "Open tool", "publication": "View publication"}.get(primary, "Visit project")
        actions.append(f'<a class="button button-primary" href="{_escape(value=entry["url"])}" rel="noopener noreferrer">{_icon(name="external")} {action_label}</a>')
    if entry["documentation"]:
        actions.append(f'<a class="button button-secondary" href="{_escape(value=entry["documentation"])}" rel="noopener noreferrer">{_icon(name="book")} Documentation</a>')
    if entry["pdf"]:
        actions.append(f'<a class="button button-secondary" href="{_escape(value=entry["pdf"])}" rel="noopener noreferrer">{_icon(name="file")} PDF</a>')
    actions.append(render_repository_link(url=str(entry["projectlink"])))

    abstract = str(entry["abstract"])
    about_heading = {"tool": "About this tool", "publication": "Abstract"}.get(primary, "About this project")
    abstract_section = (
        f'<section class="paper-section"><h2>{about_heading}</h2><p class="abstract">{_escape(value=abstract)}</p></section>'
        if abstract
        else f'<section class="paper-section muted-section"><h2>{about_heading}</h2><p>No description is available in the bibliography.</p></section>'
    )
    tag_html = "".join(f'<span>{_escape(value=tag)}</span>' for tag in tags)
    tag_section = f'<section class="paper-section"><h2>Tags</h2><div class="keyword-list">{tag_html}</div></section>' if tags else ""
    related_html = "".join(
        f'<li><a href="{_escape(value=related["filename"])}">{_escape(value=related["title"])}</a><span>{_escape(value=related["type_label"])}</span></li>'
        for related in entry["related_entries"]
    )
    related_section = f'<section class="paper-section"><h2>Related entries</h2><ul class="related-list">{related_html}</ul></section>' if related_html else ""
    if entry["citation_bibtex"]:
        bibtex_heading, bibtex = "Cite (BibTeX)", str(entry["citation_bibtex"])
    else:
        bibtex_heading, bibtex = "BibTeX", str(entry["raw_bibtex"])
    type_icon = {"tool": "code", "publication": "book"}.get(primary, "folder")
    body = f"""
<div class="detail-back"><a href="../{primary_page.filename}">← Back to {_escape(value=primary_page.label)}</a></div>
<article class="paper">
  <header class="paper-header">
    <div class="paper-type">{_icon(name=type_icon)} {_escape(value=entry['type_label'])}{status}</div>
    <h1>{_escape(value=title)}</h1>{subtitle}
    {author_line}{venue}{_partner_line(entry=entry)}
    <nav class="category-links" aria-label="Listed in">{category_links}</nav>
    <div class="paper-actions">{''.join(actions)}</div>
  </header>
  <div class="paper-layout">
    <div>{abstract_section}{tag_section}{related_section}
      <section class="paper-section citation-section"><div class="section-title-row"><h2>{bibtex_heading}</h2><button class="copy-button" type="button" data-copy-bib>{_icon(name='copy')} Copy</button></div><pre><code id="bibtex-entry">{_escape(value=bibtex)}</code></pre></section>
    </div>
    <aside class="paper-facts"><h2>{_escape(value=CATEGORY_LABELS[primary])} details</h2><dl>{_detail_rows(entry=entry)}</dl></aside>
  </div>
</article>
"""
    page = _page_shell(
        title=f"{title} · {project_name}",
        description=abstract[:155] if abstract else f"{CATEGORY_LABELS[primary]} details for {title}.",
        body=body,
        asset_prefix="../",
        asset_version=asset_version,
        project_name=project_name,
        active=primary_page.slug,
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
    project_name: str,
    project_subtitle: str,
    project_data_path: Path,
    logo_path: Path,
    source_root: Path,
) -> dict[str, int]:
    """Validate parsed BibTeX entries and rebuild the complete site."""
    catalogue_entries = _sort_entries(entries=(_entry_to_catalogue_entry(entry=entry) for entry in entries))
    _link_related_entries(entries=catalogue_entries)
    project_data = load_inf_project_data(path=project_data_path)
    asset_version = _asset_version(source_root=source_root)
    if docs_dir.exists():
        if not docs_dir.is_dir():
            raise NotADirectoryError(f"Site output path is not a directory: {docs_dir}")
        shutil.rmtree(docs_dir)
    publication_dir = docs_dir / "publications"
    publication_dir.mkdir(parents=True)
    _write_assets(docs_dir=docs_dir, logo_path=logo_path, source_root=source_root)

    for entry in catalogue_entries:
        (publication_dir / str(entry["filename"])).write_text(
            render_detail(entry=entry, project_name=project_name, asset_version=asset_version),
            encoding="utf-8",
        )
    pages = {
        "index.html": render_index(
            entries=catalogue_entries,
            project_name=project_name,
            project_subtitle=project_subtitle,
            asset_version=asset_version,
            project_data=project_data,
        ),
        PAGES_BY_SLUG["about"].filename: render_about_page(project_data=project_data, project_name=project_name, asset_version=asset_version),
        PAGES_BY_SLUG["people"].filename: render_people_page(project_data=project_data, project_name=project_name, asset_version=asset_version),
    }
    for page in CATEGORY_PAGES.values():
        pages[page.filename] = render_category_page(
            page=page, entries=catalogue_entries, project_name=project_name, asset_version=asset_version
        )
    for filename, content in pages.items():
        (docs_dir / filename).write_text(content, encoding="utf-8")

    manifest = {
        "entries": [
            {
                "bib_key": entry["bib_key"],
                "filename": entry["filename"],
                "title": entry["title"],
                "year": entry["year"],
                "categories": entry["categories"],
            }
            for entry in catalogue_entries
        ]
    }
    (publication_dir / "index.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (docs_dir / ".nojekyll").touch()
    result = {"total": len(catalogue_entries)}
    for category in CATEGORY_ORDER:
        result[CATEGORY_PAGES[category].slug] = sum(category in entry["categories"] for entry in catalogue_entries)
    return result


def build_site(
    *,
    bib_path: Path,
    docs_dir: Path,
    project_name: str,
    project_subtitle: str,
    project_data_path: Path,
    logo_path: Path,
    source_root: Path,
) -> dict[str, int]:
    """Read one BibTeX file and rebuild the complete catalogue site."""
    return generate_site_from_entries(
        entries=read_bibtex_file(path=bib_path),
        docs_dir=docs_dir,
        project_name=project_name,
        project_subtitle=project_subtitle,
        project_data_path=project_data_path,
        logo_path=logo_path,
        source_root=source_root,
    )


def _argument_parser(
    *,
    default_docs_dir: Path,
    default_bib_path: Path,
    default_project_data_path: Path,
    default_logo_path: Path,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild the GitHub Pages catalogue from one BibTeX file and the INF project JSON.")
    parser.add_argument("bib_file", nargs="?", type=Path, default=default_bib_path, help=f"authoritative BibTeX input (default: {default_bib_path})")
    parser.add_argument("--docs-dir", type=Path, default=default_docs_dir, help=f"site output directory (default: {default_docs_dir})")
    parser.add_argument("--project-data", type=Path, default=default_project_data_path, help=f"editable INF homepage JSON (default: {default_project_data_path})")
    parser.add_argument("--logo", type=Path, default=default_logo_path, help=f"INF logo SVG (default: {default_logo_path})")
    parser.add_argument("--project-name", default="NegLab INF", help="short project name shown in the site header")
    parser.add_argument("--project-subtitle", default="Infrastructure for research on negation", help="main heading shown on the home page")
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
    result = build_site(
        bib_path=arguments.bib_file,
        docs_dir=arguments.docs_dir,
        project_name=arguments.project_name,
        project_subtitle=arguments.project_subtitle,
        project_data_path=arguments.project_data,
        logo_path=arguments.logo,
        source_root=Path(__file__).resolve().parent,
    )
    counts = ", ".join(f"{result[page.slug]} {page.slug}" for page in CATEGORY_PAGES.values())
    print(f"Rebuilt site from {arguments.bib_file}: {result['total']} catalogue entries ({counts}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=None))
