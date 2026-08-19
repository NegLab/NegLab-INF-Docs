# Proposed `@project` BibTeX schema

`@project` is a NegLab INF catalogue extension rather than a standard BibTeX
entry type. It represents a research, development, annotation, or collaboration
activity carried out by INF, possibly together with another CRC project.

Reusable software, hosted services, infrastructure resources, and reusable
workflows belong in `@tool`; see
[TOOL_BIBTEX_SCHEMA.md](TOOL_BIBTEX_SCHEMA.md). A project may produce a tool,
but the activity and the reusable result remain separate catalogue objects.

## Example

```bibtex
@project{INF:ScopeAnnotation:2026,
  name        = {Scope Annotation Study},
  subtitle    = {Developing annotations for German scope relations},
  author      = {Doe, Jane and M{\"u}ller, Max},
  year        = {2026},
  abstract    = {A collaborative activity to define an annotation scheme,
                 prepare source data, coordinate annotation, and validate the
                 resulting research dataset.},
  url         = {https://example.org/scope-annotation},
  keywords    = {negation, annotation, scope, German},
  note        = {ongoing}
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
| `url` | Recommended | Primary project or collaboration landing page. |
| `projectlink` | Optional | Persistent archive or repository for project-specific materials. Edit this field manually in the BibTeX input. |
| `keywords` | Recommended | Comma- or semicolon-separated terms used for display and search. |
| `subtitle` | Optional | Short explanatory subtitle displayed below the project name. |
| `note` | Optional | Short lifecycle label such as `active`, `beta`, `archived`, or `forthcoming`. |
| `doi` | Optional | DOI without, or with, a `https://doi.org/` prefix. |
| `pdf` | Optional | Absolute URL for a directly downloadable project report or paper. |
| `institution` | Optional | Responsible or collaborating institution; displayed as the venue when present. |

## Conventions

- Use a stable, descriptive BibTeX key. Colons are allowed; for example,
  `INF:ScopeAnnotation:2026`.
- Store URLs as absolute `https://` links.
- Keep `abstract` suitable for public display and avoid LaTeX layout commands.
- Use `url` for the project’s main destination and `projectlink` for a
  persistent archive or repository of project-specific materials.
- Treat the BibTeX file as the authoritative source and rebuild the website
  after every manual edit.
