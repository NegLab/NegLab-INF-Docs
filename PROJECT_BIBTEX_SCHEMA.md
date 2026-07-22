# Proposed `@project` BibTeX schema

`@project` is a NegLab INF catalogue extension rather than a standard BibTeX
entry type. It represents software, datasets, services, repositories, research
infrastructure, and unpublished or ongoing projects.

## Example

```bibtex
@project{INF:NegationExplorer:2026,
  name        = {Negation Data Explorer},
  subtitle    = {Interactive access to multilingual negation annotations},
  author      = {Doe, Jane and M{\"u}ller, Max},
  year        = {2026},
  abstract    = {A web application for exploring, comparing, and exporting
                 multilingual negation annotations produced by the INF
                 subproject.},
  url         = {https://example.org/negation-explorer},
  projectlink = {https://github.com/example/negation-explorer},
  keywords    = {negation, dataset, software, multilingual},
  note        = {active}
}
```

## Fields

| Field | Status | Meaning |
| --- | --- | --- |
| BibTeX key | Required | Stable unique identifier used to derive the page filename. Do not change it after publication. |
| `name` or `title` | Required | Human-readable project name. `title` takes precedence when both are present. |
| `abstract` | Required | Plain-language description displayed as the main project-page content. |
| `author` | Recommended | Contributors in normal BibTeX `and`-separated form. Both `Last, First` and `First Last` are accepted. |
| `year` | Recommended | Start, release, or principal catalogue year. Entries without it are shown as undated. |
| `url` | Recommended | Primary project homepage, service, documentation, or publication landing page. |
| `projectlink` | Recommended | Source-code repository or persistent archival record. Edit this field manually in the BibTeX input. |
| `keywords` | Recommended | Comma- or semicolon-separated terms used for display and search. |
| `subtitle` | Optional | Short explanatory subtitle displayed below the project name. |
| `note` | Optional | Short lifecycle label such as `active`, `beta`, `archived`, or `forthcoming`. |
| `doi` | Optional | DOI without, or with, a `https://doi.org/` prefix. |
| `pdf` | Optional | Absolute URL for a directly downloadable project report or paper. |
| `institution` | Optional | Responsible institution; displayed as the venue when present. |

## Conventions

- Use a stable, descriptive BibTeX key. Colons are allowed; for example,
  `INF:ToolName:2026`.
- Store URLs as absolute `https://` links.
- Keep `abstract` suitable for public display and avoid LaTeX layout commands.
- Use `url` for the project’s main destination and `projectlink` specifically
  for source code or an archival record.
- Treat the BibTeX file as the authoritative source and rebuild the website
  after every manual edit.
