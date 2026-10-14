"""Šablóny nových dokumentov a projektov (Quarto/Markdown)."""

from __future__ import annotations

import datetime
from pathlib import Path

# kľúč -> (popis, prípona, obsah). {title} a {date} sa doplnia pri vytvorení.
DOCUMENTS: dict[str, tuple[str, str, str]] = {
    "qmd": ("Dokument Quarto", ".qmd", """---
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
"""),
    "md": ("Dokument Markdown (Pandoc)", ".md", """---
title: "{title}"
author: ""
date: "{date}"
lang: sk
---

# Úvod

Text dokumentu.
"""),
    "revealjs": ("Prezentácia Reveal.js (HTML)", ".qmd", """---
title: "{title}"
subtitle: ""
author: ""
date: today
lang: sk
format:
  revealjs:
    theme: simple
    slide-number: true
    footer: "{title}"
    incremental: false
---

## Úvod

- Prvý bod
- Druhý bod
- Tretí bod

## Dva stĺpce

:::: {{.columns}}
::: {{.column width="50%"}}
Ľavý stĺpec
:::
::: {{.column width="50%"}}
Pravý stĺpec
:::
::::

## Postupné odkrývanie

::: {{.incremental}}
- Zobrazí sa najprv
- Potom toto
:::

## Záver

Ďakujem za pozornosť.

::: {{.notes}}
Poznámky pre prednášajúceho (kláves S).
:::
"""),
    "beamer": ("Prezentácia Beamer (PDF)", ".qmd", """---
title: "{title}"
subtitle: ""
author: ""
institute: ""
date: today
lang: sk
format:
  beamer:
    theme: Madrid
    colortheme: default
    aspectratio: 169
    navigation: horizontal
---

## Úvod

- Prvý bod
- Druhý bod

## Dva stĺpce

:::: {{.columns}}
::: {{.column width="50%"}}
Ľavý stĺpec
:::
::: {{.column width="50%"}}
Pravý stĺpec
:::
::::

## Záver

Ďakujem za pozornosť.
"""),
    "pptx": ("Prezentácia PowerPoint (PPTX)", ".qmd", """---
title: "{title}"
subtitle: ""
author: ""
date: today
lang: sk
format:
  pptx:
    slide-level: 2
    # reference-doc: sablona.pptx   # vlastná predloha PowerPointu
---

## Úvod

- Prvý bod
- Druhý bod

## Dva stĺpce

:::: {{.columns}}
::: {{.column}}
Ľavý stĺpec
:::
::: {{.column}}
Pravý stĺpec
:::
::::

## Záver

Ďakujem za pozornosť.

::: {{.notes}}
Poznámky pre prednášajúceho.
:::
"""),
    "dashboard": ("Dashboard (HTML)", ".qmd", """---
title: "{title}"
author: ""
lang: sk
format: dashboard
---

## Riadok {{height=40%}}

::: {{.card title="Prehľad"}}
Stručný opis stavu. Karty sa skladajú do riadkov a stĺpcov podľa nadpisov `##`.
:::

::: {{.card title="Poznámky"}}
- Prvá poznámka
- Druhá poznámka
:::

## Riadok {{height=60%}}

::: {{.card title="Tabuľka"}}
| Ukazovateľ | Hodnota |
|:-----------|--------:|
| A          | 12      |
| B          | 7       |
:::
"""),
}

# Projekty: kľúč -> (popis, hlavný súbor, {cesta: obsah})
PROJECTS: dict[str, tuple[str, str, dict[str, str]]] = {
    "website": ("Webová stránka (projekt)", "index.qmd", {
        "_quarto.yml": """project:
  type: website

lang: sk

website:
  title: "{title}"
  navbar:
    left:
      - href: index.qmd
        text: Domov
      - href: about.qmd
        text: O projekte

format:
  html:
    theme: cosmo
    css: styles.css
    toc: true
""",
        "index.qmd": """---
title: "{title}"
---

Úvodná stránka webu. Ďalšie stránky pridáš ako súbory `.qmd`
a do navigácie ich zapíšeš v `_quarto.yml`.
""",
        "about.qmd": """---
title: "O projekte"
---

Informácie o projekte.
""",
        "styles.css": "/* vlastné štýly webu */\n",
    }),
    "book": ("Kniha (projekt)", "index.qmd", {
        "_quarto.yml": """project:
  type: book

lang: sk

book:
  title: "{title}"
  author: ""
  date: today
  chapters:
    - index.qmd
    - uvod.qmd
    - zaver.qmd
    - literatura.qmd

bibliography: literatura.bib

format:
  html:
    theme: cosmo
  pdf:
    documentclass: scrreprt
    papersize: a4
""",
        "index.qmd": """# Predhovor {.unnumbered}

Úvodné slovo ku knihe.
""",
        "uvod.qmd": """# Úvod

Text prvej kapitoly. Citácia: [@knuth1984].
""",
        "zaver.qmd": """# Záver

Zhrnutie.
""",
        "literatura.qmd": """# Literatúra {.unnumbered}

::: {#refs}
:::
""",
        "literatura.bib": """@article{knuth1984,
  author  = {Knuth, Donald E.},
  title   = {Literate Programming},
  journal = {The Computer Journal},
  volume  = {27},
  number  = {2},
  pages   = {97--111},
  year    = {1984}
}
""",
    }),
}


def catalog() -> list[dict]:
    """Zoznam typov pre dialóg „Nový“."""
    items = [{"key": k, "label": v[0], "ext": v[1], "project": False} for k, v in DOCUMENTS.items()]
    items += [{"key": k, "label": v[0], "ext": "", "project": True} for k, v in PROJECTS.items()]
    return items


def _fill(text: str, title: str) -> str:
    return text.format(title=title.replace('"', "'"), date=datetime.date.today().strftime("%d. %m. %Y"))


def create(target: Path, kind: str) -> Path:
    """Vytvorí dokument alebo projekt; vráti cestu k súboru, ktorý sa má otvoriť."""
    if kind in PROJECTS:
        _, main, files = PROJECTS[kind]
        if target.exists() and any(target.iterdir()):
            raise FileExistsError("Priečinok projektu už existuje a nie je prázdny.")
        target.mkdir(parents=True, exist_ok=True)
        title = target.name.replace("-", " ").replace("_", " ").strip().capitalize()
        for rel, content in files.items():
            # súbory projektu nie sú formátovacie reťazce okrem {title}
            text = content.replace("{title}", title.replace('"', "'"))
            (target / rel).write_text(text, encoding="utf-8")
        return target / main
    _, ext, content = DOCUMENTS.get(kind, DOCUMENTS["qmd"])
    if target.suffix.lower() != ext:
        target = target.with_name(target.name + ext) if not target.suffix else target.with_suffix(ext)
    if target.exists():
        raise FileExistsError("Súbor už existuje.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_fill(content, target.stem), encoding="utf-8")
    return target
