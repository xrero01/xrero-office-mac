#!/bin/bash
# make_dmg.sh <Xrero Office.app> <out.dmg>   - drag-to-install DMG (app + /Applications shortcut); signed with SIGN_ID if set.
set -euo pipefail
APP="$1"; DMG_OUT="$2"
STAGE="$(mktemp -d)"
ditto "$APP" "$STAGE/Xrero Office.app"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG_OUT"
# hdiutil on the CI Macs sometimes fails with "create failed - Resource busy" (run 17): try again a few times
for try in 1 2 3 4; do
  hdiutil create -volname "Xrero Office" -srcfolder "$STAGE" -ov -format UDZO "$DMG_OUT" >/dev/null && break
  [ "$try" = 4 ] && exit 1
  echo "hdiutil create failed (try $try) - again in 15 s"; rm -f "$DMG_OUT"; sleep 15
done
rm -rf "$STAGE"
if [ -n "${SIGN_ID:-}" ]; then
  codesign --force --timestamp --sign "$SIGN_ID" "$DMG_OUT"
fi
ls -la "$DMG_OUT"
