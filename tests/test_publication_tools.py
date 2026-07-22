from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from add_publication_link import update_publication_link
from build_publications import build_site, parse_bibtex


class PublicationToolTests(unittest.TestCase):
    def _build_fixture(self, *, root: Path, full_rebuild: bool = False) -> dict[str, int]:
        bib_path = root / "publications.bib"
        if not bib_path.exists():
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

@project{ignored, name = {Not a publication}, year = {2026}}
""",
                encoding="utf-8",
            )
        return build_site(
            bib_paths=[bib_path],
            docs_dir=root / "docs",
            full_rebuild=full_rebuild,
            allowed_entry_types=frozenset({"article"}),
            project_name="Test INF",
            project_subtitle="Test publications",
            source_root=Path(__file__).resolve().parent.parent / "src",
        )

    def test_parser_handles_nested_braces_and_latex_names(self) -> None:
        entries = parse_bibtex(
            text='@article{key, title={{Nested} title}, author={M{\\\"u}ller, Max}}',
            source="memory",
        )
        self.assertEqual(entries[0]["bib_key"], "key")
        self.assertEqual(entries[0]["fields"]["title"], "{Nested} title")

    def test_build_is_incremental_and_ignores_project_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = self._build_fixture(root=root)
            second = self._build_fixture(root=root)
            self.assertEqual(first, {"generated": 1, "skipped": 0, "total": 1, "ignored": 1})
            self.assertEqual(second, {"generated": 0, "skipped": 1, "total": 1, "ignored": 1})
            manifest = json.loads((root / "docs/publications/index.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["publications"][0]["bib_key"], "Doe:2026")
            page = next((root / "docs/publications").glob("*.html")).read_text(encoding="utf-8")
            self.assertIn("Max Müller", page)
            self.assertIn("https://doi.org/10.1000/example", page)

    def test_full_rebuild_removes_orphaned_html(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._build_fixture(root=root)
            orphan = root / "docs/publications/orphan.html"
            orphan.write_text('<meta name="bib-key" content="old:key">', encoding="utf-8")
            manual_page = root / "docs/publications/manual.html"
            manual_page.write_text("This page is not generated.", encoding="utf-8")
            result = self._build_fixture(root=root, full_rebuild=True)
            self.assertFalse(orphan.exists())
            self.assertTrue(manual_page.exists())
            self.assertEqual(result["generated"], 1)

    def test_link_update_is_persistent_across_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._build_fixture(root=root)
            page_path = update_publication_link(
                docs_dir=root / "docs",
                bib_key="Doe:2026",
                url="https://github.com/example/result",
            )
            self.assertIn("https://github.com/example/result", page_path.read_text(encoding="utf-8"))
            self._build_fixture(root=root, full_rebuild=True)
            self.assertIn("https://github.com/example/result", page_path.read_text(encoding="utf-8"))
            update_publication_link(docs_dir=root / "docs", bib_key="Doe:2026", url=None)
            self.assertNotIn("https://github.com/example/result", page_path.read_text(encoding="utf-8"))

    def test_duplicate_keys_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bib_path = root / "duplicate.bib"
            bib_path.write_text("@article{same,title={One}}\n@book{same,title={Two}}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate BibTeX key"):
                build_site(
                    bib_paths=[bib_path],
                    docs_dir=root / "docs",
                    full_rebuild=False,
                    allowed_entry_types=frozenset({"article", "book"}),
                    project_name="Test",
                    project_subtitle="Test",
                    source_root=Path(__file__).resolve().parent.parent / "src",
                )


if __name__ == "__main__":
    unittest.main()
