from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from add_publication_link import update_publication_link
from build_publications import build_site, parse_bibtex, supported_entry_types


class PublicationToolTests(unittest.TestCase):
    def _source_root(self) -> Path:
        return Path(__file__).resolve().parent.parent / "src"

    def _write_fixture(self, *, root: Path) -> Path:
        bib_path = root / "import.bib"
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

    def _build(
        self,
        *,
        root: Path,
        bib_paths: list[Path],
        update_existing: bool = False,
        full_rebuild: bool = False,
    ) -> dict[str, int]:
        return build_site(
            bib_paths=bib_paths,
            database_path=root / "data/neglab-inf.bib",
            update_existing=update_existing,
            docs_dir=root / "docs",
            full_rebuild=full_rebuild,
            allowed_entry_types=supported_entry_types(include_projects=True),
            project_name="Test INF",
            project_subtitle="Test projects",
            source_root=self._source_root(),
        )

    def test_parser_handles_nested_braces_and_latex_names(self) -> None:
        entries = parse_bibtex(
            text='@article{key, title={{Nested} title}, author={M{\\\"u}ller, Max}}',
            source="memory",
        )
        self.assertEqual(entries[0]["bib_key"], "key")
        self.assertEqual(entries[0]["fields"]["title"], "{Nested} title")

    def test_import_creates_database_and_keeps_existing_entries_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = self._write_fixture(root=root)
            first = self._build(root=root, bib_paths=[source])
            second = self._build(root=root, bib_paths=[source])
            self.assertEqual(
                first,
                {"generated": 2, "skipped": 0, "total": 2, "publications": 1, "ignored": 0, "added": 2, "updated": 0, "kept": 0},
            )
            self.assertEqual(
                second,
                {"generated": 0, "skipped": 2, "total": 2, "publications": 1, "ignored": 0, "added": 0, "updated": 0, "kept": 2},
            )
            database = (root / "data/neglab-inf.bib").read_text(encoding="utf-8")
            self.assertIn("@article{Doe:2026", database)
            self.assertIn("@project{Repository:2026", database)
            self.assertIn("projectlink", database)
            index = (root / "docs/index.html").read_text(encoding="utf-8")
            self.assertIn("<strong>2</strong><span>Projects</span>", index)
            self.assertIn("<strong>1</strong><span>Publications</span>", index)
            self.assertRegex(index, r"assets/site\.css\?v=[a-f0-9]{12}")
            manifest = json.loads((root / "docs/publications/index.json").read_text(encoding="utf-8"))
            project = next(item for item in manifest["publications"] if item["bib_key"] == "Repository:2026")
            page = (root / "docs/publications" / project["filename"]).read_text(encoding="utf-8")
            self.assertIn("https://github.com/example/explorer-source", page)

    def test_update_flag_replaces_matching_database_entry_and_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = self._write_fixture(root=root)
            self._build(root=root, bib_paths=[source])
            update = root / "update.bib"
            update.write_text(
                "@article{Doe:2026, title={A revised result}, author={Doe, Jane}, year={2026}}\n",
                encoding="utf-8",
            )
            kept = self._build(root=root, bib_paths=[update])
            self.assertEqual(kept["kept"], 1)
            self.assertNotIn("A revised result", (root / "data/neglab-inf.bib").read_text(encoding="utf-8"))

            updated = self._build(root=root, bib_paths=[update], update_existing=True)
            self.assertEqual(updated["updated"], 1)
            self.assertIn("A revised result", (root / "data/neglab-inf.bib").read_text(encoding="utf-8"))
            manifest = json.loads((root / "docs/publications/index.json").read_text(encoding="utf-8"))
            record = next(item for item in manifest["publications"] if item["bib_key"] == "Doe:2026")
            page = (root / "docs/publications" / record["filename"]).read_text(encoding="utf-8")
            self.assertIn("A revised result", page)

    def test_full_rebuild_wipes_database_and_generated_orphans(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = self._write_fixture(root=root)
            self._build(root=root, bib_paths=[source])
            orphan = root / "docs/publications/orphan.html"
            orphan.write_text('<meta name="bib-key" content="old:key">', encoding="utf-8")
            replacement = root / "replacement.bib"
            replacement.write_text("@project{Only:Project, name={Only project}, abstract={Only this remains.}}\n", encoding="utf-8")
            result = self._build(root=root, bib_paths=[replacement], full_rebuild=True)
            database = (root / "data/neglab-inf.bib").read_text(encoding="utf-8")
            self.assertNotIn("Doe:2026", database)
            self.assertIn("Only:Project", database)
            self.assertFalse(orphan.exists())
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["publications"], 0)

    def test_link_tool_stores_updates_and_removes_projectlink_in_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = self._write_fixture(root=root)
            self._build(root=root, bib_paths=[source])
            arguments = {
                "database_path": root / "data/neglab-inf.bib",
                "docs_dir": root / "docs",
                "bib_key": "Repository:2026",
                "project_name": "Test INF",
                "project_subtitle": "Test projects",
                "source_root": self._source_root(),
            }
            page_path = update_publication_link(url="https://github.com/example/first", **arguments)
            database = (root / "data/neglab-inf.bib").read_text(encoding="utf-8")
            self.assertIn("projectlink", database)
            self.assertIn("https://github.com/example/first", database)
            self.assertIn("https://github.com/example/first", page_path.read_text(encoding="utf-8"))

            update_publication_link(url="https://zenodo.org/records/123", **arguments)
            database = (root / "data/neglab-inf.bib").read_text(encoding="utf-8")
            self.assertNotIn("https://github.com/example/first", database)
            self.assertIn("https://zenodo.org/records/123", database)

            update_publication_link(url=None, **arguments)
            database = (root / "data/neglab-inf.bib").read_text(encoding="utf-8")
            self.assertNotIn("projectlink", database)
            self.assertNotIn("https://zenodo.org/records/123", page_path.read_text(encoding="utf-8"))

    def test_duplicate_keys_in_one_import_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bib_path = root / "duplicate.bib"
            bib_path.write_text("@article{same,title={One}}\n@book{same,title={Two}}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate BibTeX key"):
                self._build(root=root, bib_paths=[bib_path])


if __name__ == "__main__":
    unittest.main()
