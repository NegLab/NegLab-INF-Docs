# NegLab INF catalogue

Static GitHub Pages catalogue for tools, projects, publications, and
collaborations of the INF subproject of CRC 1629 NegLaB. The complete site is generated with
dependency-free Python from two manually maintained content files and one logo
asset:

- `data/neglab-inf.bib` is the single authoritative catalogue source for
  tools, projects, publications, collaborations, and their links.
- `data/inf-project.json` contains the INF description, services, research
  areas, related links, contact text, and people.
- `data/inf_logo.svg` is retained as the INF visual-identity source and defines
  the blue and pink site palette; the homepage itself uses text branding.

The generator only reads these inputs. It never edits or merges BibTeX data.
Everything under `docs/` is generated output and is replaced on every build.

## Rebuilding the website

From the repository root, run:

```bash
python3 src/build_publications.py
```

This uses `data/neglab-inf.bib` and `data/inf-project.json`, deletes the
previous generated site under `docs/`, and writes the complete site again.

To build from a different BibTeX file or homepage JSON:

```bash
python3 src/build_publications.py /path/to/projects.bib \
  --project-data /path/to/inf-project.json
```

An alternate output directory can be useful for previews:

```bash
python3 src/build_publications.py --docs-dir /tmp/neglab-inf-preview
```

The selected output directory is replaced completely during the build.

## Editing tools, projects, publications, and collaborations

Edit `data/neglab-inf.bib` directly. Every entry uses the same BibTeX type,
`@project`. Its `keywords` field lists the catalogue categories that decide
on which website tabs the entry appears:

```bibtex
@project{INF:ExampleService,
  keywords      = {tool, project, collaboration},
  collaboration = {B01},
  name        = {Example Service},
  abstract    = {What the service provides.},
  tooltype    = {service},
  url         = {https://example.org/service},
  projectlink = {https://github.com/example/service},
  tags        = {annotation, hosting}
}
```

- `tool` → **Tools & Services**
- `project` → **Projects**
- `publication` → **Publications** (also set `pubtype`, e.g. `article` or
  `inproceedings`)
- `collaboration` → **Collaborations** (joint work with other CRC projects;
  also add `collaboration = {A02, C05}` listing the partner projects)

An entry may list several categories. It then appears on every matching tab
but keeps a single detail page. The first category is the primary one, which
sets the back link and the label on that page. Topical search terms go in
`tags`, not in `keywords`. Other entry types, unknown categories, duplicate
keys, and `related` keys that do not exist all stop the build with an error.

See [PROJECT_BIBTEX_SCHEMA.md](PROJECT_BIBTEX_SCHEMA.md) for all fields.

Each entry's BibTeX key determines its stable, collision-resistant filename
under `docs/publications/`, so do not rename published keys.

The link fields have distinct uses:

- `url`: primary landing page, shown as “Open tool”, “Visit project”, or
  “View publication”.
- `projectlink`: code repository or archival record, shown as “Code & archive”.
  If it is absent, the detail page displays a disabled placeholder.
- `documentation`: dedicated documentation, shown as “Documentation”.
- `pdf`: direct PDF link.

Publication detail pages offer a standard citation BibTeX generated from the
entry, using `pubtype` as the entry type and leaving out catalogue-only
fields.

After adding or editing an entry, rebuild:

```bash
python3 src/build_publications.py
```

## Editing the homepage and people

Edit `data/inf-project.json` directly. Each person is represented by an object:

```json
{
  "name": "Example Person",
  "role": "Scientific Staff",
  "affiliation": "Goethe University Frankfurt",
  "profile_url": "https://example.org/profile"
}
```

Change `role` to regroup someone, append an object to add a person, or remove
the object to remove them. `affiliation` and `profile_url` may be empty.
Descriptions are arrays of paragraphs; service groups contain a `name` and an
`items` array.

After any BibTeX or JSON edit, run the normal build command again.

## Generated website

The build writes:

- `docs/index.html`: home page with one panel per tab, including counts.
- `docs/about.html`: INF description, research areas, services, and contact.
- `docs/people.html`: the INF team, grouped by role.
- `docs/tools.html`, `docs/projects.html`, `docs/publications.html`,
  `docs/collaborations.html`: searchable, filterable lists of the entries in
  each category.
- `docs/publications/*.html`: one detail page per BibTeX entry.
- `docs/publications/index.json`: mapping from BibTeX keys to generated files
  and categories.
- `docs/assets/`: the stylesheet, JavaScript, and copied visual-identity asset
  used by GitHub Pages.
- `docs/.nojekyll`: disables unnecessary Jekyll processing.

Asset URLs contain a content hash so browsers and GitHub Pages do not retain an
older stylesheet after a rebuild.

Preview the generated site locally:

```bash
python3 -m http.server 8000 --directory docs
```

Then open <http://localhost:8000/>.

## Tests

Run the parser and site-generation tests with:

```bash
python3 -m unittest discover -s tests -v
```

## GitHub Pages

In the repository settings, select **Deploy from a branch**, choose the `main`
branch, and use `/docs` as the folder. Commit both manually maintained input
files, generator changes, and the regenerated `docs/` output.
