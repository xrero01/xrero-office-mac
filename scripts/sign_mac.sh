#!/bin/bash
# sign_mac.sh <Xrero Office.app>   (env SIGN_ID = "Developer ID Application: ... (TEAMID)")
# Developer ID signature with the hardened runtime + secure timestamp on every piece of code, inside-out, so Apple
# notarization accepts it. Entitlements = the ones the official bundle ships (Chromium/V8 JIT + plug-in libraries),
# without the debug-only get-task-allow that notarization rejects.
set -euo pipefail
APP="$1"
: "${SIGN_ID:?SIGN_ID not set}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENT="$ROOT/launcher/xrero.entitlements"
sign() { codesign --force --timestamp --options runtime --sign "$SIGN_ID" "$@"; }

is_macho() { file -b "$1" | grep -q "Mach-O"; }

# 1) every loose Mach-O file (dylibs, framework binaries, x2t, helper and main executables)
while IFS= read -r -d '' f; do
  if is_macho "$f"; then
    case "$f" in
      */Contents/MacOS/*|*/converter/x2t) sign --entitlements "$ENT" "$f" ;;
      *) sign "$f" ;;
    esac
  fi
done < <(find "$APP/Contents" -type f \( -perm -u+x -o -name "*.dylib" -o -name "*.so" \) -print0)

# 2) nested bundles, deepest first (XPC services, helper apps, frameworks)
while IFS= read -r -d '' b; do
  case "$b" in
    *.app) sign --entitlements "$ENT" "$b" ;;
    *) sign "$b" ;;
  esac
done < <(find "$APP/Contents" -depth -type d \( -name "*.xpc" -o -name "*.app" -o -name "*.framework" \) -print0)

# 3) the app itself (main executable = launcher; Contents/MacOS/XreroOffice was signed in step 1)
sign --entitlements "$ENT" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
codesign -dv --verbose=4 "$APP" 2>&1 | grep -E "Authority|TeamIdentifier|Timestamp|Runtime|flags" || true
