"""Používateľská konfigurácia (naposledy otvorené priečinky) a dialóg na výber priečinka."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

CONFIG_DIR = Path.home() / ".qgui"
CONFIG_FILE = CONFIG_DIR / "config.json"
# Aktuálny priečinok + 5 predošlých (v okne sa zobrazí 5). Poradie podľa posledného
# použitia: otvorený priečinok ide navrch, najstarší vypadne.
MAX_RECENT = 6

_dialog_lock = threading.Lock()


def load_config() -> dict:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(data: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def recent_folders() -> list[str]:
    """Nedávne priečinky (najnovší prvý), iba tie, ktoré ešte existujú."""
    return [f for f in load_config().get("recent", []) if Path(f).is_dir()][:MAX_RECENT]


def last_folder() -> str | None:
    recent = recent_folders()
    return recent[0] if recent else None


def remember_folder(folder: Path) -> None:
    folder_s = str(Path(folder).resolve())
    cfg = load_config()
    recent = [f for f in cfg.get("recent", []) if f != folder_s]
    # neexistujúce priečinky sa pri aktualizácii zabudnú, aby nezaberali miesto
    cfg["recent"] = [folder_s, *[f for f in recent if Path(f).is_dir()]][:MAX_RECENT]
    save_config(cfg)


def forget_folder(folder: str) -> None:
    cfg = load_config()
    cfg["recent"] = [f for f in cfg.get("recent", []) if f != folder]
    save_config(cfg)


def _applescript_str(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _pick_folder_macos(start: Path) -> str | None:
    """Natívny výber priečinka na macOS (AppleScript) – funguje z ľubovoľného vlákna,
    na rozdiel od tkinteru, ktorý na macOS smie bežať iba v hlavnom vlákne."""
    script = ("activate\n"
              f"set f to choose folder with prompt {_applescript_str('Quarto Studio – vyber priečinok s dokumentmi')}"
              f" default location (POSIX file {_applescript_str(start)})\n"
              "POSIX path of f")
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        return None
    chosen = r.stdout.strip().rstrip("/")
    if r.returncode != 0 or not chosen:  # zrušené (Cancel) alebo chyba
        return None
    return chosen


def show_message_macos(text: str, error: bool = True) -> None:
    script = (f"display dialog {_applescript_str(text)} with title {_applescript_str('Quarto Studio')}"
              f" buttons {{\"OK\"}} default button 1 with icon {'stop' if error else 'note'}")
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        pass


def pick_folder(initial: str | Path | None = None) -> str | None:
    """Grafický výber priečinka (macOS: AppleScript, inak tkinter). None pri zrušení."""
    if sys.platform == "darwin":
        start = Path(initial) if initial else Path.home() / "Documents"
        return _pick_folder_macos(start if start.is_dir() else Path.home())
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None
    with _dialog_lock:  # naraz najviac jeden dialóg
        try:
            win = tk.Tk()
        except tk.TclError:  # bez grafického prostredia
            return None
        try:
            win.withdraw()
            win.attributes("-topmost", True)
            # Pri spustení z minimalizovaného okna by sa dialóg mohol skryť na lište.
            win.lift()
            win.focus_force()
            win.update()
            start = Path(initial) if initial else Path.home() / "Documents"
            if not start.is_dir():
                start = Path.home()
            chosen = filedialog.askdirectory(
                parent=win,
                title="Quarto Studio – vyber priečinok s dokumentmi",
                initialdir=str(start),
                mustexist=True,
            )
        finally:
            win.destroy()
    return chosen or None
