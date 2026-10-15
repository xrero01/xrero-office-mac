#!/usr/bin/env python3
"""store_shots.py <Xrero Office.app> <test dir> <out dir>
App Store screenshots from the real (sandboxed) app: a large window, the start page, then sample documents
(Arabic report, colour document, spreadsheet, presentation) with the first-run "New feature" tips dismissed.
Writes <out>/store-<name>.png (window only) + store.json."""
import asyncio, json, os, plistlib, shutil, subprocess, sys, time
import aiohttp
from PIL import Image

APP, TDIR, OUT = [os.path.abspath(a) for a in sys.argv[1:4]]
EXE = os.path.join(APP, "Contents", "MacOS", plistlib.load(open(os.path.join(APP, "Contents", "Info.plist"), "rb"))["CFBundleExecutable"])
PORT = 9333
os.makedirs(OUT, exist_ok=True)
PROC = 'tell application "System Events" to tell (first process whose bundle identifier is "com.xrero.office")'
DOCS = [("writer-ar", "ar_report.docx"), ("writer-en", "en_colour.docx"), ("calc", "sheet_ar.xlsx"), ("slides", "slides_ar.pptx")]
res = {"shots": [], "log": []}


def osa(*lines):
    r = subprocess.run(["osascript"] + [a for l in lines for a in ("-e", l)], capture_output=True, text=True, timeout=30)
    return (r.stdout or r.stderr).strip()


def place_window():
    osa('tell application id "com.xrero.office" to activate')
    osa(PROC + ' to set position of window 1 to {60, 50}', PROC + ' to set size of window 1 to {1800, 1010}')
    time.sleep(1.5)
    b = osa(PROC + ' to get {position, size} of window 1')
    try:
        x, y, w, h = [int(v) for v in b.replace(" ", "").split(",")]
    except ValueError:
        x, y, w, h = 60, 50, 1800, 1010
    return x, y, w, h


def shot(name):
    x, y, w, h = place_window()
    full = os.path.join(OUT, "full-%s.png" % name)
    subprocess.run(["screencapture", "-x", full], capture_output=True)
    im = Image.open(full)
    try:
        sx = im.width / float(subprocess.run(["osascript", "-e", 'tell application "Finder" to get bounds of window of desktop'],
                                             capture_output=True, text=True, timeout=20).stdout.split(",")[2])
    except Exception:
        sx = 1.0
    crop = im.crop((int(x * sx), int(y * sx), int((x + w) * sx), int((y + h) * sx)))
    p = os.path.join(OUT, "store-%s.png" % name)
    crop.save(p)
    os.remove(full)
    res["shots"].append({"name": name, "file": os.path.basename(p), "size": crop.size})
    print("shot", name, crop.size, flush=True)


DISMISS = """(function(){var n=0;function go(d){if(!d)return;d.querySelectorAll('button,.btn,a').forEach(function(b){
  var t=(b.innerText||'').trim();if(t==='Got it'||t==='حسناً'||t==='OK, got it'){b.click();n++;}});
  d.querySelectorAll('iframe').forEach(function(f){try{go(f.contentDocument);}catch(e){}});}
  go(document);return n;})()"""


async def ev(ws, expr, i=[0]):
    i[0] += 1
    await ws.send_json({"id": i[0], "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}})
    while True:
        r = await ws.receive_json()
        if r.get("id") == i[0]:
            return r.get("result", {}).get("result", {}).get("value")


async def main():
    proc = subprocess.Popen([EXE, "--remote-debugging-port=%d" % PORT], stdout=open(os.path.join(OUT, "store-app.log"), "w"),
                            stderr=subprocess.STDOUT)
    async with aiohttp.ClientSession() as s:
        async def targets():
            async with s.get("http://127.0.0.1:%d/json" % PORT) as r:
                return await r.json(content_type=None)
        for _ in range(60):
            await asyncio.sleep(1)
            try:
                if [t for t in await targets() if t.get("type") == "page"]:
                    break
            except Exception:
                pass
        await asyncio.sleep(6)
        shot("start")
        for name, doc in DOCS:
            src = os.path.join(TDIR, "inputs", doc)
            if not os.path.exists(src):
                res["log"].append("missing " + doc)
                continue
            dst = os.path.join(OUT, doc)
            shutil.copy(src, dst)
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
                res["log"].append("did not open " + doc)
                continue
            await asyncio.sleep(10)
            async with s.ws_connect(ed["webSocketDebuggerUrl"], max_msg_size=0) as ws:
                for _ in range(4):
                    n = await ev(ws, DISMISS)
                    res["log"].append("%s: dismissed %s tip(s)" % (doc, n))
                    await asyncio.sleep(1.5)
            await asyncio.sleep(2)
            shot(name)
    osa('tell application id "com.xrero.office" to quit')
    for _ in range(20):
        if proc.poll() is not None:
            break
        time.sleep(1)
    if proc.poll() is None:
        proc.kill()

asyncio.run(main())
json.dump(res, open(os.path.join(OUT, "store.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
