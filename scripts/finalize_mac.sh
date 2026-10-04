#!/bin/bash
# finalize_mac.sh <Developer-ID-signed Xrero Office.app> <arm64|x86_64> <version> <out dir> [max notary wait, default 150m]
# (env SIGN_ID + NOTARY_KEY/NOTARY_KEY_ID/NOTARY_ISSUER)
# Notarization ticket for the app (reuses an existing ticket when Apple already accepted these exact binaries) -> staple ->
# DMG -> sign -> notarize the DMG -> staple -> Gatekeeper check. Exit 2 when Apple is still processing (run it again later).
set -uo pipefail
APP="$1"; ARCH="$2"; VERSION="$3"; OUT="$4"; WAIT="${5:-150m}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${SIGN_ID:?SIGN_ID not set}"
DMG_OUT="$OUT/XreroOffice-$VERSION-mac-$ARCH.dmg"

echo "== [$ARCH] notarization ticket for the app"
if xcrun stapler staple "$APP" 2>/dev/null; then
  echo "already notarized: ticket stapled"
else
  ZIP="$OUT/$ARCH/notarize-app-$ARCH.zip"
  ditto -c -k --keepParent "$APP" "$ZIP"
  bash "$ROOT/scripts/notarize.sh" "$ZIP" "$WAIT"; rc=$?
  [ $rc -ne 0 ] && exit $rc
  rm -f "$ZIP"
  xcrun stapler staple "$APP" || exit 1
fi
spctl --assess --type execute -vv "$APP" 2>&1 | tee /dev/stderr | grep -q "source=Notarized Developer ID" || exit 1

echo "== [$ARCH] dmg (signed + notarized + stapled)"
bash "$ROOT/scripts/make_dmg.sh" "$APP" "$DMG_OUT" || exit 1
bash "$ROOT/scripts/notarize.sh" "$DMG_OUT" "$WAIT"; rc=$?
[ $rc -ne 0 ] && exit $rc
xcrun stapler staple "$DMG_OUT" || exit 1
spctl --assess --type open --context context:primary-signature -vv "$DMG_OUT" || exit 1
rm -f "$DMG_OUT.notary-pending" "$DMG_OUT.notary-id"
shasum -a 256 "$DMG_OUT" | tee "$DMG_OUT.sha256"
