#!/bin/bash
# build_mac.sh <official ONLYOFFICE dmg> <arm64|x86_64> <version> <payload dir> [out dir]
# Builds "Xrero Office.app" from the official ONLYOFFICE Desktop Editors 9.4.0 macOS bundle + the Xrero web payload,
# regenerates the converter's V8 snapshots with THIS bundle's x2t, signs it ad-hoc and packs a DMG.
set -euo pipefail
DMG="$1"; ARCH="$2"; VERSION="$3"; PAYLOAD="$4"; OUT="${5:-out}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$OUT/$ARCH"
OUT="$(cd "$OUT" && pwd)"
APP="$OUT/$ARCH/Xrero Office.app"

echo "== [$ARCH] extract official bundle"
MNT="$(mktemp -d)"
hdiutil attach -nobrowse -readonly -mountpoint "$MNT" "$DMG" >/dev/null
rm -rf "$APP"
ditto "$MNT/ONLYOFFICE.app" "$APP"
hdiutil detach "$MNT" >/dev/null
xattr -cr "$APP"
lipo -info "$APP/Contents/MacOS/ONLYOFFICE"

echo "== [$ARCH] icon"
ICONSET="$(mktemp -d)/AppIcon.iconset"; mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$ROOT/assets/xrero-icon-1024.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2)); sips -z $d $d "$ROOT/assets/xrero-icon-1024.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"

echo "== [$ARCH] rebrand + Xrero web layer"
python3 "$ROOT/scripts/patch_bundle.py" "$APP" "$PAYLOAD" "$VERSION"

echo "== [$ARCH] first-run launcher"
clang -arch "$ARCH" -mmacosx-version-min=11.0 -O2 -Wall -Werror -framework CoreFoundation \
  -o "$APP/Contents/MacOS/Xrero Office" "$ROOT/launcher/launcher.c"
lipo -info "$APP/Contents/MacOS/Xrero Office" "$APP/Contents/MacOS/XreroOffice"

echo "== [$ARCH] start-tab logo (replaces the ONLYOFFICE artwork the binary used to load)"
mkdir -p "$OUT/test/logo-$ARCH"
swift "$ROOT/scripts/tab_logo.swift" "$APP" "$ROOT/assets/xrero-icon-1024.png" "$OUT/test/logo-$ARCH"
ls -la "$APP/Contents/Resources/"xrero-tab*.tiff

echo "== [$ARCH] converter JS engine"
CONV="$APP/Contents/Resources/converter"
cat "$CONV/DoctRenderer.config" || true
# The macOS converter is a JavaScriptCore build (small doctrenderer, as ONLYOFFICE's build_tools treat it):
# it has no V8 snapshots and loads sdk-all*.js directly, so the patched JS is what it runs. A V8 build
# (doctrenderer > 5 MB) would need its snapshots regenerated.
DR="$CONV/doctrenderer.framework/Versions/A/doctrenderer"
if [ -f "$DR" ] && [ "$(stat -f %z "$DR")" -gt 5242880 ]; then
  RUN=""; [ "$ARCH" = "x86_64" ] && RUN="arch -x86_64"
  (cd "$CONV" && $RUN ./x2t -create-js-snapshots)
  ls -la "$APP/Contents/Resources/editors/sdkjs/"*/sdk-all.bin
else
  echo "JavaScriptCore converter ($(stat -f %z "$DR") bytes): no snapshots to build"
fi
grep -l "XRERO-RTL-CODEPOINTS" "$APP/Contents/Resources/editors/sdkjs/word/sdk-all-min.js"
grep -l "XRERO-RTL-GRAPHEME" "$APP/Contents/Resources/editors/sdkjs/word/sdk-all.js"

echo "== [$ARCH] sign (ad-hoc) + verify"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
codesign -dv "$APP" 2>&1 | grep -E "Identifier|Signature|Format" || true

echo "== [$ARCH] dmg"
STAGE="$(mktemp -d)"
ditto "$APP" "$STAGE/Xrero Office.app"
ln -s /Applications "$STAGE/Applications"
DMG_OUT="$OUT/XreroOffice-$VERSION-mac-$ARCH.dmg"
rm -f "$DMG_OUT"
hdiutil create -volname "Xrero Office" -srcfolder "$STAGE" -ov -format UDZO "$DMG_OUT" >/dev/null
ls -la "$DMG_OUT"
shasum -a 256 "$DMG_OUT" | tee "$DMG_OUT.sha256"
