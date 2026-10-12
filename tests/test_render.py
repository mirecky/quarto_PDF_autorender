import tempfile
import unittest
from pathlib import Path

from qgui import render as R
from qgui.server import Workspace


class BuildCommandTest(unittest.TestCase):
    def setUp(self):
        self.src = Path("/tmp/doc/clanok.qmd")

    def test_quarto_pdf(self):
        cmd, out = R.build_command(self.src, {"engine": "quarto", "format": "pdf", "toc": True,
                                              "pdf_engine": "lualatex", "lang": "sk"})
        self.assertEqual(cmd[1:5], ["render", "clanok.qmd", "--to", "pdf"])
        self.assertIn("--toc", cmd)
        self.assertEqual(cmd[cmd.index("--pdf-engine") + 1], "lualatex")
        self.assertIn("lang:sk", cmd)
        self.assertEqual(out, Path("/tmp/doc/_output"))

    def test_quarto_yaml_format_passes_nothing(self):
        cmd, _ = R.build_command(self.src, {"engine": "quarto", "format": "", "output_dir": ""})
        self.assertEqual(cmd[1:], ["render", "clanok.qmd"])

    def test_pandoc_pdf(self):
        cmd, _ = R.build_command(self.src, {"engine": "pandoc", "format": "pdf", "pdf_engine": "xelatex",
                                            "geometry": "margin=2cm", "metadata": "author=Ja\n# komentár"})
        self.assertIn("--pdf-engine=xelatex", cmd)
        self.assertEqual(cmd[cmd.index("-o") + 1], "/tmp/doc/_output/clanok.pdf")
        self.assertIn("geometry=margin=2cm", cmd)
        self.assertIn("author=Ja", cmd)
        self.assertNotIn("# komentár", " ".join(cmd))

    def test_extra_args_shlex(self):
        cmd, _ = R.build_command(self.src, {"engine": "pandoc", "format": "html",
                                            "extra_args": '--css "moj styl.css"'})
        self.assertEqual(cmd[-2:], ["--css", "moj styl.css"])


class WorkspaceTest(unittest.TestCase):
    def test_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Workspace(Path(d))
            with self.assertRaises(PermissionError):
                ws.resolve("../etc/passwd")
            self.assertEqual(ws.resolve("a/b.md"), Path(d).resolve() / "a/b.md")


if __name__ == "__main__":
    unittest.main()
