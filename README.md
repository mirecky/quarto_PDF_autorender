# Quarto Studio (`qgui`)

Lokálne grafické rozhranie na úpravu súborov Markdown (`.md`) a Quarto (`.qmd`, `.Rmd`),
ich priebežný náhľad a renderovanie prostredníctvom nástrojov **Quarto** alebo **Pandoc**
do formátov PDF, HTML, DOCX, ODT, EPUB, PPTX, Reveal.js, Beamer, LaTeX a Typst.

Aplikácia je napísaná výlučne v štandardnej knižnici Pythonu (bez externých závislostí);
používateľské rozhranie beží v ľubovoľnom webovom prehliadači a komunikuje s lokálnym
serverom na adrese `127.0.0.1`. Editor (CodeMirror 5) je súčasťou repozitára, preto
rozhranie funguje aj bez pripojenia na internet.

## Požiadavky

| Komponent | Účel | Poznámka |
|:--|:--|:--|
| Python ≥ 3.9 | beh aplikácie | bez ďalších balíkov |
| Quarto (odporúčané ≥ 1.4) | render `.qmd`, plný náhľad | obsahuje vlastný Pandoc aj Typst |
| Pandoc | rýchly náhľad, render bez Quarta | |
| TinyTeX / TeX Live | PDF cez LaTeX (`xelatex`, `lualatex`, `pdflatex`) | `quarto install tinytex` |

Dostupnosť nástrojov a PDF enginov sa zobrazuje v pravom hornom rohu rozhrania.

## Spustenie

```bash
# priamo z repozitára
./qgui.sh ~/Dokumenty/praca          # Linux / macOS
qgui.bat C:\Users\ja\Dokumenty\praca  # Windows

# alebo inštalácia ako príkaz
pip install -e .
qgui ~/Dokumenty/praca --port 8765
```

Prehliadač sa otvorí automaticky (`--no-browser` to potlačí). Argument určuje
**pracovný priečinok** – aplikácia pristupuje výhradne k súborom v ňom.

## Funkcie

**Editor.** Zvýraznenie syntaxe Markdownu, YAML hlavičky a blokov kódu; vyhľadávanie
(`Ctrl+F`); automatické pokračovanie zoznamov; panel na vkladanie bežných konštrukcií
(nadpis, zvýraznenie, odkaz, obrázok s krížovým odkazom, tabuľka s popisom, rovnica,
citácia, poznámka pod čiarou, Quarto callout, blok kódu, zlom strany).

**Správa súborov.** Strom pracovného priečinka, vytvorenie súboru (so vzorovou YAML
hlavičkou) alebo priečinka; premenovanie a zmazanie cez kontextovú ponuku (pravé tlačidlo).

**Náhľad.**

- *rýchly (Pandoc)* – aktualizuje sa počas písania, nevykonáva kód; Quarto-špecifické
  prvky (callouty, krížové odkazy `@fig-…`) sa nespracujú;
- *plný (Quarto HTML)* – aktualizuje sa pri uložení, zodpovedá skutočnému výstupu Quarta.

**Render.** Výstup sa ukladá do priečinka `_output/` vedľa zdrojového súboru (nastaviteľné)
a zobrazí sa na záložke *Výstup* – PDF priamo vo vstavanom prehliadači PDF. Úplný výpis
príkazu a jeho výstupu je na záložke *Log*. Voľba **auto-render** spúšťa render po každom
uložení.

**Profily renderu.** Nastavenia (nástroj, formát, PDF engine, obsah, číslovanie kapitol,
bibliografia a citačný štýl, jazyk, papier, písmo, okraje, šablóna, referenčný dokument,
ľubovoľné metadáta a ďalšie argumenty) sa ukladajú ako pomenované profily do súboru
`.qgui.json` v pracovnom priečinku. Dialóg nastavení priebežne zobrazuje výsledný príkaz.

Prázdne pole alebo nezaškrtnutá voľba znamená, že sa **nepreberá** z GUI a platí hodnota
z YAML hlavičky dokumentu. Formát „(podľa YAML)“ spustí `quarto render` bez `--to`, teda
vyrenderuje všetky formáty uvedené v dokumente.

### Klávesové skratky

| Skratka | Akcia |
|:--|:--|
| `Ctrl+S` | uložiť |
| `Ctrl+Enter` | renderovať aktívnym profilom |
| `Ctrl+B` / `Ctrl+I` | tučné / kurzíva |
| `Ctrl+F` | hľadať v dokumente |
| `Ctrl+Shift+P` | obnoviť náhľad |

## Poznámky k implementácii

- Quarto sa spúšťa bez prepínača `--output-dir`, pretože ten pri samostatných súboroch
  vyprázdňuje cieľový priečinok; výstupy (vrátane pomocného priečinka `*_files` pri HTML)
  presúva aplikácia. Ak súbor patrí do Quarto projektu (`_quarto.yml`), umiestnenie
  výstupov určuje konfigurácia projektu.
- Server počúva len na `127.0.0.1`, odmieta cesty mimo pracovného priečinka a zápisové
  požiadavky z cudzieho originu.
- Cesty k nástrojom možno vynútiť premennými prostredia `QGUI_QUARTO` a `QGUI_PANDOC`.
- Typst pri prvom použití niektorých funkcií (napr. ikony v calloutoch) sťahuje balíky
  z `packages.typst.org`; bez internetu môže render zlyhať.

## Testy

```bash
python3 -m unittest -v
```

## Štruktúra

```
qgui/
  __main__.py     spúšťač (CLI)
  server.py       HTTP server a API
  render.py       zostavenie príkazov Quarto/Pandoc, render a náhľad
  static/         rozhranie (HTML, CSS, JS, CodeMirror 5 – licencia MIT)
examples/         ukážkový dokument s bibliografiou
tests/            jednotkové testy
```
