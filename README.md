# NegLab INF projects

Static GitHub Pages catalogue for projects and publications of the INF
subproject of CRC 1629 NegLaB. The site is generated from BibTeX and has no
runtime or build dependencies.

## Generate the site

From the repository root, import one or more bibliography files:

```bash
python3 src/build_publications.py data/ttlab-base-neglab.bib
```

The normal import is incremental: an existing project page is not overwritten.
The main index and catalogue manifest are refreshed each time.
Use a full rebuild when BibTeX metadata has changed or entries were removed:

```bash
python3 src/build_publications.py --full-rebuild data/ttlab-base-neglab.bib
```

Every supported project or publication receives a stable, collision-resistant
filename in `docs/publications/`, derived from its BibTeX key. `@project`
entries are supported alongside standard publication types. A project can use
`name` or `title`, and can include `abstract`, `author`, `year`, `url`, and
`keywords` fields. Duplicate keys stop the build with an error.

To preview locally:

```bash
python3 -m http.server 8000 --directory docs
```

Then open <http://localhost:8000/>.

## Add a code or archive link

Use the exact BibTeX key and an absolute GitHub or archival-service URL:

```bash
python3 src/add_publication_link.py \
  'Hammerla:et:al:2025b' \
  'https://github.com/example/d-neg'
```

Remove a link with:

```bash
python3 src/add_publication_link.py --remove 'Hammerla:et:al:2025b'
```

Mappings are saved in `docs/publications/links.json`, so links are restored when
`--full-rebuild` is used. The generated `index.json` provides the unique mapping
between BibTeX keys and project-page filenames.

## GitHub Pages

In the repository settings, select **Deploy from a branch**, choose the `main`
branch, and use `/docs` as the folder. Commit changes under `docs/` whenever the
bibliography or project links are updated.
