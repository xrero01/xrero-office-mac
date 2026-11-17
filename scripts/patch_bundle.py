#!/usr/bin/env python3
"""Turn the official ONLYOFFICE Desktop Editors 9.4.0 macOS bundle into Xrero Office (runs ON macOS).

usage: patch_bundle.py <path/to/Xrero Office.app> <payload dir> <version>

payload dir (from the Windows release payload, same 9.4.0 web build):
    editors/{sdkjs,web-apps,sdkjs-plugins,webext}   Xrero-branded web layer incl. the 20.0.9 Arabic PDF fix
    login/index.html                                 Xrero start page
    assets/icons/*.icns                              (repo) app + document icons, copied in by build_mac.sh
    assets/icons/small/*.png                         (repo) title-bar pictures: start-tab logo + document tab icons
                                                     (scripts/make_icons.py -> tab_logo.swift)
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
# Document icons (15 Nov 2026, the new Xrero kit): each document type -> one of the four kind icons that build_mac.sh
# copied into Resources (xr-doc / xr-sheet / xr-slide / xr-pdf .icns). The official names (file-docx ...) live in the
# asset catalog; new names that are not in it make macOS load our loose .icns, the same way as CFBundleIconFile above.
KIND_OF = {}
for k, exts in (("xr-doc", "docx doc odt rtf txt htm html dotx ott fodt xml epub mht fb2 pages hwpx hwp hml docxf"),
                ("xr-sheet", "xlsx xls ods ots fods csv xlsm xlsb numbers xltx"),
                ("xr-slide", "pptx ppt odp ppsx pps potx otp key odg vsdx vstx"),
                ("xr-pdf", "pdf djvu xps oform")):
    for e in exts.split():
        KIND_OF[e] = k
n_icons = 0
for dt in p.get("CFBundleDocumentTypes", []):
    exts = [e.lower() for e in dt.get("CFBundleTypeExtensions", [])]
    kind = next((KIND_OF[e] for e in exts if e in KIND_OF), "xr-doc")
    dt["CFBundleTypeIconFile"] = kind
    dt.pop("CFBundleTypeIconFiles", None)
    dt.pop("CFBundleTypeIconSystemGenerated", None)
    n_icons += 1
for key in ("UTExportedTypeDeclarations", "UTImportedTypeDeclarations"):
    for ut in p.get(key, []):
        tags = ut.get("UTTypeTagSpecification", {}).get("public.filename-extension", [])
        tags = [tags] if isinstance(tags, str) else tags
        hit = next((KIND_OF[e.lower()] for e in tags if e.lower() in KIND_OF), None)
        if hit and ("UTTypeIconFile" in ut or "UTTypeIconFiles" in ut or "UTTypeIconName" in ut):
            ut["UTTypeIconFile"] = hit
            ut.pop("UTTypeIconFiles", None); ut.pop("UTTypeIconName", None)
            n_icons += 1
log("document icons -> xr-doc/xr-sheet/xr-slide/xr-pdf:", n_icons)
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
    # the document tabs' kind icons (16 Nov 2026): the stock blue page -> the Xrero kit's Doc / Sheet / Slide / PDF
    # pictures (xrero_tab_*.tiff, made by tab_logo.swift); 've' (diagrams) keeps its own
    (b"icon_tabs_de_active\0", b"xrero_tab_de_active\0"),
    (b"icon_tabs_de_inactive\0", b"xrero_tab_de_inactive\0"),
    (b"icon_tabs_se_active\0", b"xrero_tab_se_active\0"),
    (b"icon_tabs_se_inactive\0", b"xrero_tab_se_inactive\0"),
    (b"icon_tabs_pe_active\0", b"xrero_tab_pe_active\0"),
    (b"icon_tabs_pe_inactive\0", b"xrero_tab_pe_inactive\0"),
    (b"icon_tabs_pdf_active\0", b"xrero_tab_pdf_active\0"),
    (b"icon_tabs_pdf_inactive\0", b"xrero_tab_pdf_inactive\0"),
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
# the start tab's first paint comes from the storyboard, which names the same artwork (NIBArchive strings are
# varint-length-prefixed: 0x8d = 13, 0x8e = 14 -> same-length names keep the archive valid)
NIB_SWAPS = [(b"\x8dlogo-tab-dark", b"\x8dxrero-tabdark"), (b"\x8elogo-tab-light", b"\x8exrero-tab-lite")]
nib_hits = 0
nibs = [os.path.join(d, f) for lp in glob.glob(os.path.join(RES, "*.lproj"))
        for d, _, fs in os.walk(lp) for f in fs if f.endswith(".nib")]   # some .nib are folders (keyedobjects.nib inside)
for nib in nibs:
    b = open(nib, "rb").read()
    n = sum(b.count(o) for o, _ in NIB_SWAPS)
    if n:
        for o, nw in NIB_SWAPS:
            b = b.replace(o, nw)
        open(nib, "wb").write(b)
        nib_hits += n
        log("storyboard logo:", os.path.relpath(nib, RES), n)
if nib_hits == 0:
    raise SystemExit("storyboard tab logo reference not found")


# The title bar's download indicator (16 Nov 2026, found in the Arabic store pictures, located by the title bar's
# accessibility dump of build-mac run 43772417382): the storyboard puts a download box (downloadBackgroundView: an image
# view + a button, 32 points wide) at the trailing end of the title bar, past the right edge of the window - left to right
# it is never on screen. Right to left the title bar is mirrored and the box lands inside the window at its left end:
# a grey square with a light-blue bar in every Arabic window. The box is archived hidden (NSvFlags hidden bit), so it
# is not drawn in either direction - as left to right, where it never comes on screen; the Mac app has no cloud
# downloads for it to show. A NIBArchive cannot change a value's size in place (the flags grow from 2 to 4 bytes), so the
# storyboard file is written again from its parts.
# Under the box (run 43773855657) sits the cloud account button (userProfileButton) the same way: a faint grey person at
# the left end of right-to-left windows. The app shows that button itself (archived hidden it still came back, run
# 43775991617), so its two storyboard pictures (icon-login_normal / _hover, named only in this storyboard) become
# transparent ones of the same name length; the Mac app has no cloud account for it.
def nib_read(b):
    """NIBArchive -> dict: header words, sections (objects/keys/values/classes) as lists, section order"""
    import struct
    if b[:10] != b"NIBArchive":
        return None
    hdr = list(struct.unpack("<10I", b[10:50]))
    _, _, oc, oo, kc, ko, vc, vo, cc, co = hdr

    def varint(p):
        v = s = 0
        while True:
            x = b[p]; p += 1
            v |= (x & 0x7f) << s; s += 7
            if x & 0x80:
                return v, p
    size = {0: 1, 1: 2, 2: 4, 3: 8, 4: 0, 5: 0, 6: 4, 7: 8, 9: 0, 10: 4}
    objs, p = [], oo
    for _ in range(oc):
        c, p = varint(p); vi, p = varint(p); n, p = varint(p)
        objs.append([c, vi, n])
    keys, p = [], ko
    for _ in range(kc):
        n, p = varint(p); keys.append(bytes(b[p:p + n])); p += n
    vals, p = [], vo
    for _ in range(vc):
        k, p = varint(p); t = b[p]; p += 1
        if t == 8:
            n, p = varint(p); data = bytes(b[p:p + n]); p += n
        else:
            data = bytes(b[p:p + size[t]]); p += size[t]
        vals.append([k, t, data])
    classes, p = [], co
    for _ in range(cc):
        n, p = varint(p); ex, p = varint(p)
        extras = bytes(b[p:p + 4 * ex]); p += 4 * ex
        classes.append([ex, extras, bytes(b[p:p + n])]); p += n
    order = [name for _, name in sorted([(oo, "objects"), (ko, "keys"), (vo, "values"), (co, "classes")])]
    return {"hdr": hdr, "objects": objs, "keys": keys, "values": vals, "classes": classes, "order": order}


def nib_write(n):
    import struct

    def varint(v):
        out = bytearray()
        while True:
            x = v & 0x7f; v >>= 7
            if v == 0:
                out.append(x | 0x80)
                return bytes(out)
            out.append(x)
    sec = {
        "objects": b"".join(varint(c) + varint(vi) + varint(k) for c, vi, k in n["objects"]),
        "keys": b"".join(varint(len(k)) + k for k in n["keys"]),
        "values": b"".join(varint(k) + bytes([t]) + ((varint(len(d)) + d) if t == 8 else d) for k, t, d in n["values"]),
        "classes": b"".join(varint(len(name)) + varint(ex) + extras + name for ex, extras, name in n["classes"]),
    }
    off, body, at = {}, b"", 50
    for name in n["order"]:
        off[name] = at; body += sec[name]; at += len(sec[name])
    h = n["hdr"]
    hdr = [h[0], h[1], len(n["objects"]), off["objects"], len(n["keys"]), off["keys"],
           len(n["values"]), off["values"], len(n["classes"]), off["classes"]]
    return b"NIBArchive" + struct.pack("<10I", *hdr) + body


def nib_hide_outlets(b, outlets):
    """the storyboard bytes with the views behind <outlets> archived hidden (None: none of them here)"""
    import struct
    n = nib_read(b)
    if not n or nib_write(n) != bytes(b):            # only a storyboard this code reads back byte for byte
        return None
    keys = [k.decode("latin1") for k in n["keys"]]
    cls = [name.rstrip(b"\0").decode("latin1") for _, _, name in n["classes"]]

    def fields(i):
        c, vi, cnt = n["objects"][i]
        return [(keys[k], t, d, vi + j) for j, (k, t, d) in enumerate(n["values"][vi:vi + cnt])]

    def ref(d):
        return struct.unpack("<I", d)[0]

    def string(i):
        for k, t, d, _ in fields(i):
            if k == "NS.bytes" and t == 8:
                return d.decode("utf-8", "replace")
        return None
    hits = 0
    for i, (c, _, _) in enumerate(n["objects"]):
        if cls[c] != "NSNibOutletConnector":
            continue
        f = {k: (t, d) for k, t, d, _ in fields(i)}
        if f.get("NSLabel", (0,))[0] != 10 or string(ref(f["NSLabel"][1])) not in outlets:
            continue
        box = ref(f["NSDestination"][1])
        for k, t, d, at in fields(box):
            if k == "NSvFlags":
                v = struct.unpack({0: "<b", 1: "<h", 2: "<i", 3: "<q"}[t], d)[0]
                n["values"][at][1] = 2
                n["values"][at][2] = struct.pack("<I", (v & 0xffffffff) | 0x80000000)
                hits += 1
    return (nib_write(n), hits) if hits else None


hide_hits = 0
for nib in nibs:
    b = open(nib, "rb").read()
    if b"downloadBackgroundView" not in b:
        continue
    r = nib_hide_outlets(b, ("downloadBackgroundView",))
    if not r:
        continue
    nb = r[0]
    # (NIBArchive strings: a varint length, 0x80 | n for n < 128, then the bytes)
    for old, new in ((b"\x91icon-login_normal", b"\x91xr-noaccount-norm"), (b"\x90icon-login_hover", b"\x90xr-noaccount-hov")):
        if nb.count(old) != 1 or len(old) != len(new):
            raise SystemExit("title bar account button picture %r: found %d" % (old, nb.count(old)))
        nb = nb.replace(old, new)
    open(nib, "wb").write(nb)
    hide_hits += r[1]
    log("title bar: download box archived hidden, account button pictures transparent:", os.path.relpath(nib, RES),
        len(b), "->", len(nb), "bytes")
if hide_hits != 1:
    raise SystemExit("title bar download box: %d found in the storyboard" % hide_hits)


def blank_png(w, h):
    """a fully transparent w x h PNG"""
    import struct, zlib
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    raw = b"".join(b"\0" + b"\0\0\0\0" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


for name in ("xr-noaccount-norm", "xr-noaccount-hov"):
    open(os.path.join(RES, name + ".png"), "wb").write(blank_png(12, 12))

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
# Editor header colour: the payload's XR-HEADER block (from the Windows release) paints the top bar of each editor in
# its own colour (#2B579A blue for documents ...). The Mac app uses the one Xrero teal for all of them (15 Nov 2026).
TEAL = "#0585A1"
# The active ribbon tab's underline (round 3 of the store pictures, 16 Nov 2026): the tabs sit on the header, and the
# underline kept each editor's own colour (--highlight-toolbar-tab-underline-*: #446995 documents, #3A8056
# spreadsheets, #B75B44 presentations, #AA5252 PDF) - on the one teal the documents and spreadsheet underlines all but
# disappeared, so no tab looked active. White, like the tab names, in all four (XR-TABLINE; only the tab underline
# uses these variables: web-apps toolbar.less .tab-toolbar-color)
# Run 32 measured the variables' own colours on the Mac even with them set !important on .theme-white (the same file
# and selector as the teal header, and white in Chrome with this stylesheet alone): something the Mac app adds at run
# time sets them closer to the tabs. So the underline itself is white too, under the same theme (where the header is
# teal: XR-HEADER above), for the line and for its hover preview.
TABLINE = ("/*XR-TABLINE*/.theme-white{" + "".join("--highlight-toolbar-tab-underline-%s:#fff!important;" % k for k in
                                                     ("document", "spreadsheet", "presentation", "pdf", "visio")) +
           "}.theme-white .toolbar .tabs li:after,.theme-white .toolbar .tabs li.ribtab:after,"
           ".theme-white .toolbar.editor-native-color .tabs li:after{border-top-color:#fff!important}/*XR-TABLINE-END*/")
n_hdr = n_line = 0
for css in glob.glob(os.path.join(E, "web-apps", "apps", "*", "main", "resources", "css", "app.css")):
    t = open(css, encoding="utf-8", errors="surrogateescape").read()
    def teal(m):
        b = re.sub(r"(--toolbar-header-(?:document|spreadsheet|presentation|pdf|visio):)\s*#[0-9A-Fa-f]{3,8}", r"\g<1>" + TEAL, m.group(0))
        return b.replace("/*XR-HEADER-END*/", "/*XR-HEADER-END*/" + TABLINE) if "/*XR-TABLINE*/" not in t else b
    t2 = re.sub(r"/\*XR-HEADER\*/.*?/\*XR-HEADER-END\*/", teal, t, flags=re.S)
    if t2 != t:
        open(css, "w", encoding="utf-8", errors="surrogateescape").write(t2)
        n_hdr += 1
        n_line += "/*XR-TABLINE*/" in t2
log("editor header colour -> Xrero teal in", n_hdr, "stylesheets; white tab underline in", n_line)
if n_line < 4:
    raise SystemExit("tab underline: expected the four editors' app.css, changed %d" % n_line)

# The window title (the file name over the ribbon) in the right-to-left interface (round 3 of the store pictures): the
# header centres the title by padding its box by the difference between the space on its left and on its right
# (Header.js updateDocNamePosition). Both measures are physical - "left" = the box's left offset, "right" = the width of
# the next header group - so right to left, where the next group is on the LEFT and the quick-access buttons on the
# right, both measured the left side: the title was centred in the space beside the buttons, 90 pt left of the window's
# centre in every Arabic editor. Right to left the two sides now swap: left = the next group, right = the groups before
# the box (on its right). Left to right nothing changes. (XR-TITLE-RTL; Mac bundle only)
HDR = os.path.join(E, "web-apps", "apps", "common", "main", "lib", "view", "Header.js")
s = open(HDR, encoding="utf-8").read()
s, n_title = re.subn(
    r"var _left_width = Common\.Utils\.getPosition\(\$parent\)\.left,\s*_right_width = \$parent\.next\(\)\.outerWidth\(\)",
    "var _xrRtl = !!(Common.UI.isRTL && Common.UI.isRTL()), /*XR-TITLE-RTL*/\n"
    "                        _left_width = _xrRtl ? $parent.next().outerWidth() : Common.Utils.getPosition($parent).left,\n"
    "                        _right_width = _xrRtl ? _.reduce($parent.prevAll().toArray(), function (sum, e) { return sum + $(e).outerWidth(); }, 0)"
    " : $parent.next().outerWidth()", s)
if n_title != 2:
    raise SystemExit("window title centring (Header.js updateDocNamePosition): expected 2 places, found %d" % n_title)
open(HDR, "w", encoding="utf-8").write(s)
log("window title centred right to left (Header.js):", n_title, "places")

# Arabic wording in the editors (16 Nov 2026, store-picture review; Mac bundle only, the Windows payload is unchanged):
#  - status bar "Word count": "تعداد الكلمات" (enumeration of the words) -> "عدد الكلمات"
#  - the AI ribbon tab (AI plugin: buttonMainToolbar.text = "AI", shown through the plugin's own translation table,
#    which has no "AI" entry for Arabic) -> "الذكاء الاصطناعي", as the editors' own Arabic text already says
import json
n_ar = 0
for f in glob.glob(os.path.join(E, "web-apps", "apps", "*", "main", "locale", "ar.json")):
    t = open(f, encoding="utf-8").read()
    t2 = t.replace('"تعداد الكلمات"', '"عدد الكلمات"')
    if t2 != t:
        open(f, "w", encoding="utf-8").write(t2)
        n_ar += 1
AI_AR = "الذكاء الاصطناعي"
for f in glob.glob(os.path.join(E, "sdkjs-plugins", "*", "translations", "ar-SA.json")):
    plug = os.path.dirname(os.path.dirname(f))
    try:
        cfg = json.load(open(os.path.join(plug, "config.json"), encoding="utf-8"))
    except Exception:
        continue
    if cfg.get("name") != "AI":
        continue
    tr = json.load(open(f, encoding="utf-8"))
    tr["AI"] = AI_AR
    json.dump(tr, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cfg.setdefault("nameLocale", {})["ar-SA"] = AI_AR
    cfg["nameLocale"]["ar"] = AI_AR
    json.dump(cfg, open(os.path.join(plug, "config.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_ar += 1
log("Arabic wording (word count, AI tab):", n_ar, "files")
if n_ar < 2:
    raise SystemExit("Arabic wording: expected the documenteditor ar.json and the AI plugin, changed %d" % n_ar)
# (16 Nov 2026, store pictures 3-5) the PDF editor's Arabic ribbon showed its Collaboration tab in English: the payload's
# pdfeditor ar.json keeps "Collaboration" there; the document and presentation editors' Arabic text is "التعاون"
n_pdf_ar = 0
for f in glob.glob(os.path.join(E, "web-apps", "apps", "pdfeditor", "main", "locale", "ar.json")):
    t = open(f, encoding="utf-8").read()
    t2 = re.sub(r'("PDFE\.Views\.Toolbar\.textTabCollaboration"\s*:\s*)"Collaboration"', '\\1"التعاون"', t)
    if t2 != t:
        open(f, "w", encoding="utf-8").write(t2)
        n_pdf_ar += 1
log("Arabic wording (PDF editor Collaboration tab):", n_pdf_ar, "files")
# (16 Nov 2026, store pictures round 4) two Arabic labels the pictures show:
#  - the PDF editor's Comment tab button "Text Comment" (it puts a typed text box on the page) is "تعليق للنص" ("a
#    comment for the text"); its own tooltip already says "إدراج تعليق نصي" -> "تعليق نصي"
#  - the presentation editor's notes pane says "اضغط لإضافة ملاحظات" ("press", phone / keyboard wording); a Mac is clicked
#    -> "انقر لإضافة ملاحظات"
AR_LABELS = (("pdfeditor", "PDFE.Views.Toolbar.capBtnTextComment", "تعليق للنص", "تعليق نصي"),
             ("presentationeditor", "PE.Controllers.Main.txtAddNotes", "اضغط لإضافة ملاحظات", "انقر لإضافة ملاحظات"))
for app, key, old_ar, new_ar in AR_LABELS:
    hits = glob.glob(os.path.join(E, "web-apps", "apps", app, "main", "locale", "ar.json"))
    if not hits:
        raise SystemExit("Arabic label %s: no %s ar.json" % (key, app))
    for f in hits:
        t = open(f, encoding="utf-8").read()
        t2, n = re.subn(r'("%s"\s*:\s*)"%s"' % (re.escape(key), re.escape(old_ar)), '\\1"%s"' % new_ar, t)
        if not n and not re.search(r'"%s"\s*:\s*"%s"' % (re.escape(key), re.escape(new_ar)), t):
            raise SystemExit("Arabic label %s: neither %r nor %r in %s" % (key, old_ar, new_ar, f))
        if t2 != t:
            open(f, "w", encoding="utf-8").write(t2)
        log("Arabic label %s -> %s:" % (key, new_ar), n, "changed")
# (16 Nov 2026, store-picture review) the spreadsheet editor's Arabic ribbon calls the same tab "العمل المشترك"; the
# document, presentation and (above) PDF editors say "التعاون" - one name for the tab in all four
n_sse_ar = 0
for f in glob.glob(os.path.join(E, "web-apps", "apps", "spreadsheeteditor", "main", "locale", "ar.json")):
    t = open(f, encoding="utf-8").read()
    t2 = re.sub(r'("SSE\.Views\.Toolbar\.textTabCollaboration"\s*:\s*)"العمل المشترك"', '\\1"التعاون"', t)
    # (16 Nov 2026, run 28: the wider picture window shows the Home tab's cells group) its "Format" button is left in
    # English in the payload's Arabic text, and so is the number-format dialog's "Format" label; the other Arabic
    # strings with this meaning say "التنسيق"
    t2, n_fmt = re.subn(r'("SSE\.Views\.Toolbar\.textCellFormat"\s*:\s*)"Format"', '\\1"تنسيق"', t2)
    t2, n_fmt2 = re.subn(r'("Common\.Views\.FormatSettingsDialog\.textFormat"\s*:\s*)"Format"', '\\1"التنسيق"', t2)
    if re.search(r'"(SSE\.Views\.Toolbar\.textCellFormat|Common\.Views\.FormatSettingsDialog\.textFormat)"\s*:\s*"Format"', t2):
        raise SystemExit("spreadsheet Format button: still English in " + f)
    log("Arabic wording (spreadsheet Format button / format dialog):", n_fmt, n_fmt2)
    if t2 != t:
        open(f, "w", encoding="utf-8").write(t2)
        n_sse_ar += 1
log("Arabic wording (spreadsheet editor Collaboration tab, Format button):", n_sse_ar, "files")
if n_sse_ar != 1:
    raise SystemExit("spreadsheet Collaboration tab: expected the spreadsheeteditor ar.json, changed %d" % n_sse_ar)
# the spreadsheet formula bar in the Arabic (right-to-left) interface took the interface's direction for a formula too:
# "=SUM(B5:D5)" read "SUM(B5:D5)=". Each line now takes its direction from its own first letter (a formula left to
# right, Arabic text right to left), still aligned to the right like the rest of the right-to-left bar
FBIDI = ("/*XR-FBIDI*/.rtl #cell-editing-box .ce-group-content #ce-cell-content{unicode-bidi:plaintext;text-align:right}"
         "/*XR-FBIDI-END*/")
n_fb = 0
for css in glob.glob(os.path.join(E, "web-apps", "apps", "spreadsheeteditor", "main", "resources", "css", "app.css")):
    t = open(css, encoding="utf-8", errors="surrogateescape").read()
    if "#ce-cell-content" in t and "/*XR-FBIDI*/" not in t:
        open(css, "w", encoding="utf-8", errors="surrogateescape").write(t.rstrip() + "\n" + FBIDI + "\n")
        n_fb += 1
log("formula bar direction (right-to-left interface):", n_fb, "stylesheets")
if n_fb != 1:
    raise SystemExit("formula bar direction: expected the spreadsheeteditor app.css, changed %d" % n_fb)

# Hide the Xrero header controls that call Windows-only native commands (PDF->Word converter, Designs dialog,
# EN/AR switch = 'xrero:lang:*' relaunch handled only by the Windows shell, share) - on Mac they would be dead buttons.
# The Mac UI language follows macOS (or the start page's Settings). The account chip + menu stay: web/xr-account.js
# (appended below) answers them on Mac.
# the Xrero account (REQUIRED since 24 Oct 2026, like Windows: sign in / create / sign out / delete) - web/xr-account.js,
# start page + editors; the four apps as large start-page tiles - web/xr-home.js
ACCT_JS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "xr-account.js"), encoding="utf-8").read()
if "/*XR-ACCT-START*/" not in ACCT_JS or "/*XR-ACCT-END*/" not in ACCT_JS:
    raise SystemExit("web/xr-account.js markers missing")
HOME_JS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "xr-home.js"), encoding="utf-8").read()
HOME_JS = HOME_JS.replace("__XR_VERSION__", VERSION)          # the Mac app's own version in the About window
if "/*XR-HOME-START*/" not in HOME_JS or "/*XR-HOME-END*/" not in HOME_JS:
    raise SystemExit("web/xr-home.js markers missing")
MAC_JS = r"""
/*XR-MAC-START*/
(function(){
  if (!/Mac/i.test(navigator.platform || '')) return;
  var css = '#xr-b-ctx,#xr-hdr-btns .xr-lang,#xr-b-share,#xr-designs-launch,#xr-design-ov{display:none!important}' +
    // the account chip's initials in the Mac system font (its Windows face is Segoe UI, absent on a Mac)
    '#xr-hdr-btns .xr-ava{font:600 10.5px/24px -apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif!important;letter-spacing:.2px}' +
    // XR-PRESENT (round 3 of the store pictures): the presentation editor's red Present button (the payload's
    // stylePresentButton) - its label ran into the split divider (Bootstrap's ".btn-group .btn + .btn" margin wins over
    // the payload's 7 px) and its chevron was half dark on the red (only the top border was made white). The label in
    // the Mac system font (its Windows face, Segoe UI, is absent), 9 px before the divider; the chevron white
    '#slot-status-btn-preview .xr-present-btn .xr-present-label{font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif!important;margin-inline-end:9px!important}' +
    '#slot-status-btn-preview .xr-present-btn .dropdown-toggle .caret{border-color:#fff!important}';
  function add(){
    if (document.getElementById('xr-mac-css')) return;
    var s = document.createElement('style'); s.id = 'xr-mac-css'; s.textContent = css;
    (document.head || document.documentElement).appendChild(s);
  }
  add(); document.addEventListener('DOMContentLoaded', add);
  // ONLYOFFICE's first-run "New: Paste options / Multipage view / Chart tab ..." tips (TooltipManager, isNewFeature)
  // announce the engine's release news on top of the user's document the first time each editor opens. Same as the
  // iOS app (ios/web/xr-host.js noFeatureTips): their "already seen" keys - '<de|sse|pe|pdfe>-help-tip-*' and the
  // 'help-tip-*' New-labels - read as seen. Only these announcement keys: the features themselves stay, and the real
  // warnings (connection lost, read-only, licence ...) have no such key and still show.
  (function noFeatureTips(){
    var re = /(^|-)help-tip-/;
    try {
      var gi = Storage.prototype.getItem;
      Storage.prototype.getItem = function (k) { return re.test(String(k)) ? '1' : gi.apply(this, arguments); };
    } catch (e) {}
    var n = 0, t = setInterval(function () {          // the editors' own store too (used when localStorage is off)
      var ls = window.Common && Common.localStorage;
      if (ls && ls.getItem && !ls.getItem.__xr) {
        var g = ls.getItem;
        ls.getItem = function (k) { return re.test(String(k)) ? '1' : g.apply(this, arguments); };
        ls.getItem.__xr = true;
      }
      if (++n > 1200) clearInterval(t);
    }, 25);
    window.__xrNoFeatureTips = true;
  })();
  // PDF forms (sdkjs 9.4): Enter on a focused check box or radio button - the keyboard way to tick it - changed the
  // box on screen only. CPDFDoc.EnterDownActiveField calls the box's onMouseUp() outside an editing action and never
  // commits it, so Save wrote the box as "Off" (store capture run 28: ticked in the app, "Off" in the saved file and
  // after reopening) and the editor logged "changesError". A mouse click goes through CPDFDoc.OnMouseUpField: the
  // same toggle inside DoAction, then the commit. Enter on a box now takes that path; every other field keeps the
  // original function. (16 Nov 2026; Mac bundle only)
  (function pdfKeyTick(){
    var n = 0, t = setInterval(function () {
      var P = window.AscPDF, D = P && P.CPDFDoc && P.CPDFDoc.prototype, T = P && P.FIELD_TYPES;
      if (D && T && D.EnterDownActiveField && D.OnMouseUpField) {
        clearInterval(t);
        if (D.EnterDownActiveField.__xr) return;
        var orig = D.EnterDownActiveField;
        D.EnterDownActiveField = function () {
          var f = this.activeForm, k = f && f.GetType && f.GetType();
          if (f && f.IsInForm && f.IsInForm() && (k === T.checkbox || k === T.radiobutton)) {
            if (this.SetGlobalHistory) this.SetGlobalHistory();
            f.SetInForm(false);
            this.GetController().resetSelection();
            this.OnMouseUpField(f);
            window.__xrPdfKeyTick = (window.__xrPdfKeyTick || 0) + 1;
            return;
          }
          return orig.apply(this, arguments);
        };
        D.EnterDownActiveField.__xr = true;
      } else if (++n > 2400) clearInterval(t);
    }, 25);
  })();
  // XR-FIELD-FIRST-INPUT (16 Nov 2026, store NOTES "first letter lost"): the first thing typed into a PDF form field in
  // a script the editor had not used yet (digits in the Arabic form's date field) did not arrive; typed letter by letter
  // the first letter was lost, typed as one piece the whole piece. The engine's input log (scripts/engine_checks.py,
  // build-mac run 39) shows the text reaching the PDF editor's text entry (asc_enterText) and being refused: the entry
  // asks for the active field (CPDFDoc.getTextController), which first checks that the field's fonts are in the
  // document's loaded list (checkFieldFont) - the font chosen for the new script is not yet, so it starts loading it and
  // answers "no field", and the text is dropped (the next input finds the font listed and works).
  // Two layers (17 Nov 2026 review):
  //  1. checkFieldFont itself: when the fonts it starts loading are already there, the font loader calls back BEFORE
  //     checkFieldFont returns (fontLoader.LoadFonts checks at once) - the fonts are then listed, yet the caller is told
  //     "not ready". That is the case of the date field (run 43's input log: the callback ran inside the call). Such a
  //     call now answers "ready" and does not call the caller's callback; a load that is really pending keeps the
  //     contract (false now, the callback later). This fixes every caller of getTextController at once: text entry,
  //     IME composition, autocorrect, the caret update.
  //  2. a load that is really pending (font files read asynchronously): the text entry holds the input back in ONE
  //     ordered queue - while it is not empty every later typed input joins it - and enters the queue in order, into the
  //     same field, when the fonts are loaded; if the field is no longer the one being edited the queue is dropped (the
  //     old behaviour: lost, never typed elsewhere). Paste is not queued (it loads its fonts itself before it enters).
  // (window.__xrNoFirstInputFix = both off, the original path, for the engine checks' control rounds)
  (function fieldFirstInput(){
    var n = 0, t = setInterval(function () {
      var A = window.Asc && window.Asc.editor, P = window.AscPDF, D = P && P.CPDFDoc && P.CPDFDoc.prototype;
      if (A && A.asc_enterText && A.getPDFDoc && D && D.checkFieldFont) {
        clearInterval(t);
        var off = function () { return !!window.__xrNoFirstInputFix; };
        var bump = function (k, by) { window[k] = (window[k] || 0) + (by === undefined ? 1 : by); };
        if (!D.checkFieldFont.__xr) {
          var cff = D.checkFieldFont;
          D.checkFieldFont = function (oField, callback) {
            if (off()) return cff.apply(this, arguments);
            var running = true, sync = false, r;
            try {
              r = cff.call(this, oField, function () {
                if (running) { sync = true; return; }          // loaded inside the call: answered "ready" below
                if (typeof callback === 'function') return callback.apply(this, arguments);
              });
            } finally { running = false; }
            if (!r && sync) { bump('__xrFieldFontSync'); return true; }
            return r;
          };
          D.checkFieldFont.__xr = true;
        }
        if (A.asc_enterText.__xr) return;
        var orig = A.asc_enterText, q = [];
        var drop = function () { if (q.length) { bump('__xrFirstInputDropped', q.length); q.length = 0; } };
        var flush = function () {
          while (q.length) {
            var it = q[0];
            if (it.doc.activeForm !== it.f || !(it.f.IsInForm && it.f.IsInForm())) { drop(); return; }
            var ready = true;
            try { ready = it.doc.checkFieldFont(it.f, flush); } catch (e) { ready = true; }
            if (!ready) return;                                // more to load: flush runs again when it is loaded
            q.shift();
            bump('__xrFirstInputRetried');
            try { orig.apply(it.api, it.args); } catch (e) {}
          }
        };
        A.asc_enterText = function (codePoints, isFromPaste) {
          if (isFromPaste || off()) return orig.apply(this, arguments);
          var doc = null, f = null;
          try { doc = this.getPDFDoc(); f = doc && doc.activeForm; } catch (e) {}
          var item = {api: this, args: [codePoints && codePoints.slice ? codePoints.slice() : codePoints, isFromPaste],
                      doc: doc, f: f, t: Date.now()};
          if (q.length) {
            // an earlier input still waits for this field's fonts: this one goes after it (4 s at most, then the old path)
            if (f && f === q[0].f && f.IsInForm && f.IsInForm() && item.t - q[0].t < 4000) {
              q.push(item); bump('__xrFirstInputHeld'); return true;
            }
            drop();
          }
          if (doc && f && f.IsInForm && f.IsInForm() && f.IsCanEditText && f.IsCanEditText()) {
            var ready = true;
            try { ready = doc.checkFieldFont(f, flush); } catch (e) { ready = true; }
            if (!ready) { q.push(item); bump('__xrFirstInputHeld'); return true; }
          }
          return orig.apply(this, arguments);
        };
        A.asc_enterText.__xr = true;
      } else if (++n > 2400) clearInterval(t);
    }, 25);
  })();
})();
/*XR-MAC-END*/
"""
# the editors' account chip (the payload's header): the initials of an Arabic name skip its article, as on the start
# page (web/xr-account.js): "فريق المشاريع" -> "فم", not "فا" (16 Nov 2026; Mac bundle only)
INI_OLD = "var p=n.split(/\\s+/); return ((p[0][0]||'')+(p.length>1?(p[p.length-1][0]||''):'')).toUpperCase(); }"
INI_NEW = ("var p=n.split(/\\s+/); var i1=function(w){return /^\\u0627\\u0644[\\u0621-\\u064A]{2,}/.test(w)?w[2]:(w[0]||'');}; "
           "return (i1(p[0])+(p.length>1?i1(p[p.length-1]):'')).toUpperCase(); }")
# the Present button's Arabic label (round 3): "عرض تقديمي" is the noun "a presentation" - the name of the Presentation
# app on the start page - on a button that starts the slide show; "بدء العرض" (start the show), the words of the
# button's own tooltip in the editor's Arabic text (PE.Views.Statusbar.tipPreview)
PRESENT_OLD = "var txt=(lang()==='en' ? 'Present' : 'عرض تقديمي');"
PRESENT_NEW = "var txt=(lang()==='en' ? 'Present' : 'بدء العرض');"
n_ini = n_present = 0
for e in ("documenteditor", "spreadsheeteditor", "presentationeditor", "pdfeditor"):
    f = os.path.join(E, "web-apps", "apps", e, "main", "app.js")
    if os.path.exists(f):
        s = open(f, encoding="utf-8").read()
        s = s.replace(INI_OLD, INI_NEW)
        n_ini += INI_NEW in s
        s = s.replace(PRESENT_OLD, PRESENT_NEW)
        n_present += e == "presentationeditor" and PRESENT_NEW in s
        s = re.sub(r"\n?/\*XR-MAC-START\*/.*?/\*XR-MAC-END\*/\n?", "", s, flags=re.S)
        s = re.sub(r"\n?/\*XR-ACCT-START\*/.*?/\*XR-ACCT-END\*/\n?", "", s, flags=re.S)
        open(f, "w", encoding="utf-8").write(s.rstrip() + "\n" + MAC_JS + ACCT_JS + "\n")
log("mac header shim (+ no first-run feature tips) + Xrero account appended to app.js; Arabic initials:", n_ini, "editors")
if n_ini != 4:
    raise SystemExit("account chip initials: expected the four editors' app.js, changed %d" % n_ini)
if n_present != 1:
    raise SystemExit("Present button Arabic label: not found in the presentation editor's app.js")
log("Present button: Arabic label 'بدء العرض'")
# the engine functions the shims above wrap at run time (MAC_JS: pdfKeyTick, XR-FIELD-FIRST-INPUT) and the sdkjs patches
# below change or call must be in this payload's sdkjs under these names - a payload whose engine renamed them would leave
# a shim silently idle (XR-FIELD-AP: or quietly back on the old unshaped text), so a renamed engine fails the build here
SDK_WORD = open(os.path.join(E, "sdkjs", "word", "sdk-all.js"), encoding="utf-8", errors="surrogateescape").read()
for need in ("CBaseField.prototype.WriteRenderToBinary = function(memory)", "CDocumentRenderer.prototype.tg = function(gid, x, y, codePoints)",
             "LoadStringPathCode : function(code, isGid, fX, fY, worker)", "window['AscFonts'].getEmbeddedFontPrefix = function()",
             # XR-FIELD-AP's private internals (the renderer's current font, the measurer's font set-up, the glyph outline)
             "return this.m_arrayPages[this.m_lPagesCount - 1].m_oFont;",
             "SetFontInternal : function(_name, _size, _style, _dpi)",
             "this.m_pFont.GetStringPath(string, worker);",
             "this.GetGIDByUnicode = function(glyph)",
             "this.GetFirstGlyph = function()",
             "this.m_oGlyphString = new AscFonts.CGlyphString();",
             "this.m_oLastFont = new AscCommon.CFontSetup();",
             "extendFonts : function(fonts, isNoRealExtend)",
             "CPDFDoc.prototype.EnterDownActiveField = function()",
             # XR-FIELD-FIRST-INPUT: checkFieldFont (wrapped), its caller, and the loader that calls back inside the call
             "CPDFDoc.prototype.checkFieldFont = function(oField, callback)",
             "CPDFDoc.prototype.getTextController = function()",
             "if (activeForm && this.checkFieldFont(activeForm) && activeForm.IsCanEditText())",
             "this.LoadFonts = function(fonts, callback)",
             "this.fontLoader             = AscCommon.g_font_loader;"):
    if need not in SDK_WORD:
        raise SystemExit("engine shim target missing in the payload's sdkjs: " + need)
SDK_WORD_MIN = open(os.path.join(E, "sdkjs", "word", "sdk-all-min.js"), encoding="utf-8", errors="surrogateescape").read()
for need in ("PDFEditorApi.prototype.asc_enterText = function(codePoints, isFromPaste)",):
    if need not in SDK_WORD_MIN:
        raise SystemExit("engine shim target missing in the payload's sdkjs (min): " + need)
log("engine shim targets present in sdkjs/word/sdk-all.js + sdk-all-min.js")

# XR-FIELD-AP (16 Nov 2026, APP-BACKLOG 18, HIGH): Arabic typed into a PDF form field whose font is EMBEDDED in the PDF
# (/DR - many real Arabic forms, and the Windows store demo's /Dubai) looked right while typing but was saved as
# separate, overlapping letters - in the app after reopening and in every other PDF reader (build-mac runs 39-42:
# ink match 0.44 with the same text shaped in the same font; Latin 1.0). On Save a changed field's appearance is drawn
# by sdkjs (CBaseField.WriteRenderToBinary) with its shaped glyphs - glyph id + code points (CDocumentRenderer.tg) -
# and the native converter writes them into the PDF. For a font embedded in the PDF the converter takes the glyph by its
# FIRST CODE POINT, not by the glyph id (core PdfWriter CFontEmbedded::EncodeUnicode looks the code point up in the
# font's ToUnicode first), so every Arabic letter got its isolated form at the place of its joined form, and lam-alef
# lost its alef. In a field's appearance, a glyph of an embedded font that the converter cannot address by its code
# point - a shaped form, a ligature, any complex-script glyph - is now drawn as its outline (the same font program, the
# same place, the same colour): the PDF shows exactly what the editor showed. Glyphs the code point gives right (Latin,
# digits) stay text; fields in system fonts (the converter embeds those by glyph id) and all other drawing are
# unchanged; if no outline comes out for a glyph it goes as text, as before. This is a change of sdkjs itself, not a
# shim in the editor page: since 8.2 the desktop app builds the saved PDF in the converter from the editor's changes
# (sdkjs isSupportSaveInPDF), so the field appearance is drawn by the converter's copy of sdk-all.js (run 42: a shim in
# the editor page was installed on the field and never called by the save). (Mac bundle only.)
FIELD_AP_JS = r"""
/*XR-FIELD-AP-START*/
(function (window) {
  var AscCommon = window['AscCommon'];
  if (!AscCommon) return;
  // counters of the last saves in this context (the editor page's copy is read by scripts/engine_checks.py)
  var dbg = AscCommon.xrFieldApStat = {writes: 0, flagged: 0, outlines: 0, text: 0, why: {}, names: {}, err: ''};
  try { window['__xrFieldApDbg'] = dbg; } catch (e) {}
  var why = function (k) { dbg.why[k] = (dbg.why[k] || 0) + 1; };
  var complex = function (c) {
    return (c >= 0x0590 && c <= 0x08FF) || (c >= 0x0900 && c <= 0x0DFF) || (c >= 0x0E00 && c <= 0x0EFF) ||
           (c >= 0xFB1D && c <= 0xFDFF) || (c >= 0xFE70 && c <= 0xFEFF) || c === 0x200C || c === 0x200D;
  };
  // true = the glyph was drawn as its outline; false = draw it as text (the original path)
  AscCommon.xrFieldApTg = function (dr, gid, x, y, codePoints) {
    if (!(dr.m_lPagesCount > 0)) return false;
    dbg.flagged++;
    var mem = dr.Memory, p0 = mem ? mem.pos : -1;
    try {
      var F = window['AscFonts'], prefix = F && F.getEmbeddedFontPrefix ? F.getEmbeddedFontPrefix() : 'Embedded: ';
      var mf = dr.m_arrayPages[dr.m_lPagesCount - 1], f = mf && mf.m_oFont;
      var nm = f && typeof f.Name === 'string' ? f.Name : '';
      if (Object.keys(dbg.names).length < 12) dbg.names[nm] = (dbg.names[nm] || 0) + 1;
      if (nm.indexOf(prefix) !== 0) { why('not an embedded font'); dbg.text++; return false; }
      var cps = codePoints || [], need = cps.length !== 1, tm = AscCommon.g_oTextMeasurer;
      for (var i = 0; !need && i < cps.length; i++) need = complex(cps[i]);
      // this font, freshly set up in the measurer's own font manager (72 dpi: outlines in mm, as the page)
      if (tm.m_oLastFont) tm.m_oLastFont.SetUpName = '';
      var font = tm.SetFontInternal(nm, f.FontSize, Math.max(f.Style || 0, 0));
      var mgr = tm.m_oManager;
      if (!font || !mgr || mgr.m_pFont !== font || !mgr.LoadStringPathCode) { why('font not set up'); dbg.text++; return false; }
      if (!need) need = font.GetGIDByUnicode(cps[0]) !== gid;
      if (!need) { why('text: its code point gives it'); dbg.text++; return false; }
      var g0 = mgr.m_oGlyphString.GetFirstGlyph();
      g0.fX = 0; g0.fY = 0;
      mgr.LoadStringPathCode(gid, true, x, y, dr);
      // an outline = a path start + its points + a fill + an end (more than the 7 bytes of an empty frame)
      if (mem && mem.pos - p0 >= 8) { dbg.outlines++; return true; }
      why('no outline');
    } catch (e) { dbg.err = '' + e; why('error'); }
    if (mem && p0 >= 0 && mem.pos > p0) mem.pos = p0;
    dbg.text++;
    return false;
  };
})(window);
/*XR-FIELD-AP-END*/
"""
FIELD_AP_DRAW_OLD = "oContentToDraw.Draw(oContentToDraw.GetAbsolutePage(), memory.docRenderer);"
FIELD_AP_DRAW_NEW = ("if (AscCommon.xrFieldApStat) AscCommon.xrFieldApStat.writes++; /*XR-FIELD-AP*/\n"
                     "        memory.docRenderer.__xrFieldAp = true;\n"
                     "        try { oContentToDraw.Draw(oContentToDraw.GetAbsolutePage(), memory.docRenderer); }\n"
                     "        finally { memory.docRenderer.__xrFieldAp = false; }")
FIELD_AP_TG_OLD = "CDocumentRenderer.prototype.tg = function(gid, x, y, codePoints)\n\t{\n"
FIELD_AP_TG_NEW = ("CDocumentRenderer.prototype.tg = function(gid, x, y, codePoints)\n\t{\n"
                   "\t\tif (this.__xrFieldAp && AscCommon.xrFieldApTg && AscCommon.xrFieldApTg(this, gid, x, y, codePoints)) return; /*XR-FIELD-AP*/\n")
f = os.path.join(E, "sdkjs", "word", "sdk-all.js")
t = open(f, encoding="utf-8", errors="surrogateescape", newline="").read()        # (line ends kept as they are)
if "/*XR-FIELD-AP-START*/" not in t:
    nl = "\r\n" if "\r\n" in t[:20000] else "\n"
    for old, new in ((FIELD_AP_DRAW_OLD, FIELD_AP_DRAW_NEW), (FIELD_AP_TG_OLD, FIELD_AP_TG_NEW)):
        k = t.count(old.replace("\n", nl))
        if k != 1:
            raise SystemExit("XR-FIELD-AP: expected 1 place in sdkjs/word/sdk-all.js for %r, found %d" % (old[:60], k))
        t = t.replace(old.replace("\n", nl), new.replace("\n", nl))
    t = t.rstrip("\r\n") + nl + FIELD_AP_JS.replace("\n", nl)
    open(f, "w", encoding="utf-8", errors="surrogateescape", newline="").write(t)
log("Arabic in embedded-font PDF form fields saved as drawn (XR-FIELD-AP, sdkjs/word/sdk-all.js)")

# XR-PPTX-BIDI-LANG (16 Nov 2026, store NOTES "presentation status bar language"): Arabic slide text written as
# lang="ar-AE" was reported as "Arabic (Saudi Arabia)". A DrawingML run has ONE language (a:rPr lang), and the reader
# (sdkjs BinaryPPTYLoader.ReadRunProperties) puts it into Lang.Val only, while the editor reads the language of right-
# to-left text from Lang.Bidi (CFontCalculator: the status bar; the spell checker), which then fell back to the
# default ar-SA. For a run whose language is a right-to-left one (Arabic, Hebrew, Persian, Urdu ...) that language is
# now also its Lang.Bidi - what Word documents already carry (w:lang w:bidi), and what the document editor reports.
# Nothing is written differently (a:rPr lang is still Lang.Val); left-to-right languages are unchanged. All bundles
# that read DrawingML text (presentations, and charts / shapes in the other editors); the macOS converter (JSC) loads
# the same files.
PPTX_LANG_OLD = ("var nLcid = Asc.g_oLcidNameToIdMap[lang];\n"
                 "                        if(nLcid)\n"
                 "                            rPr.Lang.Val = nLcid;")
PPTX_LANG_NEW = ("var nLcid = Asc.g_oLcidNameToIdMap[lang];\n"
                 "                        if(nLcid)\n"
                 "                            rPr.Lang.Val = nLcid;\n"
                 "                        /*XR-PPTX-BIDI-LANG*/ if(nLcid && /^(ar|he|iw|fa|prs|ur|ps|ug|yi|dv|syr|ckb)(-|$)|^(sd|pa)-PK$|^(sd|ku|pa|ks|az|uz)-Arab(-|$)/i.test(lang))\n"
                 "                            rPr.Lang.Bidi = nLcid;")
n_lang = 0
for b in ("word", "slide", "cell", "visio"):
    f = os.path.join(E, "sdkjs", b, "sdk-all.js")
    if not os.path.exists(f):
        continue
    t = open(f, encoding="utf-8", errors="surrogateescape", newline="").read()       # (line ends kept as they are)
    if "/*XR-PPTX-BIDI-LANG*/" in t:          # (already patched: counted as done, so a second run stays green)
        n_lang += 1
        continue
    nl = "\r\n" if PPTX_LANG_OLD.replace("\n", "\r\n") in t else "\n"
    k = t.count(PPTX_LANG_OLD.replace("\n", nl))
    if k != 1:
        raise SystemExit("DrawingML run language reader: expected 1 place in sdkjs/%s/sdk-all.js, found %d" % (b, k))
    open(f, "w", encoding="utf-8", errors="surrogateescape", newline="").write(
        t.replace(PPTX_LANG_OLD.replace("\n", nl), PPTX_LANG_NEW.replace("\n", nl)))
    n_lang += 1
log("right-to-left run language also as Lang.Bidi (DrawingML reader):", n_lang, "bundles")
if n_lang < 2:
    raise SystemExit("DrawingML run language reader: expected at least the document and presentation bundles, changed %d" % n_lang)

# ---------------------------------------------------------------- start page
login = os.path.join(RES, "login", "index.html")
s = open(os.path.join(PAYLOAD, "login", "index.html"), encoding="utf-8").read()
n0 = len(s)
# the Windows sign-in wall waits for the Windows shell's answer - on Mac nobody answers and it would never unlock; the
# Mac gets its own required account card (web/xr-account.js, talks to xrero.com itself) + the four app tiles
s, n_wall = re.subn(r'<script id="xrero-wall">.*?</script>\s*',
                    lambda m: '<script id="xrero-account">' + ACCT_JS + '</script>\n<script id="xrero-home">' + HOME_JS + '</script>\n',
                    s, flags=re.S)
# "Open PDF as DOCX..." needs the Windows PDF converter
s, n_conv = re.subn(r"function addConvertItem\(\)\s*\{", "function addConvertItem(){ if (/Mac/i.test(navigator.platform||'')) return true;", s)
if n_wall != 1 or n_conv != 1:
    raise SystemExit("start page anchors not found (wall=%d convert=%d)" % (n_wall, n_conv))
open(login, "w", encoding="utf-8").write(s)
log("start page: wall -> Xrero account (required) + four app tiles, convert item disabled (%d -> %d chars)" % (n0, len(s)))

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
