"""Lokálny HTTP server pre GUI (iba štandardná knižnica Pythonu)."""

from __future__ import annotations

import json
import mimetypes
import shutil
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import render as R

STATIC = Path(__file__).parent / "static"
SETTINGS_FILE = ".qgui.json"
EDITABLE = {".md", ".qmd", ".rmd", ".markdown", ".txt", ".yml", ".yaml", ".bib", ".csl",
            ".tex", ".css", ".scss", ".lua", ".json", ".typ", ".html"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".quarto", "renv", ".venv", "venv"}

NEW_FILE_TEMPLATE = """---
title: "{title}"
author: ""
date: today
lang: sk
format:
  pdf:
    toc: true
    number-sections: true
---

# Úvod

Text dokumentu.
"""


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def resolve(self, rel: str) -> Path:
        p = (self.root / (rel or "").lstrip("/")).resolve()
        if p != self.root and self.root not in p.parents:
            raise PermissionError("Cesta mimo pracovného priečinka.")
        return p

    def rel(self, p: Path) -> str:
        return p.resolve().relative_to(self.root).as_posix()

    def lock(self, key: str) -> threading.Lock:
        with self._guard:
            return self.locks.setdefault(key, threading.Lock())

    def tree(self, d: Path | None = None, depth: int = 0) -> list[dict]:
        d = d or self.root
        items = []
        try:
            entries = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return items
        for p in entries:
            if p.name.startswith(".") or p.name in SKIP_DIRS or p.name.endswith("_files"):
                continue
            if p.is_dir():
                if depth < 8:
                    items.append({"name": p.name, "path": self.rel(p), "dir": True,
                                  "children": self.tree(p, depth + 1)})
            else:
                items.append({"name": p.name, "path": self.rel(p), "dir": False,
                              "editable": p.suffix.lower() in EDITABLE})
        return items

    # --- nastavenia (profily) uložené v .qgui.json v koreni pracovného priečinka
    def load_settings(self) -> dict:
        f = self.root / SETTINGS_FILE
        data = {}
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        profiles = data.get("profiles") or {}
        if not profiles:
            profiles = {
                "PDF (Quarto)": R.merged({"engine": "quarto", "format": "pdf"}),
                "PDF (Pandoc, XeLaTeX)": R.merged({"engine": "pandoc", "format": "pdf",
                                                   "pdf_engine": "xelatex"}),
                "HTML (Quarto)": R.merged({"engine": "quarto", "format": "html"}),
                "DOCX (Pandoc)": R.merged({"engine": "pandoc", "format": "docx"}),
                "Podľa YAML (Quarto)": R.merged({"engine": "quarto", "format": ""}),
            }
        profiles = {k: R.merged(v) for k, v in profiles.items()}
        active = data.get("active") if data.get("active") in profiles else next(iter(profiles))
        ui = data.get("ui") or {}
        return {"profiles": profiles, "active": active, "ui": ui, "defaults": R.DEFAULT_SETTINGS}

    def save_settings(self, data: dict) -> None:
        clean = {
            "profiles": {k: R.merged(v) for k, v in (data.get("profiles") or {}).items()},
            "active": data.get("active"),
            "ui": data.get("ui") or {},
        }
        (self.root / SETTINGS_FILE).write_text(json.dumps(clean, ensure_ascii=False, indent=2),
                                               encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    ws: Workspace  # nastavené v make_server
    server_version = "qgui/1.0"

    def log_message(self, fmt, *args):  # tichší log
        if not str(args[0]).startswith(("GET /raw", "GET /static", "POST /api/preview")):
            super().log_message(fmt, *args)

    # ------------------------------------------------------------ pomocné
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _err(self, msg: str, code: int = 400):
        self._json({"ok": False, "error": msg}, code)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def _file(self, p: Path, download: bool = False):
        if not p.is_file():
            return self._err("Súbor neexistuje.", 404)
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/json", "application/javascript"):
            ctype += "; charset=utf-8"
        disp = ("attachment" if download else "inline") + f"; filename*=UTF-8''{urllib.parse.quote(p.name)}"
        self._send(200, p.read_bytes(), ctype, {"Content-Disposition": disp})

    def _same_origin(self) -> bool:
        # Ochrana proti CSRF z iných webov: povoliť len požiadavky z vlastného originu.
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("Host", "")
        return urllib.parse.urlparse(origin).netloc == host

    # ------------------------------------------------------------ GET
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        path = urllib.parse.unquote(url.path)
        try:
            if path in ("/", "/index.html"):
                return self._file(STATIC / "index.html")
            if path.startswith("/static/"):
                p = (STATIC / path[len("/static/"):]).resolve()
                if STATIC.resolve() not in p.parents:
                    return self._err("Zakázané.", 403)
                return self._file(p)
            if path.startswith("/raw/"):
                return self._file(self.ws.resolve(path[len("/raw/"):]), "download" in q)
            if path == "/api/info":
                return self._json({"ok": True, "root": str(self.ws.root), "tools": R.tool_versions()})
            if path == "/api/tree":
                return self._json({"ok": True, "tree": self.ws.tree()})
            if path == "/api/file":
                p = self.ws.resolve(q.get("path", [""])[0])
                if not p.is_file():
                    return self._err("Súbor neexistuje.", 404)
                return self._json({"ok": True, "path": self.ws.rel(p),
                                   "content": p.read_text(encoding="utf-8", errors="replace"),
                                   "mtime": p.stat().st_mtime})
            if path == "/api/settings":
                return self._json({"ok": True, **self.ws.load_settings()})
            if path == "/api/command":
                p = self.ws.resolve(q.get("path", [""])[0])
                settings = json.loads(q.get("settings", ["{}"])[0])
                cmd, _ = R.build_command(p, settings)
                return self._json({"ok": True, "cmd": cmd})
            return self._err("Nenájdené.", 404)
        except PermissionError as exc:
            return self._err(str(exc), 403)
        except Exception as exc:  # pragma: no cover
            return self._err(f"{type(exc).__name__}: {exc}", 500)

    # ------------------------------------------------------------ POST
    def do_POST(self):
        if not self._same_origin():
            return self._err("Nepovolený origin.", 403)
        path = urllib.parse.urlparse(self.path).path
        try:
            data = self._body()
            ws = self.ws
            if path == "/api/file":
                p = ws.resolve(data["path"])
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(data.get("content", ""), encoding="utf-8")
                return self._json({"ok": True, "mtime": p.stat().st_mtime})
            if path == "/api/new":
                p = ws.resolve(data["path"])
                if p.exists():
                    return self._err("Súbor už existuje.", 409)
                p.parent.mkdir(parents=True, exist_ok=True)
                if data.get("dir"):
                    p.mkdir()
                else:
                    content = data.get("content")
                    if content is None:
                        content = NEW_FILE_TEMPLATE.format(title=p.stem) if p.suffix.lower() in (".md", ".qmd") else ""
                    p.write_text(content, encoding="utf-8")
                return self._json({"ok": True, "path": ws.rel(p)})
            if path == "/api/rename":
                src, dst = ws.resolve(data["path"]), ws.resolve(data["to"])
                if dst.exists():
                    return self._err("Cieľ už existuje.", 409)
                dst.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dst)
                return self._json({"ok": True, "path": ws.rel(dst)})
            if path == "/api/delete":
                p = ws.resolve(data["path"])
                if p == ws.root:
                    return self._err("Koreň nemožno zmazať.", 403)
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                return self._json({"ok": True})
            if path == "/api/settings":
                ws.save_settings(data)
                return self._json({"ok": True})
            if path == "/api/preview":
                p = ws.resolve(data["path"])
                fn = R.preview_quarto if data.get("mode") == "quarto" else R.preview_pandoc
                res = fn(p, data.get("content", ""))
                res["base"] = "/raw/" + urllib.parse.quote(ws.rel(p.parent) + "/" if p.parent != ws.root else "")
                return self._json(res)
            if path == "/api/render":
                p = ws.resolve(data["path"])
                if not p.is_file():
                    return self._err("Súbor neexistuje.", 404)
                lock = ws.lock(str(p))
                if not lock.acquire(blocking=False):
                    return self._err("Tento súbor sa práve renderuje.", 409)
                try:
                    res = R.render(p, data.get("settings") or {})
                finally:
                    lock.release()
                res["outputs"] = [ws.rel(Path(o)) for o in res["outputs"]
                                  if ws.root in Path(o).resolve().parents]
                return self._json(res)
            return self._err("Nenájdené.", 404)
        except PermissionError as exc:
            return self._err(str(exc), 403)
        except (KeyError, ValueError) as exc:
            return self._err(f"Neplatná požiadavka: {exc}")
        except Exception as exc:  # pragma: no cover
            return self._err(f"{type(exc).__name__}: {exc}", 500)


def make_server(root: Path, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    ws = Workspace(root)
    handler = type("BoundHandler", (Handler,), {"ws": ws})
    return ThreadingHTTPServer((host, port), handler)
