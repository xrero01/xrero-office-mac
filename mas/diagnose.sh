#!/bin/bash
# diagnose.sh <unsigned patched app> <sandbox-signed app> <log dir>
# Why does an app not start? Runs (A) the patched app without any sandbox, (B) the sandboxed app's real binary and
# launcher directly, (C) through LaunchServices, and collects exit codes, output, unified-log lines and crash reports.
set -uo pipefail
SRC="$1"; APP="$2"; L="$3"; mkdir -p "$L"
D="$L/diag"; mkdir -p "$D"
T0="$(date '+%Y-%m-%d %H:%M:%S')"

run() {  # run <name> <secs> <cmd...> : start, wait, report alive/exit code
  local name="$1" secs="$2"; shift 2
  "$@" > "$D/$name.out" 2>&1 &
  local pid=$!
  sleep "$secs"
  if kill -0 "$pid" 2>/dev/null; then
    echo "$name: ALIVE after ${secs}s (pid $pid)" | tee -a "$D/summary.txt"
    pkill -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null; sleep 2; kill -9 "$pid" 2>/dev/null
    pkill -f "Xrero Office.app" 2>/dev/null; pkill -f "plain-test.app" 2>/dev/null
  else
    wait "$pid"; echo "$name: EXITED rc=$? within ${secs}s" | tee -a "$D/summary.txt"
  fi
  echo "--- $name output (tail):" >> "$D/summary.txt"; tail -25 "$D/$name.out" >> "$D/summary.txt"
}

# A) no sandbox at all (ad-hoc, no entitlements): is the patched bundle itself healthy?
rm -rf /tmp/plain-test.app; ditto "$SRC" /tmp/plain-test.app
codesign --force --deep --sign - /tmp/plain-test.app >/dev/null 2>&1
run A-plain 20 "/tmp/plain-test.app/Contents/MacOS/XreroOffice" --remote-debugging-port=9301

# B) sandboxed: the real binary directly, then the launcher
run B1-sandbox-binary 20 "$APP/Contents/MacOS/XreroOffice" --remote-debugging-port=9302

# C) the way Finder starts it
open -a "$APP" --args --remote-debugging-port=9304 > "$D/C-open.out" 2>&1
sleep 20
if pgrep -f "Xrero Office.app/Contents/MacOS/XreroOffice" >/dev/null; then echo "C-open: RUNNING" | tee -a "$D/summary.txt"; else echo "C-open: NOT RUNNING" | tee -a "$D/summary.txt"; fi
curl -s --max-time 3 http://127.0.0.1:9304/json | head -c 600 >> "$D/summary.txt"; echo >> "$D/summary.txt"
osascript -e 'quit app "Xrero Office"' 2>/dev/null; sleep 3; pkill -f "Xrero Office.app" 2>/dev/null

sleep 8   # crash reports are written a few seconds after a crash
codesign -d --entitlements - "$APP/Contents/MacOS/XreroOffice" > "$D/ent-binary.txt" 2>&1
codesign -d --entitlements - "$APP/Contents/Frameworks/editors_helper.app" > "$D/ent-helper.txt" 2>&1
log show --start "$T0" --style compact --predicate 'process == "Xrero Office" OR process == "XreroOffice" OR process BEGINSWITH "editors_helper" OR process == "amfid" OR process == "taskgated" OR process == "syspolicyd" OR (process == "kernel" AND (eventMessage CONTAINS[c] "xrero" OR eventMessage CONTAINS[c] "editors_helper" OR eventMessage CONTAINS "CODE SIGNING")) OR eventMessage CONTAINS[c] "XreroOffice"' > "$D/unified-log.txt" 2>&1
wc -l "$D/unified-log.txt"
ls -la ~/Library/Logs/DiagnosticReports/ /Library/Logs/DiagnosticReports/ > "$D/crash-dirs.txt" 2>&1
for f in $(ls -t ~/Library/Logs/DiagnosticReports/ 2>/dev/null | grep -i -E "xrero|editors|plain" | head -4); do cp ~/Library/Logs/DiagnosticReports/"$f" "$D/" ; done
for f in $(ls -t /Library/Logs/DiagnosticReports/ 2>/dev/null | grep -i -E "xrero|editors|plain" | head -4); do sudo cp /Library/Logs/DiagnosticReports/"$f" "$D/" ; done
ls "$D"
cat "$D/summary.txt"
