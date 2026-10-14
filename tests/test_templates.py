import tempfile
import unittest
from pathlib import Path

from qgui import render as R
from qgui import templates as T


class TemplatesTest(unittest.TestCase):
    def test_documents_have_expected_format(self):
        with tempfile.TemporaryDirectory() as d:
            for kind, fmt in (("revealjs", "revealjs"), ("beamer", "beamer"), ("pptx", "pptx"),
                              ("dashboard", "dashboard"), ("qmd", "pdf")):
                f = T.create(Path(d) / f"x-{kind}", kind)
                self.assertEqual(f.suffix, ".qmd")
                text = f.read_text(encoding="utf-8")
                self.assertNotIn("{{", text)
                self.assertEqual(R._yaml_first_format(text), fmt)
            md = T.create(Path(d) / "pozn", "md")
            self.assertEqual(md.name, "pozn.md")
            with self.assertRaises(FileExistsError):
                T.create(Path(d) / "pozn", "md")

    def test_projects(self):
        with tempfile.TemporaryDirectory() as d:
            web = T.create(Path(d) / "moj-web", "website")
            self.assertEqual(web.name, "index.qmd")
            info = R.project_info(web)
            self.assertEqual((info["type"], info["output_dir"]), ("website", "_site"))
            book = T.create(Path(d) / "kniha", "book")
            info = R.project_info(book)
            self.assertEqual((info["type"], info["output_dir"], info["format"]), ("book", "_book", "html"))
            self.assertIn("{.unnumbered}", (book.parent / "literatura.qmd").read_text(encoding="utf-8"))


class EffectiveFormatTest(unittest.TestCase):
    def test_presentation_overrides_profile_but_document_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            pres = T.create(Path(d) / "p", "revealjs")
            doc = T.create(Path(d) / "d", "qmd")
            self.assertEqual(R.effective_format(pres, "pdf"), "revealjs")
            self.assertEqual(R.effective_format(doc, "docx"), "docx")
            page = T.create(Path(d) / "web", "website")
            self.assertEqual(R.effective_format(page, "pdf"), "html")


if __name__ == "__main__":
    unittest.main()
