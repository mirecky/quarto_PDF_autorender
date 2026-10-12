"""Spustenie: python -m qgui [PRIEČINOK] [--port 8765] [--no-browser]

Bez priečinka sa otvorí dialóg na jeho výber (ak je dostupný tkinter).
"""

from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path

from .server import make_server


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
    start = Path.home() / "Documents"
    chosen = filedialog.askdirectory(
        title="Quarto Studio – vyber priečinok s dokumentmi",
        initialdir=str(start if start.is_dir() else Path.home()),
        mustexist=True,
    )
    win.destroy()
    return chosen or None


def main() -> None:
    ap = argparse.ArgumentParser(prog="qgui", description="GUI pre Markdown/Quarto: úpravy, náhľad, render do PDF.")
    ap.add_argument("folder", nargs="?", help="pracovný priečinok (bez neho sa otvorí dialóg na výber)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="neotvárať prehliadač automaticky")
    args = ap.parse_args()

    folder = args.folder or pick_folder()
    if not folder:
        ap.error("Nebol zvolený pracovný priečinok.")
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        ap.error(f"Priečinok neexistuje: {root}\n"
                 f"Tip: spusti qgui bez cesty a priečinok vyber v dialógovom okne.")
    srv = make_server(root, args.host, args.port)
    url = f"http://{args.host}:{srv.server_address[1]}/"
    print(f"qgui beží na {url}  (pracovný priečinok: {root})\nUkončenie: Ctrl+C")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nUkončené.")


if __name__ == "__main__":
    main()
