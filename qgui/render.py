"""Zostavenie príkazov pre Quarto/Pandoc a spúšťanie renderu."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

# Formát -> prípona výstupu (pre pandoc; quarto má rovnaké mapovanie okrem typst).
FORMAT_EXT = {
    "pdf": "pdf",
    "beamer": "pdf",
    "html": "html",
    "revealjs": "html",
    "docx": "docx",
    "odt": "odt",
    "epub": "epub",
    "pptx": "pptx",
    "latex": "tex",
    "typst": "typ",
    "gfm": "md",
    "commonmark": "md",
}
OUTPUT_EXTS = {"pdf", "html", "docx", "odt", "epub", "pptx", "tex", "typ", "md"}
PDF_FORMATS = {"pdf", "beamer", "typst"}
MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml-full.js"
# Staršie šablóny Pandocu vkladajú skript z polyfill.io (kompromitovaná doména) – odstraňujeme ho.
_POLYFILL_RE = re.compile(r'<script[^>]*polyfill\.io[^>]*>\s*</script>\s*', re.I)
REFERENCE_DOC_FORMATS = {"docx", "odt", "pptx"}

DEFAULT_SETTINGS = {
    "engine": "quarto",          # quarto | pandoc
    "format": "pdf",             # "" = podľa YAML hlavičky
    "pdf_engine": "",            # xelatex, lualatex, pdflatex, tectonic, typst, weasyprint, ...
    "output_dir": "_output",
    "toc": False,
    "toc_depth": "",
    "number_sections": False,
    "citeproc": False,
    "bibliography": "",
    "csl": "",
    "lang": "",
    "papersize": "",
    "fontsize": "",
    "geometry": "",
    "mainfont": "",
    "template": "",
    "reference_doc": "",
    "metadata": "",              # riadky key=value
    "extra_args": "",            # ďalšie argumenty (shlex)
    "timeout": 600,
}


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run so skrytým oknom na Windows a s kódovaním UTF-8.

    Pri spustení cez pythonw (bez konzoly) by Windows pre každý konzolový program
    (pandoc, quarto) otvoril nové okno terminálu, ktoré by kradlo fokus editoru.
    """
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    if os.name == "nt":
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
    return subprocess.run(cmd, **kwargs)


def _which(name: str) -> str | None:
    env = os.environ.get("QGUI_" + name.upper())
    if env and Path(env).exists():
        return env
    return shutil.which(name)


def tool_versions() -> dict:
    out: dict = {}
    for tool, args in (("quarto", ["--version"]), ("pandoc", ["--version"])):
        exe = _which(tool)
        if not exe:
            out[tool] = None
            continue
        try:
            res = _run([exe, *args], timeout=30)
            out[tool] = (res.stdout or res.stderr).splitlines()[0].strip()
        except Exception as exc:  # pragma: no cover - diagnostika
            out[tool] = f"chyba: {exc}"
    tinytex = [d for d in (Path.home() / ".TinyTeX/bin", Path.home() / "Library/TinyTeX/bin",
                           Path(os.environ.get("APPDATA", "~")) / "TinyTeX/bin") if d.is_dir()]
    tinytex_bins = [str(b) for d in tinytex for b in d.iterdir() if b.is_dir()]
    search = os.pathsep.join([os.environ.get("PATH", ""), *tinytex_bins])
    out["pdf_engines"] = {
        e: bool(shutil.which(e, path=search))
        for e in ("xelatex", "lualatex", "pdflatex", "tectonic", "typst", "weasyprint", "wkhtmltopdf")
    }
    # Quarto má vstavaný Typst.
    if out.get("quarto"):
        out["pdf_engines"]["typst"] = True
    return out


def _metadata_pairs(text: str) -> list[tuple[str, str]]:
    pairs = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
        elif ":" in line:
            k, v = line.split(":", 1)
        else:
            k, v = line, "true"
        pairs.append((k.strip(), v.strip()))
    return pairs


def merged(settings: dict | None) -> dict:
    s = dict(DEFAULT_SETTINGS)
    s.update({k: v for k, v in (settings or {}).items() if k in DEFAULT_SETTINGS})
    return s


def build_command(src: Path, settings: dict) -> tuple[list[str], Path | None]:
    """Vráti (príkaz, očakávaný výstupný adresár). Príkaz sa spúšťa s cwd = src.parent."""
    s = merged(settings)
    fmt = (s["format"] or "").strip()
    out_dir_rel = (s["output_dir"] or "").strip()
    out_dir = (src.parent / out_dir_rel).resolve() if out_dir_rel else src.parent
    is_pdfish = fmt in PDF_FORMATS or fmt == ""

    if s["engine"] == "pandoc":
        exe = _which("pandoc") or "pandoc"
        fmt = fmt or "html"
        ext = FORMAT_EXT.get(fmt, fmt)
        if fmt == "typst" and s["pdf_engine"] == "typst":
            ext = "pdf"
        out_file = out_dir / f"{src.stem}.{ext}"
        cmd = [exe, src.name, "-f", "markdown", "-o", str(out_file), "--resource-path", str(src.parent)]
        if fmt in ("beamer", "revealjs", "latex", "typst", "gfm", "commonmark", "pptx", "epub"):
            cmd += ["-t", fmt]
        if fmt in ("html", "revealjs", "latex"):
            cmd += ["-s"]
        if fmt in ("html", "revealjs"):
            cmd += [f"--mathjax={MATHJAX_URL}"]
        if s["pdf_engine"] and fmt in PDF_FORMATS:
            cmd += [f"--pdf-engine={s['pdf_engine']}"]
        meta_flag = lambda k, v: ["-M", f"{k}={v}"]  # noqa: E731
        var_flag = lambda k, v: ["-V", f"{k}={v}"]  # noqa: E731
    else:
        exe = _which("quarto") or "quarto"
        cmd = [exe, "render", src.name]
        if fmt:
            cmd += ["--to", fmt]
        # --output-dir sa zámerne nepoužíva: Quarto pri ňom vyčistí celý cieľový priečinok.
        # Výstupy presúva render() po úspešnom behu; v Quarto projekte rozhoduje _quarto.yml.
        if find_project(src):
            out_dir = None
        if s["pdf_engine"] and is_pdfish:
            cmd += ["--pdf-engine", s["pdf_engine"]]
        meta_flag = lambda k, v: ["-M", f"{k}:{v}"]  # noqa: E731
        var_flag = meta_flag

    if s["toc"]:
        cmd += ["--toc"]
        if str(s["toc_depth"]).strip():
            cmd += [f"--toc-depth={int(s['toc_depth'])}"]
    if s["number_sections"]:
        cmd += ["--number-sections"]
    if s["citeproc"] or s["bibliography"]:
        cmd += ["--citeproc"]
    if s["bibliography"]:
        cmd += ["--bibliography", s["bibliography"]]
    if s["csl"]:
        cmd += ["--csl", s["csl"]]
    if s["template"]:
        cmd += ["--template", s["template"]]
    if s["reference_doc"] and (fmt in REFERENCE_DOC_FORMATS or fmt == ""):
        cmd += ["--reference-doc", s["reference_doc"]]
    if s["lang"]:
        cmd += meta_flag("lang", s["lang"])
    for key in ("papersize", "fontsize", "geometry", "mainfont"):
        if s[key]:
            cmd += var_flag(key, s[key])
    for k, v in _metadata_pairs(s["metadata"]):
        cmd += meta_flag(k, v)
    if s["extra_args"].strip():
        cmd += shlex.split(s["extra_args"])
    return cmd, out_dir


def find_project(src: Path) -> Path | None:
    """Koreň Quarto projektu (priečinok s _quarto.yml), ak súbor do nejakého patrí."""
    for d in [src.parent, *src.parent.parents][:8]:
        if (d / "_quarto.yml").exists() or (d / "_quarto.yaml").exists():
            return d
    return None


def _fresh(p: Path, since: float) -> bool:
    return p.stat().st_mtime >= since - 1


def _find_outputs(src: Path, dirs: list[Path], since: float) -> list[Path]:
    found = []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if (
                p.is_file()
                and p.stem == src.stem
                and p.suffix.lstrip(".") in OUTPUT_EXTS
                and p.resolve() != src.resolve()
                and _fresh(p, since)
            ):
                found.append(p)
    return sorted(set(found), key=lambda p: p.stat().st_mtime, reverse=True)


def _find_project_outputs(project: Path, src: Path, since: float, limit: int = 40) -> list[Path]:
    found = []
    for p in project.rglob("*"):
        if any(part.startswith(".") for part in p.relative_to(project).parts):
            continue
        if (p.is_file() and p.suffix.lstrip(".") in OUTPUT_EXTS and p.suffix != src.suffix
                and _fresh(p, since)):
            found.append(p)
            if len(found) >= limit:
                break
    # Najprv súbory s rovnakým menom ako zdroj, potom PDF, potom ostatné.
    return sorted(found, key=lambda p: (p.stem != src.stem, p.suffix != ".pdf", -p.stat().st_mtime))


def _move(p: Path, target_dir: Path) -> Path:
    target = target_dir / p.name
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()
    shutil.move(str(p), target)
    return target


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_KEY_LINE_RE = re.compile(r"(FATAL|ERROR|Error|error:|Traceback|^! |ModuleNotFoundError|not found)", re.M)
_HINTS = [
    (re.compile(r"rsvg-convert", re.I),
     "Obrázok je vo formáte SVG a LaTeX (PDF) ho bez programu rsvg-convert nevie vložiť. "
     "Riešenie: generuj obrázok ako PNG (napr. schemdraw.use('matplotlib') a "
     "Image(d.get_imagedata('png'))), použi PDF cez Typst, alebo nainštaluj rsvg-convert."),
    (re.compile(r"No module named '([\w.]+)'"),
     "Chýba Python balík „{0}“. Nainštaluj ho: py -m pip install {0}"),
    (re.compile(r"[Jj]upyter.*(not found|is not available|could not)|No module named 'jupyter"),
     "Na spúšťanie Python blokov treba Jupyter: py -m pip install jupyter"),
    (re.compile(r"LaTeX Error: File `([^']+)' not found"),
     "LaTeX nemá balík „{0}“. Spusti: quarto install tinytex --update-path, prípadne tlmgr install <balík>."),
    (re.compile(r"(xelatex|lualatex|pdflatex)[^\n]*(not found|No such file)", re.I),
     "Nenašiel sa LaTeX. Nainštaluj ho: quarto install tinytex"),
]


def diagnose(log: str) -> dict:
    """Podstatné riadky chyby a slovenská rada pre známe problémy."""
    lines = (log or "").splitlines()
    key: list[str] = []
    for i, l in enumerate(lines):
        if _KEY_LINE_RE.search(l) and not l.strip().startswith("..."):
            for x in (l, lines[i + 1] if i + 1 < len(lines) else ""):  # aj riadok s vysvetlením
                x = x.strip()
                if x and x not in key and not x.startswith(("...", "[C]")):
                    key.append(x)
    hints = []
    for rx, text in _HINTS:
        m = rx.search(log or "")
        if m:
            hints.append(text.format(*m.groups()) if m.groups() else text)
    return {"key_lines": key[:8], "hints": hints}


_OUTPUT_CREATED_RE = re.compile(r"^\s*Output created:\s*(.+?)\s*$", re.M)


def reported_outputs(log: str, cmd: list[str], base: Path) -> list[Path]:
    """Výstupy, ktoré nahlásil nástroj: Quarto riadkom „Output created:“, Pandoc parametrom -o."""
    paths = [m.group(1).strip().strip('"') for m in _OUTPUT_CREATED_RE.finditer(log or "")]
    if "-o" in cmd[:-1]:
        paths.append(cmd[cmd.index("-o") + 1])
    out = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = base / p
        if p.is_file():
            p = p.resolve()
            if p not in out:
                out.append(p)
    return out


def render(src: Path, settings: dict) -> dict:
    s = merged(settings)
    cmd, out_dir = build_command(src, s)
    project = find_project(src) if s["engine"] != "pandoc" else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    start = time.time()
    try:
        res = _run(cmd, cwd=src.parent, timeout=int(s["timeout"] or 600))
        code, log = res.returncode, _ANSI_RE.sub("", (res.stdout or "") + (res.stderr or ""))
    except FileNotFoundError:
        return {"ok": False, "cmd": cmd, "log": f"Program sa nenašiel: {cmd[0]}", "outputs": []}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "cmd": cmd, "log": f"Prekročený časový limit ({exc.timeout} s).", "outputs": []}

    # 1) Čo nahlásil samotný nástroj (Quarto: „Output created: …“, Pandoc: -o) – spoľahlivé
    #    aj pri vlastnom názve výstupu (output-file v YAML) či inom priečinku.
    reported = reported_outputs(log, cmd, src.parent if not project else project)
    if project:
        outputs = reported or _find_project_outputs(project, src, start)
    else:
        # 2) Záloha: súbory s rovnakým menom ako zdroj, vytvorené počas renderu.
        found = _find_outputs(src, [d for d in {out_dir, src.parent} if d], start)
        fmt = (s["format"] or "").strip()
        if fmt:  # ponechať iba prípony zodpovedajúce zvolenému formátu
            wanted = {FORMAT_EXT.get(fmt, fmt)} | ({"pdf"} if fmt in PDF_FORMATS else set())
            found = [p for p in found if p.suffix.lstrip(".") in wanted]
        outputs = list(dict.fromkeys(reported + [p for p in found if p not in reported]))
        if code == 0 and out_dir and out_dir != src.parent:
            moved = []
            for p in outputs:
                if p.parent == src.parent:
                    target = _move(p, out_dir)
                    # Pomocné súbory HTML výstupu (obrázky, knižnice) musia ísť spolu s ním.
                    # (Quarto ich pomenuje podľa výstupu alebo podľa zdroja.)
                    if p.suffix == ".html":
                        for stem in dict.fromkeys((p.stem, src.stem)):
                            files_dir = src.parent / f"{stem}_files"
                            if files_dir.is_dir():
                                _move(files_dir, out_dir)
                    moved.append(target)
                else:
                    moved.append(p)
            outputs = moved
    if code == 0 and not outputs:
        log += ("\n[Quarto Studio] Výstupný súbor sa nenašiel. Skontroluj v YAML hlavičke "
                "kľúče output-file / output-dir, prípadne priečinok projektu (_quarto.yml).\n")
    return {
        **(diagnose(log) if code != 0 else {}),
        "ok": code == 0,
        "code": code,
        "cmd": cmd,
        "log": log,
        "outputs": [str(p) for p in outputs],
        "seconds": round(time.time() - start, 2),
    }


# --------------------------------------------------------------------------- náhľad

_CHUNK_RE = re.compile(r"^```\{(\w+)[^}]*\}", re.M)


_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
_LIST_RE = re.compile(r"^([-*+]|\d+[.)]|#\.)\s")
_DIV_OPEN_RE = re.compile(r"^:{3,}\s*\S")
_DIV_CLOSE_RE = re.compile(r"^:{3,}\s*$")


def add_line_markers(text: str) -> str:
    """Pred začiatok každého bloku vloží prázdny <div data-line="N"> (N = riadok od 0).

    Náhľad podľa nich synchronizuje posúvanie s editorom. Značky sa nevkladajú do
    YAML hlavičky, blokov kódu, matematiky, komentárov, Quarto divov (callouty by
    stratili titulok), medzi položky zoznamu ani pred popisy tabuliek (`: ...`).
    """
    lines = text.split("\n")
    out: list[str] = []
    fence = None
    in_yaml = in_math = in_comment = False
    div_depth = 0
    prev_blank = True
    in_list = False
    for i, line in enumerate(lines):
        s = line.strip()
        if i == 0 and s == "---":
            in_yaml = True
            out.append(line)
            continue
        if in_yaml:
            out.append(line)
            if s in ("---", "..."):
                in_yaml, prev_blank = False, True
            continue
        if fence:
            out.append(line)
            if s and set(s) == {fence[0]} and len(s) >= len(fence):
                fence = None
            prev_blank = False
            continue
        if in_comment:
            out.append(line)
            in_comment = "-->" not in line
            continue
        if in_math:
            out.append(line)
            in_math = "$$" not in s
            continue

        indented = line[:1] in (" ", "\t")
        is_list = bool(_LIST_RE.match(s)) and not indented
        if s and not indented and not is_list:
            in_list = False
        block_start = (prev_blank and s and not indented and div_depth == 0
                       and not (s.startswith(":") and not s.startswith(":::"))
                       and not (is_list and in_list))
        if block_start:
            out += [f'<div class="qgui-line" data-line="{i}"></div>', ""]
        out.append(line)

        m = _FENCE_RE.match(s) if not indented else None
        if m:
            fence = m.group(1)
        elif s.startswith("<!--") and "-->" not in s[4:]:
            in_comment = True
        elif s.startswith("$$") and s.count("$$") == 1:
            in_math = True
        elif _DIV_CLOSE_RE.match(s):
            div_depth = max(0, div_depth - 1)
        elif _DIV_OPEN_RE.match(s):
            div_depth += 1
        if is_list:
            in_list = True
        prev_blank = not s
    return "\n".join(out)


def preview_pandoc(src: Path, content: str) -> dict:
    """Rýchly HTML náhľad cez pandoc (bez vykonávania kódu)."""
    exe = _which("pandoc")
    if not exe:
        return {"ok": False, "log": "Pandoc nie je nainštalovaný – rýchly náhľad nie je dostupný."}
    # Quarto bloky ```{python} → ```python, aby ich pandoc zvýraznil ako kód.
    text = _CHUNK_RE.sub(lambda m: "```" + m.group(1), add_line_markers(content))
    cmd = [exe, "-f", "markdown", "-t", "html5", "-s", f"--mathjax={MATHJAX_URL}",
           "--resource-path", str(src.parent), "--metadata", f"pagetitle={src.stem}"]
    try:
        res = _run(cmd, input=text, cwd=src.parent, timeout=60)
    except subprocess.TimeoutExpired:
        return {"ok": False, "log": "Náhľad prekročil časový limit."}
    return {"ok": res.returncode == 0, "html": _POLYFILL_RE.sub("", res.stdout), "log": res.stderr}


_YAML_FORMAT_RE = re.compile(r"^format:[ \t]*(\S*)[ \t]*$", re.M)
_YAML_SUBKEY_RE = re.compile(r"^[ \t]+([\w-]+):", re.M)


def _yaml_first_format(content: str) -> str:
    """Prvý formát z YAML hlavičky (format: pdf / format:\n  pdf: ...); inak ""."""
    m = re.match(r"^---\s*\n(.*?)\n(---|\.\.\.)\s*$", content, re.S | re.M)
    if not m:
        return ""
    yaml = m.group(1)
    f = _YAML_FORMAT_RE.search(yaml)
    if not f:
        return ""
    if f.group(1):
        return f.group(1).strip("\"'")
    sub = _YAML_SUBKEY_RE.search(yaml, f.end())
    return sub.group(1) if sub else ""


def _hide(path: Path) -> None:
    """Na Windows označí súbor ako skrytý (dočasné súbory náhľadu v Prieskumníkovi)."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x02)
        except Exception:
            pass


PREVIEWABLE = {"pdf", "beamer", "typst", "html", "revealjs"}


def preview_real(src: Path, content: str, settings: dict, out_dir: Path) -> dict:
    """Skutočný náhľad podľa profilu (PDF/HTML) do dočasného priečinka out_dir.

    Výstup sa nezapisuje do priečinka používateľa: zdroj sa dočasne uloží ako skrytý
    súbor vedľa originálu (kvôli relatívnym cestám k obrázkom a bibliografii) a hotový
    výstup sa presunie do out_dir. Formáty, ktoré prehliadač nezobrazí (DOCX…), sa
    v náhľade nahradia HTML.
    """
    s = merged(settings)
    fmt = (s["format"] or "").strip() or _yaml_first_format(content) or "html"
    note = ""
    if fmt not in PREVIEWABLE:
        note = f"Formát „{fmt}“ sa nedá zobraziť v prehliadači – náhľad je v HTML."
        fmt = "html"
    if s["engine"] == "pandoc" and fmt == "typst":
        fmt, s["pdf_engine"] = "pdf", "typst"
    is_html = fmt in ("html", "revealjs")
    s["format"] = fmt
    s["output_dir"] = str(out_dir)
    if is_html:
        if s["engine"] == "pandoc":
            s["extra_args"] = (s["extra_args"] + " --embed-resources --standalone").strip()
        else:
            s["metadata"] = (s["metadata"] + "\nembed-resources=true").strip()

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.iterdir():  # ponechať iba posledný náhľad
        shutil.rmtree(old, ignore_errors=True) if old.is_dir() else old.unlink(missing_ok=True)

    tmp = src.parent / f".qgui-preview-{os.getpid()}-{int(time.time() * 1000)}{src.suffix}"
    try:
        tmp.write_text(add_line_markers(content) if is_html else content, encoding="utf-8")
        _hide(tmp)
        res = render(tmp, s)
    finally:
        for leftover in src.parent.glob(tmp.stem + "*"):  # .tex, _files, .log …
            shutil.rmtree(leftover, ignore_errors=True) if leftover.is_dir() else leftover.unlink(missing_ok=True)
    outputs = [Path(o) for o in res.get("outputs", []) if Path(o).parent == out_dir]
    want = (".html",) if is_html else (".pdf",)
    out = next((o for o in outputs if o.suffix.lower() in want), None)
    if not res["ok"] or not out:
        log = res.get("log", "") or "Náhľad sa nepodarilo vytvoriť."
        return {"ok": False, "log": log, "note": note, **diagnose(log)}
    result = {"ok": True, "kind": "html" if is_html else "pdf", "file": out.name,
              "seconds": res.get("seconds"), "note": note, "log": res.get("log", "")}
    if is_html:
        result["html"] = out.read_text(encoding="utf-8", errors="replace")
    return result
