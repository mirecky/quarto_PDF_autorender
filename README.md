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

Najprv si stiahni repozitár (kým nie je PR zlúčený, z vetvy `claude/bold-lamport-ag0660`):

```bash
git clone -b claude/bold-lamport-ag0660 https://github.com/mirecky/quarto_PDF_autorender.git
cd quarto_PDF_autorender
```

**Windows (PowerShell):**

```powershell
.\qgui.ps1            # bez cesty: otvorí sa okno na výber priečinka
.\qgui.ps1 C:\Users\ja\Documents\praca
# ak PowerShell blokuje skripty:
powershell -ExecutionPolicy Bypass -File .\qgui.ps1 C:\Users\ja\Documents\praca
# alternatívne (PowerShell aj cmd):
.\qgui.bat C:\Users\ja\Documents\praca
```

**Zástupca na ploche (Windows):**

```powershell
powershell -ExecutionPolicy Bypass -File .\vytvor-zastupcu.ps1
# s pevne zvoleným priečinkom a vlastným názvom:
powershell -ExecutionPolicy Bypass -File .\vytvor-zastupcu.ps1 -Name "Diplomovka" -Folder "C:\Users\Admin\Documents\diplomovka"
```

Zástupca spúšťa Python bez konzolového okna (`pyw`/`pythonw`); aplikácia sa ukončí
tlačidlom **⏻ Ukončiť** v rozhraní. Výstup servera a prípadné chyby sa zapisujú do
`%USERPROFILE%\.qgui\qgui.log`; chyba pri spustení sa navyše zobrazí v dialógovom okne.
Na diagnostiku možno vytvoriť zástupcu s konzolou parametrom `-Console`. Pri obsadenom
porte sa automaticky použije nasledujúci voľný.

Zástupca používa ikonu `assets/quarto.ico` (alternatíva: `assets/qgui.ico`); vlastnú ikonu nastavíš parametrom
`-Icon "C:\cesta\ikona.ico"`. Konverzia SVG na ICO (napr. cez ImageMagick,
`winget install ImageMagick.ImageMagick`):

```powershell
magick ikona.svg -background none -define icon:auto-resize=256,128,64,48,32,24,16 ikona.ico
```

**Linux / macOS:**

```bash
./qgui.sh ~/Dokumenty/praca
```

**Ako príkaz `qgui` (všetky systémy):**

```bash
pip install -e .
qgui ~/Dokumenty/praca --port 8765
```

Prehliadač sa otvorí automaticky (`--no-browser` to potlačí). Argument určuje
**pracovný priečinok** – aplikácia pristupuje výhradne k súborom v ňom. Ak ho
neuvedieš, otvorí sa naposledy použitý priečinok; pri prvom spustení (alebo s prepínačom
`--choose`) sa zobrazí dialóg na jeho výber. Za behu sa priečinok mení tlačidlom
**📂 názov priečinka** v hornej lište, ktoré ponúka aj zoznam nedávnych priečinkov
(uložený v `~/.qgui/config.json`).

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

**Synchronizované posúvanie.** Editor a náhľad sa posúvajú spolu v oboch smeroch.
Do náhľadu sa pred každý blok textu vkladajú neviditeľné značky s číslom riadku zdroja,
takže zhoda je presná na úrovni odsekov a nadpisov (vypínateľné voľbou *synchr. posúvanie*).

**Autoukladanie.** Súbor sa uloží 1,5 s po poslednej zmene, ako aj pri prepnutí súboru,
priečinka alebo opustení okna. Automatické uloženie nespúšťa render ani plný Quarto
náhľad – tie sa spúšťajú pri ručnom uložení (`Ctrl+S`).

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
