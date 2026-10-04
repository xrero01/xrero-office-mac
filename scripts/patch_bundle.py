#!/usr/bin/env python3
"""Turn the official ONLYOFFICE Desktop Editors 9.4.0 macOS bundle into Xrero Office (runs ON macOS).

usage: patch_bundle.py <path/to/Xrero Office.app> <payload dir> <version>

payload dir (from the Windows release payload, same 9.4.0 web build):
    editors/{sdkjs,web-apps,sdkjs-plugins,webext}   Xrero-branded web layer incl. the 20.0.9 Arabic PDF fix
    login/index.html                                 Xrero start page
    assets/xrero-icon-1024.png                       (repo) app icon source - turned into AppIcon.icns by build_mac.sh
"""
import glob, os, plistlib, re, shutil, sys

APP, PAYLOAD, VERSION = sys.argv[1], sys.argv[2], sys.argv[3]
C = os.path.join(APP, "Contents")
RES = os.path.join(C, "Resources")
NAME = "Xrero Office"

def log(*a):
    print("[patch]", *a, flush=True)

# ---------------------------------------------------------------- Info.plist
pl_path = os.path.join(C, "Info.plist")
p = plistlib.load(open(pl_path, "rb"))
old_exe = p["CFBundleExecutable"]
p["CFBundleName"] = NAME
p["CFBundleDisplayName"] = NAME
p["CFBundleIdentifier"] = "com.xrero.office"
p["CFBundleShortVersionString"] = VERSION
p["NSHumanReadableCopyright"] = "© 2026 Xrero. Free and open-source software (AGPL-3.0)."
p["ASCWebappsHelpUrl"] = "https://xrero.com/office/help"
for k in list(p):
    if k.startswith("NS") and k.endswith("UsageDescription") and isinstance(p[k], str):
        p[k] = p[k].replace("ONLYOFFICE Desktop Editors", NAME).replace("ONLYOFFICE", NAME)
# Updates: never offer ONLYOFFICE builds. The feed is Xrero's own (an empty appcast = "you're up to date") and
# updates must carry an EdDSA signature made with Xrero's key (the private half never leaves Xrero's PC).
p.pop("SUScheduledCheckInterval", None)
p["SUPublicEDKey"] = "69Gj4ww/33jDQRAKhj3gP1RbblQ+SIVBCI9cDSdTk7k="
p["SUFeedURL"] = "https://xrero.com/office/mac/appcast.xml"
p["SUEnableAutomaticChecks"] = False
p["SUAllowsAutomaticUpdates"] = False
p["SUAutomaticallyUpdate"] = False
# Icon: the compiled asset catalog (Assets.car) carries the ONLYOFFICE icon under CFBundleIconName -> use the .icns
p.pop("CFBundleIconName", None)
p["CFBundleIconFile"] = "AppIcon"
# CFBundleExecutable "Xrero Office" = launcher/launcher.c (built by build_mac.sh): seeds the first-run
# preferences, then execs the real binary, renamed to XreroOffice (the process name in ps / crash reports).
p["CFBundleExecutable"] = NAME
os.rename(os.path.join(C, "MacOS", old_exe), os.path.join(C, "MacOS", "XreroOffice"))
# every other user-visible plist string (e.g. Finder "Kind" of the form formats)
def walk(o):
    if isinstance(o, dict):
        return {k: walk(v) for k, v in o.items()}
    if isinstance(o, list):
        return [walk(v) for v in o]
    if isinstance(o, str):
        return o.replace("ONLYOFFICE Desktop Editors", NAME).replace("ONLYOFFICE", NAME)
    return o
p = walk(p)
plistlib.dump(p, open(pl_path, "wb"), fmt=plistlib.FMT_XML)
log("Info.plist:", p["CFBundleName"], p["CFBundleIdentifier"], p["CFBundleShortVersionString"], "exe:", old_exe, "-> XreroOffice")

# ---------------------------------------------------------------- app binary: same-length string swaps
# (each string is in __cstring once; CFString literals keep their stored length, so lengths must match exactly)
def padded(url, n):
    """url + filler query so the result is exactly n characters"""
    fill = n - len(url) - len("&x=")
    if fill < 0:
        raise SystemExit("replacement too long: " + url)
    return url + "&x=" + "0" * fill

BIN_SWAPS = [
    # start-tab logo: the asset catalog's ONLYOFFICE artwork -> Xrero files in Resources (made by tab_logo.swift)
    (b"logo-tab-light\0", b"xrero-tab-lite\0"),
    (b"logo-tab-dark\0", b"xrero-tabdark\0"),
    # no analytics to Google under Xrero's name: an RFC 6761 .invalid host never resolves
    (b"google-analytics.com", b"xrerooffline.invalid"),
    (b"https://onlyoffice.com/desktopeditors.aspx\0", None),
    (b"https://onlyoffice.com/registration.aspx?desktop=true\0", None),
    (b"http://helpcenter.onlyoffice.com/%@ONLYOFFICE-Editors/index.aspx\0", None),
]
TARGET = {
    b"https://onlyoffice.com/desktopeditors.aspx\0": "https://xrero.com/office?from=mac-app",
    b"https://onlyoffice.com/registration.aspx?desktop=true\0": "https://xrero.com/office?from=mac-app-signup",
    b"http://helpcenter.onlyoffice.com/%@ONLYOFFICE-Editors/index.aspx\0": "https://xrero.com/office/help?hl=%@",
}
exe = os.path.join(C, "MacOS", "XreroOffice")
data = open(exe, "rb").read()
for old, new in BIN_SWAPS:
    if new is None:
        new = padded(TARGET[old], len(old) - 1).encode() + b"\0"
    if len(new) != len(old):
        raise SystemExit("length mismatch %r" % old)
    if data.count(old) != 1:
        raise SystemExit("expected exactly one %r in the binary, found %d" % (old, data.count(old)))
    data = data.replace(old, new)
    log("binary:", old.rstrip(b"\0").decode(), "->", new.rstrip(b"\0").decode())
open(exe, "wb").write(data)

# ---------------------------------------------------------------- .strings (menus, window titles, messages)
VALUE = re.compile(r'(=\s*")((?:[^"\\]|\\.)*)(")')
GLUED = re.compile("(?<=[؀-ۿ])ONLYOFFICE")      # e.g. Arabic "خروج منONLYOFFICE" has no space

def rebrand(v):
    v = GLUED.sub(" ONLYOFFICE", v)
    return v.replace("ONLYOFFICE Desktop Editors", NAME).replace("ONLYOFFICE", NAME)

def fix_strings(path):
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "utf-16"
    elif raw[:3] == b"\xef\xbb\xbf":
        enc = "utf-8-sig"
    else:
        try:
            raw.decode("utf-8"); enc = "utf-8"
        except UnicodeDecodeError:
            enc = "utf-16"
    s = raw.decode(enc)
    s2 = VALUE.sub(lambda m: m.group(1) + rebrand(m.group(2)) + m.group(3), s)
    if s2 != s:
        open(path, "wb").write(s2.encode(enc))
        return True
    return False

changed = [f for f in glob.glob(os.path.join(RES, "*.lproj", "*.strings")) if fix_strings(f)]
log("strings files rebranded:", len(changed))

# English has no Main.strings (the storyboard's base titles say ONLYOFFICE) -> add overrides for the 7 objects
EN_MAIN = {
    "1Xt-HY-uBw.title": NAME,                  # app menu
    "uQy-DD-JDr.title": NAME,                  # app menu (NSMenu)
    "5kV-Vb-QxS.title": "About " + NAME,
    "Olw-nP-bQN.title": "Hide " + NAME,
    "4sb-4s-VLi.title": "Quit " + NAME,
    "IQv-IB-iLA.title": NAME,                  # main window
    "kcg-El-49G.label": NAME,                  # start tab
}
for lp in ("en.lproj",):
    d = os.path.join(RES, lp)
    if os.path.isdir(d):
        f = os.path.join(d, "Main.strings")
        if not os.path.exists(f):
            open(f, "w", encoding="utf-8").write("".join('"%s" = "%s";\n' % kv for kv in EN_MAIN.items()))
            log("added", f)

# ---------------------------------------------------------------- web layer (editors) from the Xrero payload
E = os.path.join(RES, "editors")
for sub in ("sdkjs", "web-apps", "sdkjs-plugins", "webext"):
    src = os.path.join(PAYLOAD, "editors", sub)
    if not os.path.isdir(src):
        raise SystemExit("payload lacks editors/" + sub)
    shutil.rmtree(os.path.join(E, sub), ignore_errors=True)
    shutil.copytree(src, os.path.join(E, sub), symlinks=True)
# V8 snapshots are per platform/arch: drop any copied ones, build_mac.sh regenerates them with this bundle's x2t
for b in glob.glob(os.path.join(E, "sdkjs", "*", "sdk-all.bin")) + glob.glob(os.path.join(E, "sdkjs", "*", "sdk-all.cache")):
    os.remove(b)
log("editors replaced; snapshots removed")

# Hide the Xrero header controls that call Windows-only native commands (PDF->Word converter, Designs dialog,
# EN/AR switch = 'xrero:lang:*' relaunch handled only by the Windows shell, share, account) - on Mac they would be
# dead buttons. The Mac UI language follows macOS (or the start page's Settings).
MAC_JS = r"""
/*XR-MAC-START*/
(function(){
  if (!/Mac/i.test(navigator.platform || '')) return;
  var css = '#xr-b-ctx,#xr-hdr-btns .xr-lang,#xr-b-share,#xr-b-acct,#xr-acct-menu,#xr-designs-launch,#xr-design-ov{display:none!important}';
  function add(){
    if (document.getElementById('xr-mac-css')) return;
    var s = document.createElement('style'); s.id = 'xr-mac-css'; s.textContent = css;
    (document.head || document.documentElement).appendChild(s);
  }
  add(); document.addEventListener('DOMContentLoaded', add);
})();
/*XR-MAC-END*/
"""
for e in ("documenteditor", "spreadsheeteditor", "presentationeditor", "pdfeditor"):
    f = os.path.join(E, "web-apps", "apps", e, "main", "app.js")
    if os.path.exists(f):
        s = open(f, encoding="utf-8").read()
        s = re.sub(r"\n?/\*XR-MAC-START\*/.*?/\*XR-MAC-END\*/\n?", "", s, flags=re.S)
        open(f, "w", encoding="utf-8").write(s.rstrip() + "\n" + MAC_JS)
log("mac header shim appended to app.js")

# ---------------------------------------------------------------- start page
login = os.path.join(RES, "login", "index.html")
s = open(os.path.join(PAYLOAD, "login", "index.html"), encoding="utf-8").read()
n0 = len(s)
# the sign-in wall waits for the Windows shell's answer - on Mac nobody answers and it would never unlock
s, n_wall = re.subn(r'<script id="xrero-wall">.*?</script>\s*', "", s, flags=re.S)
# "Open PDF as DOCX..." needs the Windows PDF converter
s, n_conv = re.subn(r"function addConvertItem\(\)\s*\{", "function addConvertItem(){ if (/Mac/i.test(navigator.platform||'')) return true;", s)
if n_wall != 1 or n_conv != 1:
    raise SystemExit("start page anchors not found (wall=%d convert=%d)" % (n_wall, n_conv))
open(login, "w", encoding="utf-8").write(s)
log("start page: wall removed, convert item disabled (%d -> %d chars)" % (n0, len(s)))

# ---------------------------------------------------------------- leftovers report
left = []
for f in glob.glob(os.path.join(RES, "*.lproj", "*.strings")):
    raw = open(f, "rb").read()
    for enc in ("utf-8", "utf-16"):
        try:
            t = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if re.search(r'=\s*"[^"]*ONLYOFFICE', t):
            left.append(f)
        break
log("strings values still mentioning ONLYOFFICE:", len(left), left[:5])
