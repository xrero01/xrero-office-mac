#!/bin/bash
# install_from_dmg.sh <dmg>
# Installs "Xrero Office.app" into /Applications the way a user does (drag it out of the DMG) and resets the
# app's preferences so the next launch is a true first launch.
set -euo pipefail
DMG="$1"
DEST="/Applications/Xrero Office.app"
MNT="$(mktemp -d)"
hdiutil attach -nobrowse -readonly -mountpoint "$MNT" "$DMG" >/dev/null
ls -la "$MNT"
test -L "$MNT/Applications"                       # the drag-to-install shortcut is in the DMG
osascript -e 'quit app "Xrero Office"' 2>/dev/null || true
rm -rf "$DEST" 2>/dev/null || sudo rm -rf "$DEST"
ditto "$MNT/Xrero Office.app" "$DEST" 2>/dev/null || sudo ditto "$MNT/Xrero Office.app" "$DEST"
hdiutil detach "$MNT" >/dev/null
codesign --verify --deep --strict "$DEST"
# Gatekeeper verdict a downloaded copy gets: signed builds must say "Notarized Developer ID"
# (a build whose notarization is still pending at Apple must at least carry the Developer ID signature)
if [ -n "${SIGN_ID:-}" ] && [ -f "$DMG.notary-pending" ]; then
  codesign -dv --verbose=2 "$DEST" 2>&1 | tee /dev/stderr | grep "Authority=Developer ID Application" >/dev/null
  spctl --assess --type execute -vv "$DEST" || true
elif [ -n "${SIGN_ID:-}" ]; then
  spctl --assess --type execute -vv "$DEST" 2>&1 | tee /dev/stderr | grep "source=Notarized Developer ID" >/dev/null
else
  spctl --assess --type execute -vv "$DEST" || true
fi
/usr/libexec/PlistBuddy -c "Print :CFBundleExecutable" -c "Print :CFBundleShortVersionString" "$DEST/Contents/Info.plist"
lipo -info "$DEST/Contents/MacOS/Xrero Office" "$DEST/Contents/MacOS/XreroOffice"
defaults delete com.xrero.office 2>/dev/null || true
rm -rf ~/Library/Preferences/com.xrero.office.plist
# app data of a previous test run (recent files, recovery copies) -> the next launch is a true first launch
ls ~/Library/Application\ Support/ || true
rm -rf ~/Library/Application\ Support/asc.onlyoffice.ONLYOFFICE ~/Library/Application\ Support/ONLYOFFICE \
       ~/Library/Application\ Support/com.xrero.office ~/Library/Application\ Support/Xrero\ Office \
       ~/Library/Caches/com.xrero.office ~/Library/Saved\ Application\ State/com.xrero.office.savedState
echo "installed $DEST"
