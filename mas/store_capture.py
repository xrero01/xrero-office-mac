#!/usr/bin/env python3
"""store_capture.py <Xrero Office.app> <shots|audit|switch> <en|ar> <out dir> <demo.docx | inputs dir>

Mac App Store pictures (16 Nov 2026) from the real app on the CI Mac - meant for the App Store variant (sandboxed test
copy, ad hoc): nothing here talks to App Store Connect, and no account is created on xrero.com (the workflow blocks
xrero.com while this runs; the start page's sign-in card gets the locally stored state of a signed-in user, the same as
the previous pictures' local render).

shots: the app in the chosen interface language (the app's own setting, asc_user_ui_lang = en-US / ar-SA), the window
       at the largest size the screen allows. First four demo files are opened from Finder once (a document, a
       spreadsheet, a presentation, a PDF) so the start page lists them under Recent files, as a user's would; then
       the app starts again and the start page is photographed, then the neutral demo document (mas/store_demo.docx,
       mas/store_demo_ar.docx for ar) opened from Finder as "Q3 report.docx" (en) / "التقرير الربعي.docx" (ar), the
       caret in its Arabic summary (the status bar and the ribbon show the Arabic paragraph), then (16 Nov 2026, the
       five-picture set) the other three demo files in the same window, each in its own tab:
         sheet  store_demo_sheet[_ar].xlsx - E5 selected (=SUM(B5:D5) in the formula bar), the column chart beside it
         slide  store_demo_slides[_ar].pptx - a real click into slide 1's title, the caret then put after its text
         pdf    store_demo_form[_ar].pdf - the Comment tab, then the reviewer's marks made with its tools (16 Nov
                2026: the deadline line selected with the mouse + Highlight, a circle drawn with the red pen around
                the date field, a sticky note added with right click > Add comment beside it), then the form filled
                the way a user does it: Tab to each field, type, Enter on the check boxes to tick; the caret is left
                in the Notes field. After the pictures the form is saved (Cmd+S), read back from the file and opened
                again in the app (pdf_roundtrip: the store text may say "form filling and comments" only if it holds)
       Each picture is written twice:
         <lang>-<name>-window.png  the window as the screen shows it (screencapture, 1x on the CI display)
         <lang>-<name>-page2x.png  the same page drawn by the app at Retina scale (DevTools, device scale 2)
audit: first run in a fresh container: what a user sees in the first seconds and on the first open of each editor
       (Word, spreadsheet, presentation, PDF): tip balloons, dialogs, extra windows -> audit-*.png + capture-audit.json.
switch: after audit, the same container relaunched in the other language (what a user does in Settings > Interface
       language): the start page must follow it (direction, account pill on the far side, not over the sidebar).
Window size (16 Nov 2026 review): the spreadsheet and presentation ribbons folded groups into "More" at the 1024 pt
       window and left a gap beside it. audit (en) and switch (ar) measure, in the spreadsheet and presentation editors,
       the narrowest window width at which nothing is folded (ribbon-fit.json); shots then takes ALL ten pictures at
       that one width (WIN_H high) - mas/hidpi.swift gives the CI display a 1600 x 1200 mode for it.
"""
import asyncio, base64, json, os, plistlib, re, shutil, subprocess, sys, time
import aiohttp

APP, MODE, LANG, OUT, SRC = sys.argv[1:6]
APP, OUT, SRC = os.path.abspath(APP), os.path.abspath(OUT), os.path.abspath(SRC)
EXE = os.path.join(APP, "Contents", "MacOS", plistlib.load(open(os.path.join(APP, "Contents", "Info.plist"), "rb"))["CFBundleExecutable"])
BID = "com.xrero.office"
PORT = 9333
CODE = {"en": "en-US", "ar": "ar-SA"}[LANG]
HERE = os.path.dirname(os.path.abspath(__file__))
# the names the pictures show (tab titles, Recent files); short enough for whole tab titles (run 23: "Projects 2026.xlsx",
# "*Room request.pdf", "عرض الربع الثالث.pptx" were cut to "...", and a name with digits read out of order right to left)
NAMES = {"en": dict(editor="Q3 report.docx", sheet="Projects.xlsx", slide="Q3 review.pptx", pdf="Booking.pdf"),
         "ar": dict(editor="التقرير الربعي.docx", sheet="المشاريع.xlsx", slide="الربع الثالث.pptx", pdf="حجز قاعة.pdf")}[LANG]
DOC_NAME = NAMES["editor"]
SUF = "_ar" if LANG == "ar" else ""
DEMO = {"sheet": os.path.join(HERE, "store_demo_sheet%s.xlsx" % SUF), "slide": os.path.join(HERE, "store_demo_slides%s.pptx" % SUF),
        "pdf": os.path.join(HERE, "store_demo_form%s.pdf" % SUF)}
FONT = "Geeza Pro" if LANG == "ar" else "Helvetica Neue"      # the demo files' face (store_demo.py)
# the signed-in account the pictures show: a team, not a person (16 Nov 2026 review: "Xrero Office" read as a product
# badge, not an account); its initials are on the start page pill and the editors' account chip
ACCOUNT = {"en": ("Projects team", "PT"), "ar": ("فريق المشاريع", "فم")}[LANG]
# the window of all ten pictures: its width comes from ribbon-fit.json (picture_width), its height is fixed
WIN_H = 800
RIBBON_FIT = os.path.join(OUT, "ribbon-fit.json")
# the sticky note the capture adds beside the date field (the PDF picture)
PDF_NOTE = {"en": "The main room is free on this date.", "ar": "القاعة الكبرى متاحة في هذا التاريخ."}[LANG]
# the Recent files' times on the start picture: working hours, newest first (run 27 showed the CI's 03:31-03:36)
RECENT_TIMES = ["10:40", "10:31", "10:22", "10:15"]
# the folder the pictures' files are opened from: the start picture's Recent files show its path (run 28 showed the CI
# checkout, "...ro-office-mac/out/store/docs-shots-ar/"), so shots use a neutral shared folder with no user name in its
# path; its files are copied into OUT/docs-shots-<lang> at the end (evidence). audit / switch keep their OUT folder.
DOCS = "/Users/Shared/Office files" if MODE == "shots" else os.path.join(OUT, "docs-%s-%s" % (MODE, LANG))
if MODE == "shots":
    shutil.rmtree(DOCS, ignore_errors=True)
# the Recent files of the start picture: the four demo files of the pictures, opened oldest first
RECENTS = [(NAMES["pdf"], DEMO["pdf"]), (NAMES["slide"], DEMO["slide"]), (NAMES["sheet"], DEMO["sheet"]), (DOC_NAME, "DEMO")]
# the PDF form as the capture fills it in (store_demo.py PDF_FIELDS order = the form's tab order); True = tick (Enter)
PDF_FILL = {"en": [("department", "Projects"), ("office", "Sharjah"), ("date", "24 Nov 2026"), ("attendees", "12"),
                   ("display", True), ("video", True), ("refreshments", False),
                   ("notes", "Q3 results review with the office teams")],
            # (runs 23-25: the Arabic form's date field drops the FIRST letter typed into it - run 25 typed "24/11/2026"
            # letter by letter: "2" was lost, "4/11/2026" stayed; typed as one piece the whole piece was lost. prep_pdf
            # types the missing start again at the field's start, as a user would - mas/store/NOTES.md)
            "ar": [("department", "المشاريع"), ("office", "الشارقة"), ("date", "24/11/2026"), ("attendees", "12"),
                   ("display", True), ("video", True), ("refreshments", False),
                   ("notes", "مراجعة نتائج الربع الثالث مع فرق المكاتب")]}[LANG]
PROC = 'tell application "System Events" to tell (first process whose bundle identifier is "%s")' % BID
os.makedirs(OUT, exist_ok=True)
res = {"mode": MODE, "lang": CODE, "shots": [], "log": []}


def log(*a):
    s = " ".join(str(x) for x in a)
    res["log"].append(s)
    print(s, flush=True)


def osa(*lines):
    try:
        r = subprocess.run(["osascript"] + [a for l in lines for a in ("-e", l)], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        # (run 23: "quit" waits on the app's "save changes?" question after the form was filled - ensure_quit goes on)
        log("osascript timed out:", lines[0][:80])
        return "timeout"
    return (r.stdout or r.stderr).strip()


def set_language():
    """the app's own interface-language setting (what Settings > Interface language writes), for the plain and the
    sandboxed (container) preferences; read by the app at launch"""
    cont = os.path.expanduser("~/Library/Containers/%s/Data/Library/Preferences/%s" % (BID, BID))
    for dom in [BID] + ([cont] if os.path.isdir(os.path.dirname(cont)) else []):
        subprocess.run(["defaults", "write", dom, "asc_user_ui_lang", "-string", CODE], capture_output=True)
    subprocess.run(["killall", "-u", os.environ.get("USER", ""), "cfprefsd"], capture_output=True)
    time.sleep(1)


def visible_frame():
    """the screen area a window may use (below the menu bar, beside the Dock), top-left origin, points"""
    js = ("ObjC.import('AppKit');var s=$.NSScreen.mainScreen,f=s.frame,v=s.visibleFrame;"
          "JSON.stringify([v.origin.x, f.size.height-(v.origin.y+v.size.height), v.size.width, v.size.height, s.backingScaleFactor])")
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True, timeout=20)
    try:
        x, y, w, h, sc = json.loads(r.stdout)
        return int(x), int(y), int(w), int(h), sc
    except Exception:
        log("visible frame unknown:", r.stdout, r.stderr)
        return 0, 25, 1920, 1055, 1.0


WIN = None          # shots: (width, height) of every picture's window; audit / switch: the whole visible frame


def picture_width(vis_w):
    """the pictures' window width: the widest of the ribbon-fit widths measured by audit (en) and switch (ar) in the
    spreadsheet and presentation editors (no ribbon group folded into "More"), else 1280; within 1024 .. the screen"""
    try:
        fit = json.load(open(RIBBON_FIT, encoding="utf-8"))
    except Exception:
        fit = {}
    got = [(lang, tag, v) for lang, d in fit.items() for tag, v in d.items()]
    if {(l, t) for l, t, _ in got} >= {("en", "sheet"), ("en", "slide"), ("ar", "sheet"), ("ar", "slide")}:
        w = max(v if isinstance(v, int) else vis_w for _, _, v in got)
        src = "ribbon-fit %s" % fit
    else:
        w, src = 1280, "default (ribbon-fit incomplete: %s)" % fit
    w = max(1024, min(vis_w, w))
    log("picture window width", w, "-", src)
    return w


def place_window():
    osa('tell application id "%s" to activate' % BID)
    x, y, w, h, sc = visible_frame()
    if WIN:
        w, h = min(w, WIN[0]), min(h, WIN[1])
    osa(PROC + ' to set position of window 1 to {%d, %d}' % (x, y), PROC + ' to set size of window 1 to {%d, %d}' % (w, h))
    time.sleep(1.5)
    b = osa(PROC + ' to get {position, size} of window 1')
    try:
        bx, by, bw, bh = [int(v) for v in b.replace(" ", "").split(",")]
    except ValueError:
        bx, by, bw, bh = x, y, w, h
    return bx, by, bw, bh, sc


class Page:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def call(self, m, p=None, timeout=60):
        self.n += 1
        await self.ws.send_json({"id": self.n, "method": m, "params": p or {}})

        async def wait():
            while True:
                r = await self.ws.receive_json()
                if r.get("id") == self.n:
                    return r
        try:
            return await asyncio.wait_for(wait(), timeout)
        except asyncio.TimeoutError:
            log("TIMEOUT", m)
            return {}

    async def ev(self, expr):
        r = await self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("result", {}).get("value")

    async def click(self, x, y):
        """a real left click (the browser's own input path, as a mouse would)"""
        await self.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        for t in ("mousePressed", "mouseReleased"):
            await self.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1})

    async def key(self, code, name, mods=0):
        k = name[-1].lower() if name.startswith("Key") else name
        for t in ("rawKeyDown", "keyUp"):
            await self.call("Input.dispatchKeyEvent", {"type": t, "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code,
                                                       "code": name, "key": k, "modifiers": mods})

    async def drag(self, pts):
        """a left-button drag through the points (page coordinates), as a mouse does it"""
        x, y = pts[0]
        await self.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        await self.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1,
                                                     "clickCount": 1})
        for x, y in pts[1:]:
            await self.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "left", "buttons": 1})
            await asyncio.sleep(0.015)
        await self.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0,
                                                     "clickCount": 1})

    async def right_click(self, x, y):
        await self.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        await self.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "right", "buttons": 2,
                                                     "clickCount": 1})
        await self.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "right", "buttons": 0,
                                                     "clickCount": 1})


TIPS_JS = """(function(){var f=document.querySelector('iframe[name=frameEditor]');var docs=[document];
  if(f&&f.contentDocument) docs.push(f.contentDocument);
  function vis(e){var s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;}
  var tips=[],dlgs=[];docs.forEach(function(d){
    [].slice.call(d.querySelectorAll('.synch-tip-root')).filter(vis).forEach(function(e){tips.push((e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,90));});
    [].slice.call(d.querySelectorAll('.asc-window')).filter(vis).forEach(function(e){var h=e.querySelector('.title');dlgs.push(((h||e).innerText||'').replace(/\\s+/g,' ').trim().slice(0,60));});
    var t=d.getElementById('xr-rec-toast'); if(t&&vis(t)) dlgs.push('recovery: '+(t.innerText||'').slice(0,60));
    var a=d.getElementById('xr-acct-ov'); if(a&&vis(a)) dlgs.push('account card');});
  return {shim:!!((f&&f.contentWindow)||window).__xrNoFeatureTips, tips:tips, dialogs:dlgs, url:location.search.slice(0,160)};})()"""

# the stored state of a signed-in user (what the account card writes after a sign-in) - local only, no server account;
# the name is a team, not a person (ACCOUNT: "Projects team" -> "PT"; "فريق المشاريع" -> "فم", the article skipped -
# web/xr-account.js initials)
SESSION_JS = """new Promise(function(done){try{
  if(!localStorage.getItem('xr-acct-token')){localStorage.setItem('xr-acct-token','local-store-pictures');
    localStorage.setItem('xr-acct',JSON.stringify({locked:false,name:__NAME__,email:'preview@example.invalid'}));}""".replace(
    "__NAME__", json.dumps(ACCOUNT[0])) + """
  var o=document.getElementById('xr-acct-ov'); if(o) o.parentNode.removeChild(o);}catch(e){done('error: '+e);return;}
  setTimeout(function(){done(document.getElementById('xr-acct-ov')?'card came back':'open');},2500);})"""


START_JS = """(function(){var its=[].slice.call(document.querySelectorAll('#area-document-creation-grid .document-creation-item'));
  var p=document.getElementById('xr-acct-start'), pr=p?p.getBoundingClientRect():null, hit=[];
  [].slice.call(document.querySelectorAll('.tool-menu li, .tool-menu a')).forEach(function(e){var r=e.getBoundingClientRect();
    if(pr&&r.width&&r.height&&getComputedStyle(e).display!=='none'&&r.left<pr.right&&r.right>pr.left&&r.top<pr.bottom&&r.bottom>pr.top)
      hit.push((e.innerText||'').trim().slice(0,30));});
  return {dir:getComputedStyle(document.body).direction, lang:location.search, cards:its.map(function(e){return (e.innerText||'').trim();}),
    pill:p?((p.querySelector('.av')||{}).textContent||'')+'|'+((p.querySelector('.nm')||{}).textContent||''):'',
    pill_side:pr?(pr.left+pr.width/2<innerWidth/2?'left':'right'):'', pill_over_sidebar:hit,
    pill_card_gap:(function(){var c=its[0];if(!c||!pr)return null;return Math.round(c.getBoundingClientRect().top-pr.bottom);})(),
    recents:[].slice.call(document.querySelectorAll('#box-recent .file-list-body .row')).filter(vis).map(function(e){
      var n=e.querySelector('.col-name'), i=e.querySelector('.col-name svg.icon');
      return ((n&&n.innerText)||'').replace(/\\s+/g,' ').trim()+' ['+(i?getComputedStyle(i).backgroundImage.slice(0,26):'')+']';}),
    dates:[].slice.call(document.querySelectorAll('#box-recent .file-list-body .row')).filter(vis).map(function(e){
      var t=e.querySelector('.col-date');return ((t&&t.innerText)||'').trim();}),
    locs:[].slice.call(document.querySelectorAll('#box-recent .file-list-body .row')).filter(vis).map(function(e){
      var t=e.querySelector('.col-location');return ((t&&t.innerText)||'').trim();}),
    loc_bidi:(function(){var t=document.querySelector('#box-recent .file-list-body .row .col-location');
      return t?getComputedStyle(t).unicodeBidi:'';})(),
    date_head:((document.querySelector('#box-recent .file-list-head .col-date')||document.querySelector('#box-recent .col-date')||{}).innerText||'').trim(),
    cards_bg:its.map(function(e){return getComputedStyle(e,'::before').backgroundImage.slice(27,60);}), xr_ar:document.documentElement.classList.contains('xr-ar'),
    latin_ui:latin(), wall:!!document.getElementById('xr-acct-ov')};
  function vis(e){var s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;}
  function latin(){var out=[],w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n;
    while((n=w.nextNode())){var t=n.nodeValue.replace(/\\s+/g,' ').trim(),e=n.parentElement;
      if(!t||!/[A-Za-z]{2,}/.test(t)||!e||e.closest('script,style,svg,.file-list-body')||!vis(e))continue;   // (file names are the user's)
      if(/^(Xrero( Office)?|PDF|[A-Z]{1,2}|\\.[a-z0-9]{2,5})$/.test(t))continue;
      out.push(t.slice(0,50));}
    return out;}})()"""


def port_free():
    import socket
    with socket.socket() as so:
        so.settimeout(1)
        return so.connect_ex(("127.0.0.1", PORT)) != 0


def ensure_quit():
    """no instance of the app left from the previous pass (macOS would hand a document to it, and its DevTools port
    would block the next launch's - run 17 lost the switch check and both editor pictures that way)"""
    osa('tell application id "%s" to quit' % BID)
    for _ in range(20):
        if subprocess.run(["pgrep", "-x", "XreroOffice"], capture_output=True).returncode != 0 and port_free():
            return
        time.sleep(1)
    subprocess.run(["pkill", "-9", "-x", "XreroOffice"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "editors_helper"], capture_output=True)
    for _ in range(15):
        if port_free():
            break
        time.sleep(1)
    time.sleep(1)
    log("ensure_quit: had to kill; port free:", port_free())


def container_ready():
    return os.path.isdir(os.path.expanduser("~/Library/Containers/%s/Data/Library/Preferences" % BID))


def prime():
    """a fresh container has no preferences yet: one plain launch makes it, so the language can be set before the
    launch that is photographed"""
    import urllib.request
    p = subprocess.Popen([EXE, "--remote-debugging-port=%d" % PORT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        time.sleep(1)
        try:
            if "/login/" in urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT, timeout=3).read().decode():
                break
        except Exception:
            pass
    time.sleep(4)
    ensure_quit()
    log("primed the container:", container_ready())


def screen_shot(name, box):
    x, y, w, h = box
    pre = {"shots": LANG, "switch": "switch-" + LANG}.get(MODE, "audit")
    p = os.path.join(OUT, "%s-%s-window.png" % (pre, name))
    subprocess.run(["screencapture", "-x", "-o", "-R", "%d,%d,%d,%d" % (x, y, w, h), p], capture_output=True)
    full = os.path.join(OUT, "%s-%s-screen.png" % (pre, name))
    subprocess.run(["screencapture", "-x", full], capture_output=True)
    res["shots"].append({"name": name, "window": os.path.basename(p), "screen": os.path.basename(full), "box": box})
    log("shot", name, box)


async def page_shot_2x(pg, name, rest=None, caret=False):
    """the page drawn at device scale 2 (Retina), the layout size unchanged. rest = where the page's pointer rests (sent
    again just before the capture: run 26's Arabic start picture had the first Recent row in its hover state); caret =
    the editor's caret held visible for the capture (it blinks every 500 ms: run 26's slide pictures caught it off)"""
    vw = await pg.ev("[innerWidth, innerHeight, devicePixelRatio]") or [0, 0, 1]
    await pg.call("Emulation.setDeviceMetricsOverride", {"width": vw[0], "height": vw[1], "deviceScaleFactor": 2, "mobile": False})
    await asyncio.sleep(4)
    if rest:
        await pg.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": rest[0], "y": rest[1]})
        await asyncio.sleep(0.8)
    held = await pg.ev(CARET_JS.replace("__HOLD__", "true")) if caret else None
    dpr = await pg.ev("devicePixelRatio")
    hover = await pg.ev(HOVER_JS)
    r = await pg.call("Page.captureScreenshot", {"format": "png"})
    if caret:
        await pg.ev(CARET_JS.replace("__HOLD__", "false"))
    await pg.call("Emulation.clearDeviceMetricsOverride")
    await asyncio.sleep(2)
    if r.get("result", {}).get("data"):
        p = os.path.join(OUT, "%s-%s-page2x.png" % (LANG, name))
        open(p, "wb").write(base64.b64decode(r["result"]["data"]))
        res["shots"].append({"name": name, "page2x": os.path.basename(p), "viewport": vw[:2], "dpr_then": dpr,
                             "caret": held, "hover": hover})
        log("page 2x", name, vw, "dpr", dpr, "caret", held, "hover", hover)


def make_doc(name, src):
    """a file to open, copied into DOCS under the name the picture shows (src None -> a small PDF)"""
    dst = os.path.join(DOCS, name)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if src:
        shutil.copy(src, dst)
        return dst
    try:
        import fitz
        d = fitz.open(); pgp = d.new_page()
        pgp.insert_text((72, 90), "Xrero Office", fontsize=22)
        pgp.insert_text((72, 130), "PDF first-open check.", fontsize=12)
        d.save(dst)
        return dst
    except Exception as e:
        log("no PDF:", e)
        return None


TITLEBAR_JXA = """(function(){var se=Application('System Events');
  var p=se.processes.whose({bundleIdentifier:'%s'})[0], w=p.windows[0], wp=w.position(), out=[];
  function g(e,f){try{var v=e[f]();return v===null||v===undefined?'':v;}catch(x){return '';}}
  function walk(e,depth){var els;try{els=e.uiElements();}catch(x){return;}
    for(var i=0;i<els.length;i++){var c=els[i],pos,sz;try{pos=c.position();sz=c.size();}catch(x){continue;}
      if(pos[1]-wp[1]>40)continue;
      out.push([g(c,'role'),g(c,'subrole'),g(c,'description'),g(c,'title'),g(c,'help'),pos[0]-wp[0],pos[1]-wp[1],sz[0],sz[1]].join(' | '));
      if(depth<5)walk(c,depth+1);}}
  walk(w,0);return JSON.stringify(out);})()""" % BID


def titlebar():
    """what the window's title bar holds (accessibility: role, subrole, description, title, help, x, y, w, h) -
    run evidence for anything drawn there (e.g. the right-to-left title bar's left end)"""
    try:
        r = subprocess.run(["osascript", "-l", "JavaScript", "-e", TITLEBAR_JXA], capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout)
    except Exception as e:
        return ["unreadable: %s" % e]


# ---- the spreadsheet / presentation / PDF pictures (16 Nov 2026) --------------------------------------------------
# every snippet runs in the editor tab's page; the editor itself is in its frameEditor frame (w, d, api); fr = the
# frame's place in the page (CDP input events take page coordinates)
FRAME = r"""var f=document.querySelector('iframe[name=frameEditor]');var w=f&&f.contentWindow||window,d=w.document;
  var fr=f?f.getBoundingClientRect():{left:0,top:0};var api=(w.Asc&&w.Asc.editor)||w.editor;
  function fontbox(){var e=d.querySelector('#slot-field-fontname input');return e?e.value:'';}
  function statusbar(){var s=d.getElementById('statusbar');return s?(s.innerText||'').replace(/\s+/g,' ').trim().slice(0,200):'';}"""

READY_JS = r"""(function(tag){""" + FRAME + r"""
  if(!api)return 'no editor api';
  if([].slice.call(d.querySelectorAll('.asc-loadmask')).some(function(e){return e.offsetParent!==null;}))return 'loading';
  try{if(tag==='sheet')return api.wbModel&&api.wb?'ok':'no workbook';
    if(tag==='slide')return api.WordControl.m_oLogicDocument.Slides.length?'ok':'no slides';
    if(tag==='pdf')return api.getPDFDoc().widgets.length?'ok':'no form fields';
    return api.WordControl.m_oLogicDocument?'ok':'no document';}catch(e){return 'error: '+e;}})(__TAG__)"""

SHEET_SELECT_JS = r"""(function(){""" + FRAME + r"""try{api.asc_findCell('E5');return 'ok';}catch(e){return 'error: '+e;}})()"""
SHEET_STATE_JS = r"""(function(){""" + FRAME + r"""var o={};
  try{var ws=api.wbModel.getActiveWs(),CH=w.AscDFH.historyitem_type_ChartSpace;
    var t=(ws.Drawings||[]).map(function(x){var g=x.graphicObject;return g&&g.getObjectType?g.getObjectType():-1;});
    o.charts=t.filter(function(v){return v===CH;}).length;o.drawings=t.length;o.sheet=ws.getName();
    try{o.rtl=!!api.wb.getWorksheet().getRightToLeft();}catch(e){o.rtl='unknown: '+e;}}catch(e){o.err=''+e;}
  o.cell=(d.getElementById('ce-cell-name')||{}).value||'';o.formula=(d.getElementById('ce-cell-content')||{}).value||'';
  var ce=d.getElementById('ce-cell-content');o.formula_bidi=ce?w.getComputedStyle(ce).unicodeBidi:'';
  o.font=fontbox();o.statusbar=statusbar();return o;})()"""

# slide 1's title: its middle line, near the side the text starts from (the click lands on the title's text)
SLIDE_POINT_JS = r"""(function(rtl){""" + FRAME + r"""var o={};
  try{var wc=api.WordControl,p=wc.m_oLogicDocument;if(p.CurPage!==0&&wc.GoToPage)wc.GoToPage(0);
    var sp=null;p.Slides[0].cSld.spTree.forEach(function(s){if(!sp&&s.isPlaceholder&&s.isPlaceholder()&&
      [w.AscFormat.phType_ctrTitle,w.AscFormat.phType_title].indexOf(s.getPlaceholderType())>=0)sp=s;});
    if(!sp)return {err:'no title placeholder'};
    var xm=sp.x+sp.extX*(rtl?0.95:0.05),ym=sp.y+sp.extY*0.78,dd=wc.m_oDrawingDocument;
    var a=dd.ConvertCoordsToCursor3(xm,ym,false),g=dd.ConvertCoordsToCursor3(xm,ym,true);
    var v=d.getElementById('id_viewer').getBoundingClientRect();
    o={shape_mm:[sp.x,sp.y,sp.extX,sp.extY].map(Math.round),x:fr.left+v.left+a.X,y:fr.top+v.top+a.Y,gx:fr.left+g.X,gy:fr.top+g.Y};
  }catch(e){o.err=''+e;}return o;})(__RTL__)"""
SLIDE_STATE_JS = r"""(function(){""" + FRAME + r"""var o={};
  try{var p=api.WordControl.m_oLogicDocument;o.slide=p.CurPage;o.slides=p.Slides.length;
    var c=p.GetCurrentController&&p.GetCurrentController(),tc=c&&c.getTargetDocContent&&c.getTargetDocContent();
    o.in_text=!!tc;if(tc){var cp=tc.GetCurrentParagraph&&tc.GetCurrentParagraph();o.paragraph=cp&&cp.GetText?cp.GetText().slice(0,60):'';
      o.at_end=tc.IsCursorAtEnd?tc.IsCursorAtEnd():'unknown';}
  }catch(e){o.err=''+e;}o.font=fontbox();o.statusbar=statusbar();return o;})()"""

# the Comment tab (annotation tools) and a blank spot of the page's margin (gives the page the keyboard)
PDF_PREP_JS = r"""(function(){""" + FRAME + r"""var o={};
  var tab=d.querySelector('.ribtab a[data-tab=comment]');
  if(tab){var r=tab.getBoundingClientRect();o.tab=[fr.left+r.left+r.width/2,fr.top+r.top+r.height/2];}
  try{var v=api.getDocumentRenderer(),det=v.getPageLikeDetector(0),rp=w.AscCommon.AscBrowser.retinaPixelRatio||1;
    var cv=v.canvas.getBoundingClientRect(),W=v.file.pages[0].W,pl=cv.left+det.x/rp,pt=cv.top+det.y/rp,sc=(det.w/rp)/W;
    o.page=[pl,pt,det.w/rp,det.h/rp].map(Math.round);o.px_per_pt=sc;o.focus=[fr.left+pl+24*sc,fr.top+pt+118*sc];
    o.org=[fr.left+pl,fr.top+pt];
  }catch(e){o.err=''+e;}return o;})()"""
PDF_STATE_JS = r"""(function(){""" + FRAME + r"""var o={};
  try{var doc=api.getPDFDoc();
    o.fields=doc.widgets.map(function(x){return [x.GetFullName(),x.IsChecked?x.IsChecked():x.GetValue()];});
    o.active=doc.activeForm?doc.activeForm.GetFullName():'';o.annots=doc.annots.map(function(a){return a.GetType();});
  }catch(e){o.err=''+e;}
  var t=d.querySelector('.ribtab.active a');o.tab=t?t.getAttribute('data-tab'):'';o.statusbar=statusbar();return o;})()"""

# the visible interface text of the editor tab (its page + editor frame): Latin words (the Arabic pictures should have
# none that a capture choice can avoid) and the whole text (private-data check); input fields' values too
UI_JS = r"""(function(){""" + FRAME + r"""
  function vis(e){var vw=e.ownerDocument.defaultView,s=vw.getComputedStyle(e),r=e.getBoundingClientRect();
    return s&&s.display!=='none'&&s.visibility!=='hidden'&&+s.opacity!==0&&r.width>0&&r.height>0&&r.right>0&&r.bottom>0&&
      r.left<vw.innerWidth&&r.top<vw.innerHeight;}
  var latin=[],all=[];
  [document,d].forEach(function(doc){if(!doc||!doc.body)return;var tw=doc.createTreeWalker(doc.body,NodeFilter.SHOW_TEXT),n;
    while((n=tw.nextNode())){var t=n.nodeValue.replace(/\s+/g,' ').trim(),e=n.parentElement;
      if(!t||!e||e.closest('script,style,svg,noscript')||!vis(e))continue;
      all.push(t);if(/[A-Za-z]{2,}/.test(t))latin.push(t.slice(0,60));}});
  var inputs=[].slice.call(d.querySelectorAll('input,textarea')).filter(vis).map(function(i){return i.value;}).filter(String);
  var chip=d.getElementById('xr-b-acct');
  return {latin:latin,inputs:inputs,text:all.join(' | ').slice(0,6000),chip:chip?chip.textContent:null};})()"""


# a visible control of the editor frame by CSS selector: its centre (page coordinates, for CDP input), pressed or not;
# on a split button its main part (not the arrow)
CTRL_JS = r"""(function(sel){""" + FRAME + r"""
  function vis(e){var s=w.getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;}
  var es=[].slice.call(d.querySelectorAll(sel)).filter(vis);if(!es.length)return null;var e=es[0];
  if(['BUTTON','TEXTAREA','A','INPUT'].indexOf(e.tagName)<0){var b=e.querySelector('button:not(.dropdown-toggle)')||e.querySelector('button');if(b)e=b;}
  var r=e.getBoundingClientRect();
  return {x:fr.left+r.left+r.width/2,y:fr.top+r.top+r.height/2,on:/(^|\s)active(\s|$)/.test(e.className||''),
    cls:(e.className||'').toString().slice(0,60)};})(__SEL__)"""
# the page's context menu: its "Add comment" item (the PDF editor's own menu item object, else the item with its caption)
ADD_COMMENT_JS = r"""(function(){""" + FRAME + r"""
  function vis(e){var s=w.getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;}
  var it=null;try{it=w.PDFE.getController('DocumentHolder').documentHolder.menuAddComment;}catch(e){}
  var a=it&&it.cmpEl&&it.cmpEl[0];a=a&&(a.querySelector('a')||a);var cap=(it&&it.caption)||'';
  if(!a||!vis(a))a=[].slice.call(d.querySelectorAll('.dropdown-menu li a')).filter(function(x){
    return vis(x)&&cap&&(x.innerText||'').trim()===cap;})[0];
  if(!a)return {err:'no visible Add comment item',caption:cap,menus:[].slice.call(d.querySelectorAll('.dropdown-menu')).filter(vis)
    .map(function(m){return (m.innerText||'').replace(/\s+/g,' ').slice(0,160);})};
  var r=a.getBoundingClientRect();return {x:fr.left+r.left+r.width/2,y:fr.top+r.top+r.height/2,text:(a.innerText||'').trim()};})()"""
# the PDF's text selection (after the mouse drag) and its annotations: [type, rect (points), contents]
PDF_SEL_JS = r"""(function(){""" + FRAME + r"""var o={};try{var f=api.getDocumentRenderer().file;o.quads=f.getSelectionQuads().length;
  try{o.text=(f.copy()||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim().slice(0,120);}catch(e){o.text='?';}}catch(e){o.err=''+e;}
  return o;})()"""
PDF_ANNOTS_JS = r"""(function(){""" + FRAME + r"""try{return api.getPDFDoc().annots.map(function(a){var r=[];try{r=a.GetRect();}catch(e){}
  return [a.GetType(),(r||[]).map(function(v){return Math.round(v);}),String((a.GetContents&&a.GetContents())||'').slice(0,60)];});
  }catch(e){return 'error: '+e;}})()"""
HIGHLIGHT, TEXT_NOTE, INK = 8, 0, 14          # AscPDF.ANNOTATIONS_TYPES (sdkjs pdf/src/defines.js)

# the caret: its blink timer paused and the caret shown for a capture (hold), then the timer started again (release);
# only where the editor wants a caret (NeedTarget) - the caret the picture shows is the editor's own, at its place
CARET_JS = r"""(function(hold){""" + FRAME + r"""var dd=null;
  try{dd=(api.WordControl&&api.WordControl.m_oDrawingDocument)||null;}catch(e){}
  try{if((!dd||!dd.TargetHtmlElement)&&api.getPDFDoc)dd=api.getPDFDoc().GetDrawingDocument();}catch(e){}
  if(!dd||!dd.TargetHtmlElement)return 'no caret';
  if(hold){if(!dd.NeedTarget)return 'no caret wanted';
    if(dd.m_lTimerTargetId!=-1){clearInterval(dd.m_lTimerTargetId);dd.m_lTimerTargetId=-1;dd.__xrHeld=1;}
    if(dd.showTarget)dd.showTarget(true);else dd.TargetHtmlElement.style.display='block';
    var cs=w.getComputedStyle(dd.TargetHtmlElement),r=dd.TargetHtmlElement.getBoundingClientRect();
    return 'held: '+cs.display+'/'+cs.visibility+' '+Math.round(r.width)+'x'+Math.round(r.height);}
  if(dd.__xrHeld){dd.__xrHeld=0;if(dd.TargetStart)dd.TargetStart(true);}return 'released';})(__HOLD__)"""

# what is in its hover state in the tab's page and editor frame (cards, Recent rows, ribbon buttons, tabs)
HOVER_JS = r"""(function(){var out=[];[document].concat((function(){var f=document.querySelector('iframe[name=frameEditor]');
  return f&&f.contentDocument?[f.contentDocument]:[];})()).forEach(function(d){
  [].slice.call(d.querySelectorAll('#box-recent .row:hover, .document-creation-item:hover, .btn:hover, .ribtab:hover, .tool-menu li:hover'))
    .forEach(function(e){out.push((e.className||e.tagName).toString().slice(0,40)+': '+(e.innerText||'').replace(/\s+/g,' ').trim().slice(0,30));});});
  return out;})()"""


def park_pointer():
    """the Mac's own pointer in the menu bar's right end, off the window (no hover state from where it last was)"""
    js = "ObjC.import('CoreGraphics');$.CGWarpMouseCursorPosition({x:1000,y:10});'parked'"
    try:
        r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True, timeout=20)
        return (r.stdout or r.stderr).strip()[:120]
    except Exception as e:
        return "not parked: %s" % e


async def frame_ready(pg, tag):
    st = None
    for _ in range(45):
        st = await pg.ev(READY_JS.replace("__TAG__", json.dumps(tag)))
        if st == "ok":
            break
        await asyncio.sleep(1)
    return st


async def prep_sheet(pg):
    sel = await pg.ev(SHEET_SELECT_JS)
    await asyncio.sleep(2)
    o = await pg.ev(SHEET_STATE_JS) or {}
    o["select"] = sel
    return o


async def prep_slide(pg):
    pt = await pg.ev(SLIDE_POINT_JS.replace("__RTL__", "true" if LANG == "ar" else "false")) or {}
    if "x" in pt:
        await pg.click(pt["x"], pt["y"])
        await asyncio.sleep(1.5)
        # the caret after the title's last letter (run 23: the End key left it before the first one on macOS)
        pt["end"] = await pg.ev("(function(){" + FRAME + "try{api.WordControl.m_oLogicDocument.MoveCursorToEndPos(false);"
                                "return 'ok';}catch(e){return ''+e;}})()")
        await asyncio.sleep(1.5)
    o = await pg.ev(SLIDE_STATE_JS) or {}
    o["point"] = pt
    return o


def pdf_marks():
    """where the reviewer's marks go, in PDF points of the demo form (read with PyMuPDF): the deadline line (its words,
    selected from the line's start to its end), the pen circle around the date field, the sticky note's corner between
    the date label and the field (the places store_demo.py used for the marks it stored before 16 Nov 2026)"""
    import math
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    d = pymupdf.open(DEMO["pdf"])
    pg = d[0]
    W, rtl = pg.rect.width, LANG == "ar"
    clip = pymupdf.Rect(W - 545, 350, W - 50, 368) if rtl else pymupdf.Rect(50, 350, 545, 368)
    words = pg.get_text("words", clip=clip)
    box = pymupdf.Rect(words[0][:4])
    for wd in words[1:]:
        box |= pymupdf.Rect(wd[:4])
    dr = [pymupdf.Rect(w.rect) for w in pg.widgets() if w.field_name == "date"][0]
    d.close()
    cx, cy, rx, ry = (dr.x0 + dr.x1) / 2, (dr.y0 + dr.y1) / 2, dr.width / 2 + 9, dr.height / 2 + 8
    ring = [(cx + rx * (1 + 0.03 * math.sin(3 * t)) * math.cos(t), cy + ry * (1 + 0.05 * math.cos(2 * t)) * math.sin(t))
            for t in [-2.7 + k * (2 * math.pi + 0.5) / 60 for k in range(61)]]
    y = (box.y0 + box.y1) / 2
    a, b = (box.x1 - 0.4, box.x0 + 0.4) if rtl else (box.x0 + 0.4, box.x1 - 0.4)
    line = [(a + (b - a) * k / 16.0, y) for k in range(17)]
    note = (dr.x1 + 12, dr.y0 + 2) if rtl else (dr.x0 - 32, dr.y0 + 2)
    return {"line": line, "ring": ring, "note": note, "box": [round(v, 1) for v in box], "date": [round(v, 1) for v in dr]}


async def ctrl(pg, sel):
    return await pg.ev(CTRL_JS.replace("__SEL__", json.dumps(sel)))


async def prep_marks(pg, pre):
    """the reviewer's marks, made with the Comment tab's tools the way a user makes them (16 Nov 2026 review: they were
    stored in the demo file): the deadline line selected with the mouse and highlighted (Highlight button), a circle
    drawn around the date field with the red pen, a sticky note added beside it (right click > Add comment, typed, Add)"""
    o = {}
    try:
        m = pdf_marks()
    except Exception as e:
        return {"err": "marks: %s" % e}
    org, sc = pre.get("org"), pre.get("px_per_pt")
    if not org or not sc:
        return {"err": "no page geometry", "pre": pre}

    def P(x, y):
        return (org[0] + x * sc, org[1] + y * sc)
    o["marks"] = {"box": m["box"], "date": m["date"], "note": m["note"]}
    # 1. highlight: select the line with the mouse (the Select tool), then the Highlight button
    await pg.drag([P(*q) for q in m["line"]])
    await asyncio.sleep(1.2)
    o["selection"] = await pg.ev(PDF_SEL_JS)
    b = await ctrl(pg, "#id-toolbar-btn-highlight")
    o["highlight_button"] = b
    if b:
        await pg.click(b["x"], b["y"])
        await asyncio.sleep(1.5)
        b2 = await ctrl(pg, "#id-toolbar-btn-highlight")
        if b2 and b2.get("on"):                  # (the marker stays switched on after use: switched off as a user does)
            await pg.click(b2["x"], b2["y"])
            await asyncio.sleep(1)
            o["highlight_button_off"] = await ctrl(pg, "#id-toolbar-btn-highlight")
    # 2. the red pen (the Comment tab's second pen): a circle around the date field, then the pen switched off
    pen = await ctrl(pg, "#slot-btn-draw-pen-1")
    o["pen_button"] = pen
    if pen:
        await pg.click(pen["x"], pen["y"])
        await asyncio.sleep(1)
        await pg.drag([P(*q) for q in m["ring"]])
        await asyncio.sleep(1.5)
        pen2 = await ctrl(pg, "#slot-btn-draw-pen-1")
        if pen2 and pen2.get("on"):
            await pg.click(pen2["x"], pen2["y"])
            await asyncio.sleep(1.2)
        o["pen_button_off"] = await ctrl(pg, "#slot-btn-draw-pen-1")
    # 3. the sticky note: right click beside the date field > Add comment, the note typed, Add
    x, y = P(*m["note"])
    await pg.right_click(x, y)
    await asyncio.sleep(1.5)
    item = await pg.ev(ADD_COMMENT_JS) or {}
    o["menu_item"] = item
    if "x" in item:
        await pg.click(item["x"], item["y"])
        await asyncio.sleep(2)
        ta = await ctrl(pg, "#id-popover textarea")
        o["note_box"] = ta
        if ta:
            await pg.click(ta["x"], ta["y"])
            await asyncio.sleep(0.5)
            await pg.call("Input.insertText", {"text": PDF_NOTE})
            await asyncio.sleep(0.8)
            add = await ctrl(pg, "#id-popover #id-comments-change-popover")
            o["add_button"] = add
            if add:
                await pg.click(add["x"], add["y"])
                await asyncio.sleep(2)
    else:
        await pg.key(27, "Escape")
        await asyncio.sleep(1)
    o["annots"] = await pg.ev(PDF_ANNOTS_JS)
    return o


async def prep_pdf(pg):
    pre = await pg.ev(PDF_PREP_JS) or {}
    if pre.get("tab"):
        await pg.click(*pre["tab"])
        await asyncio.sleep(2)
        pre = await pg.ev(PDF_PREP_JS) or pre          # (the page's place once the Comment tab's ribbon is shown)
    marks = await prep_marks(pg, pre)
    log("pdf marks:", json.dumps(marks, ensure_ascii=False)[:1500])
    if pre.get("focus"):
        await pg.click(*pre["focus"])
        await asyncio.sleep(1.5)
    # the frame's errors while the form is filled (diagnosis of a field that does not keep what is typed)
    await pg.ev("(function(){" + FRAME + "w.__xrErr=[];var ce=w.console.error;w.console.error=function(){try{w.__xrErr.push("
                "[].slice.call(arguments).map(String).join(' ').slice(0,240));}catch(e){}return ce.apply(this,arguments);};"
                "w.addEventListener('error',function(e){w.__xrErr.push('onerror: '+e.message);});return 1;})()")
    active = "(function(){" + FRAME + ("try{var a=api.getPDFDoc().activeForm;return a?[a.GetFullName(),a.IsChecked?a.IsChecked():"
                                       "a.GetValue(),a.IsInForm?a.IsInForm():'?']:'';}catch(e){return ''+e;}})()")
    to_start = "(function(){" + FRAME + ("try{var a=api.getPDFDoc().activeForm;a.content.MoveCursorToStartPos();"
                                         "a.content.RecalculateCurPos();return 'ok';}catch(e){return ''+e;}})()")
    steps = []
    for name, v in PDF_FILL:                    # the form's tab order (store_demo.py PDF_FIELDS)
        await pg.key(9, "Tab")
        st = None
        for _ in range(20):                     # the field has the keyboard (active + in edit) before anything is typed
            await asyncio.sleep(0.4)
            st = await pg.ev(active) or ["", "", ""]
            if st[0] == name and st[2] is True:
                break
        await asyncio.sleep(0.8)
        if v is True:
            await pg.key(13, "Enter")
            await asyncio.sleep(1)
        elif v:
            await pg.call("Input.insertText", {"text": v})
            await asyncio.sleep(1)
            got = (await pg.ev(active) or ["", ""])[1]
            if got != v and got and v.endswith(got):
                # the first letter(s) did not arrive (runs 23-25, Arabic date): typed again at the field's start
                steps.append([name + " retyped start", [got, v[:len(v) - len(got)], await pg.ev(to_start)]])
                await asyncio.sleep(0.5)
                await pg.call("Input.insertText", {"text": v[:len(v) - len(got)]})
                await asyncio.sleep(1)
            elif got != v and not got:
                steps.append([name + " typed again", got])
                await pg.call("Input.insertText", {"text": v})
                await asyncio.sleep(1)
        steps.append([name, await pg.ev(active)])
    await asyncio.sleep(1.5)
    o = await pg.ev(PDF_STATE_JS) or {}
    o["prep"], o["steps"], o["marks"] = pre, steps, marks
    o["annots_full"] = await pg.ev(PDF_ANNOTS_JS)
    o["popover"] = await ctrl(pg, "#id-popover")
    o["errors"] = await pg.ev("(function(){" + FRAME + "return (w.__xrErr||[]).slice(0,30);})()")
    # the boxes ticked with Enter through the Mac fix (patch_bundle.py pdfKeyTick: the tick is committed, run 28 lost it)
    o["key_ticks"] = await pg.ev("(function(){" + FRAME + "return w.__xrPdfKeyTick||0;})()")
    return o


PREP = {"sheet": prep_sheet, "slide": prep_slide, "pdf": prep_pdf}

# the ribbon of the active toolbar tab: groups folded into "More" (its button shown) or not
MORE_JS = r"""(function(){""" + FRAME + r"""
  function vis(e){var s=w.getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;}
  var t=d.querySelector('.ribtab.active a');
  return {more:[].slice.call(d.querySelectorAll('.more-box')).some(vis),tab:t?t.getAttribute('data-tab'):'',width:w.innerWidth};})()"""


async def ribbon_fit(pg, tag):
    """the narrowest window width (32 pt steps, 1024 .. the screen) from which on this editor's ribbon folds nothing into
    "More" -> ribbon-fit.json {lang: {sheet|slide: width or null}} (picture_width reads it)"""
    x, y, vw, vh, sc = visible_frame()
    seen = {}
    for wd in range(1024, vw + 1, 32):
        osa(PROC + ' to set size of window 1 to {%d, %d}' % (wd, min(vh, WIN_H)))
        await asyncio.sleep(1.6)
        seen[wd] = (await pg.ev(MORE_JS) or {}).get("more")
    ws = sorted(seen)
    fit = next((wd for i, wd in enumerate(ws) if all(seen[v] is False for v in ws[i:])), None)
    try:
        allfit = json.load(open(RIBBON_FIT, encoding="utf-8"))
    except Exception:
        allfit = {}
    allfit.setdefault(LANG, {})[{"cell": "sheet"}.get(tag, tag)] = fit
    json.dump(allfit, open(RIBBON_FIT, "w", encoding="utf-8"), indent=1)
    log("ribbon fit", LANG, tag, fit, "(More shown at: %s)" % [wd for wd in ws if seen[wd]])
    res.setdefault("ribbon_fit", {})[tag] = {"fit": fit, "more": seen}
    return fit


def recent_times():
    """the start picture's Recent files at working hours: the app's own list (recents.xml in its container, read at
    launch; newest first) gets RECENT_TIMES on its dates, the day kept"""
    base = os.path.expanduser("~/Library/Containers/%s/Data/Library" % BID)
    done = []
    for root, dirs, files in os.walk(base):
        if "recents.xml" in files:
            f = os.path.join(root, "recents.xml")
            t = open(f, encoding="utf-8").read()
            n = [0]

            def at(mo):
                k = n[0]
                n[0] += 1
                return 'date="%s %s"' % (mo.group(1), RECENT_TIMES[min(k, len(RECENT_TIMES) - 1)])
            t2 = re.sub(r'date="(\d\d\.\d\d\.\d{4}) \d\d:\d\d"', at, t)
            open(f, "w", encoding="utf-8").write(t2)
            done.append([f.replace(base, "~"), n[0], re.findall(r'date="[^"]*"', t2)])
    log("recent files' times:", done)
    return done


async def pdf_roundtrip(pg, dst, targets, s):
    """the filled + annotated form saved (Cmd+S), read back from the file (PyMuPDF), and opened again in the app (a copy,
    in a new tab): the store text may say "form filling and comments" only if all three keep the fields and the marks"""
    out = {}
    try:
        m0 = os.stat(dst).st_mtime
        await pg.key(83, "KeyS", 4)                       # Cmd+S
        for _ in range(25):
            await asyncio.sleep(1)
            if os.stat(dst).st_mtime > m0:
                break
        await asyncio.sleep(4)
        out["saved"] = os.stat(dst).st_mtime > m0
        out["tips_after_save"] = await pg.ev(TIPS_JS)
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf
        d = pymupdf.open(dst)
        p0 = d[0]
        out["file_fields"] = {w.field_name: w.field_value for w in p0.widgets()}
        out["file_annots"] = [a.type[1] for a in p0.annots()]
        d.close()
        dst2 = os.path.join(os.path.dirname(dst), "check " + os.path.basename(dst))
        shutil.copy(dst, dst2)
        old = {t["id"] for t in await targets()}
        subprocess.run(["open", "-a", APP, dst2])
        ed = None
        for _ in range(60):
            await asyncio.sleep(1)
            new = [t for t in await targets() if t["id"] not in old and t.get("type") == "page"]
            if new:
                ed = new[0]
                break
        if ed:
            await asyncio.sleep(10)
            async with s.ws_connect(ed["webSocketDebuggerUrl"], max_msg_size=0) as ws:
                p2 = Page(ws)
                out["reopen_ready"] = await frame_ready(p2, "pdf")
                st = await p2.ev(PDF_STATE_JS) or {}
                out["app_fields"] = st.get("fields")
                out["app_annots"] = st.get("annots")
    except Exception as e:
        out["err"] = "%s: %s" % (type(e).__name__, e)

    def on(v):
        return v not in (None, False, "", "Off", "off", 0)
    want = dict(PDF_FILL)
    ff = out.get("file_fields") or {}
    af = dict(out.get("app_fields") or [])
    ok_file = all((on(ff.get(k)) == v) if isinstance(v, bool) else (ff.get(k) == v) for k, v in want.items())
    ok_app = all((on(af.get(k)) == v) if isinstance(v, bool) else (af.get(k) == v) for k, v in want.items())
    fa = " ".join(out.get("file_annots") or [])
    marks_file = all(x in fa for x in ("Highlight", "Ink", "Text"))
    marks_app = all(x in (out.get("app_annots") or []) for x in (HIGHLIGHT, INK, TEXT_NOTE))
    out["ok"] = bool(out.get("saved") and ok_file and ok_app and marks_file and marks_app)
    out["checks"] = {"saved": out.get("saved"), "file_fields": ok_file, "app_fields": ok_app, "file_marks": marks_file,
                     "app_marks": marks_app}
    log("PDF ROUND TRIP:", "OK" if out["ok"] else "NOT OK", json.dumps(out, ensure_ascii=False)[:1500])
    return out


async def main():
    global WIN
    ensure_quit()
    if MODE in ("shots", "switch"):
        if not container_ready():
            prime()
        set_language()
    if MODE == "shots" and WIN is None:
        vis = visible_frame()
        WIN = (picture_width(vis[2]), WIN_H)
        res["picture_window"] = list(WIN)
    proc = subprocess.Popen([EXE, "--remote-debugging-port=%d" % PORT],
                            stdout=open(os.path.join(OUT, "app-%s-%s.log" % (MODE, LANG)), "w"), stderr=subprocess.STDOUT)
    t0 = time.time()
    async with aiohttp.ClientSession() as s:
        async def targets():
            async with s.get("http://127.0.0.1:%d/json" % PORT) as r:
                return await r.json(content_type=None)

        start = None
        for _ in range(90):
            await asyncio.sleep(1)
            try:
                start = next((t for t in await targets() if t.get("type") == "page" and "/login/" in t.get("url", "")), None)
            except Exception:
                continue
            if start:
                break
        if not start:
            log("no start page")
            proc.kill()
            ensure_quit()
            return proc
        log("start page after %.0fs: %s" % (time.time() - t0, start.get("url", "")[-120:]))
        if MODE == "audit":            # the first seconds as a user sees them (the window where macOS put it)
            for sec in (3, 8):
                await asyncio.sleep(max(0, sec - (time.time() - t0)))
                p = os.path.join(OUT, "audit-first-%02ds-screen.png" % sec)
                subprocess.run(["screencapture", "-x", p], capture_output=True)
            res["windows_first_run"] = osa(PROC + ' to get {name, subrole} of every window')
        await asyncio.sleep(5)
        async with s.ws_connect(start["webSocketDebuggerUrl"], max_msg_size=0) as ws:
            pg = Page(ws)
            res["start_lang_query"] = await pg.ev("location.search")
            if MODE in ("shots", "switch") and ("lang=" + CODE) not in (res["start_lang_query"] or "") and not res.get("relaunched_for_language"):
                log("interface language is not", CODE, "->", res["start_lang_query"], "- the app's Settings path (settings:apply)")
                await pg.ev("window.AscDesktopEditor.execCommand('settings:apply', JSON.stringify({langid:%s}))" % json.dumps(CODE))
                await asyncio.sleep(2)
                res["relaunched_for_language"] = True
            elif MODE == "audit":
                res["start_first_run"] = await pg.ev(TIPS_JS)
            res["session"] = await pg.ev(SESSION_JS)
            log("session:", res["session"])
        if res.get("relaunched_for_language") and not res.get("relaunched"):
            res["relaunched"] = True
            osa('tell application id "%s" to quit' % BID)
            for _ in range(30):
                if proc.poll() is not None:
                    break
                await asyncio.sleep(1)
            if proc.poll() is None:
                proc.kill()
            return "again"

        if MODE == "shots" and not res.get("recents_done"):
            # a user's start page lists the files they opened: the four demo files, opened from Finder once (oldest
            # first), then the app starts again (the start page reads its Recent files at launch)
            res["recents_done"] = True
            opened = []
            for name, src in RECENTS:
                dst = make_doc(name, SRC if src == "DEMO" else src)
                if not dst:
                    continue
                old = {t["id"] for t in await targets()}
                subprocess.run(["open", "-a", APP, dst])
                for _ in range(45):
                    await asyncio.sleep(1)
                    if [t for t in await targets() if t["id"] not in old and t.get("type") == "page"]:
                        opened.append(name)
                        break
                await asyncio.sleep(6)
            res["recents_opened"] = opened
            log("recent files opened:", opened)
            osa('tell application id "%s" to quit' % BID)
            for _ in range(40):
                if proc.poll() is not None:
                    break
                await asyncio.sleep(1)
            if proc.poll() is None:
                log("the app did not quit after the recent files: killed")
                proc.kill()
            res["recent_times"] = recent_times()
            return "again"

        box = place_window()
        log("window", box)
        res["window"] = box
        await asyncio.sleep(3)
        if MODE in ("shots", "switch"):
            async with s.ws_connect(start["webSocketDebuggerUrl"], max_msg_size=0) as ws:
                pg = Page(ws)
                vw = await pg.ev("[innerWidth, innerHeight]") or [1000, 700]
                log("pointer:", park_pointer())
                # no hover highlight on a card: the page's pointer rests on an empty spot at the bottom
                await pg.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": vw[0] * 0.55, "y": vw[1] - 6})
                await asyncio.sleep(1.5)
                res["start_page"] = await pg.ev(START_JS)
                log("start page:", json.dumps(res["start_page"], ensure_ascii=False))
                screen_shot("start", box[:4])
                res["titlebar_start"] = titlebar()
                log("title bar (start):", json.dumps(res["titlebar_start"], ensure_ascii=False)[:1500])
                if MODE == "shots":
                    open_tabs = [t.get("url", "")[-80:] for t in await targets() if t.get("type") == "page" and "/login/" not in t.get("url", "")]
                    if open_tabs:
                        log("documents still open on the start picture:", open_tabs)
                    await page_shot_2x(pg, "start", rest=(vw[0] * 0.55, vw[1] - 6))

        # documents, opened the way Finder does
        if MODE == "switch":
            # (16 Nov 2026) the Arabic spreadsheet + presentation ribbons: the window width that folds nothing (ribbon_fit)
            docs = [(NAMES["sheet"], DEMO["sheet"], "sheet"), (NAMES["slide"], DEMO["slide"], "slide")]
        elif MODE == "shots":
            docs = [(DOC_NAME, SRC, "editor"), (NAMES["sheet"], DEMO["sheet"], "sheet"), (NAMES["slide"], DEMO["slide"], "slide"),
                    (NAMES["pdf"], DEMO["pdf"], "pdf")]
        else:
            docs = [("Q3 report.docx", os.path.join(HERE, "store_demo.docx"), "word"),
                    ("sheet.xlsx", os.path.join(SRC, "sheet_ar.xlsx"), "cell"),
                    ("slides.pptx", os.path.join(SRC, "slides_ar.pptx"), "slide"),
                    ("document.pdf", None, "pdf")]
        for name, src, tag in docs:
            dst = make_doc(name, src)
            if not dst:
                continue
            old = {t["id"] for t in await targets()}
            subprocess.run(["open", "-a", APP, dst])
            ed = None
            for _ in range(60):
                await asyncio.sleep(1)
                new = [t for t in await targets() if t["id"] not in old and t.get("type") == "page"]
                if new:
                    ed = new[0]
                    break
            if not ed:
                log("did not open", name)
                continue
            await asyncio.sleep(14)
            async with s.ws_connect(ed["webSocketDebuggerUrl"], max_msg_size=0) as ws:
                pg = Page(ws)
                state = await pg.ev(TIPS_JS)
                log(tag, "tips/dialogs:", json.dumps(state, ensure_ascii=False))
                res.setdefault("editors", {})[tag] = state
                if MODE == "shots":
                    res.setdefault("ready", {})[tag] = await frame_ready(pg, tag)
                    log(tag, "ready:", res["ready"][tag])
                if MODE == "shots" and tag != "editor":
                    info = await PREP[tag](pg)
                    res[tag + "_info"] = info
                    log(tag + ":", json.dumps(info, ensure_ascii=False))
                elif MODE == "shots":
                    info = await pg.ev("""(function(){var f=document.querySelector('iframe[name=frameEditor]');var w=f&&f.contentWindow||window;
                      // the caret in the Arabic summary (the headline is about Arabic: the status bar's language and the
                      // ribbon's paragraph state then show the Arabic paragraph, not an English line)
                      var caret='';
                      try{var d=w.editor.WordControl.m_oLogicDocument;d.RemoveSelection();d.MoveCursorToStartPos(false);
                        for(var i=0;i<14;i++){var cp=d.GetCurrentParagraph&&d.GetCurrentParagraph();
                          var tx=cp&&cp.GetText?cp.GetText():'';
                          if(tx.replace(/^\\s+/,'').indexOf('\\u064A\\u0633\\u062A\\u0639\\u0631\\u0636')===0){caret='summary after '+i+' lines';break;}
                          d.MoveCursorDown(false,false);}
                        if(d.UpdateInterface)d.UpdateInterface();else if(d.Document_UpdateInterfaceState)d.Document_UpdateInterfaceState();
                        if(d.UpdateSelection)d.UpdateSelection();
                      }catch(e){caret='error: '+e;}
                      var m=(w.AscFonts&&w.AscFonts.g_map_font_index)||{};
                      var sb=w.document.getElementById('statusbar');
                      return {caret:caret, statusbar:sb?(sb.innerText||'').replace(/\\s+/g,' ').trim().slice(0,160):'',
                        fonts:['Helvetica Neue','Arial','Geeza Pro'].map(function(n){return n+':'+(n in m);}),
                        title:(w.document.title||''), rtl:w.document.body.className.indexOf('rtl')>=0,
                        tabs:[].slice.call(w.document.querySelectorAll('#toolbar .ribtab a')).map(function(a){return a.innerText.trim();}).filter(String).slice(0,12)};})()""")
                    res["editor_info"] = info
                    log("editor:", json.dumps(info, ensure_ascii=False))
                if MODE == "shots":
                    # the page's pointer rests on an empty stretch of the status bar (no table handle, no tooltip)
                    vw = await pg.ev("[innerWidth, innerHeight]") or [1000, 700]
                    rest = (vw[0] * (0.36 if LANG == "en" else 0.64), vw[1] - 11)
                    park_pointer()
                    await pg.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": rest[0], "y": rest[1]})
                    await asyncio.sleep(2)
                    # what the picture holds: tips / dialogs, English words left in the Arabic UI, private data
                    res.setdefault("editors_final", {})[tag] = await pg.ev(TIPS_JS)
                    res.setdefault("ui", {})[tag] = await pg.ev(UI_JS)
                    log(tag, "final:", json.dumps(res["editors_final"][tag], ensure_ascii=False),
                        "latin:", json.dumps((res["ui"][tag] or {}).get("latin"), ensure_ascii=False))
                    caret = tag in ("editor", "slide", "pdf")
                    box = place_window()[:4]
                    await asyncio.sleep(1.5)
                    res.setdefault("more_final", {})[tag] = await pg.ev(MORE_JS)
                    if caret:
                        await pg.ev(CARET_JS.replace("__HOLD__", "true"))
                    screen_shot(tag, box)
                    if caret:
                        await pg.ev(CARET_JS.replace("__HOLD__", "false"))
                    res["titlebar_" + tag] = titlebar()
                    log("title bar (%s):" % tag, json.dumps(res["titlebar_" + tag], ensure_ascii=False)[:1500])
                    await page_shot_2x(pg, tag, rest=rest, caret=caret)
                    res.setdefault("editor_users", []).append(
                        (re.search(r"[?&]username=([^&]*)", ed.get("url", "")) or [None, ""])[1])
                    if tag == "pdf":
                        res["pdf_roundtrip"] = await pdf_roundtrip(pg, dst, targets, s)
                else:
                    screen_shot(tag, place_window()[:4])
                    res["windows_" + tag] = osa(PROC + ' to get {name, subrole} of every window')
                    if tag in ("cell", "sheet", "slide"):
                        await ribbon_fit(pg, tag)
    ensure_quit()
    return proc


r = asyncio.run(main())
for _ in range(3):              # one more launch after the language switch (Settings path) / the recent files
    if r != "again":
        break
    res["log"].append("relaunch")
    r = asyncio.run(main())
json.dump(res, open(os.path.join(OUT, "capture-%s-%s.json" % (MODE, LANG)), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if MODE == "shots":
    try:
        shutil.copytree(DOCS, os.path.join(OUT, "docs-shots-%s" % LANG), dirs_exist_ok=True)
    except Exception as e:
        print("docs evidence not copied:", e)
print(json.dumps({k: v for k, v in res.items() if k != "log"}, ensure_ascii=False, indent=1)[:4000])
bad = ["tips in " + t for t, v in res.get("editors", {}).items() if v and v.get("tips")]
sp = res.get("start_page") or {}
if MODE in ("shots", "switch"):
    want = "rtl" if LANG == "ar" else "ltr"
    if sp.get("dir") != want or ("lang=" + CODE) not in (sp.get("lang") or ""):
        bad.append("start page not in %s: %s %s" % (CODE, sp.get("dir"), sp.get("lang")))
    if sp.get("pill_over_sidebar") or sp.get("pill_side") != ("left" if LANG == "ar" else "right"):
        bad.append("account pill %s over %s" % (sp.get("pill_side"), sp.get("pill_over_sidebar")))
    if sp.get("pill_card_gap") is None or sp["pill_card_gap"] < 12:
        bad.append("account pill too close to the cards: %s px" % sp.get("pill_card_gap"))
    # the Arabic start page: no English left (Xrero / PDF / extensions are fine). The account's name is the user's own
    # data, not interface text: switch keeps the account signed in under audit's English name ("Projects team") and
    # the interface must not translate it (run 29 failed on it; the shots pictures sign in with the Arabic name)
    acct_name = (sp.get("pill") or "").split("|", 1)[-1]
    left_ui = [t for t in sp.get("latin_ui") or [] if t != acct_name]
    if LANG == "ar" and left_ui:
        bad.append("English on the Arabic start page: %s" % left_ui)
if MODE == "shots":
    if len(sp.get("recents") or []) < 4 or not all("data:image/webp" in x for x in sp.get("recents") or []):
        bad.append("recent files on the start picture (4, kit pictures): %s" % sp.get("recents"))
    # (16 Nov 2026 review) the account reads as a team account, at working hours, the Arabic date column's own name
    if sp.get("pill") != "%s|%s" % (ACCOUNT[1], ACCOUNT[0]):
        bad.append("account pill %r, not %s|%s" % (sp.get("pill"), ACCOUNT[1], ACCOUNT[0]))
    if (sp.get("dates") or []) and not all(d.split()[-1:] and d.split()[-1] in RECENT_TIMES for d in sp.get("dates")):
        bad.append("recent files' times not at working hours: %s" % sp.get("dates"))
    if LANG == "ar" and sp.get("date_head") != "آخر فتح":
        bad.append("Arabic Recent files date column: %r" % sp.get("date_head"))
    # (run 28) the Recent files' folder is the neutral shared one, not the CI checkout
    if (sp.get("locs") or []) and not all("Shared/Office files" in x for x in sp.get("locs")):
        bad.append("recent files' folder on the start picture: %s" % sp.get("locs"))
    # (run 29) in the Arabic start page the path keeps its own direction (web/xr-home.js), not "Users/.../Office files/"
    if LANG == "ar" and (sp.get("locs") or []) and sp.get("loc_bidi") != "plaintext":
        bad.append("Arabic Recent files' folder not laid out from its own text: %r" % sp.get("loc_bidi"))
    for tag, m in (res.get("more_final") or {}).items():
        if not m or m.get("more") is not False:
            bad.append("%s picture: ribbon groups folded into More (window %s): %s" % (tag, res.get("picture_window"), m))
    if not str((res.get("editor_info") or {}).get("caret", "")).startswith("summary"):
        bad.append("caret not in the Arabic summary: %s" % (res.get("editor_info") or {}).get("caret"))
    # the five-picture set (16 Nov 2026): every editor picture taken, ready, no tips / dialogs, nothing private
    taken = {x.get("name") for x in res.get("shots", []) if x.get("page2x")}
    for tag in ("start", "editor", "sheet", "slide", "pdf"):
        if tag not in taken:
            bad.append("no %s picture" % tag)
    for x in res.get("shots", []):
        if x.get("page2x") and x.get("hover"):
            bad.append("%s picture: hover state on %s" % (x.get("name"), x.get("hover")))
        if x.get("page2x") and x.get("name") in ("editor", "slide", "pdf") and not str(x.get("caret", "")).startswith("held"):
            bad.append("%s picture: caret not shown (%s)" % (x.get("name"), x.get("caret")))
    for tag, st in (res.get("ready") or {}).items():
        if st != "ok":
            bad.append("%s editor not ready: %s" % (tag, st))
    for tag, v in (res.get("editors_final") or {}).items():
        if not v or v.get("tips") or v.get("dialogs"):
            bad.append("%s picture: tips / dialogs %s" % (tag, v))
    who = [x for x in {os.environ.get("USER", ""), os.environ.get("LOGNAME", ""), os.path.basename(os.path.expanduser("~"))}
           | set(res.get("editor_users") or []) if len(x) > 2]
    priv = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+" + "".join(r"|\b%s\b" % re.escape(x) for x in who), re.I)
    # Latin words an Arabic picture may keep: the product name, the account chip's initials, PDF, file extensions
    latin_ok = re.compile(r"^(Xrero( Office)?|XO|PDF|.*\.(docx|xlsx|pptx|pdf))$")
    for tag, u in (res.get("ui") or {}).items():
        u = u or {}
        hits = priv.findall(" | ".join([u.get("text", "")] + (u.get("inputs") or [])))
        if hits:
            bad.append("%s picture: private data on screen %s" % (tag, hits[:5]))
        if LANG == "ar":
            left = [t for t in u.get("latin") or [] if not latin_ok.match(t)]
            if left:
                bad.append("%s picture: English in the Arabic interface %s" % (tag, left[:12]))
        if u.get("chip") != ACCOUNT[1]:
            bad.append("%s picture: account chip %r, not %s" % (tag, u.get("chip"), ACCOUNT[1]))
    for k, v in res.items():
        if k.startswith("titlebar_") and priv.findall(json.dumps(v, ensure_ascii=False)):
            bad.append("%s: private data %s" % (k, priv.findall(json.dumps(v, ensure_ascii=False))[:5]))
    si = res.get("sheet_info") or {}
    if (si.get("cell") != "E5" or not str(si.get("formula", "")).upper().startswith("=SUM(") or (si.get("charts") or 0) < 1
            or si.get("font") != FONT or si.get("rtl") is not (LANG == "ar")
            or (LANG == "ar" and si.get("formula_bidi") != "plaintext")):     # (patch_bundle.py XR-FBIDI)
        bad.append("spreadsheet picture (E5 =SUM, a chart, %s, rtl=%s): %s" % (FONT, LANG == "ar", si))
    sl = res.get("slide_info") or {}
    if not sl.get("in_text") or sl.get("at_end") is not True or sl.get("slide") != 0 or sl.get("slides") != 4 or sl.get("font") != FONT:
        bad.append("presentation picture (caret in slide 1's title, %s): %s" % (FONT, sl))
    pi = res.get("pdf_info") or {}
    got = {k: v for k, v in (pi.get("fields") or [])}
    if (any(got.get(k) != v for k, v in PDF_FILL) or pi.get("active") != "notes" or pi.get("tab") != "comment"
            or HIGHLIGHT not in (pi.get("annots") or []) or TEXT_NOTE not in (pi.get("annots") or []) or pi.get("popover")):
        bad.append("PDF picture (form filled, caret in notes, a highlight + a sticky note made in the app, Comment tab, "
                   "no comment balloon): %s" % json.dumps(pi, ensure_ascii=False)[:2500])
    if INK not in (pi.get("annots") or []):
        print("note: no pen circle on the PDF picture (optional):", (pi.get("marks") or {}).get("pen_button"))
    rt = res.get("pdf_roundtrip") or {}
    print("PDF round trip (save, file, reopen):", "OK" if rt.get("ok") else "NOT OK", rt.get("checks"))
    # (run 28: the boxes ticked with Enter were "Off" in the saved file) the store text says "form filling" only if
    # the filled form, its ticks and the marks survive Save + reopen
    if not rt.get("ok"):
        bad.append("PDF round trip (save, file, reopen) NOT OK: %s file %s app %s" % (
            rt.get("checks"), rt.get("file_fields"), rt.get("app_fields")))
if bad:
    print("FAIL:", bad)
sys.exit(3 if bad else 0)
