from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from build_publications import build_site, parse_bibtex, supported_entry_types


class PublicationToolTests(unittest.TestCase):
    def _source_root(self, *, root: Path) -> Path:
        source_root = root / "src"
        assets = source_root / "site_assets"
        assets.mkdir(parents=True, exist_ok=True)
        repository_assets = Path(__file__).resolve().parent.parent / "src/site_assets"
        for name in ("site.css", "site.js"):
            (assets / name).write_text((repository_assets / name).read_text(encoding="utf-8"), encoding="utf-8")
        return source_root

    def _write_bibliography(self, *, root: Path) -> Path:
        bib_path = root / "data/projects.bib"
        bib_path.parent.mkdir(parents=True)
        bib_path.write_text(
            """@article{Doe:2026,
  title = {{A} useful result},
  author = {Doe, Jane and M{\\\"u}ller, Max},
  journal = {Journal of Tests},
  year = {2026},
  doi = {10.1000/example},
  keywords = {negation; infrastructure},
  abstract = {An abstract with {nested braces}.}
}

@project{Repository:2026,
  name = {Negation Data Explorer},
  author = {Doe, Jane},
  year = {2026},
  url = {https://github.com/example/explorer},
  projectlink = {https://github.com/example/explorer-source},
  abstract = {A repository for exploring negation data.},
  keywords = {software, data}
}

@tool{Example:Tool,
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
  keywords = {testing, reusable software},
  license = {MIT}
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
                        {
                            "name": "Jane Doe",
                            "role": "Project Leader",
                            "affiliation": "Test University",
                            "profile_url": "https://example.org/jane",
                        },
                        {
                            "name": "Max Müller",
                            "role": "Scientific Staff",
                            "affiliation": "",
                            "profile_url": "",
                        },
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
            allowed_entry_types=supported_entry_types(include_projects=True),
            project_name="Test INF",
            project_subtitle="Test projects",
            project_data_path=self._write_project_data(root=root),
            logo_path=Path(__file__).resolve().parent.parent / "data/inf_logo.svg",
            source_root=self._source_root(root=root),
        )

    def test_parser_handles_nested_braces_and_latex_names(self) -> None:
        entries = parse_bibtex(
            text='@article{key, title={{Nested} title}, author={M{\\\"u}ller, Max}}',
            source="memory",
        )
        self.assertEqual(entries[0]["bib_key"], "key")
        self.assertEqual(entries[0]["fields"]["title"], "{Nested} title")

    def test_tool_is_a_supported_catalogue_entry_type(self) -> None:
        self.assertIn("tool", supported_entry_types())

    def test_mouse_tracking_is_catalogued_as_a_project(self) -> None:
        catalogue_path = Path(__file__).resolve().parent.parent / "data/neglab-inf.bib"
        entries = parse_bibtex(text=catalogue_path.read_text(encoding="utf-8"), source=str(catalogue_path))
        mouse_tracking = next(entry for entry in entries if entry["bib_key"] == "INF:MoTR:2025")
        self.assertEqual(mouse_tracking["entry_type"], "project")

    def test_tools_keep_separate_project_or_publication_counterparts(self) -> None:
        catalogue_path = Path(__file__).resolve().parent.parent / "data/neglab-inf.bib"
        entries = parse_bibtex(text=catalogue_path.read_text(encoding="utf-8"), source=str(catalogue_path))
        entries_by_key = {entry["bib_key"]: entry for entry in entries}
        self.assertEqual(len(entries_by_key), len(entries))

        counterparts = {
            "INF:RT-SEG": ("Hammerla:etal:2026:c", "inproceedings"),
            "INF:DUUI": ("Abrami:et:al:2025:a", "article"),
            "INF:OpenWebUI": ("INF:OpenWebUI:2025", "project"),
            "INF:LabelStudio": ("INF:LabelStudio:2025", "project"),
            "INF:Slurm": ("INF:Slurm:2026", "project"),
            "INF:SurrealDB": ("INF:SurrealDB:2025", "project"),
            "INF:DigitalDataManagementProtocol:Tool": ("INF:DigitalDataManagementProtocol", "project"),
            "INF:Surprisal": ("INF:Surprisal:2025", "project"),
        }
        for tool_key, (counterpart_key, counterpart_type) in counterparts.items():
            with self.subTest(tool_key=tool_key):
                self.assertEqual(entries_by_key[tool_key]["entry_type"], "tool")
                self.assertEqual(entries_by_key[counterpart_key]["entry_type"], counterpart_type)
                self.assertEqual(entries_by_key[tool_key]["fields"]["related"], counterpart_key)

    def test_build_reads_inputs_without_modifying_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bibliography = self._write_bibliography(root=root)
            project_data = self._write_project_data(root=root)
            bib_before = bibliography.read_bytes()
            json_before = project_data.read_bytes()

            result = self._build(root=root, bib_path=bibliography)

            self.assertEqual(
                result,
                {
                    "generated": 3,
                    "total": 3,
                    "tools": 1,
                    "projects": 1,
                    "publications": 1,
                    "ignored": 0,
                },
            )
            self.assertEqual(bibliography.read_bytes(), bib_before)
            self.assertEqual(project_data.read_bytes(), json_before)
            self.assertTrue((root / "docs/assets/inf_logo.svg").is_file())
            index = (root / "docs/index.html").read_text(encoding="utf-8")
            self.assertNotIn('class="hero-logo"', index)
            self.assertNotIn('src="assets/inf_logo.svg"', index)
            self.assertIn('class="section-navigation"', index)
            self.assertEqual(index.count('class="section-panel"'), 4)
            self.assertIn('<h2>About INF</h2>', index)
            self.assertIn('<h2>People</h2>', index)
            self.assertIn('<h2>Tools &amp; Services</h2>', index)
            self.assertIn('<h2>Projects &amp; Publications</h2>', index)
            self.assertIn("<strong>2</strong><span>Team members</span>", index)
            self.assertIn("<strong>1</strong><span>Tools</span>", index)
            self.assertIn("<strong>1</strong><span>Projects</span>", index)
            self.assertIn("<strong>1</strong><span>Publications</span>", index)
            self.assertIn('id="tools"', index)
            self.assertIn('id="tool-search"', index)
            self.assertIn('id="catalogue-search"', index)
            self.assertIn("Editable project description.", index)
            self.assertIn("Jane Doe", index)
            tool_section = index.split('<section class="publication-section tool-section" id="tools">', maxsplit=1)[1]
            tool_section, catalogue_section = tool_section.split('<section class="publication-section" id="projects">', maxsplit=1)
            self.assertIn("Example Tool", tool_section)
            self.assertNotIn("Negation Data Explorer", tool_section)
            self.assertNotIn("A useful result", tool_section)
            self.assertNotIn("Example Tool", catalogue_section)
            self.assertIn("Negation Data Explorer", catalogue_section)
            self.assertIn("A useful result", catalogue_section)
            manifest = json.loads((root / "docs/publications/index.json").read_text(encoding="utf-8"))
            project = next(item for item in manifest["publications"] if item["bib_key"] == "Repository:2026")
            project_page = (root / "docs/publications" / project["filename"]).read_text(encoding="utf-8")
            self.assertIn("https://github.com/example/explorer-source", project_page)
            self.assertIn("Project details", project_page)
            self.assertIn("Visit project", project_page)

            publication = next(item for item in manifest["publications"] if item["bib_key"] == "Doe:2026")
            publication_page = (root / "docs/publications" / publication["filename"]).read_text(encoding="utf-8")
            self.assertIn("Publication details", publication_page)
            self.assertIn("View publication", publication_page)

            tool = next(item for item in manifest["publications"] if item["bib_key"] == "Example:Tool")
            self.assertEqual(tool["entry_type"], "tool")
            tool_page = (root / "docs/publications" / tool["filename"]).read_text(encoding="utf-8")
            self.assertIn("Tool details", tool_page)
            self.assertIn("Open tool", tool_page)
            self.assertIn("Documentation", tool_page)
            self.assertIn("Jane Doe", tool_page)
            self.assertIn("Software", tool_page)
            self.assertIn("Active", tool_page)
            self.assertIn("Public", tool_page)
            self.assertIn("MIT", tool_page)
            self.assertIn("@tool{Example:Tool,", tool_page)

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

            self.assertEqual(result["generated"], 3)
            self.assertFalse(stale_file.exists())
            self.assertFalse(stale_page.exists())
            self.assertTrue((root / "docs/assets/site.css").is_file())

    def test_manual_bibtex_edits_are_reflected_on_next_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bibliography = self._write_bibliography(root=root)
            self._build(root=root, bib_path=bibliography)
            bibliography.write_text(
                "@project{Only:Project, name={Manually revised project}, abstract={Only this remains.}}\n",
                encoding="utf-8",
            )

            result = self._build(root=root, bib_path=bibliography)

            self.assertEqual(result["total"], 1)
            self.assertEqual(result["tools"], 0)
            self.assertEqual(result["projects"], 1)
            self.assertEqual(result["publications"], 0)
            pages = list((root / "docs/publications").glob("*.html"))
            self.assertEqual(len(pages), 1)
            self.assertIn("Manually revised project", pages[0].read_text(encoding="utf-8"))

    def test_duplicate_keys_in_input_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bib_path = root / "duplicate.bib"
            bib_path.write_text(
                "@article{same,title={One}}\n"
                "@project{same,name={Two}}\n"
                "@tool{same,name={Three},tooltype={software}}",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate BibTeX key"):
                self._build(root=root, bib_path=bib_path)


if __name__ == "__main__":
    unittest.main()
