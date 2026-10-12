"""Spustenie: python -m qgui [PRIEČINOK] [--port 8765] [--no-browser]"""

import argparse
import threading
import webbrowser
from pathlib import Path

from .server import make_server


def main() -> None:
    ap = argparse.ArgumentParser(prog="qgui", description="GUI pre Markdown/Quarto: úpravy, náhľad, render do PDF.")
    ap.add_argument("folder", nargs="?", default=".", help="pracovný priečinok (predvolene aktuálny)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="neotvárať prehliadač automaticky")
    args = ap.parse_args()

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        ap.error(f"Priečinok neexistuje: {root}")
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
