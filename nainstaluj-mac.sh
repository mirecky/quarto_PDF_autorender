#!/bin/bash
# Inštalácia Quarto Studio na macOS – zistí, čo chýba, a doinštaluje to:
#   1. Xcode Command Line Tools (git, python3)
#   2. Quarto (oficiálny balík .pkg)
#   3. TinyTeX (LaTeX pre PDF)
#   4. repozitár Quarto Studio (~/quarto_PDF_autorender) – stiahne alebo aktualizuje
#   5. aplikáciu „Quarto Studio.app“ (vytvor-mac-aplikaciu.sh)
#
# Spustenie (Terminál):
#   curl -fsSL https://raw.githubusercontent.com/mirecky/quarto_PDF_autorender/main/nainstaluj-mac.sh | bash
set -euo pipefail

REPO_URL="https://github.com/mirecky/quarto_PDF_autorender.git"
REPO_DIR="${QGUI_DIR:-$HOME/quarto_PDF_autorender}"
QUARTO_FALLBACK="1.8.27"

ok()   { printf '  \033[32m✔\033[0m %s\n' "$1"; }
info() { printf '\n\033[1m%s\033[0m\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }

[ "$(uname)" = "Darwin" ] || { echo "Tento skript je iba pre macOS."; exit 1; }
export PATH="/Applications/quarto/bin:/opt/homebrew/bin:/usr/local/bin:/Library/TeX/texbin:$HOME/Library/TinyTeX/bin/universal-darwin:$PATH"

# ---------------------------------------------------------------- 1. nástroje pre vývojárov
info "1/5 Xcode Command Line Tools (git, python3)"
if xcode-select -p >/dev/null 2>&1 && command -v git >/dev/null; then
  ok "nainštalované"
else
  warn "chýbajú – otvára sa inštalátor macOS. Dokonči inštaláciu v okne, ktoré sa zobrazí,"
  warn "a potom tento príkaz spusti znova."
  xcode-select --install 2>/dev/null || true
  exit 1
fi

PY=""
for c in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -x "$c" ] && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then PY="$c"; break; fi
done
if [ -n "$PY" ]; then
  ok "Python $("$PY" -c 'import sys; print(sys.version.split()[0])') ($PY)"
else
  warn "Python 3.9+ sa nenašiel. Nainštaluj ho z https://www.python.org/downloads/macos/ a spusti príkaz znova."
  exit 1
fi

# ---------------------------------------------------------------- 2. Quarto
info "2/5 Quarto"
if command -v quarto >/dev/null; then
  ok "Quarto $(quarto --version)"
else
  latest="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/quarto-dev/quarto-cli/releases/latest 2>/dev/null || true)"
  ver="${latest##*/v}"
  case "$ver" in [0-9]*.[0-9]*) ;; *) ver="$QUARTO_FALLBACK" ;; esac
  pkg="$(mktemp -d)/quarto-$ver-macos.pkg"
  echo "  sťahujem Quarto $ver…"
  curl -fL --progress-bar -o "$pkg" "https://github.com/quarto-dev/quarto-cli/releases/download/v$ver/quarto-$ver-macos.pkg"
  echo "  inštalujem (macOS si vypýta heslo správcu)…"
  sudo installer -pkg "$pkg" -target /
  rm -f "$pkg"
  command -v quarto >/dev/null && ok "Quarto $(quarto --version)" || { warn "Quarto sa nepodarilo nainštalovať."; exit 1; }
fi

# ---------------------------------------------------------------- 3. TinyTeX
info "3/5 LaTeX (TinyTeX) pre PDF"
if command -v xelatex >/dev/null || [ -d "$HOME/Library/TinyTeX" ]; then
  ok "nainštalovaný"
else
  echo "  inštalujem TinyTeX (niekoľko minút)…"
  quarto install tinytex --no-prompt || warn "TinyTeX sa nepodarilo nainštalovať – PDF cez Typst bude fungovať aj tak."
  [ -d "$HOME/Library/TinyTeX" ] && ok "nainštalovaný"
fi

# ---------------------------------------------------------------- 4. Quarto Studio
info "4/5 Quarto Studio ($REPO_DIR)"
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" checkout -q main 2>/dev/null || true
  git -C "$REPO_DIR" pull -q --ff-only && ok "aktualizované" || warn "aktualizácia zlyhala (lokálne zmeny?) – pokračujem s existujúcou verziou"
else
  git clone -q "$REPO_URL" "$REPO_DIR" && ok "stiahnuté"
fi

# ---------------------------------------------------------------- 5. aplikácia
info "5/5 Aplikácia Quarto Studio.app"
bash "$REPO_DIR/vytvor-mac-aplikaciu.sh"

info "Všetko je pripravené."
echo "  Spusti Quarto Studio z Launchpadu alebo z ~/Applications a pretiahni ho do Docku."
open "$HOME/Applications" 2>/dev/null || true
