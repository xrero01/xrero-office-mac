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
       caret in its Arabic summary (the status bar and the ribbon show the Arabic paragraph). Each picture is written
       twice:
         <lang>-<name>-window.png  the window as the screen shows it (screencapture, 1x on the CI display)
         <lang>-<name>-page2x.png  the same page drawn by the app at Retina scale (DevTools, device scale 2)
audit: first run in a fresh container: what a user sees in the first seconds and on the first open of each editor
       (Word, spreadsheet, presentation, PDF): tip balloons, dialogs, extra windows -> audit-*.png + capture-audit.json.
switch: after audit, the same container relaunched in the other language (what a user does in Settings > Interface
       language): the start page must follow it (direction, account pill on the far side, not over the sidebar).
"""
import asyncio, base64, json, os, plistlib, shutil, subprocess, sys, time
import aiohttp

APP, MODE, LANG, OUT, SRC = sys.argv[1:6]
APP, OUT, SRC = os.path.abspath(APP), os.path.abspath(OUT), os.path.abspath(SRC)
EXE = os.path.join(APP, "Contents", "MacOS", plistlib.load(open(os.path.join(APP, "Contents", "Info.plist"), "rb"))["CFBundleExecutable"])
BID = "com.xrero.office"
PORT = 9333
CODE = {"en": "en-US", "ar": "ar-SA"}[LANG]
DOC_NAME = {"en": "Q3 report.docx", "ar": "التقرير الربعي.docx"}[LANG]    # (en: short enough for the whole tab title)
# the Recent files of the start picture: (name, source in the repo or None = a PDF made here), opened oldest first
HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = os.path.join(HERE, "..", "test", "inputs")
RECENTS = {"en": [("Welcome guide.pdf", None), ("Q3 review.pptx", "slides_ar.pptx"),
                  ("Projects by office.xlsx", "sheet_ar.xlsx"), (DOC_NAME, "DEMO")],
           "ar": [("دليل الترحيب.pdf", None), ("عرض الربع الثالث.pptx", "slides_ar.pptx"),
                  ("المشاريع حسب المكتب.xlsx", "sheet_ar.xlsx"), (DOC_NAME, "DEMO")]}[LANG]
PROC = 'tell application "System Events" to tell (first process whose bundle identifier is "%s")' % BID
os.makedirs(OUT, exist_ok=True)
res = {"mode": MODE, "lang": CODE, "shots": [], "log": []}


def log(*a):
    s = " ".join(str(x) for x in a)
    res["log"].append(s)
    print(s, flush=True)


def osa(*lines):
    r = subprocess.run(["osascript"] + [a for l in lines for a in ("-e", l)], capture_output=True, text=True, timeout=30)
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


def place_window():
    osa('tell application id "%s" to activate' % BID)
    x, y, w, h, sc = visible_frame()
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
# the name "Xrero Office" -> initials "XO" on the editors' account chip (a lone "X" there read as a close button)
SESSION_JS = """new Promise(function(done){try{
  if(!localStorage.getItem('xr-acct-token')){localStorage.setItem('xr-acct-token','local-store-pictures');
    localStorage.setItem('xr-acct',JSON.stringify({locked:false,name:'Xrero Office',email:'preview@example.invalid'}));}
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


async def page_shot_2x(pg, name):
    """the page drawn at device scale 2 (Retina), the layout size unchanged"""
    vw = await pg.ev("[innerWidth, innerHeight, devicePixelRatio]") or [0, 0, 1]
    await pg.call("Emulation.setDeviceMetricsOverride", {"width": vw[0], "height": vw[1], "deviceScaleFactor": 2, "mobile": False})
    await asyncio.sleep(4)
    dpr = await pg.ev("devicePixelRatio")
    r = await pg.call("Page.captureScreenshot", {"format": "png"})
    await pg.call("Emulation.clearDeviceMetricsOverride")
    await asyncio.sleep(2)
    if r.get("result", {}).get("data"):
        p = os.path.join(OUT, "%s-%s-page2x.png" % (LANG, name))
        open(p, "wb").write(base64.b64decode(r["result"]["data"]))
        res["shots"].append({"name": name, "page2x": os.path.basename(p), "viewport": vw[:2], "dpr_then": dpr})
        log("page 2x", name, vw, "dpr", dpr)


def make_doc(name, src):
    """a file to open, copied into the run's folder under the name the picture shows (src None -> a small PDF)"""
    dst = os.path.join(OUT, "docs-%s-%s" % (MODE, LANG), name)
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


async def main():
    ensure_quit()
    if MODE in ("shots", "switch"):
        if not container_ready():
            prime()
        set_language()
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
                dst = make_doc(name, SRC if src == "DEMO" else (os.path.join(INPUTS, src) if src else None))
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
            return "again"

        box = place_window()
        log("window", box)
        res["window"] = box
        await asyncio.sleep(3)
        if MODE in ("shots", "switch"):
            async with s.ws_connect(start["webSocketDebuggerUrl"], max_msg_size=0) as ws:
                pg = Page(ws)
                vw = await pg.ev("[innerWidth, innerHeight]") or [1000, 700]
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
                    await page_shot_2x(pg, "start")

        # documents, opened the way Finder does
        if MODE == "switch":
            docs = []
        elif MODE == "shots":
            docs = [(DOC_NAME, SRC, "editor")]
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
                    # the page's pointer rests on an empty stretch of the status bar (no table handle, no tooltip)
                    vw = await pg.ev("[innerWidth, innerHeight]") or [1000, 700]
                    await pg.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": vw[0] * (0.36 if LANG == "en" else 0.64), "y": vw[1] - 11})
                    await asyncio.sleep(2)
                    screen_shot(tag, place_window()[:4])
                    res["titlebar_" + tag] = titlebar()
                    log("title bar (%s):" % tag, json.dumps(res["titlebar_" + tag], ensure_ascii=False)[:1500])
                    await page_shot_2x(pg, tag)
                else:
                    screen_shot(tag, place_window()[:4])
                    res["windows_" + tag] = osa(PROC + ' to get {name, subrole} of every window')
    ensure_quit()
    return proc


r = asyncio.run(main())
for _ in range(3):              # one more launch after the language switch (Settings path) / the recent files
    if r != "again":
        break
    res["log"].append("relaunch")
    r = asyncio.run(main())
json.dump(res, open(os.path.join(OUT, "capture-%s-%s.json" % (MODE, LANG)), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
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
    if LANG == "ar" and sp.get("latin_ui"):     # the Arabic start page: no English left (Xrero / PDF / extensions are fine)
        bad.append("English on the Arabic start page: %s" % sp.get("latin_ui"))
if MODE == "shots":
    if len(sp.get("recents") or []) < 4 or not all("data:image/webp" in x for x in sp.get("recents") or []):
        bad.append("recent files on the start picture (4, kit pictures): %s" % sp.get("recents"))
    if not str((res.get("editor_info") or {}).get("caret", "")).startswith("summary"):
        bad.append("caret not in the Arabic summary: %s" % (res.get("editor_info") or {}).get("caret"))
if bad:
    print("FAIL:", bad)
sys.exit(3 if bad else 0)
