"""Spúšťač Quarto Studio bez konzolového okna (Windows: pyw.exe / pythonw.exe).

Použitie: pyw qgui_start.pyw [PRIEČINOK | SÚBOR.md | SÚBOR.qmd]
Funguje bez ohľadu na aktuálny priečinok, preto ho používa aj asociácia súborov.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qgui.__main__ import main  # noqa: E402

main()
