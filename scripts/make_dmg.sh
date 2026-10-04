#!/bin/bash
# make_dmg.sh <Xrero Office.app> <out.dmg>   - drag-to-install DMG (app + /Applications shortcut); signed with SIGN_ID if set.
set -euo pipefail
APP="$1"; DMG_OUT="$2"
STAGE="$(mktemp -d)"
ditto "$APP" "$STAGE/Xrero Office.app"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG_OUT"
hdiutil create -volname "Xrero Office" -srcfolder "$STAGE" -ov -format UDZO "$DMG_OUT" >/dev/null
rm -rf "$STAGE"
if [ -n "${SIGN_ID:-}" ]; then
  codesign --force --timestamp --sign "$SIGN_ID" "$DMG_OUT"
fi
ls -la "$DMG_OUT"
