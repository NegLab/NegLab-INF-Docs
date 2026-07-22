# NegLab INF project catalogue

Static GitHub Pages catalogue for projects and publications of the INF
subproject of CRC 1629 NegLaB. The site is generated from an authoritative
BibTeX database using dependency-free Python.

## Repository workflow

`data/neglab-inf.bib` is the database and the single source of truth for the
website. Files passed on the command line are import files: they are merged
into the database by BibTeX key, and the site under `docs/` is then generated
from the complete database.

Do not edit generated HTML to change metadata or links. Make the change in an
import file or use `add_publication_link.py`, then regenerate.

### First import and adding new entries

The database is created as an empty file when it does not exist. Import one or
more BibTeX files from the repository root:

```bash
python3 src/build_publications.py incoming/projects.bib
python3 src/build_publications.py incoming/projects.bib incoming/publications.bib
```

New keys are appended to `data/neglab-inf.bib`. If an imported key is already
present, the database version is retained by default. Pages whose generated
content has not changed are left untouched.

### Updating existing entries

Use `--update` to replace database entries with matching entries from the
import file. The entire entry associated with that BibTeX key is replaced:

```bash
python3 src/build_publications.py --update incoming/corrections.bib
```

Entries that are not present in the import file remain unchanged. New entries
are still added normally.

### Full rebuild

`--full-rebuild` is intentionally destructive: it empties the authoritative
database first, imports only the supplied files, removes generated project
pages that are no longer represented, and rebuilds every page.

```bash
python3 src/build_publications.py \
  --full-rebuild \
  incoming/complete-export.bib
```

Any database entry or `projectlink` not included in the supplied complete
export is removed. Commit or back up `data/neglab-inf.bib` before using this
option when its contents are not reproducible elsewhere.

To regenerate the website from the database without importing anything:

```bash
python3 src/build_publications.py
```

Useful path overrides are available for testing or alternate deployments:

```bash
python3 src/build_publications.py \
  --database /path/to/database.bib \
  --docs-dir /path/to/site \
  /path/to/import.bib
```

## Supported entries

Standard BibTeX publication types such as `@article`, `@inproceedings`, and
`@techreport` are supported. The catalogue also supports the project-specific
`@project` type for software, datasets, services, repositories, and ongoing or
unpublished work.

Project entries use `name` or `title` for their heading and can provide an
`abstract` for the project description. See
[PROJECT_BIBTEX_SCHEMA.md](PROJECT_BIBTEX_SCHEMA.md) for the complete proposed
schema and an example.

Every supported entry receives a stable, collision-resistant filename under
`docs/publications/`, derived from its BibTeX key. Duplicate keys inside a
single import file stop the import with an error.

## Code and archive links

Store a GitHub, GitLab, Zenodo, OSF, or other archival URL by its exact BibTeX
key:

```bash
python3 src/add_publication_link.py \
  'Hammerla:et:al:2025b' \
  'https://github.com/example/d-neg'
```

The tool writes or replaces the `projectlink` field directly in
`data/neglab-inf.bib` and then regenerates the documentation. It never patches
the generated HTML directly.

Remove the field and restore the empty website placeholder with:

```bash
python3 src/add_publication_link.py --remove 'Hammerla:et:al:2025b'
```

An imported entry that already contains `projectlink` is handled in exactly the
same way. The distinction between link fields is:

- `url`: primary project or publication landing page, shown as “Visit project”
  or “View publication”.
- `projectlink`: code repository or archival record, shown as “Code & archive”.
- `pdf`: direct PDF link where one exists.

## Generated website

The generation process writes:

- `docs/index.html`: searchable and filterable project catalogue.
- `docs/publications/*.html`: one page per BibTeX key.
- `docs/publications/index.json`: mapping from keys to generated filenames.
- `docs/assets/`: stylesheet and JavaScript used by GitHub Pages.

Asset URLs contain a content hash. This prevents GitHub Pages or the browser
from retaining an older color scheme after CSS changes.

Preview the site locally:

```bash
python3 -m http.server 8000 --directory docs
```

Then open <http://localhost:8000/>.

## Tests

Run the importer, database, link, and rendering tests with:

```bash
python3 -m unittest discover -s tests -v
```

## GitHub Pages

In the repository settings, select **Deploy from a branch**, choose the `main`
branch, and use `/docs` as the folder. Commit the authoritative database,
generator changes, and regenerated `docs/` output together.
