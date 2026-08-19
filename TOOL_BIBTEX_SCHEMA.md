# NegLab INF `@tool` BibTeX schema

`@tool` is a NegLab INF-specific catalogue extension, analogous to `@project`.
It represents a reusable software system, hosted service, infrastructure
resource, or reusable workflow that INF makes available to CRC members or the
wider research community.

Projects and tools are separate catalogue objects. A research, development,
annotation, or collaboration activity belongs in `@project`, even when that
activity produces a tool. The reusable result may be described separately as
an `@tool` entry and connected to its project or publications with `related`.

## Example

```bibtex
@tool{INF:ExampleTool,
  name          = {Example Tool},
  subtitle      = {A reusable service for collaborative research},
  author        = {Doe, Jane and M{\"u}ller, Max},
  maintainer    = {Doe, Jane},
  year          = {2026},
  abstract      = {Example Tool provides a reusable workflow for processing
                   and sharing research data.},
  tooltype      = {software},
  url           = {https://example.org/tool},
  projectlink   = {https://github.com/example/tool},
  documentation = {https://example.org/tool/docs},
  access        = {Public},
  status        = {active},
  keywords      = {research data, workflow, collaboration},
  institution   = {Example University},
  license       = {MIT},
  related       = {Doe:2026}
}
```

## Fields

| Field | Requirement | Meaning |
| --- | --- | --- |
| BibTeX key | Required | Stable unique identifier used to derive the detail-page filename. |
| `name` or `title` | Required | Display name. `title` takes precedence if both fields are present. |
| `abstract` | Required | Plain-language description of what the tool provides. |
| `tooltype` | Required | Tool category from the controlled vocabulary below. |
| `maintainer` | Recommended | INF person or people, or the responsible group, maintaining or providing the tool. Use normal BibTeX `and` separation for multiple maintainers. |
| `author` | Optional | Original developers or authors where relevant, in normal BibTeX name format. |
| `year` | Recommended | First release or first provision through INF. |
| `url` | Recommended | Main user-facing tool, service, or landing-page URL. |
| `projectlink` | Recommended | Source repository or persistent archive. |
| `documentation` | Optional | Dedicated documentation URL. |
| `access` | Recommended | Who can use the tool and any access conditions. |
| `status` | Recommended | Lifecycle state from the controlled vocabulary below. |
| `keywords` | Recommended | Comma- or semicolon-separated search and filter terms. |
| `institution` | Optional | Responsible institution or group. |
| `license` | Optional | Software or data license. |
| `related` | Optional | Comma- or semicolon-separated BibTeX keys of related project or publication entries. |
| `subtitle` | Optional | Short description shown below the tool name. |

## Controlled vocabularies

Use one of these values for `tooltype`:

- `software`
- `service`
- `infrastructure`
- `workflow`

Use one of these values for `status`:

- `active`
- `beta`
- `maintenance`
- `retired`

New tools should use `status` rather than `note`. During migration, the site
generator can use `note` as a fallback when a tool has no `status` field.

## Conventions

- Prefer a stable tool key without a year, such as `INF:DUUI`. The `year`
  field records the first release or provision date while the key identifies
  the persistent catalogue entity.
- Do not rename existing keys merely to remove a year; keys determine existing
  stable page filenames.
- Store `url`, `projectlink`, and `documentation` as absolute HTTP or HTTPS
  URLs.
- Keep `abstract` suitable for public display and avoid LaTeX layout commands.
- Use `@tool` for all four tool categories. Do not introduce `@software`,
  `@service`, or `@infrastructure` entry types.
- Treat `data/neglab-inf.bib` as the authoritative catalogue and rebuild the
  website after every manual edit.
