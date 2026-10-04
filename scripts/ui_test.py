#!/usr/bin/env python3
"""ui_test.py <Xrero Office.app> <arm64|x86_64> <test dir> <out dir>
Launches the real app (DevTools port 9222), screenshots the start page, opens a document, types English + Arabic,
presses Enter / Cmd+B / Cmd+S, verifies the text and the saved file, checks the Windows-only header buttons are
hidden and the start page has no sign-in wall / ONLYOFFICE text. Writes <out>/ui-<arch>.json + PNGs."""
import asyncio, base64, json, os, plistlib, shutil, subprocess, sys, time
import aiohttp

APP, ARCH, TDIR, OUT = sys.argv[1:5]
APP, TDIR, OUT = os.path.abspath(APP), os.path.abspath(TDIR), os.path.abspath(OUT)
EXE = os.path.join(APP, "Contents", "MacOS", plistlib.load(open(os.path.join(APP, "Contents", "Info.plist"), "rb"))["CFBundleExecutable"])
PORT = 9222
os.makedirs(OUT, exist_ok=True)
res = {"arch": ARCH, "checks": {}, "shots": []}

def ok(name, cond, detail=""):
    res["checks"][name] = {"pass": bool(cond), "detail": detail}
    print(("PASS " if cond else "FAIL ") + name, detail, flush=True)

def screencap(name):
    p = os.path.join(OUT, "%s-%s-screen.png" % (name, ARCH))
    subprocess.run(["screencapture", "-x", p], capture_output=True)
    if os.path.exists(p): res["shots"].append(os.path.basename(p))

async def targets(s):
    async with s.get("http://127.0.0.1:%d/json" % PORT) as r:
        return await r.json(content_type=None)

def is_start(t):
    u = t.get("url", "")
    return t.get("type") == "page" and u.startswith(("file:", "http")) and "/apps/" not in u and "documents/" not in u

def windows():
    # best effort (needs Accessibility for the runner's shell): every window the app shows, with its subrole
    r = subprocess.run(["osascript", "-e", 'tell application "System Events" to tell (first process whose bundle identifier is "com.xrero.office") '
                        'to get {name, subrole} of every window'], capture_output=True, text=True, timeout=20)
    return (r.stdout or r.stderr).strip()

class Page:
    def __init__(self, ws): self.ws, self.n = ws, 0
    async def call(self, m, p=None):
        self.n += 1; await self.ws.send_json({"id": self.n, "method": m, "params": p or {}})
        while True:
            r = await self.ws.receive_json()
            if r.get("id") == self.n: return r
    async def ev(self, expr):
        r = await self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("result", {}).get("value")
    async def shot(self, name):
        r = await self.call("Page.captureScreenshot", {"format": "png"})
        p = os.path.join(OUT, "%s-%s.png" % (name, ARCH))
        open(p, "wb").write(base64.b64decode(r["result"]["data"])); res["shots"].append(os.path.basename(p))
    async def key(self, code, name, mods=0, text=None):
        k = name[-1].lower() if name.startswith("Key") else name
        down = {"type": "keyDown" if text else "rawKeyDown", "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code,
                "code": name, "key": k, "modifiers": mods}
        if text: down["text"] = text
        await self.call("Input.dispatchKeyEvent", down)
        await self.call("Input.dispatchKeyEvent", {"type": "keyUp", "windowsVirtualKeyCode": code, "code": name, "key": k, "modifiers": mods})
    async def click(self, x, y):
        for t in ("mousePressed", "mouseReleased"):
            await self.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1})

async def main():
    cmd = (["arch", "-x86_64"] if ARCH == "x86_64" else []) + [EXE, "--remote-debugging-port=%d" % PORT]
    proc = subprocess.Popen(cmd, stdout=open(os.path.join(OUT, "app-%s.log" % ARCH), "w"), stderr=subprocess.STDOUT)
    t0 = time.time()
    async with aiohttp.ClientSession() as s:
        ts, seen = [], ""
        for i in range(90):
            await asyncio.sleep(1)
            if proc.poll() is not None: break
            try:
                ts = await targets(s)
            except Exception:
                continue
            now = " | ".join("%s %s" % (t.get("type"), t.get("url", "")[-90:]) for t in ts)
            if now != seen: print("[%2ds] targets: %s" % (i + 1, now or "(none)"), flush=True); seen = now
            if any(is_start(t) for t in ts): break
        start = next((t for t in ts if is_start(t)), None)
        ok("app_starts", proc.poll() is None and start, "start page target after %.0fs: %s" % (time.time() - t0, (start or {}).get("url", "")[-120:]))
        if not start:
            screencap("01-start-failed"); return
        await asyncio.sleep(8)
        screencap("01-start")
        # first launch must not greet the user with prompts (Sparkle "check automatically?", etc.)
        d = subprocess.run(["defaults", "read", "com.xrero.office", "SUEnableAutomaticChecks"], capture_output=True, text=True)
        ok("first_launch_no_update_prompt", d.stdout.strip() == "0", "SUEnableAutomaticChecks=%r" % d.stdout.strip())
        w = windows()
        res["windows_at_start"] = w
        print("windows:", w, flush=True)
        async with s.ws_connect(start["webSocketDebuggerUrl"], max_msg_size=0) as ws:
            pg = Page(ws)
            await pg.shot("01-start-page")
            info = await pg.ev("""(function(){var t=document.body.innerText||'';return {title:document.title,
              onlyoffice:(t.match(/ONLYOFFICE/g)||[]).length, wall:!!document.querySelector('.xr-card'),
              recover: typeof (window.AscDesktopEditor||{}).LocalFileRecovers, len:t.length};})()""")
            ok("start_page_rendered", info and info.get("len", 0) > 50, json.dumps(info))
            ok("start_page_no_wall", info and not info.get("wall"), "")
            ok("start_page_no_onlyoffice_text", info and info.get("onlyoffice", 1) == 0, "count=%s" % (info or {}).get("onlyoffice"))
        # open a document the way Finder does
        doc = os.path.join(OUT, "ui-test-%s.docx" % ARCH)
        shutil.copy(os.path.join(TDIR, "inputs", "edge_cases.docx"), doc)
        m0 = os.stat(doc).st_mtime
        old = {t["id"] for t in await targets(s)}
        subprocess.run(["open", "-a", APP, doc])
        ed = None
        seen = ""
        for i in range(60):
            await asyncio.sleep(1)
            new = [t for t in await targets(s) if t["id"] not in old and t.get("type") == "page"]
            now = " | ".join(t.get("url", "")[-90:] for t in new)
            if now != seen: print("[%2ds] new targets: %s" % (i + 1, now or "(none)"), flush=True); seen = now
            eds = [t for t in new if "documents/index.html" in t.get("url", "") or "/apps/" in t.get("url", "")]
            if eds: ed = eds[0]; break
        ok("document_opens", ed is not None, (ed or {}).get("url", "")[-120:])
        if not ed: screencap("02-open-failed"); return
        await asyncio.sleep(10)
        async with s.ws_connect(ed["webSocketDebuggerUrl"], max_msg_size=0) as ws:
            pg = Page(ws)
            await pg.shot("02-editor-open")
            screencap("02-editor-open")
            hidden = await pg.ev("""(function(){var d=document.querySelector('iframe[name=frameEditor]');d=d&&d.contentDocument||document;
              var ids=['xr-b-ctx','xr-lang','xr-b-share','xr-b-acct'];var o={};ids.forEach(function(i){var e=d.getElementById(i);
              o[i]= e? getComputedStyle(e).display : 'absent';});return o;})()""")
            ok("windows_only_buttons_hidden", hidden and all(v in ("none", "absent") for v in hidden.values()), json.dumps(hidden))
            vw = await pg.ev("[innerWidth, innerHeight]") or [1200, 800]
            x, y = vw[0] * 0.5, vw[1] * 0.45
            await pg.click(x, y); await asyncio.sleep(0.6); await pg.click(x, y); await asyncio.sleep(0.6)
            await pg.ev("(function(){try{var w=document.querySelector('iframe[name=frameEditor]').contentWindow;w.editor.WordControl.m_oLogicDocument.MoveCursorToEndPos();}catch(e){}})()")
            await pg.key(13, "Enter", 0, "\r")
            await pg.call("Input.insertText", {"text": "Mac typing check 20.0.9 - English OK."})
            await pg.key(13, "Enter", 0, "\r")
            await pg.call("Input.insertText", {"text": "فحص الكتابة على ماك بالعربي يعمل"})
            await pg.key(13, "Enter", 0, "\r")
            await pg.key(66, "KeyB", 4)               # Cmd+B
            await pg.call("Input.insertText", {"text": "Bold عريض"})
            await pg.key(66, "KeyB", 4)
            await asyncio.sleep(1.5)
            txt = await pg.ev("""(function(){var w=document.querySelector('iframe[name=frameEditor]').contentWindow;
              var d=w.editor.WordControl.m_oLogicDocument;d.SelectAll();var t=d.GetSelectedText(false);d.RemoveSelection();
              return {tail:t.slice(-160), modified:w.editor.isDocumentModified()};})()""")
            tail = (txt or {}).get("tail", "")
            ok("typing_english", "Mac typing check 20.0.9 - English OK." in tail, "")
            ok("typing_arabic", "فحص الكتابة على ماك بالعربي يعمل" in tail, "")
            ok("typing_bold_text", "Bold عريض" in tail, repr(tail[-80:]))
            await pg.shot("03-editor-typed")
            await pg.key(83, "KeyS", 4)               # Cmd+S
            await asyncio.sleep(6)
            mod = await pg.ev("document.querySelector('iframe[name=frameEditor]').contentWindow.editor.isDocumentModified()")
            ok("save_in_place", os.stat(doc).st_mtime > m0 and mod is False, "mtime changed=%s modified=%s" % (os.stat(doc).st_mtime > m0, mod))
            screencap("04-after-save")
    try:
        subprocess.run(["osascript", "-e", 'quit app "Xrero Office"'], timeout=20)
        time.sleep(5)
    except Exception: pass
    if proc.poll() is None: proc.kill()

asyncio.run(main())
res["passed"] = sum(1 for c in res["checks"].values() if c["pass"]); res["total"] = len(res["checks"])
json.dump(res, open(os.path.join(OUT, "ui-%s.json" % ARCH), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("UI %s: %d/%d" % (ARCH, res["passed"], res["total"]))
sys.exit(0 if res["passed"] == res["total"] else 4)
