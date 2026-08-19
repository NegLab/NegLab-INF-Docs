# NegLab INF catalogue

Static GitHub Pages catalogue for tools, projects, and publications of the INF
subproject of CRC 1629 NegLaB. The complete site is generated with
dependency-free Python from two manually maintained content files and one logo
asset:

- `data/neglab-inf.bib` is the single authoritative catalogue source for
  tools, projects, publications, and their links.
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

## Editing tools, projects, and publications

Edit `data/neglab-inf.bib` directly. Standard BibTeX publication types such as
`@article`, `@inproceedings`, and `@techreport` are supported. The catalogue
also accepts two NegLab INF-specific entry types:

- `@tool` for reusable software, hosted services, infrastructure, and
  workflows made available by INF.
- `@project` for research, development, annotation, and collaboration
  activities carried out by INF.

The categories are additive rather than mutually exclusive. If a project or
publication also has a reusable tool, keep the original entry unchanged and
add a separate `@tool` entry with its own unique key. Use the tool’s `related`
field to reference the project or publication key. The two records then appear
in their respective homepage catalogues and receive separate detail pages.

All three categories live in the same `data/neglab-inf.bib` file. Do not create
a separate tool catalogue or data file. See
[TOOL_BIBTEX_SCHEMA.md](TOOL_BIBTEX_SCHEMA.md) and
[PROJECT_BIBTEX_SCHEMA.md](PROJECT_BIBTEX_SCHEMA.md) for their complete
schemas and the distinction between them.

Each entry must have a unique BibTeX key. That key determines its stable,
collision-resistant filename under `docs/publications/`. Duplicate keys stop
the build with an error.

For code or archive links, manually add a `projectlink` field to the entry:

```bibtex
projectlink = {https://github.com/example/project},
```

The link fields have distinct uses:

- `url`: primary tool, project, or publication landing page, shown as “Open
  tool”, “Visit project”, or “View publication”.
- `projectlink`: code repository or archival record, shown as “Code & archive”.
- `documentation`: dedicated tool documentation, shown as “Documentation” on
  `@tool` detail pages.
- `pdf`: direct PDF link.

If `projectlink` is absent, the detail page displays an empty disabled
placeholder.

After adding or editing a tool, project, or publication, rebuild in exactly the
same way:

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

- `docs/index.html`: INF information, people, category statistics, a searchable
  Tools & Services catalogue, and a separate searchable Projects &
  Publications catalogue.
- `docs/publications/*.html`: one detail page per supported BibTeX entry.
- `docs/publications/index.json`: mapping from BibTeX keys to generated files.
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
