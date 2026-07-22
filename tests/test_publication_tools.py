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
            source_root=self._source_root(root=root),
        )

    def test_parser_handles_nested_braces_and_latex_names(self) -> None:
        entries = parse_bibtex(
            text='@article{key, title={{Nested} title}, author={M{\\\"u}ller, Max}}',
            source="memory",
        )
        self.assertEqual(entries[0]["bib_key"], "key")
        self.assertEqual(entries[0]["fields"]["title"], "{Nested} title")

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
                {"generated": 2, "total": 2, "publications": 1, "ignored": 0},
            )
            self.assertEqual(bibliography.read_bytes(), bib_before)
            self.assertEqual(project_data.read_bytes(), json_before)
            index = (root / "docs/index.html").read_text(encoding="utf-8")
            self.assertIn("<strong>2</strong><span>Projects</span>", index)
            self.assertIn("<strong>1</strong><span>Publications</span>", index)
            self.assertIn("Editable project description.", index)
            self.assertIn("Jane Doe", index)
            manifest = json.loads((root / "docs/publications/index.json").read_text(encoding="utf-8"))
            project = next(item for item in manifest["publications"] if item["bib_key"] == "Repository:2026")
            page = (root / "docs/publications" / project["filename"]).read_text(encoding="utf-8")
            self.assertIn("https://github.com/example/explorer-source", page)

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

            self.assertEqual(result["generated"], 2)
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
            self.assertEqual(result["publications"], 0)
            pages = list((root / "docs/publications").glob("*.html"))
            self.assertEqual(len(pages), 1)
            self.assertIn("Manually revised project", pages[0].read_text(encoding="utf-8"))

    def test_duplicate_keys_in_input_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bib_path = root / "duplicate.bib"
            bib_path.write_text("@article{same,title={One}}\n@book{same,title={Two}}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate BibTeX key"):
                self._build(root=root, bib_path=bib_path)


if __name__ == "__main__":
    unittest.main()
