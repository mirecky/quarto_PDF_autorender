#!/bin/bash
# Vytvorí aplikáciu „Quarto Studio.app“ pre macOS (spúšťanie z Docku/Launchpadu,
# otváranie súborov .md a .qmd dvojklikom alebo cez „Otvoriť pomocou“).
#
#   ./vytvor-mac-aplikaciu.sh                 # do ~/Applications
#   ./vytvor-mac-aplikaciu.sh /Applications   # do iného priečinka
#
# Aplikácia je malý AppleScript applet: macOS odovzdáva otvorené súbory udalosťou
# (Apple Event), nie parametrom príkazového riadka – applet ju prijme a spustí
# qgui_start.pyw z tohto repozitára. Repozitár preto po vytvorení nepresúvaj.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-$HOME/Applications}"
APP="$DEST/Quarto Studio.app"
BUNDLE_ID="sk.qgui.quartostudio"

[ "$(uname)" = "Darwin" ] || { echo "Tento skript je iba pre macOS."; exit 1; }
command -v osacompile >/dev/null || { echo "Chýba osacompile (súčasť macOS)."; exit 1; }

# Python 3.9+ (prednostne z python.org alebo Homebrew; /usr/bin/python3 je z Xcode CLT)
PY=""
for c in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3 || true)" /usr/bin/python3; do
  if [ -n "$c" ] && [ -x "$c" ] && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Nenašiel sa Python 3.9 alebo novší. Nainštaluj ho z https://www.python.org/downloads/macos/"
  echo "(alebo: xcode-select --install) a spusti skript znova."
  exit 1
fi
echo "Python: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"

if ! command -v quarto >/dev/null && [ ! -x /Applications/quarto/bin/quarto ]; then
  echo "Upozornenie: Quarto sa nenašlo. Nainštaluj ho z https://quarto.org/docs/get-started/"
fi

# AppleScript reťazec: \ a " treba zdvojiť/escapovať
as_str() { printf '"%s"' "$(printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat > "$TMP/qgui.applescript" <<EOF
property repo : $(as_str "$REPO")
property py : $(as_str "$PY")

on launchQgui(args)
	do shell script "cd " & quoted form of repo & " && QGUI_BACKGROUND=1 " & quoted form of py & " qgui_start.pyw " & args & " > /dev/null 2>&1 &"
end launchQgui

on run
	launchQgui("")
end run

on open theFiles
	repeat with f in theFiles
		launchQgui(quoted form of (POSIX path of f))
		delay 0.7
	end repeat
end open
EOF

mkdir -p "$DEST"
rm -rf "$APP"
osacompile -o "$APP" "$TMP/qgui.applescript"

# Ikona (assets/quarto-1024.png → .icns)
ICONSET="$TMP/quarto.iconset"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z "$s" "$s" "$REPO/assets/quarto-1024.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2))
  sips -z "$d" "$d" "$REPO/assets/quarto-1024.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns -o "$APP/Contents/Resources/applet.icns" "$ICONSET"

# Info.plist: názov, identifikátor a typy dokumentov (.md, .markdown, .qmd, .rmd)
PL="$APP/Contents/Info.plist"
pb() { /usr/libexec/PlistBuddy -c "$1" "$PL" >/dev/null 2>&1 || true; }
pb "Delete :CFBundleIdentifier";  pb "Add :CFBundleIdentifier string $BUNDLE_ID"
pb "Delete :CFBundleName";        pb "Add :CFBundleName string Quarto Studio"
pb "Delete :CFBundleDisplayName"; pb "Add :CFBundleDisplayName string Quarto Studio"
pb "Delete :CFBundleDocumentTypes"
pb "Add :CFBundleDocumentTypes array"
pb "Add :CFBundleDocumentTypes:0 dict"
pb "Add :CFBundleDocumentTypes:0:CFBundleTypeName string Dokument Markdown/Quarto"
pb "Add :CFBundleDocumentTypes:0:CFBundleTypeRole string Editor"
pb "Add :CFBundleDocumentTypes:0:LSHandlerRank string Alternate"
pb "Add :CFBundleDocumentTypes:0:LSItemContentTypes array"
pb "Add :CFBundleDocumentTypes:0:LSItemContentTypes:0 string net.daringfireball.markdown"
pb "Add :CFBundleDocumentTypes:0:LSItemContentTypes:1 string org.quarto.qmd"
pb "Add :CFBundleDocumentTypes:0:LSItemContentTypes:2 string org.rstudio.rmarkdown"
pb "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions array"
i=0; for e in md markdown qmd rmd Rmd; do pb "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions:$i string $e"; i=$((i + 1)); done
pb "Delete :UTImportedTypeDeclarations"
pb "Add :UTImportedTypeDeclarations array"
j=0
for t in "org.quarto.qmd|Dokument Quarto|qmd" "org.rstudio.rmarkdown|Dokument R Markdown|rmd"; do
  IFS='|' read -r id desc ext <<< "$t"
  pb "Add :UTImportedTypeDeclarations:$j dict"
  pb "Add :UTImportedTypeDeclarations:$j:UTTypeIdentifier string $id"
  pb "Add :UTImportedTypeDeclarations:$j:UTTypeDescription string $desc"
  pb "Add :UTImportedTypeDeclarations:$j:UTTypeConformsTo array"
  pb "Add :UTImportedTypeDeclarations:$j:UTTypeConformsTo:0 string public.plain-text"
  pb "Add :UTImportedTypeDeclarations:$j:UTTypeTagSpecification dict"
  pb "Add :UTImportedTypeDeclarations:$j:UTTypeTagSpecification:public.filename-extension array"
  pb "Add :UTImportedTypeDeclarations:$j:UTTypeTagSpecification:public.filename-extension:0 string $ext"
  j=$((j + 1))
done

# Zmenený balík znova podpísať (ad-hoc), inak ho macOS môže označiť za poškodený
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
touch "$APP"
LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
[ -x "$LSREG" ] && "$LSREG" -f "$APP" || true

# Voliteľne nastaviť ako predvolenú aplikáciu (ak je nainštalovaný nástroj duti)
if command -v duti >/dev/null; then
  for u in net.daringfireball.markdown org.quarto.qmd org.rstudio.rmarkdown; do duti -s "$BUNDLE_ID" "$u" all || true; done
  echo "Quarto Studio je nastavené ako predvolená aplikácia pre .md a .qmd (duti)."
fi

echo
echo "Hotovo: $APP"
echo "• Spusti ju z Launchpadu alebo Findera (Aplikácie) a pretiahni si ju do Docku."
echo "• Predvolená aplikácia pre .md/.qmd: Finder → súbor → Cmd+I → Otvoriť pomocou →"
echo "  Quarto Studio → Zmeniť všetko…"
echo "• Log aplikácie: ~/.qgui/qgui.log"
