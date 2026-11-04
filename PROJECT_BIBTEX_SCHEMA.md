# NegLab INF `@project` BibTeX schema

The catalogue uses a single BibTeX entry type, `@project`, for every tool,
project, publication, and collaboration. `@project` is a NegLab INF catalogue
extension rather than a standard BibTeX type. All entries live in
`data/neglab-inf.bib`. Any other entry type (`@article`, `@tool`, …) stops the
build with an error.

## Categories: the `keywords` field

`keywords` is a comma- or semicolon-separated list of **catalogue categories**.
It decides on which website tabs the entry appears:

| Category | Tab | Use for |
| --- | --- | --- |
| `tool` | Tools & Services | Reusable software, hosted services, infrastructure, and workflows INF makes available. |
| `project` | Projects | Research, development, annotation, or infrastructure activities carried out by INF. |
| `publication` | Publications | Articles, conference papers, reports, and other citable outputs. |
| `collaboration` | Collaborations | Work done together with another CRC 1629 project. |

An entry may carry several categories, such as `{tool, project}` for a hosted
service that is also an INF activity, or `{project, collaboration}` for joint
work. It is then listed on every matching tab but has a single detail page.
The **first** category is the entry's primary category: it determines the
back link, the label, and the main action button on the detail page. Values
are case-insensitive, and plural forms (`tools`) are accepted. At least one
category is required, and unknown values stop the build.

Topical search terms do **not** belong in `keywords`; put them in `tags`.

## Example

```bibtex
@project{INF:ExampleService,
  keywords      = {tool, project, collaboration},
  collaboration = {B01, C05},
  name          = {Example Service},
  subtitle      = {A reusable service for collaborative research},
  author        = {Doe, Jane and M{\"u}ller, Max},
  maintainer    = {Doe, Jane},
  year          = {2026},
  abstract      = {Example Service provides a reusable workflow for processing
                   and sharing research data.},
  tooltype      = {service},
  status        = {active},
  access        = {CRC members},
  url           = {https://example.org/service},
  projectlink   = {https://github.com/example/service},
  documentation = {https://example.org/service/docs},
  license       = {MIT},
  tags          = {research data, workflow},
  related       = {Doe:2026}
}

@project{Doe:2026,
  keywords      = {publication, collaboration},
  collaboration = {A02},
  pubtype       = {inproceedings},
  title     = {A Useful Result},
  author    = {Doe, Jane},
  booktitle = {Proceedings of the Example Conference},
  year      = {2026},
  doi       = {10.1000/example},
  tags      = {negation, neglab}
}
```

## Fields

### All entries

| Field | Requirement | Meaning |
| --- | --- | --- |
| BibTeX key | Required | Stable unique identifier; determines the detail-page URL. Do not change it after publication. |
| `keywords` | Required | Catalogue categories, as described above. |
| `title` or `name` | Required | Display name. `title` takes precedence if both fields are present. |
| `abstract` | Recommended | Plain-language description shown as the main page content. |
| `author` | Recommended | Authors or contributors in normal BibTeX `and`-separated form. `editor` is used if `author` is missing. |
| `year` | Recommended | Publication, release, or start year. Entries without it are shown as undated. |
| `subtitle` | Optional | Short line shown below the title. |
| `status` | Optional | Lifecycle chip, such as `active`, `closed`, or `retired`. If absent, `note` (then `pubstate`) is shown instead. |
| `tags` | Optional | Comma- or semicolon-separated topical terms used for display and search. |
| `related` | Optional | Comma- or semicolon-separated keys of other catalogue entries. Links are shown in both directions, and unknown keys stop the build. |
| `url` | Recommended | Primary landing page (“Open tool”, “Visit project”, or “View publication”). Falls back to the DOI. |
| `projectlink` | Optional | Code repository or archive (“Code & archive”). |
| `documentation` | Optional | Dedicated documentation (“Documentation”). |
| `pdf` | Optional | Direct PDF link. |
| `doi` | Optional | DOI, with or without the `https://doi.org/` prefix. |
| `institution` | Optional | Responsible or collaborating institution. |

### Collaboration fields

| Field | Meaning |
| --- | --- |
| `collaboration` | Comma- or semicolon-separated list of the CRC projects INF collaborated with, e.g. `{A02, C05}`. Project codes are shown in upper case. Required whenever `keywords` contains `collaboration`. |

The partner projects appear on cards and detail pages ("In collaboration
with …"), are searchable, and can be filtered on the Collaborations tab.

### Tool fields

| Field | Meaning |
| --- | --- |
| `tooltype` | `software`, `service`, `infrastructure`, or `workflow`. |
| `maintainer` | Person, people, or group maintaining the tool (`and`-separated). |
| `access` | Who can use the tool and under which conditions. |
| `license` | Software or data license. |

Recommended `status` values for tools are `active`, `beta`, `maintenance`,
and `retired`.

### Publication fields

| Field | Meaning |
| --- | --- |
| `pubtype` | Standard BibTeX type to cite the entry with (`article`, `inproceedings`, `techreport`, `incollection`, `phdthesis`, …). Defaults to `misc`. |
| `journal`, `booktitle`, `volume`, `number`, `pages`, `publisher`, `address`, `editor`, `series`, `isbn`, `issn`, `month`, `note`, … | Any standard BibTeX fields. |

Detail pages of publications show a **citation BibTeX** generated from the
entry. It uses `pubtype` as its entry type, drops the catalogue-only fields
(`keywords`, `collaboration`, `pubtype`, `name`, `maintainer`, `tooltype`, `status`, `access`,
`documentation`, `projectlink`, `related`, `license`), and exports `tags` as
standard `keywords`. Other entries show their catalogue BibTeX unchanged.

## Conventions

- Describe one thing once. If a project and its hosted tool are the same
  thing, use one entry with `keywords = {tool, project}`. If a tool and a
  paper about it are different things, keep two entries and connect them with
  `related`.
- Prefer stable keys without a year for tools, such as `INF:DUUI`.
- Store all links as absolute `https://` URLs. Invalid links are dropped.
- Keep `abstract` suitable for public display and avoid LaTeX layout commands.
- Rebuild the website after every edit: `python3 src/build_publications.py`.
