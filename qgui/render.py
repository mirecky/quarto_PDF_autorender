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


def render(src: Path, settings: dict) -> dict:
    s = merged(settings)
    cmd, out_dir = build_command(src, s)
    project = find_project(src) if s["engine"] != "pandoc" else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    start = time.time()
    try:
        res = _run(cmd, cwd=src.parent, timeout=int(s["timeout"] or 600))
        code, log = res.returncode, (res.stdout or "") + (res.stderr or "")
    except FileNotFoundError:
        return {"ok": False, "cmd": cmd, "log": f"Program sa nenašiel: {cmd[0]}", "outputs": []}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "cmd": cmd, "log": f"Prekročený časový limit ({exc.timeout} s).", "outputs": []}

    if project:
        outputs = _find_project_outputs(project, src, start)
    else:
        outputs = _find_outputs(src, [d for d in {out_dir, src.parent} if d], start)
        fmt = (s["format"] or "").strip()
        if fmt:  # ponechať iba prípony zodpovedajúce zvolenému formátu
            wanted = {FORMAT_EXT.get(fmt, fmt)} | ({"pdf"} if fmt in PDF_FORMATS else set())
            outputs = [p for p in outputs if p.suffix.lstrip(".") in wanted]
        if code == 0 and out_dir and out_dir != src.parent:
            moved = []
            for p in outputs:
                moved.append(_move(p, out_dir) if p.parent == src.parent else p)
            # Pomocné súbory HTML výstupu (obrázky, knižnice) musia ísť spolu s ním.
            files_dir = src.parent / f"{src.stem}_files"
            if any(p.suffix == ".html" for p in moved) and files_dir.is_dir():
                _move(files_dir, out_dir)
            outputs = moved
    return {
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


def preview_quarto(src: Path, content: str) -> dict:
    """Plný Quarto HTML náhľad (vykoná kód, callouty, crossref...)."""
    exe = _which("quarto")
    if not exe:
        return {"ok": False, "log": "Quarto nie je nainštalované."}
    fd, tmp_name = tempfile.mkstemp(prefix=".qgui-preview-", suffix=".qmd", dir=src.parent)
    tmp = Path(tmp_name)
    html = tmp.with_suffix(".html")
    files_dir = tmp.parent / f"{tmp.stem}_files"
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(add_line_markers(content))
        cmd = [exe, "render", tmp.name, "--to", "html", "-M", "embed-resources:true",
               "-M", "toc:true", "--quiet"]
        res = _run(cmd, cwd=src.parent, timeout=300)
        if res.returncode != 0 or not html.exists():
            return {"ok": False, "log": res.stdout + res.stderr}
        return {"ok": True, "html": html.read_text(encoding="utf-8"), "log": res.stderr}
    except subprocess.TimeoutExpired:
        return {"ok": False, "log": "Quarto náhľad prekročil časový limit."}
    finally:
        for p in (tmp, html):
            p.unlink(missing_ok=True)
        shutil.rmtree(files_dir, ignore_errors=True)
