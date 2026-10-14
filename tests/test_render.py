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


class LineMarkersTest(unittest.TestCase):
    def lines(self, text):
        import re
        return [int(n) for n in re.findall(r'data-line="(\d+)"', R.add_line_markers(text))]

    def test_blocks_marked_with_original_line_numbers(self):
        text = "---\ntitle: X\n---\n\n# Nadpis\n\nOdsek\nďalší riadok\n\nDruhý odsek\n"
        self.assertEqual(self.lines(text), [4, 6, 9])

    def test_skips_code_math_divs_lists_and_captions(self):
        text = "\n".join([
            "```{python}", "", "# komentár", "", "```",   # 0-4 kód
            "", "$$", "", "x", "$$",                       # 5-9 matematika
            "", "::: {.callout-note}", "## T", "", "obsah", ":::",  # 10-15 callout
            "", "- a", "", "- b",                          # 16-19 zoznam
            "", "| a |", "|---|", "| 1 |", "", ": Popis",  # 20-25 tabuľka
        ])
        self.assertEqual(self.lines(text), [0, 6, 11, 17, 21])

    def test_text_is_preserved(self):
        text = "# A\n\ntext\n"
        out = R.add_line_markers(text).split("\n")
        # každá značka je samostatný riadok nasledovaný prázdnym riadkom
        cleaned = []
        skip = False
        for line in out:
            if skip:
                skip = False
                continue
            if "qgui-line" in line:
                skip = True
                continue
            cleaned.append(line)
        self.assertEqual("\n".join(cleaned), text)


class PendingOpenTest(unittest.TestCase):
    def test_token_claims_immediately_others_after_delay(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            ws = Workspace(Path(d))
            ws.request_open("a.md", "tok")
            self.assertIsNone(ws.claim_open(""))          # iná karta hneď nie
            self.assertIsNone(ws.claim_open("zly"))
            self.assertEqual(ws.claim_open("tok"), "a.md")  # karta s tokenom áno
            self.assertIsNone(ws.claim_open("tok"))        # iba raz
            ws.request_open("b.md", "tok2")
            with mock.patch("qgui.server.time.time", return_value=ws.pending["t"] + 3):
                self.assertEqual(ws.claim_open(""), "b.md")  # po 2,5 s ktokoľvek


class ReportedOutputsTest(unittest.TestCase):
    def test_quarto_output_created_and_pandoc_o(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "TVVP (finál).pdf").write_bytes(b"%PDF")
            (base / "x.docx").write_bytes(b"PK")
            log = "...\nOutput created: TVVP (finál).pdf\n"
            self.assertEqual([p.name for p in R.reported_outputs(log, ["quarto"], base)], ["TVVP (finál).pdf"])
            cmd = ["pandoc", "a.md", "-o", str(base / "x.docx")]
            self.assertEqual([p.name for p in R.reported_outputs("", cmd, base)], ["x.docx"])
            self.assertEqual(R.reported_outputs("Output created: chyba.pdf", ["quarto"], base), [])


class YamlFormatTest(unittest.TestCase):
    def test_first_format(self):
        self.assertEqual(R._yaml_first_format("---\ntitle: X\nformat: pdf\n---\n"), "pdf")
        self.assertEqual(R._yaml_first_format("---\nformat:\n  docx:\n    toc: true\n  pdf: default\n---\n"), "docx")
        self.assertEqual(R._yaml_first_format("# bez hlavičky\n"), "")


class DiagnoseTest(unittest.TestCase):
    def test_rsvg_and_missing_module(self):
        log = ("FATAL (main.lua:7020) An error occurred:\n"
               "Could not convert a SVG to a PDF for output. Please ensure that rsvg-convert is available.\n"
               "\t[C]: in ?\n\t...main.lua:1315: in upvalue\n"
               "ModuleNotFoundError: No module named 'schemdraw'\n")
        d = R.diagnose(log)
        self.assertIn("Could not convert a SVG to a PDF for output. Please ensure that rsvg-convert is available.",
                      d["key_lines"])
        self.assertTrue(any("rsvg-convert" in h for h in d["hints"]))
        self.assertTrue(any("pip install schemdraw" in h for h in d["hints"]))
        self.assertEqual(R.diagnose("Output created: x.pdf")["hints"], [])
