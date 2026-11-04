from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from build_publications import build_site, parse_bibtex, parse_categories

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
CATALOGUE_PATH = REPOSITORY_ROOT / "data/neglab-inf.bib"
TAB_PAGES = ("about.html", "people.html", "tools.html", "projects.html", "publications.html", "collaborations.html")


class PublicationToolTests(unittest.TestCase):
    def _source_root(self, *, root: Path) -> Path:
        source_root = root / "src"
        assets = source_root / "site_assets"
        assets.mkdir(parents=True, exist_ok=True)
        for name in ("site.css", "site.js"):
            (assets / name).write_text((REPOSITORY_ROOT / "src/site_assets" / name).read_text(encoding="utf-8"), encoding="utf-8")
        return source_root

    def _write_bibliography(self, *, root: Path) -> Path:
        bib_path = root / "data/projects.bib"
        bib_path.parent.mkdir(parents=True)
        bib_path.write_text(
            """@project{Doe:2026,
  keywords = {publication, collaboration},
  collaboration = {a02, Romance Lab},
  pubtype = {article},
  title = {{A} useful result},
  author = {Doe, Jane and M{\\\"u}ller, Max},
  journal = {Journal of Tests},
  year = {2026},
  doi = {10.1000/example},
  tags = {negation; infrastructure},
  abstract = {An abstract with {nested braces}.}
}

@project{Repository:2026,
  keywords = {project},
  name = {Negation Data Explorer},
  author = {Doe, Jane},
  year = {2026},
  url = {https://github.com/example/explorer},
  projectlink = {https://github.com/example/explorer-source},
  abstract = {A repository for exploring negation data.},
  tags = {software, data},
  status = {active}
}

@project{Example:Tool,
  keywords = {tool, project},
  name = {Example Tool},
  subtitle = {A reusable test service},
  author = {Roe, Richard},
  maintainer = {Doe, Jane},
  year = {2026},
  tooltype = {software},
  status = {active},
  access = {Public},
  url = {https://example.org/tool},
  documentation = {https://example.org/docs},
  projectlink = {https://github.com/example/tool},
  abstract = {Example reusable tool.},
  tags = {testing, reusable software},
  license = {MIT},
  related = {Doe:2026}
}
""",
            encoding="utf-8",
        )
        return bib_path

    def _write_project_data(self, *, root: Path) -> Path:
        path = root / "data/inf-project.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "source": {"url": "https://www.neglab.de/projects/inf/"},
                    "title": "INF",
                    "subtitle": "Scientific services and data management",
                    "description": ["Editable project description."],
                    "services": [{"name": "Consulting", "items": ["Data management"]}],
                    "research_areas": ["Natural language processing"],
                    "related_links": [],
                    "contact": "Contact the INF team.",
                    "people": [
                        {"name": "Jane Doe", "role": "Project Leader", "affiliation": "Test University", "profile_url": "https://example.org/jane"},
                        {"name": "Max Müller", "role": "Scientific Staff", "affiliation": "", "profile_url": ""},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def _build(self, *, root: Path, bib_path: Path) -> dict[str, int]:
        return build_site(
            bib_path=bib_path,
            docs_dir=root / "docs",
            project_name="Test INF",
            project_subtitle="Test projects",
            project_data_path=self._write_project_data(root=root),
            logo_path=REPOSITORY_ROOT / "data/inf_logo.svg",
            source_root=self._source_root(root=root),
        )

    def _build_with_text(self, *, text: str) -> dict[str, int]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bib_path = root / "input.bib"
            bib_path.write_text(text, encoding="utf-8")
            return self._build(root=root, bib_path=bib_path)

    def _page(self, *, root: Path, bib_key: str) -> str:
        manifest = json.loads((root / "docs/publications/index.json").read_text(encoding="utf-8"))
        item = next(item for item in manifest["entries"] if item["bib_key"] == bib_key)
        return (root / "docs/publications" / item["filename"]).read_text(encoding="utf-8")

    def test_parser_handles_nested_braces_and_latex_names(self) -> None:
        entries = parse_bibtex(
            text='@project{key, title={{Nested} title}, author={M{\\\"u}ller, Max}}',
            source="memory",
        )
        self.assertEqual(entries[0]["bib_key"], "key")
        self.assertEqual(entries[0]["fields"]["title"], "{Nested} title")

    def test_categories_are_read_from_keywords(self) -> None:
        self.assertEqual(parse_categories(bib_key="k", value="Tool, projects; tool"), ["tool", "project"])
        with self.assertRaisesRegex(ValueError, "unknown category 'software'"):
            parse_categories(bib_key="k", value="tool, software")
        with self.assertRaisesRegex(ValueError, "no categories"):
            parse_categories(bib_key="k", value="")

    def test_only_project_entries_are_accepted(self) -> None:
        with self.assertRaisesRegex(ValueError, "uses @article"):
            self._build_with_text(text="@article{Old:2025, title={Old style}, keywords={publication}}")

    def test_unknown_related_keys_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown related key 'Missing'"):
            self._build_with_text(text="@project{One, name={One}, keywords={project}, related={Missing}}")

    def test_build_writes_one_page_per_tab(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bibliography = self._write_bibliography(root=root)
            project_data = self._write_project_data(root=root)
            bib_before = bibliography.read_bytes()
            json_before = project_data.read_bytes()

            result = self._build(root=root, bib_path=bibliography)

            self.assertEqual(result, {"total": 3, "tools": 1, "projects": 2, "publications": 1, "collaborations": 1})
            self.assertEqual(bibliography.read_bytes(), bib_before)
            self.assertEqual(project_data.read_bytes(), json_before)
            self.assertTrue((root / "docs/assets/inf_logo.svg").is_file())

            index = (root / "docs/index.html").read_text(encoding="utf-8")
            self.assertEqual(index.count('class="section-panel"'), len(TAB_PAGES))
            for filename in TAB_PAGES:
                self.assertIn(f'class="section-panel" href="{filename}"', index)
                self.assertIn(f'href="{filename}"', index.split("<main", maxsplit=1)[0])
            self.assertIn("<strong>2</strong><span>Team members</span>", index)
            self.assertIn("<strong>2</strong><span>Projects</span>", index)
            self.assertIn("<strong>1</strong><span>Collaborations</span>", index)
            self.assertNotIn("Example Tool", index)
            self.assertNotIn("Jane Doe", index)

            pages = {name: (root / "docs" / name).read_text(encoding="utf-8") for name in TAB_PAGES}
            self.assertIn('href="tools.html" aria-current="page"', pages["tools.html"])
            self.assertIn("Editable project description.", pages["about.html"])
            self.assertIn("Jane Doe", pages["people.html"])
            expected = {
                "tools.html": {"Example Tool"},
                "projects.html": {"Example Tool", "Negation Data Explorer"},
                "publications.html": {"A useful result"},
                "collaborations.html": {"A useful result"},
            }
            for name, titles in expected.items():
                with self.subTest(page=name):
                    for title in ("Example Tool", "Negation Data Explorer", "A useful result"):
                        if title in titles:
                            self.assertIn(title, pages[name])
                        else:
                            self.assertNotIn(title, pages[name])
            self.assertIn('data-filter="tooltype"', pages["tools.html"])
            self.assertIn('data-filter="pubtype"', pages["publications.html"])
            self.assertIn('data-filter="partners"', pages["collaborations.html"])
            self.assertIn('<option value="A02">A02</option><option value="Romance Lab">Romance Lab</option>', pages["collaborations.html"])
            self.assertIn('data-partners="A02|Romance Lab"', pages["collaborations.html"])
            self.assertIn("In collaboration with</strong> A02, Romance Lab", pages["publications.html"])

            project_page = self._page(root=root, bib_key="Repository:2026")
            self.assertIn("https://github.com/example/explorer-source", project_page)
            self.assertIn("Project details", project_page)
            self.assertIn("Visit project", project_page)
            self.assertIn('href="../projects.html">← Back to Projects', project_page)

            tool_page = self._page(root=root, bib_key="Example:Tool")
            for text in ("Tool details", "Open tool", "Documentation", "Jane Doe", "Software", "Active", "Public", "MIT", "@project{Example:Tool,"):
                self.assertIn(text, tool_page)
            self.assertIn('<a href="../tools.html">Tools &amp; Services</a><a href="../projects.html">Projects</a>', tool_page)
            self.assertIn("A useful result</a>", tool_page)

            publication_page = self._page(root=root, bib_key="Doe:2026")
            self.assertIn("Publication details", publication_page)
            self.assertIn("View publication", publication_page)
            self.assertIn("Journal article", publication_page)
            self.assertIn("Example Tool</a>", publication_page)
            citation = publication_page.split('<code id="bibtex-entry">', maxsplit=1)[1].split("</code>", maxsplit=1)[0]
            self.assertTrue(citation.startswith("@article{Doe:2026,"))
            self.assertIn("keywords = {negation; infrastructure}", citation)
            self.assertNotIn("pubtype", citation)
            self.assertNotIn("collaboration", citation)
            self.assertIn("<dt>Collaborating projects</dt><dd>A02, Romance Lab</dd>", publication_page)

    def test_every_build_replaces_the_complete_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bibliography = self._write_bibliography(root=root)
            self._build(root=root, bib_path=bibliography)
            stale_file = root / "docs/stale.txt"
            stale_file.write_text("stale", encoding="utf-8")
            stale_page = root / "docs/publications/stale.html"
            stale_page.write_text("stale", encoding="utf-8")

            result = self._build(root=root, bib_path=bibliography)

            self.assertEqual(result["total"], 3)
            self.assertFalse(stale_file.exists())
            self.assertFalse(stale_page.exists())
            self.assertTrue((root / "docs/assets/site.css").is_file())

    def test_manual_bibtex_edits_are_reflected_on_next_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bibliography = self._write_bibliography(root=root)
            self._build(root=root, bib_path=bibliography)
            bibliography.write_text(
                "@project{Only:Project, keywords={project}, name={Manually revised project}, abstract={Only this remains.}}\n",
                encoding="utf-8",
            )

            result = self._build(root=root, bib_path=bibliography)

            self.assertEqual(result, {"total": 1, "tools": 0, "projects": 1, "publications": 0, "collaborations": 0})
            pages = list((root / "docs/publications").glob("*.html"))
            self.assertEqual(len(pages), 1)
            self.assertIn("Manually revised project", pages[0].read_text(encoding="utf-8"))

    def test_duplicate_keys_in_input_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate BibTeX key"):
            self._build_with_text(
                text="@project{same, name={One}, keywords={project}}\n@project{same, name={Two}, keywords={tool}}",
            )


class CatalogueDataTests(unittest.TestCase):
    def setUp(self) -> None:
        entries = parse_bibtex(text=CATALOGUE_PATH.read_text(encoding="utf-8"), source=str(CATALOGUE_PATH))
        self.entries = {str(entry["bib_key"]): entry for entry in entries}

    def _categories(self, *, bib_key: str) -> list[str]:
        return parse_categories(bib_key=bib_key, value=self.entries[bib_key]["fields"].get("keywords", ""))

    def test_every_entry_uses_the_single_project_type(self) -> None:
        for bib_key, entry in self.entries.items():
            with self.subTest(bib_key=bib_key):
                self.assertEqual(entry["entry_type"], "project")
                self.assertTrue(self._categories(bib_key=bib_key))
                if "publication" in self._categories(bib_key=bib_key):
                    self.assertTrue(entry["fields"].get("pubtype"))

    def test_mouse_tracking_is_a_project(self) -> None:
        self.assertIn("project", self._categories(bib_key="INF:MoTR:2025"))

    def test_collaborations_name_their_partner_projects(self) -> None:
        for bib_key, entry in self.entries.items():
            if "collaboration" in self._categories(bib_key=bib_key):
                with self.subTest(bib_key=bib_key):
                    self.assertTrue(entry["fields"].get("collaboration", "").strip())

    def test_tools_link_to_their_publications(self) -> None:
        for tool_key, publication_key in {"INF:RT-SEG": "Hammerla:etal:2026:c", "INF:DUUI": "Abrami:et:al:2025:a"}.items():
            with self.subTest(tool_key=tool_key):
                self.assertEqual(self._categories(bib_key=tool_key), ["tool"])
                self.assertIn("publication", self._categories(bib_key=publication_key))
                self.assertEqual(self.entries[tool_key]["fields"]["related"], publication_key)

    def test_hosted_services_are_single_tool_and_project_entries(self) -> None:
        for bib_key in ("INF:OpenWebUI", "INF:LabelStudio", "INF:Slurm", "INF:SurrealDB", "INF:DigitalDataManagementProtocol", "INF:Surprisal"):
            with self.subTest(bib_key=bib_key):
                self.assertEqual(self._categories(bib_key=bib_key), ["tool", "project"])


if __name__ == "__main__":
    unittest.main()
