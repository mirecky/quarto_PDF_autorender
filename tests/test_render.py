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


class HiddenWindowTest(unittest.TestCase):
    """Na Windows sa pandoc/quarto nesmú spúšťať vo viditeľnom okne terminálu."""

    def test_windows_flags(self):
        from unittest import mock

        class FakeSI:
            dwFlags = 0
            wShowWindow = 1

        with mock.patch.object(R.os, "name", "nt"), \
             mock.patch.object(R.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), \
             mock.patch.object(R.subprocess, "STARTF_USESHOWWINDOW", 1, create=True), \
             mock.patch.object(R.subprocess, "STARTUPINFO", FakeSI, create=True), \
             mock.patch.object(R.subprocess, "run") as run:
            R._run(["pandoc", "--version"])
        kw = run.call_args.kwargs
        self.assertTrue(kw["creationflags"] & 0x08000000)
        self.assertEqual(kw["startupinfo"].wShowWindow, 0)
        self.assertEqual(kw["encoding"], "utf-8")

    def test_utf8_roundtrip(self):
        res = R._run(["python3", "-c", "import sys; sys.stdout.write(sys.stdin.read())"],
                     input="ľščťžýáíé")
        self.assertEqual(res.stdout, "ľščťžýáíé")
