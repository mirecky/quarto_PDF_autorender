"""Spustenie: python -m qgui [PRIEČINOK] [--port 8765] [--no-browser]

Bez priečinka sa otvorí naposledy použitý; pri prvom spustení (alebo s --choose)
dialóg na jeho výber.
Pri spustení bez konzoly (pythonw, zástupca na ploche) sa výstup zapisuje
do ~/.qgui/qgui.log a chyby sa zobrazia v dialógovom okne.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import traceback
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from . import desktop
from .server import make_server

LOG_FILE = Path.home() / ".qgui" / "qgui.log"
WINDOWLESS = sys.stdout is None or sys.stderr is None  # pythonw.exe nemá konzolu


def _setup_log() -> None:
    if WINDOWLESS:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fh = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = fh


def message(text: str, error: bool = True) -> None:
    """Hláška do konzoly; bez konzoly do dialógového okna."""
    print(text, file=sys.stderr)
    if not WINDOWLESS:
        return
    try:
        import tkinter as tk
        from tkinter import messagebox

        win = tk.Tk()
        win.withdraw()
        win.attributes("-topmost", True)
        (messagebox.showerror if error else messagebox.showinfo)("Quarto Studio", text, parent=win)
        win.destroy()
    except Exception:
        pass


def find_running(host: str, port: int, file: Path) -> str | None:
    """URL bežiacej inštancie, ktorej pracovný priečinok obsahuje súbor (s ?open=...)."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # localhost nikdy cez proxy
    for p in range(port, port + 20):
        try:
            with opener.open(f"http://{host}:{p}/api/info", timeout=0.3) as r:
                info = json.loads(r.read().decode("utf-8"))
        except (OSError, ValueError):
            continue
        root = Path(info.get("root") or "")
        if info.get("ok") and root.is_dir() and (root == file.parent or root in file.parents):
            rel = file.relative_to(root).as_posix()
            return f"http://{host}:{p}/?open=" + urllib.parse.quote(rel)
    return None


def run() -> int:
    ap = argparse.ArgumentParser(prog="qgui", description="GUI pre Markdown/Quarto: úpravy, náhľad, render do PDF.")
    ap.add_argument("folder", nargs="?",
                    help="pracovný priečinok alebo súbor .md/.qmd na otvorenie (predvolene naposledy použitý priečinok)")
    ap.add_argument("--choose", action="store_true", help="vždy zobraziť dialóg na výber priečinka")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="neotvárať prehliadač automaticky")
    args, unknown = ap.parse_known_args()
    if unknown:
        print(f"Ignorované neznáme argumenty: {' '.join(unknown)}", file=sys.stderr)

    folder = args.folder
    open_rel = None
    if folder and Path(folder).expanduser().is_file():
        # Otvorenie konkrétneho súboru (dvojklik v Prieskumníkovi / „Otvoriť pomocou“).
        file = Path(folder).expanduser().resolve()
        running = find_running(args.host, args.port, file)
        if running:
            webbrowser.open(running)
            print(f"Súbor otvorený v bežiacej inštancii: {running}")
            return 0
        folder, open_rel = str(file.parent), file.name
    if not folder and not args.choose:
        folder = desktop.last_folder()
    if not folder:
        folder = desktop.pick_folder(desktop.last_folder())
    if not folder and not WINDOWLESS and not args.choose:
        folder = "."  # konzola bez GUI → aktuálny priečinok
    if not folder:
        print("Nebol zvolený pracovný priečinok – koniec.", file=sys.stderr)
        return 1
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        message(f"Priečinok neexistuje:\n{root}\n\nTip: priečinok vyber v dialógovom okne (qgui --choose).")
        return 2
    srv = None
    for port in range(args.port, args.port + 20):  # obsadený port → skúsiť ďalší
        try:
            srv = make_server(root, args.host, port)
            break
        except OSError:
            continue
    if srv is None:
        message(f"Porty {args.port}–{args.port + 19} sú obsadené.")
        return 3
    desktop.remember_folder(root)
    url = f"http://{args.host}:{srv.server_address[1]}/"
    open_url = url + ("?open=" + urllib.parse.quote(open_rel) if open_rel else "")
    print(f"qgui beží na {url}  (pracovný priečinok: {root})\n"
          f"Ukončenie: tlačidlo „Ukončiť“ v aplikácii alebo Ctrl+C")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(open_url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Ukončené.")
    return 0


def main() -> None:
    _setup_log()
    try:
        code = run()
    except SystemExit as exc:  # argparse --help / chybné argumenty
        code = exc.code if isinstance(exc.code, int) else 1
    except Exception:
        traceback.print_exc()
        message(f"Quarto Studio sa nepodarilo spustiť:\n\n{traceback.format_exc(limit=3)}\n"
                f"Podrobnosti: {LOG_FILE}")
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
