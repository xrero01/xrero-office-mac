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
n_hdr = 0
for css in glob.glob(os.path.join(E, "web-apps", "apps", "*", "main", "resources", "css", "app.css")):
    t = open(css, encoding="utf-8", errors="surrogateescape").read()
    def teal(m):
        return re.sub(r"(--toolbar-header-(?:document|spreadsheet|presentation|pdf|visio):)\s*#[0-9A-Fa-f]{3,8}", r"\g<1>" + TEAL, m.group(0))
    t2 = re.sub(r"/\*XR-HEADER\*/.*?/\*XR-HEADER-END\*/", teal, t, flags=re.S)
    if t2 != t:
        open(css, "w", encoding="utf-8", errors="surrogateescape").write(t2)
        n_hdr += 1
log("editor header colour -> Xrero teal in", n_hdr, "stylesheets")

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
# (16 Nov 2026, store-picture review) the spreadsheet editor's Arabic ribbon calls the same tab "العمل المشترك"; the
# document, presentation and (above) PDF editors say "التعاون" - one name for the tab in all four
n_sse_ar = 0
for f in glob.glob(os.path.join(E, "web-apps", "apps", "spreadsheeteditor", "main", "locale", "ar.json")):
    t = open(f, encoding="utf-8").read()
    t2 = re.sub(r'("SSE\.Views\.Toolbar\.textTabCollaboration"\s*:\s*)"العمل المشترك"', '\\1"التعاون"', t)
    if t2 != t:
        open(f, "w", encoding="utf-8").write(t2)
        n_sse_ar += 1
log("Arabic wording (spreadsheet editor Collaboration tab):", n_sse_ar, "files")
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
    '#xr-hdr-btns .xr-ava{font:600 10.5px/24px -apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif!important;letter-spacing:.2px}';
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
})();
/*XR-MAC-END*/
"""
# the editors' account chip (the payload's header): the initials of an Arabic name skip its article, as on the start
# page (web/xr-account.js): "فريق المشاريع" -> "فم", not "فا" (16 Nov 2026; Mac bundle only)
INI_OLD = "var p=n.split(/\\s+/); return ((p[0][0]||'')+(p.length>1?(p[p.length-1][0]||''):'')).toUpperCase(); }"
INI_NEW = ("var p=n.split(/\\s+/); var i1=function(w){return /^\\u0627\\u0644[\\u0621-\\u064A]{2,}/.test(w)?w[2]:(w[0]||'');}; "
           "return (i1(p[0])+(p.length>1?i1(p[p.length-1]):'')).toUpperCase(); }")
n_ini = 0
for e in ("documenteditor", "spreadsheeteditor", "presentationeditor", "pdfeditor"):
    f = os.path.join(E, "web-apps", "apps", e, "main", "app.js")
    if os.path.exists(f):
        s = open(f, encoding="utf-8").read()
        s = s.replace(INI_OLD, INI_NEW)
        n_ini += INI_NEW in s
        s = re.sub(r"\n?/\*XR-MAC-START\*/.*?/\*XR-MAC-END\*/\n?", "", s, flags=re.S)
        s = re.sub(r"\n?/\*XR-ACCT-START\*/.*?/\*XR-ACCT-END\*/\n?", "", s, flags=re.S)
        open(f, "w", encoding="utf-8").write(s.rstrip() + "\n" + MAC_JS + ACCT_JS + "\n")
log("mac header shim (+ no first-run feature tips) + Xrero account appended to app.js; Arabic initials:", n_ini, "editors")
if n_ini != 4:
    raise SystemExit("account chip initials: expected the four editors' app.js, changed %d" % n_ini)

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
