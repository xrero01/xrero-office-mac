#!/bin/bash
# sign_mas.sh <Xrero Office.app> <identity|-> <main entitlements> [provisioning profile]
# App Sandbox signature, inside-out. Every helper app and tool that runs as a child process (Chromium helpers, the
# document converter x2t) gets mas/child.entitlements (sandbox + inherit); the main executables get the main
# entitlements. Identity "-" = ad-hoc (the CI test copy). No hardened runtime: the App Store does not need it.
set -euo pipefail
APP="$1"; ID="$2"; ENT="$3"; PROFILE="${4:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHILD="$ROOT/mas/child.entitlements"
sign() { codesign --force --sign "$ID" "$@"; }
is_macho() { file -b "$1" | grep -q "Mach-O"; }

find "$APP" -name ".DS_Store" -delete
find "$APP" -path "*/Contents/CodeResources" -not -path "*/_CodeSignature/*" -print -delete
[ -n "$PROFILE" ] && cp "$PROFILE" "$APP/Contents/embedded.provisionprofile"

# 1) loose Mach-O files
while IFS= read -r -d '' f; do
  is_macho "$f" || continue
  case "$f" in
    "$APP/Contents/MacOS/"*) sign --entitlements "$ENT" "$f" ;;
    */Contents/MacOS/*|*/converter/x2t|*/converter/*.app/*) sign --entitlements "$CHILD" "$f" ;;
    *) if [ -x "$f" ] && ! [[ "$f" == *.dylib || "$f" == *.so || "$f" == *.framework/* ]]; then
         sign --entitlements "$CHILD" "$f"     # any other stand-alone tool started as a child process
       else
         sign "$f"
       fi ;;
  esac
done < <(find "$APP/Contents" -type f \( -perm -u+x -o -name "*.dylib" -o -name "*.so" \) -print0)

# 2) nested bundles, deepest first
while IFS= read -r -d '' b; do
  case "$b" in
    *.app|*.xpc) sign --entitlements "$CHILD" "$b" ;;
    *) sign "$b" ;;
  esac
done < <(find "$APP/Contents" -depth -type d \( -name "*.xpc" -o -name "*.app" -o -name "*.framework" \) -print0)

# 3) the app (main executable = launcher; XreroOffice was signed in step 1 with the same main entitlements)
sign --entitlements "$ENT" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
codesign -d --entitlements - "$APP" 2>/dev/null | head -40 || true
codesign -dv --verbose=2 "$APP" 2>&1 | grep -E "Authority|TeamIdentifier|Identifier=" || true
