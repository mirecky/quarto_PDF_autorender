"""Spustenie: python -m qgui [PRIEČINOK] [--port 8765] [--no-browser]

Bez priečinka sa otvorí dialóg na jeho výber (ak je dostupný tkinter).
Pri spustení bez konzoly (pythonw, zástupca na ploche) sa výstup zapisuje
do ~/.qgui/qgui.log a chyby sa zobrazia v dialógovom okne.
"""

from __future__ import annotations

import argparse
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

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


def pick_folder() -> str | None:
    """Grafický výber priečinka; pri nedostupnom tkinteri vráti aktuálny priečinok."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return "."
    try:
        win = tk.Tk()
    except tk.TclError:  # bez grafického prostredia
        return "."
    win.withdraw()
    win.attributes("-topmost", True)
    # Pri spustení z minimalizovaného okna (zástupca) by sa dialóg mohol skryť na lište.
    win.lift()
    win.focus_force()
    win.update()
    start = Path.home() / "Documents"
    chosen = filedialog.askdirectory(
        parent=win,
        title="Quarto Studio – vyber priečinok s dokumentmi",
        initialdir=str(start if start.is_dir() else Path.home()),
        mustexist=True,
    )
    win.destroy()
    return chosen or None


def run() -> int:
    ap = argparse.ArgumentParser(prog="qgui", description="GUI pre Markdown/Quarto: úpravy, náhľad, render do PDF.")
    ap.add_argument("folder", nargs="?", help="pracovný priečinok (bez neho sa otvorí dialóg na výber)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="neotvárať prehliadač automaticky")
    args, unknown = ap.parse_known_args()
    if unknown:
        print(f"Ignorované neznáme argumenty: {' '.join(unknown)}", file=sys.stderr)

    folder = args.folder or pick_folder()
    if not folder:
        print("Nebol zvolený pracovný priečinok – koniec.", file=sys.stderr)
        return 1
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        message(f"Priečinok neexistuje:\n{root}\n\nTip: spusti Quarto Studio bez cesty "
                f"a priečinok vyber v dialógovom okne.")
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
    url = f"http://{args.host}:{srv.server_address[1]}/"
    print(f"qgui beží na {url}  (pracovný priečinok: {root})\n"
          f"Ukončenie: tlačidlo „Ukončiť“ v aplikácii alebo Ctrl+C")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
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
