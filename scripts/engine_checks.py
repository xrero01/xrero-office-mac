#!/usr/bin/env python3
"""engine_checks.py - document-engine checks of the Mac UI test (16 Nov 2026, APP-BACKLOG 18 + store NOTES).

scripts/ui_test.py runs them in a second session of the real app (after its own checks and its Quit), so its own checks
are unchanged and every editor here starts with nothing typed yet. Each case is a real user's flow (CDP mouse / text
input into the editor, Cmd+S, a copy opened again from Finder) and the saved file is read and drawn with PyMuPDF
(an independent PDF renderer). Evidence: <out>/engine-<arch>/ (PNGs, the saved files, engine-<arch>.json).

  pdf_ar_field   ar_form_embedded.pdf: Arabic typed into a text field whose font is an EMBEDDED Arabic font (/DR, like
                 the Windows store demo's /Dubai and like many real Arabic forms) must be SAVED shaped - joined letters,
                 not separate overlapping ones (APP-BACKLOG 18, HIGH). The value has two lam-alef ligatures ("الإمارات",
                 "للملاحظات": ligatures take their own path in XR-FIELD-AP). The saved field is drawn with PyMuPDF and
                 compared with the same text shaped by MuPDF/HarfBuzz in the same font (ink match >= MATCH_OK), and the
                 saved appearance must hold exactly one outline fill per non-space glyph the editor shaped (counted in
                 the editor before Save; the ink match alone cannot see one broken ligature). A Latin value in the same
                 font must stay right (text), and the copy opened again in the app must show the values. (The
                 reproduction without the fix: build-mac runs 39-42, ink match 0.44 and no outlines. On the Mac the saved
                 appearance is drawn by the converter's sdkjs, so no switch in the editor gives a control round.)
  pdf_first_input  mas/store_demo_form_ar.pdf filled like a user (Tab, type): the first thing typed into the date field
                 must arrive (store NOTES: "the first input typed into the date field after tabbing into it does not
                 arrive"); the editor's input path is logged (input_log). Four rounds: the value typed as one piece with
                 the Mac fix switched off in that editor (window.__xrNoFirstInputFix - the control, it must still lose
                 the input) and on (the fix must have acted); then the same with the field's font load made truly
                 asynchronous (the font loader's callback delayed by SLOW_MS) and the date typed key by key, KEY_GAP_MS
                 apart: off it must still lose input, on every key must arrive in its order through the held-input
                 queue (XR-FIELD-FIRST-INPUT layer 2).
  pdf_bold_lamalef  ar_bold_lamalef.pdf (bold / regular / bold without hinting, IBM Plex Sans Arabic subsets) and the
                 run-27 form's 12.5 pt bold headings: the app's page drawing of each line (scrolled into view first)
                 next to MuPDF's. RECORD ONLY, not fixed: the page is drawn by the app's native renderer, not by the web
                 layer, and the ink match cannot see one broken ligature (run 42: 0.979 on a visibly broken heading) -
                 the PNGs are the evidence.
  pptx_lang      mas/store_demo_slides_ar.pptx: the caret in the Arabic title (lang="ar-AE") - the language the editor
                 reports (status bar) must be ar-AE (LCID 14337), not ar-SA (store NOTES).
"""
import asyncio, base64, json, os, re, shutil, subprocess, sys, time
import aiohttp

PORT = 9222
MATCH_OK = 0.85          # ink match of a shaped Arabic line with its reference, 2 px tolerance at 4x (calibrated 17 Nov
                         # 2026: unshaped 0.60 / 0.75 (Windows store file), 0.60 (Mac run 42); shaped: the outlines of
                         # XR-FIELD-AP 0.91, text in Mac Arial 1.0)
MATCH_K = 2
AR_CLIENT = "مؤسسة الإمارات للملاحظات"       # two lam-alef ligatures (لإ, لا)
LATIN_REF = "XO-2026-014"
AR_OFFICE = "الشارقة"
DATE = "24/11/2026"
SLOW_MS = 500            # the forced-asynchronous font load: the loader's callback this much later
KEY_GAP_MS = 30          # the key-by-key date in the asynchronous rounds
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

FRAME = r"""var f=document.querySelector('iframe[name=frameEditor]');var w=f&&f.contentWindow||window,d=w.document;
  var fr=f?f.getBoundingClientRect():{left:0,top:0};var api=(w.Asc&&w.Asc.editor)||w.editor;
  function statusbar(){var s=d.getElementById('statusbar');return s?(s.innerText||'').replace(/\s+/g,' ').trim().slice(0,200):'';}"""

READY_JS = r"""(function(tag){""" + FRAME + r"""
  if(!api)return 'no editor api';
  if([].slice.call(d.querySelectorAll('.asc-loadmask')).some(function(e){return e.offsetParent!==null;}))return 'loading';
  try{if(tag==='slide')return api.WordControl.m_oLogicDocument.Slides.length?'ok':'no slides';
    if(tag==='pdf'){var v=api.getDocumentRenderer();return v&&v.file&&v.file.pages&&v.file.pages.length&&api.getPDFDoc()?'ok':'no pages';}
    return api.WordControl.m_oLogicDocument?'ok':'no document';}catch(e){return 'error: '+e;}})(__TAG__)"""

# page (PDF points, top-left origin) -> page CSS px of the editor tab (store_capture.py PDF_SAVED_JS)
PDF_GEOM_JS = r"""(function(){""" + FRAME + r"""var o={fields:{}};
  try{var doc=api.getPDFDoc(),v=api.getDocumentRenderer(),det=v.getPageLikeDetector(0),rp=w.AscCommon.AscBrowser.retinaPixelRatio||1;
    var cv=v.canvas.getBoundingClientRect(),W=v.file.pages[0].W,sc=(det.w/rp)/W,pl=cv.left+det.x/rp,pt=cv.top+det.y/rp;
    o.org=[fr.left+pl,fr.top+pt];o.sc=sc;o.page_w=W;o.view=[fr.left+cv.left,fr.top+cv.top,fr.left+cv.right,fr.top+cv.bottom];
    doc.widgets.forEach(function(x){var r=x.GetRect();o.fields[x.GetFullName()]={rect:r,
      px:[fr.left+pl+r[0]*sc,fr.top+pt+r[1]*sc,fr.left+pl+r[2]*sc,fr.top+pt+r[3]*sc],
      value:(x.IsChecked?x.IsChecked():x.GetValue()),rtl:x.IsRTL?x.IsRTL():null,align:x.GetAlign?x.GetAlign():null};});
    var a=doc.activeForm;o.active=a?a.GetFullName():'';o.in_form=!!(a&&a.IsInForm&&a.IsInForm());
    o.modified=!!(api.isDocumentModified?api.isDocumentModified():api.isDocumentModify);
    o.fix=typeof (w.AscCommon&&w.AscCommon.xrFieldApTg)==='function';
  }catch(e){o.err=''+e;}return o;})()"""

ACTIVE_JS = r"""(function(){""" + FRAME + r"""try{var a=api.getPDFDoc().activeForm;
  return a?[a.GetFullName(),a.IsChecked?a.IsChecked():a.GetValue(),a.IsInForm?a.IsInForm():'?']:['','',false];}catch(e){return [''+e,'',false];}})()"""

# the field's paragraph direction where the caret is drawn (store NOTES: the caret at the right edge of an Arabic line)
CARET_JS = r"""(function(){""" + FRAME + r"""var o={};
  try{var a=api.getPDFDoc().activeForm,c=a.content,p=c.GetElement(0);o.field=a.GetFullName();o.field_rtl=a.IsRTL();
    o.para_bidi=!!(p.Get_CompiledPr2?p.Get_CompiledPr2(false).ParaPr.Bidi:p.Pr.Bidi);o.align=a.GetAlign?a.GetAlign():null;
    o.at_end=c.IsCursorAtEnd?c.IsCursorAtEnd():'?';}catch(e){o.err=''+e;}return o;})()"""

# the editor's text input path while a field is filled (store NOTES: the date field's first input lost): the input
# helper's own debug log (CTextInput.log), the input events, the font picker's async loads, the API's text entry
INPUT_LOG_JS = r"""(function(){""" + FRAME + r"""if(w.__xrInLog)return 'already';var L=w.__xrInLog=[];
  var ic=w.AscCommon&&w.AscCommon.g_inputContext,FP=w.AscFonts&&w.AscFonts.FontPickerByCharacter;
  function act(){try{var a=api.getPDFDoc().activeForm;return a?a.GetFullName()+'='+a.GetValue():'-';}catch(e){return 'e';}}
  function s(x){try{if(x&&x.type)return 'ev:'+x.type;if(Array.isArray(x))return '['+x.slice(0,12).join(',')+']';
    if(typeof x==='object')return 'obj';return String(x).slice(0,40);}catch(e){return '?';}}
  function push(m){L.push([Math.round(w.performance.now())].concat(m));if(L.length>300)L.shift();}
  function wrap(o,n,tag){var g=o&&o[n];if(typeof g!=='function'||g.__xrw)return;
    o[n]=function(){var a=[].slice.call(arguments),r,err='';try{r=g.apply(this,arguments);}catch(e){err=''+e;throw e;}finally{
      push([tag+'.'+n,a.map(s).join(' '),'ret='+s(r)+err,'area='+(ic&&ic.getAreaValue?JSON.stringify(ic.getAreaValue()):'?'),
        'Text='+JSON.stringify(ic?ic.Text:''),'long='+(api.isLongAction?api.isLongAction():'?'),'ro='+(ic?ic.ReadOnlyCounter:''),act()]);}
      return r;};o[n].__xrw=1;o[n].__xr=g.__xr;}
  if(ic){var lg=ic.log;ic.log=function(v){push(['ic.log',String(v).slice(0,60)]);};
    ['onInput','onKeyDown','onKeyPress','checkTextInput','addTextCodes','clear','compositeEnd'].forEach(function(n){wrap(ic,n,'ic');});}
  ['checkTextLight','loadFonts','checkText'].forEach(function(n){wrap(FP,n,'fp');});
  ['asc_enterText','asc_correctEnterText','asyncFontsDocumentStartLoaded','asyncFontsDocumentEndLoaded'].forEach(function(n){wrap(api,n,'api');});
  var PD=w.AscPDF&&w.AscPDF.CPDFDoc&&w.AscPDF.CPDFDoc.prototype;
  if(PD&&PD.checkFieldFont&&!PD.checkFieldFont.__xrl){var cf=PD.checkFieldFont;PD.checkFieldFont=function(fld,cb){
    var before=(this.loadedFonts||[]).join(',');var r=cf.apply(this,arguments);
    if(r===false)push(['doc.checkFieldFont',fld&&fld.GetFullName?fld.GetFullName():'?','cb='+!!cb,'ret=false','loaded='+before,
      'ranges='+Object.keys((FP&&FP.FontsByRange)||{}).join(',')]);return r;};PD.checkFieldFont.__xrl=1;PD.checkFieldFont.__xr=cf.__xr;}
  return 'ok';})()"""

# the Xrero account card (web/xr-account.js) over an editor or the start page: nothing may be typed while it is up
WALL_JS = r"""(function(){var f=document.querySelector('iframe[name=frameEditor]');var d2=f&&f.contentDocument;
  return !!(document.getElementById('xr-acct-ov')||(d2&&d2.getElementById('xr-acct-ov')));})()"""
# XR_NO_SIGNUP (test-only runs make no account on xrero.com): the stored state of a signed-in user, as ui_test.py writes
# it in its first session. In this second session the start page asks xrero.com about the stored test token again, is
# told it is not a real one and signs out, so the state is written again once that answer is in.
LOCAL_SESSION_JS = r"""new Promise(function(done){try{localStorage.setItem('xr-acct-token','local-ui-test');
  localStorage.setItem('xr-acct',JSON.stringify({locked:false,name:'Mac Store Check',email:'mac-check@example.invalid'}));
  var o=document.getElementById('xr-acct-ov'); if(o) o.parentNode.removeChild(o);}catch(e){done('error: '+e);return;}
  setTimeout(function(){done(document.getElementById('xr-acct-ov')?'card came back':'open');},2500);})"""

# can this editor draw a glyph of the field's (embedded) font as an outline? (the XR-FIELD-AP shim does that on Save)
OUTLINE_PROBE_JS = r"""(function(){""" + FRAME + r"""try{var a=api.getPDFDoc().widgets.filter(function(x){return x.GetFullName()==='client';})[0];
  var nm=a.GetTextFontActual(),tm=w.AscCommon.g_oTextMeasurer;if(tm.m_oLastFont)tm.m_oLastFont.SetUpName='';
  var font=tm.SetFontInternal(nm,14,0),mgr=tm.m_oManager,n={};function c(k){return function(){n[k]=(n[k]||0)+1;};}
  var wk={_s:c('s'),_m:c('m'),_l:c('l'),_c:c('c'),_c2:c('c2'),_z:c('z'),df:c('df'),_e:c('e')};
  var gid=font?font.GetGIDByUnicode(0x0628):-1;var g0=mgr.m_oGlyphString.GetFirstGlyph();g0.fX=0;g0.fY=0;
  mgr.LoadStringPathCode(gid,true,0,0,wk);
  return {font:nm,loaded:!!font,same:mgr.m_pFont===font,gid:gid,calls:n,engine:typeof w.AscFonts.FT_Glyph_Get_Measure};
  }catch(e){return 'error: '+e;}})()"""

# the glyphs the editor shaped for a field, as its Save draws them (CBaseField.WriteRenderToBinary: the field's content
# drawn into a CDocumentRenderer), counted in a throwaway renderer before Save - one per DrawGrapheme glyph (tg). Not
# through XR-FIELD-AP (the renderer is not flagged), so the count does not depend on the fix it checks.
SHAPED_JS = r"""(function(name){""" + FRAME + r"""var o={glyphs:0,nonspace:0,ligatures:0,cps:[]};
  try{var doc=api.getPDFDoc(),v=api.getDocumentRenderer(),f=doc.widgets.filter(function(x){return x.GetFullName()===name;})[0];
    var T=w.AscPDF.PDF_TRIGGERS_TYPES,c=(T&&f.GetTrigger&&f.GetTrigger(T.Format))?f.contentFormat:f.content;
    var mem=new w.AscCommon.CMemory(true);mem.Init(1<<18);
    var dr=v.InitDocRenderer(mem,f.GetPage?f.GetPage():0),tg=dr.tg;
    dr.tg=function(gid,x,y,cps){var a=[].slice.call(cps||[]);o.glyphs++;
      if(a.some(function(u){return u!==32&&u!==0xA0&&u!==9;})){o.nonspace++;if(a.length>1)o.ligatures++;}
      if(o.cps.length<80)o.cps.push(a);return tg.apply(this,arguments);};
    var old=c.transform;c.transform=new w.AscCommon.CMatrix();
    try{dr.ClearCacheProps();c.Draw(c.GetAbsolutePage(),dr);dr.ClearCacheProps();}finally{c.transform=old;}
  }catch(e){o.err=''+e;}return o;})(__NAME__)"""

# the asynchronous rounds: the font loader (doc.fontLoader = AscCommon.g_font_loader) calls back SLOW_MS later, as when the
# font files are still being read; 'off' puts the loader back
SLOW_FONTS_JS = r"""(function(op,ms){""" + FRAME + r"""try{var L=w.AscCommon.g_font_loader;
  if(op==='on'){if(!L.__xrSlowOrig){var o=L.LoadFonts;L.__xrSlowOrig=o;L.LoadFonts=function(fonts,cb){
      w.__xrSlowLoads=(w.__xrSlowLoads||0)+1;
      return o.call(this,fonts,function(){var t=this,a=arguments;setTimeout(function(){if(cb)cb.apply(t,a);},ms);});};}
    return 'slow '+ms+' ms';}
  if(L.__xrSlowOrig){L.LoadFonts=L.__xrSlowOrig;delete L.__xrSlowOrig;}return 'normal';}catch(e){return 'error: '+e;}})(__OP__,__MS__)"""

# the counters of XR-FIELD-FIRST-INPUT (patch_bundle.py MAC_JS) in this editor
FIRST_INPUT_STATE_JS = r"""(function(){""" + FRAME + r"""return {off:!!w.__xrNoFirstInputFix,font_sync:w.__xrFieldFontSync||0,
  held:w.__xrFirstInputHeld||0,retried:w.__xrFirstInputRetried||0,dropped:w.__xrFirstInputDropped||0,slow_loads:w.__xrSlowLoads||0,
  wrapped:!!(w.AscPDF&&w.AscPDF.CPDFDoc&&w.AscPDF.CPDFDoc.prototype.checkFieldFont.__xr),
  entry:!!(api&&api.asc_enterText&&api.asc_enterText.__xr)};})()"""

# a PDF page position (points from the top) scrolled to near the top of the viewer
SCROLL_PDF_JS = r"""(function(y){""" + FRAME + r"""try{var v=api.getDocumentRenderer(),dp=v.drawingPages[0],H=v.file.pages[0].H;
  v.navigateToPage(0,Math.max(0,(y-60)*dp.H/H));return 'ok';}catch(e){return 'error: '+e;}})(__Y__)"""

SLIDE_JS = r"""(function(op){""" + FRAME + r"""var o={};
  try{var wc=api.WordControl,p=wc.m_oLogicDocument;
    if(!w.__xrLangHook){w.__xrLangs=[];api.asc_registerCallback('asc_onTextLanguage',function(v){w.__xrLangs.push(v);});w.__xrLangHook=1;}
    var sp=null;p.Slides[0].cSld.spTree.forEach(function(s){if(!sp&&s.isPlaceholder&&s.isPlaceholder()&&
      [w.AscFormat.phType_ctrTitle,w.AscFormat.phType_title].indexOf(s.getPlaceholderType())>=0)sp=s;});
    if(!sp)return {err:'no title placeholder'};
    if(op==='point'){var xm=sp.x+sp.extX*0.95,ym=sp.y+sp.extY*0.78,dd=wc.m_oDrawingDocument;
      var a=dd.ConvertCoordsToCursor3(xm,ym,false),v=d.getElementById('id_viewer').getBoundingClientRect();
      return {x:fr.left+v.left+a.X,y:fr.top+v.top+a.Y};}
    if(op==='end'){p.MoveCursorToEndPos(false);}
    if(op==='enter'){var cc=p.GetCurrentController();cc.resetSelection();sp.select(cc,0);cc.selection.textSelection=sp;
      sp.getDocContent().MoveCursorToEndPos(false);p.Document_UpdateInterfaceState();}
    var par=sp.txBody.content.Content[0];
    function L(l){return l?[l.Val,l.Bidi,l.EastAsia]:null;}
    o.runs=par.Content.map(function(r){return r.Pr?L(r.Pr.Lang):null;});
    o.end=par.TextPr&&par.TextPr.Value?L(par.TextPr.Value.Lang):null;
    var c=p.GetCurrentController&&p.GetCurrentController(),tc=c&&c.getTargetDocContent&&c.getTargetDocContent();
    o.in_text=!!tc;if(tc){var t=tc.GetCalculatedTextPr();o.calc=t?L(t.Lang):null;}
    o.compiled=par.Content.length?L(par.Content[0].Get_CompiledPr(false).Lang):null;
    o.langs=w.__xrLangs.slice(-6);o.lcid={ae:w.Asc.g_oLcidNameToIdMap['ar-AE'],sa:w.Asc.g_oLcidNameToIdMap['ar-SA']};
  }catch(e){o.err=''+e;}o.statusbar=statusbar();return o;})(__OP__)"""


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
            print("TIMEOUT %s after %ss" % (m, timeout), flush=True)
            return {}

    async def ev(self, expr):
        r = await self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("result", {}).get("value")

    async def key(self, code, name, mods=0, text=None):
        k = name[-1].lower() if name.startswith("Key") else name
        down = {"type": "keyDown" if text else "rawKeyDown", "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code,
                "code": name, "key": k, "modifiers": mods}
        if text:
            down["text"] = text
        await self.call("Input.dispatchKeyEvent", down)
        await self.call("Input.dispatchKeyEvent", {"type": "keyUp", "windowsVirtualKeyCode": code, "code": name, "key": k,
                                                   "modifiers": mods})

    async def click(self, x, y):
        for t in ("mousePressed", "mouseReleased"):
            await self.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1})

    async def shot(self, path, box=None, scale=2):
        p = {"format": "png"}
        if box:
            x0, y0, x1, y1 = box
            p["clip"] = {"x": max(0, x0), "y": max(0, y0), "width": max(1, x1 - x0), "height": max(1, y1 - y0), "scale": scale}
        r = await self.call("Page.captureScreenshot", p)
        data = (r.get("result") or {}).get("data")
        if data:
            open(path, "wb").write(base64.b64decode(data))
            return path
        return None


# ---------------------------------------------------------------- PyMuPDF: the saved file, drawn independently
def _pymupdf():
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    return pymupdf


def ink_mask(pix, thr=140):
    w, h, n, s, st = pix.width, pix.height, pix.n, pix.samples, pix.stride
    rows = []
    for y in range(h):
        b = y * st
        rows.append([((s[b + x * n] * 299 + s[b + x * n + 1] * 587 + s[b + x * n + 2] * 114) // 1000) < thr if n >= 3
                     else s[b + x * n] < thr for x in range(w)])
    return rows


def _crop(m):
    ys = [y for y, r in enumerate(m) if any(r)]
    if not ys:
        return None
    xs = [x for x in range(len(m[0])) if any(m[y][x] for y in ys)]
    return [r[xs[0]:xs[-1] + 1] for r in m[ys[0]:ys[-1] + 1]]


def _dilate(m, k):
    h, w = len(m), len(m[0])
    out = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if m[y][x]:
                for yy in range(max(0, y - k), min(h, y + k + 1)):
                    row = out[yy]
                    for xx in range(max(0, x - k), min(w, x + k + 1)):
                        row[xx] = True
    return out


def ink_match(a, b, k=1):
    """how well two drawings of one line agree: each ink-cropped, b scaled to a's box, the share of each one's ink that
    lies within k px of the other's (mean of both directions). Joined (shaped) Arabic vs its reference ~1.0; the same
    letters drawn separately and overlapping ~0.4-0.65 (calibrated on the Windows store file)."""
    a, b = _crop(a), _crop(b)
    if a is None or b is None:
        return 0.0
    h, w = len(a), len(a[0])
    H, W = len(b), len(b[0])
    b = [[b[min(H - 1, y * H // h)][min(W - 1, x * W // w)] for x in range(w)] for y in range(h)]
    da, db = _dilate(a, k), _dilate(b, k)
    na = sum(v for r in a for v in r) or 1
    nb = sum(v for r in b for v in r) or 1
    pa = sum(1 for y in range(h) for x in range(w) if a[y][x] and db[y][x]) / na
    pb = sum(1 for y in range(h) for x in range(w) if b[y][x] and da[y][x]) / nb
    return round((pa + pb) / 2, 3)


def dr_font(pdf_path, name, out_dir):
    """the font program of /AcroForm/DR/Font/<name> (FontFile2), written to out_dir -> path (or None)"""
    fz = _pymupdf()
    d = fz.open(pdf_path)
    try:
        af = d.xref_get_key(d.pdf_catalog(), "AcroForm/DR/Font/" + name)
        if af[0] != "xref":
            return None
        f = int(af[1].split()[0])
        desc = re.search(r"DescendantFonts \[ ?(\d+)", d.xref_object(f))
        fobj = int(desc.group(1)) if desc else f
        fd = int(re.search(r"FontDescriptor (\d+)", d.xref_object(fobj)).group(1))
        ff = int(re.search(r"FontFile2 (\d+)", d.xref_object(fd)).group(1))
        out = os.path.join(out_dir, "_dr_%s.ttf" % name)
        open(out, "wb").write(d.xref_stream(ff))
        return out
    finally:
        d.close()


def reference_pix(value, fontfile, size, rect, zoom, rtl=True):
    """the value shaped by MuPDF (HarfBuzz) in the same font, in a box of the field's size"""
    fz = _pymupdf()
    d = fz.open()
    pg = d.new_page(width=rect.width + 20, height=rect.height + 30)
    css = "@font-face{font-family:f;src:url(%s)}div{font-family:f}" % os.path.basename(fontfile)
    h = '<div dir="%s" style="font-size:%gpt;color:#000">%s</div>' % ("rtl" if rtl else "ltr", size, value)
    box = fz.Rect(10, 10, 10 + rect.width, 10 + rect.height + 12)
    pg.insert_htmlbox(box, h, css=css, archive=fz.Archive(os.path.dirname(fontfile)), scale_low=1)
    return pg.get_pixmap(matrix=fz.Matrix(zoom, zoom), clip=box)


def glyph_fills(s):
    """the fills of paths that begin with a moveto in a content stream - glyph outlines, not the field's background
    (a 're' rectangle) or its clip (ended by 'n')"""
    s = re.sub(r"\((?:\\.|[^\\)])*\)", " ", s)          # literal and hex strings out
    s = re.sub(r"<[0-9A-Fa-f\s]*>", " ", s)
    n, has_m = 0, False
    for tok in s.split():
        if tok[0] in "/[]<>" or re.match(r"^[-+.\d]", tok):
            continue
        if tok == "m":
            has_m = True
        elif tok in ("f", "f*", "F", "B", "B*", "b", "b*"):
            n += has_m
            has_m = False
        elif tok in ("n", "S", "s"):
            has_m = False
    return n


def ap_summary(d, w):
    """what the field's saved appearance stream draws: text-showing operators, fonts, filled paths, glyph outlines"""
    out = {}
    try:
        m = re.search(r"/N (\d+) 0 R", d.xref_object(w.xref))
        if not m:
            return {"ap": None}
        x = int(m.group(1))
        s = (d.xref_stream(x) or b"").decode("latin1")
        out["text_ops"] = len(re.findall(r"\bT[jJ]\b", s))
        out["fonts"] = sorted(set(re.findall(r"/([A-Za-z0-9_.+-]+) [0-9.]+ Tf", s)))
        out["fills"] = len(re.findall(r"(?m)(?:^|\s)f\*?(?=\s|$)", s))
        out["glyph_fills"] = glyph_fills(s)
        out["bytes"] = len(s)
    except Exception as e:
        out["err"] = repr(e)
    return out


def check_saved_form(path, evid, tag, values, fontfile):
    """values {field: typed value}; -> {field: {value, match, ap}} + PNGs <tag>-<field>-saved.png / -ref.png"""
    fz = _pymupdf()
    d = fz.open(path)
    res = {}
    zoom = 4
    for pg in d:
        for w in pg.widgets():
            if w.field_name not in values:
                continue
            r = {"value": w.field_value, "ap": ap_summary(d, w)}
            pix = pg.get_pixmap(matrix=fz.Matrix(zoom, zoom), clip=w.rect, annots=True)
            pix.save(os.path.join(evid, "%s-%s-saved.png" % (tag, w.field_name)))
            if fontfile and values[w.field_name]:
                is_ar = any("؀" <= c <= "ۿ" for c in values[w.field_name])
                ref = reference_pix(values[w.field_name], fontfile, w.text_fontsize or 14, w.rect, zoom, rtl=is_ar)
                ref.save(os.path.join(evid, "%s-%s-ref.png" % (tag, w.field_name)))
                r["match"] = ink_match(ink_mask(pix), ink_mask(ref), MATCH_K)
            res[w.field_name] = r
    # the whole filled area, for eyes
    try:
        top = min(w.rect.y0 for w in d[0].widgets()) - 50
        bot = max(w.rect.y1 for w in d[0].widgets()) + 10
        d[0].get_pixmap(matrix=fz.Matrix(2, 2), clip=fz.Rect(0, max(0, top), d[0].rect.width, bot), annots=True).save(
            os.path.join(evid, "%s-saved-pymupdf.png" % tag))
    except Exception:
        pass
    d.close()
    return res


# ---------------------------------------------------------------- the app
async def targets(s):
    async with s.get("http://127.0.0.1:%d/json" % PORT) as r:
        return await r.json(content_type=None)


async def open_doc(s, app, path, tag):
    """open <path> the way Finder does -> (target, Page ws context manager args) or None"""
    old = {t["id"] for t in await targets(s)}
    subprocess.run(["open", "-a", app, path])
    for _ in range(60):
        await asyncio.sleep(1)
        new = [t for t in await targets(s) if t["id"] not in old and t.get("type") == "page"]
        eds = [t for t in new if "documents/index.html" in t.get("url", "") or "/apps/" in t.get("url", "")]
        if eds:
            return eds[0]
    return None


async def ready(pg, tag):
    st = None
    for _ in range(60):
        st = await pg.ev(READY_JS.replace("__TAG__", json.dumps(tag)))
        if st == "ok":
            return st
        await asyncio.sleep(1)
    return st


async def wait_active(pg, name, tries=20):
    st = None
    for _ in range(tries):
        await asyncio.sleep(0.4)
        st = await pg.ev(ACTIVE_JS) or ["", "", False]
        if st[0] == name and st[2] is True:
            return st
    return st


async def save(pg, path):
    m0 = os.stat(path).st_mtime
    await pg.key(83, "KeyS", 4)                       # Cmd+S
    for _ in range(30):
        await asyncio.sleep(1)
        if os.stat(path).st_mtime > m0:
            break
    await asyncio.sleep(3)
    return os.stat(path).st_mtime > m0


def box_of(px_list, pad=12):
    return [min(p[0] for p in px_list) - pad, min(p[1] for p in px_list) - pad,
            max(p[2] for p in px_list) + pad, max(p[3] for p in px_list) + pad]


async def case_pdf_ar_field(s, app, evid, variant, ok, out):
    """fill ar_form_embedded.pdf (Arabic + Latin in the embedded-font fields, Arabic in the Helvetica one), save,
    read the file, open a copy again in the app. variant 'control' = the Mac fix off for this document"""
    src = os.path.join(ROOT, "test", "inputs", "ar_form_embedded.pdf")
    path = os.path.join(evid, "ar-form-%s.pdf" % variant)
    shutil.copy(src, path)
    r = {"variant": variant}
    t = await open_doc(s, app, path, "pdf")
    if not t:
        r["err"] = "the form did not open"
        return r
    await asyncio.sleep(6)
    async with s.ws_connect(t["webSocketDebuggerUrl"], max_msg_size=0) as ws:
        pg = Page(ws)
        r["ready"] = await ready(pg, "pdf")
        r["wall"] = await pg.ev(WALL_JS)
        if r["wall"] is not False:
            return r
        g = await pg.ev(PDF_GEOM_JS) or {}
        r["fix_present"] = g.get("fix")
        fields = g.get("fields") or {}
        typed = {}
        for name, val in (("client", AR_CLIENT), ("ref", LATIN_REF), ("office", AR_OFFICE)):
            px = (fields.get(name) or {}).get("px")
            if not px:
                r.setdefault("missing", []).append(name)
                continue
            await pg.click((px[0] + px[2]) / 2, (px[1] + px[3]) / 2)
            st = await wait_active(pg, name)
            if not (st and st[0] == name and st[2] is True):           # never type anywhere but into this field
                r.setdefault("not_active", []).append([name, st])
                continue
            await asyncio.sleep(0.6)
            if await pg.ev(WALL_JS) is not False:                      # never into the account card
                r["wall_before_typing"] = name
                return r
            await pg.call("Input.insertText", {"text": val})
            await asyncio.sleep(1.2)
            got = (await pg.ev(ACTIVE_JS) or ["", ""])[1]
            typed[name] = got
            if name == "client":
                r["caret"] = await pg.ev(CARET_JS)
                r["outline_probe"] = await pg.ev(OUTLINE_PROBE_JS)      # (after typing: the field's font is loaded)
                await pg.shot(os.path.join(evid, "pdf-%s-live-typing.png" % variant), box_of([px], 30))
        r["typed"] = typed
        # the glyphs the editor shaped for the Arabic value (drawn as its Save draws them), before Save
        r["shaped"] = await pg.ev(SHAPED_JS.replace("__NAME__", json.dumps("client")))
        g = await pg.ev(PDF_GEOM_JS) or {}
        fbox = box_of([v["px"] for v in (g.get("fields") or {}).values()], 40)
        await pg.shot(os.path.join(evid, "pdf-%s-live.png" % variant), fbox)
        r["saved"] = await save(pg, path)
        r["modified_after_save"] = (await pg.ev(PDF_GEOM_JS) or {}).get("modified")
        r["shim"] = await pg.ev("(function(){" + FRAME + "return w.__xrFieldApDbg||null;})()")
    # the saved file, read and drawn by PyMuPDF
    font = dr_font(src, "PlexAr", evid)
    try:
        r["file"] = check_saved_form(path, evid, "pdf-%s" % variant, {"client": AR_CLIENT, "ref": LATIN_REF}, font)
        r["file_office"] = check_saved_form(path, evid, "pdf-%s-office" % variant, {"office": ""}, None).get("office")
    except Exception as e:
        r["file_err"] = repr(e)
    # a copy opened again in the app (drawn from the saved appearance until it is edited)
    again = os.path.join(evid, "ar-form-%s-reopened.pdf" % variant)
    shutil.copy(path, again)
    t = await open_doc(s, app, again, "pdf")
    if t:
        await asyncio.sleep(6)
        async with s.ws_connect(t["webSocketDebuggerUrl"], max_msg_size=0) as ws:
            pg = Page(ws)
            r["reopen_ready"] = await ready(pg, "pdf")
            await asyncio.sleep(2)
            g = await pg.ev(PDF_GEOM_JS) or {}
            r["reopen_values"] = {k: v.get("value") for k, v in (g.get("fields") or {}).items()}
            if g.get("fields"):
                await pg.shot(os.path.join(evid, "pdf-%s-reopened-in-app.png" % variant),
                              box_of([v["px"] for v in g["fields"].values()], 40))
    else:
        r["reopen_err"] = "the copy did not open"
    return r


async def case_pdf_first_input(s, app, evid, out, variant="fixed"):
    """mas/store_demo_form_ar.pdf, filled like store_capture.py does it (Tab to each field, type each value): the date
    field must get its first input.
      'control' / 'fixed'               the date typed as one piece; the font load as the app does it
      'async_control' / 'async'         the field's font load made truly asynchronous (SLOW_FONTS_JS, callback SLOW_MS
                                        later) just before the date, which is then typed key by key KEY_GAP_MS apart
    '*control' = the Mac fix off in this editor (window.__xrNoFirstInputFix: the original path - it must still show the
    fault, so the checks can tell 'fixed' from 'no fault to fix')"""
    src = os.path.join(ROOT, "mas", "store_demo_form_ar.pdf")
    path = os.path.join(evid, "ar-booking-%s.pdf" % variant)
    shutil.copy(src, path)
    r = {"variant": variant}
    is_async = variant.startswith("async")
    t = await open_doc(s, app, path, "pdf")
    if not t:
        r["err"] = "the form did not open"
        return r
    await asyncio.sleep(6)
    async with s.ws_connect(t["webSocketDebuggerUrl"], max_msg_size=0) as ws:
        pg = Page(ws)
        r["ready"] = await ready(pg, "pdf")
        r["wall"] = await pg.ev(WALL_JS)
        if r["wall"] is not False:
            return r
        if variant.endswith("control"):
            r["switch_off"] = await pg.ev("(function(){" + FRAME + "w.__xrNoFirstInputFix=true;return true;})()")
        r["fix_present"] = await pg.ev(FIRST_INPUT_STATE_JS)
        r["log_installed"] = await pg.ev(INPUT_LOG_JS)
        g = await pg.ev(PDF_GEOM_JS) or {}
        org, sc = g.get("org") or [0, 0], g.get("sc") or 1
        await pg.click(org[0] + 24 * sc, org[1] + 118 * sc)        # on the page beside the form (store_capture focus)
        await asyncio.sleep(1.5)
        steps = []
        for name, v in (("department", "المشاريع"), ("office", "الشارقة"), ("date", DATE)):
            await pg.key(9, "Tab")
            st = await wait_active(pg, name)
            if not (st and st[0] == name and st[2] is True):           # never type anywhere but into this field
                steps.append([name, "not active", st])
                break
            await asyncio.sleep(0.8)
            if await pg.ev(WALL_JS) is not False:                      # never into the account card
                steps.append([name, "account card up"])
                break
            if name == "date" and is_async:
                r["slow"] = await pg.ev(SLOW_FONTS_JS.replace("__OP__", json.dumps("on")).replace("__MS__", str(SLOW_MS)))
                for ch in v:                                   # key by key, quickly (no wait for the fonts)
                    await pg.call("Input.insertText", {"text": ch})
                    await asyncio.sleep(KEY_GAP_MS / 1000.0)
                await asyncio.sleep(SLOW_MS / 1000.0 + 2.0)
                r["slow_off"] = await pg.ev(SLOW_FONTS_JS.replace("__OP__", json.dumps("off")).replace("__MS__", "0"))
            else:
                await pg.call("Input.insertText", {"text": v})
                await asyncio.sleep(1.5)
            got = (await pg.ev(ACTIVE_JS) or ["", ""])[1]
            steps.append([name, v, got, st])
            if name == "date":
                r["date_first"] = got
                r["state"] = await pg.ev(FIRST_INPUT_STATE_JS)
                if got != v:                                   # as a user would: type it again over what is there
                    if await pg.ev(WALL_JS) is not False:      # never into the account card (owner rule, run 39)
                        steps.append(["date again", "account card up"])
                        break
                    st2 = await wait_active(pg, name)
                    if not (st2 and st2[0] == name and st2[2] is True):
                        steps.append(["date again", "not active", st2])
                        break
                    await pg.ev("(function(){" + FRAME + "try{var a=api.getPDFDoc().activeForm;a.content.SelectAll();"
                                "return 'ok';}catch(e){return ''+e;}})()")
                    await pg.call("Input.insertText", {"text": v})
                    await asyncio.sleep(1.2)
                    steps.append(["date again", v, (await pg.ev(ACTIVE_JS) or ["", ""])[1]])
        r["steps"] = steps
        r["input_log"] = await pg.ev("(function(){" + FRAME + "return (w.__xrInLog||[]).slice(-160);})()")
        r["field_font_log"] = [x for x in (r["input_log"] or []) if isinstance(x, list) and len(x) > 1
                               and x[1] == "doc.checkFieldFont"][-6:]
        r["retried"] = (r.get("state") or {}).get("retried")
        await pg.shot(os.path.join(evid, "pdf-first-input-%s.png" % variant))
        r["saved"] = await save(pg, path)
    return r


LAMALEF_NOTE = ("record only (store NOTES 'bold lam-alef', NOT fixed: the Mac app's native page renderer): each line is "
                "scrolled into view, then captured; ink_match cannot see one broken ligature (run 42: 0.979 on the "
                "visibly broken heading) - the PNGs are the evidence")


async def scroll_to(pg, y_top):
    """the PDF page scrolled so that y_top (points from the page top) is near the top of the viewer -> fresh geometry"""
    st = await pg.ev(SCROLL_PDF_JS.replace("__Y__", "%.2f" % y_top))
    await asyncio.sleep(1.5)
    return st, (await pg.ev(PDF_GEOM_JS) or {})


def box_in_view(box, view):
    return bool(view) and box[0] >= view[0] - 1 and box[1] >= view[1] - 1 and box[2] <= view[2] + 1 and box[3] <= view[3] + 1


async def capture_line(pg, fz, d, rc, app_png, mu_png, dpr, shot_scale):
    """one line (rc: PDF rect, points) as the app draws it, after scrolling it into view, and as MuPDF draws it"""
    st, g = await scroll_to(pg, rc.y0)
    org, sc = g.get("org") or [0, 0], g.get("sc") or 1
    box = [org[0] + rc.x0 * sc, org[1] + rc.y0 * sc, org[0] + rc.x1 * sc, org[1] + rc.y1 * sc]
    rec = {"scroll": st, "in_view": box_in_view(box, g.get("view")), "box": [round(v) for v in box], "view": g.get("view")}
    await pg.shot(app_png, box, scale=shot_scale)
    d[0].get_pixmap(matrix=fz.Matrix(sc * dpr, sc * dpr), clip=rc).save(mu_png)
    if rec["in_view"]:
        try:
            rec["ink_match"] = ink_match(ink_mask(fz.Pixmap(app_png)), ink_mask(fz.Pixmap(mu_png)), 2)
        except Exception as e:
            rec["ink_match"] = repr(e)
    return rec


async def case_pdf_lamalef(s, app, evid, out):
    """ar_bold_lamalef.pdf and the run-27 form's bold headings: each line as the app draws it (its page canvas, the line
    scrolled into view first) and as MuPDF draws it. Record only (LAMALEF_NOTE)."""
    fz = _pymupdf()
    src = os.path.join(ROOT, "test", "inputs", "ar_bold_lamalef.pdf")
    path = os.path.join(evid, "ar-bold-lamalef.pdf")
    shutil.copy(src, path)
    r = {"note": LAMALEF_NOTE}
    t = await open_doc(s, app, path, "pdf")
    if not t:
        return {"err": "did not open"}
    await asyncio.sleep(6)
    async with s.ws_connect(t["webSocketDebuggerUrl"], max_msg_size=0) as ws:
        pg = Page(ws)
        r["ready"] = await ready(pg, "pdf")
        await asyncio.sleep(3)
        r["wall"] = await pg.ev(WALL_JS)
        d = fz.open(path)
        W = d[0].rect.width
        for i, name in enumerate(("bold", "regular", "bold_nohint")):
            y0, y1 = 40 + 70 * i, 90 + 70 * i                     # make_engine_inputs.py LAMALEF_Y
            r[name] = await capture_line(pg, fz, d, fz.Rect(50, y0, W - 50, y1),
                                         os.path.join(evid, "lamalef-%s-app.png" % name),
                                         os.path.join(evid, "lamalef-%s-mupdf.png" % name), 2, 2)
        d.close()
        r["engine"] = await pg.ev("(function(){" + FRAME + "try{return typeof w.g_native_drawing_file+'/'+"
                                  "typeof (w.AscViewer&&w.AscViewer.CDrawingFile);}catch(e){return ''+e;}})()")
    # the store form of run 27 (mas/store_demo_form_ar.pdf at a81a224, kept as test/inputs/ar_form_bold_heading.pdf):
    # its 12.5 pt bold headings "ملاحظات" / "للاستخدام الإداري", drawn by the app at device scale 1 and 2 (run 27's
    # picture was the device-scale-2 page: "مادحظات"); each heading is scrolled into view before it is captured (runs 42
    # and 43 captured the second one out of view: an empty box)
    src2 = os.path.join(ROOT, "test", "inputs", "ar_form_bold_heading.pdf")
    path2 = os.path.join(evid, "ar-form-bold-heading.pdf")
    shutil.copy(src2, path2)
    t = await open_doc(s, app, path2, "pdf")
    if t:
        await asyncio.sleep(6)
        async with s.ws_connect(t["webSocketDebuggerUrl"], max_msg_size=0) as ws:
            pg = Page(ws)
            r["form_ready"] = await ready(pg, "pdf")
            await asyncio.sleep(3)
            d = fz.open(path2)
            heads = []
            for b in d[0].get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    for sp in ln["spans"]:
                        if "Bol" in sp["font"] and any(c in sp["text"] for c in "ﻻﻼﻵﻶﻷﻸﻹﻺ"):
                            heads.append(fz.Rect(sp["bbox"]) + (-3, -2, 3, 2))
            r["headings"] = len(heads)
            for scale in (1, 2):
                vw = await pg.ev("[innerWidth, innerHeight]") or [1200, 800]
                if scale == 2:
                    await pg.call("Emulation.setDeviceMetricsOverride", {"width": vw[0], "height": vw[1],
                                                                         "deviceScaleFactor": 2, "mobile": False})
                    await asyncio.sleep(4)
                for i, rc in enumerate(heads):
                    r["heading_%d_dpr%d" % (i, scale)] = await capture_line(
                        pg, fz, d, rc, os.path.join(evid, "bold-heading-%d-dpr%d-app.png" % (i, scale)),
                        os.path.join(evid, "bold-heading-%d-dpr%d-mupdf.png" % (i, scale)), scale, 1)
                if scale == 2:
                    await pg.call("Emulation.clearDeviceMetricsOverride")
                    await asyncio.sleep(2)
            d.close()
    return r


async def case_pptx_lang(s, app, evid, out):
    src = os.path.join(ROOT, "mas", "store_demo_slides_ar.pptx")
    path = os.path.join(evid, "ar-slides.pptx")
    shutil.copy(src, path)
    r = {}
    t = await open_doc(s, app, path, "slide")
    if not t:
        return {"err": "did not open"}
    await asyncio.sleep(6)
    async with s.ws_connect(t["webSocketDebuggerUrl"], max_msg_size=0) as ws:
        pg = Page(ws)
        r["ready"] = await ready(pg, "slide")
        await asyncio.sleep(2)
        r["wall"] = await pg.ev(WALL_JS)
        if r["wall"] is not False:
            return r
        pt = await pg.ev(SLIDE_JS.replace("__OP__", json.dumps("point"))) or {}
        r["point"] = pt
        if "x" in pt:
            await pg.click(pt["x"], pt["y"])
            await asyncio.sleep(1.5)
        r["after_click"] = await pg.ev(SLIDE_JS.replace("__OP__", json.dumps("read")))
        if (r["after_click"] or {}).get("in_text"):
            r["at_end"] = await pg.ev(SLIDE_JS.replace("__OP__", json.dumps("end")))
        else:                                   # (the click selected the shape only: the caret put in its text)
            r["entered"] = await pg.ev(SLIDE_JS.replace("__OP__", json.dumps("enter")))
        await asyncio.sleep(1.5)
        r["state"] = await pg.ev(SLIDE_JS.replace("__OP__", json.dumps("read")))
        await pg.shot(os.path.join(evid, "pptx-lang.png"))
    return r


async def run(exe, app, arch, out_dir, ok):
    """a second app session: the cases above; ok(name, cond, detail) records a check of the UI test"""
    evid = os.path.join(out_dir, "engine-%s" % arch)
    os.makedirs(evid, exist_ok=True)
    out = {}
    cmd = (["arch", "-x86_64"] if arch == "x86_64" else []) + [exe, "--remote-debugging-port=%d" % PORT]
    proc = subprocess.Popen(cmd, stdout=open(os.path.join(evid, "app.log"), "w"), stderr=subprocess.STDOUT)
    try:
        async with aiohttp.ClientSession() as s:
            start = None
            for _ in range(90):
                await asyncio.sleep(1)
                try:
                    ts = await targets(s)
                except Exception:
                    continue
                start = next((t for t in ts if t.get("type") == "page" and "/apps/" not in t.get("url", "")
                              and "documents/" not in t.get("url", "")), None)
                if start:
                    break
            ok("engine_session_starts", start is not None, (start or {}).get("url", "")[-80:])
            if not start:
                return out
            await asyncio.sleep(8)
            if os.environ.get("XR_NO_SIGNUP"):
                async with s.ws_connect(start["webSocketDebuggerUrl"], max_msg_size=0) as ws:
                    sp = Page(ws)
                    for _ in range(3):
                        out["local_session"] = await sp.ev(LOCAL_SESSION_JS)
                        if out["local_session"] == "open":
                            break
                        await asyncio.sleep(4)
            else:
                out["local_session"] = "real account (signed in by the first session)"
            def first_input(variant):
                return lambda *a: case_pdf_first_input(*a, variant=variant)
            for name, fn in (("pdf_first_input_control", first_input("control")), ("pdf_first_input", first_input("fixed")),
                             ("pdf_first_input_async_control", first_input("async_control")),
                             ("pdf_first_input_async", first_input("async")),
                             ("pdf_lamalef", case_pdf_lamalef), ("pptx_lang", case_pptx_lang)):
                try:
                    out[name] = await fn(s, app, evid, out)
                except Exception as e:
                    out[name] = {"err": "%s: %s" % (type(e).__name__, e)}
                print("[engine]", name, json.dumps(out[name], ensure_ascii=False)[:1500], flush=True)
            # (the reproduction without the fix: build-mac runs 39-42, the same check at ink match 0.44 - since the saved
            # appearance is drawn by the converter's sdkjs, there is no switch in the editor for a control round here)
            for variant in ("fixed",):
                try:
                    out["pdf_ar_field_" + variant] = await case_pdf_ar_field(s, app, evid, variant, ok, out)
                except Exception as e:
                    out["pdf_ar_field_" + variant] = {"err": "%s: %s" % (type(e).__name__, e)}
                print("[engine] pdf_ar_field", variant, json.dumps(out["pdf_ar_field_" + variant], ensure_ascii=False)[:1500], flush=True)
    finally:
        json.dump(out, open(os.path.join(evid, "engine-%s.json" % arch), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        try:
            subprocess.run(["osascript", "-e", 'quit app "Xrero Office"'], timeout=30)
        except Exception:
            pass
        for _ in range(20):
            if proc.poll() is not None:
                break
            await asyncio.sleep(1)
        if proc.poll() is None:
            proc.kill()

    # ---- the checks
    fx = out.get("pdf_ar_field_fixed") or {}
    ff = fx.get("file") or {}
    xm = (ff.get("client") or {}).get("match")
    ok("pdf_ar_field_typed", (fx.get("typed") or {}).get("client") == AR_CLIENT, repr(fx.get("typed")))
    ok("pdf_ar_field_saved_value", fx.get("saved") and (ff.get("client") or {}).get("value") == AR_CLIENT
       and (ff.get("ref") or {}).get("value") == LATIN_REF, "saved=%s %s" % (fx.get("saved"), {k: v.get("value") for k, v in ff.items()}))
    ok("pdf_ar_field_saved_shaped", isinstance(xm, float) and xm >= MATCH_OK,
       "ink match with the same text shaped in the same font %s (>= %s; without the fix, runs 39-42: 0.44 at 1 px / 0.60 at"
       " 2 px); appearance %s" % (xm, MATCH_OK, (ff.get("client") or {}).get("ap")))
    lm = (ff.get("ref") or {}).get("match")
    ok("pdf_latin_field_saved_ok", isinstance(lm, float) and lm >= MATCH_OK and ((ff.get("ref") or {}).get("ap") or {}).get("text_ops", 0) > 0,
       "Latin in the embedded font: match %s, still text: %s" % (lm, (ff.get("ref") or {}).get("ap")))
    ok("pdf_ar_field_reopened", (fx.get("reopen_values") or {}).get("client") == AR_CLIENT
       and (fx.get("reopen_values") or {}).get("ref") == LATIN_REF, repr(fx.get("reopen_values")))
    # one outline per glyph: every non-space glyph the editor shaped for the Arabic value (lam-alef ligatures included)
    # is one filled outline in the saved appearance - a glyph left as (unshaped) text or dropped would differ
    sh = fx.get("shaped") or {}
    cap = (ff.get("client") or {}).get("ap") or {}
    letters = len([c for c in AR_CLIENT if not c.isspace()])
    ok("pdf_ar_field_glyphs_outlined", isinstance(sh.get("nonspace"), int) and sh["nonspace"] > 0
       and cap.get("glyph_fills") == sh["nonspace"] and cap.get("text_ops") == 0
       and (sh.get("ligatures", 0) >= 2 or sh["nonspace"] <= letters - 2),
       "saved appearance: %s outline fills, %s text operators; the editor shaped %s non-space glyphs (%s with 2+ code "
       "points, from %d letters: lam-alef ligatures formed) %s"
       % (cap.get("glyph_fills"), cap.get("text_ops"), sh.get("nonspace"), sh.get("ligatures"), letters,
          sh.get("err") or ""))
    walls = [k for k, v in out.items() if isinstance(v, dict) and (v.get("wall") is not False or v.get("wall_before_typing")
             or any(isinstance(x, list) and x[1:2] == ["account card up"] for x in (v.get("steps") or [])))]
    ok("engine_no_account_card", not walls, "account card over: %s (session: %r)" % (walls, out.get("local_session")))

    # the first input of the date field: each fixed round must keep it, each control round (the same editor, the fix
    # switched off) must still lose it - so 'kept' means 'fixed', not 'no fault to fix this time'
    def fi_detail(r):
        return "date %r; %s; checkFieldFont refused: %s" % (
            r.get("date_first"), json.dumps(r.get("state"), ensure_ascii=False),
            json.dumps(r.get("field_font_log"), ensure_ascii=False)[:400])
    fi, fc = out.get("pdf_first_input") or {}, out.get("pdf_first_input_control") or {}
    fa, fac = out.get("pdf_first_input_async") or {}, out.get("pdf_first_input_async_control") or {}
    st, sa = fi.get("state") or {}, fa.get("state") or {}
    ok("pdf_first_input_control_lost", fc.get("date_first") not in (None, DATE) and (fc.get("state") or {}).get("off"),
       "WITHOUT the Mac fix the fault must still show (one input of %s): %s" % (DATE, fi_detail(fc)))
    ok("pdf_first_input_kept", fi.get("date_first") == DATE and not st.get("off")
       and (st.get("font_sync", 0) + st.get("held", 0)) >= 1 and st.get("dropped", 0) == 0,
       "with the Mac fix (the fix must have acted: font_sync or held >= 1): %s" % fi_detail(fi))
    ok("pdf_first_input_async_control_lost", fac.get("date_first") not in (None, DATE) and (fac.get("state") or {}).get("off")
       and (fac.get("state") or {}).get("slow_loads", 0) >= 1,
       "WITHOUT the Mac fix, font load %d ms late, typed key by key: the fault must still show: %s" % (SLOW_MS, fi_detail(fac)))
    ok("pdf_first_input_async_order", fa.get("date_first") == DATE and not sa.get("off") and sa.get("slow_loads", 0) >= 1
       and sa.get("held", 0) >= 2 and sa.get("retried") == sa.get("held") and sa.get("dropped", 0) == 0,
       "with the Mac fix, font load %d ms late, %d keys %d ms apart: every key held back while the fonts load "
       "(held >= 2) must arrive, in order: %s" % (SLOW_MS, len(DATE), KEY_GAP_MS, fi_detail(fa)))
    pl = out.get("pptx_lang") or {}
    langs = ((pl.get("state") or {}).get("langs") or [])
    ae = ((pl.get("state") or {}).get("lcid") or {}).get("ae")
    ok("pptx_ar_ae_language", bool(langs) and ae is not None and langs[-1] == ae,
       "reported %s, ar-AE = %s, state %s" % (langs, ae, json.dumps(pl.get("state"), ensure_ascii=False)[:300]))
    return out
