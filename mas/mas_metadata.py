#!/usr/bin/env python3
"""mas_metadata.py - fills the macOS App Store version of Xrero Office (App Store Connect API key from the secrets):
store text (en-US, ar-SA: description, promotional text, keywords, What's New, URLs), Mac screenshots (APP_DESKTOP,
mas/store/*.png), App Review contact + Mac notes (the demo account entry is kept as it is), release type AFTER_APPROVAL,
and the newest processed macOS build OF THIS VERSION. It does NOT submit for review.
21.0 (18 Nov 2026): decision D - no open-source / AGPL / source-code wording and no offline or no-account claim in the
store text; everything is pinned here (nothing is copied from the iOS version any more).
Env: ASC_KEY, ASC_KEY_ID, ASC_ISSUER; V = the macOS version to fill (default VERSION below)."""
import hashlib, json, os, sys, time, urllib.error, urllib.request

import jwt

APP_ID = "6819063639"
VERSION = os.environ.get("V") or "21.0"
API = "https://api.appstoreconnect.apple.com"
ROOT = os.path.dirname(os.path.abspath(__file__))

# What's New in 21.0 (18 Nov 2026): only what changed on the Mac since 20.2 - the editors now come from Windows 21.0
# (payload-21.0; diff vs payload-20.0.9 in the payload-21.0 release). Not listed because 20.2 already had them on the
# Mac: Arabic in PDF form fields saved shaped, first form input kept, check box ticked with Enter, ar-AE in slides.
WHATS_NEW_EN = """What's new in Xrero Office 21.0:
- Fixed: comments saved in a PDF were dated 1969. They now keep the date they were added.
- Fixed: an editor could sometimes fail to open.
- Arabic interface: hundreds more labels are now in Arabic, and some were reworded."""
WHATS_NEW_AR = """الجديد في إكسريرو أوفيس 21.0:
- إصلاح تاريخ التعليقات في ملفات PDF: كانت تُحفظ بتاريخ 1969، وأصبحت تحتفظ بتاريخ إضافتها.
- إصلاح مشكلة كانت تمنع أحد المحررات من الفتح أحيانًا.
- الواجهة العربية: تعريب مئات التسميات الإضافية وتحسين صياغة بعضها."""

TEXT = {
    "en-US": {
        "description": """Xrero Office is a free office suite for documents, spreadsheets and presentations - built Arabic-first, with editing that runs on your Mac.

OPEN AND EDIT THE FILES YOU ALREADY HAVE
- Documents (.docx), spreadsheets (.xlsx) and presentations (.pptx), plus PDF viewing, form filling and comments
- Open from Finder, iCloud Drive, Downloads or email attachments
- Save in the same format, ready to share with colleagues using other office apps

REAL ARABIC SUPPORT
- Right-to-left paragraphs, tables and slides that look right
- Arabic and English typing in the same document

A FULL EDITOR, NOT A VIEWER
- Text styles, headings, lists, tables, images, colors and page layout
- Formulas, cell formatting and multiple sheets
- Slides with layouts, themes and transitions
- Tabs: several documents open in one window

PRIVATE BY DESIGN
- Your files stay on your Mac, with no tracking
- Sign in with a free Xrero account

Xrero Office is based on ONLYOFFICE Desktop Editors.""",
        "promotionalText": "Free and Arabic-first: Documents, Spreadsheets, Presentations and PDF in one app. Open, edit and save Office files on your Mac.",
        "keywords": "docx,xlsx,pptx,office,arabic,editor,documents,spreadsheet,presentation,pdf,rtl,writer",
        "whatsNew": WHATS_NEW_EN,
        "supportUrl": "https://xrero.com/office/support",
        "marketingUrl": "https://xrero.com/office",
    },
    "ar-SA": {
        "description": """إكسريرو أوفيس حزمة مكتبية مجانية للمستندات والجداول والعروض التقديمية، مصممة للعربية أولاً، والتحرير يتم على جهاز Mac نفسه.

افتح ملفاتك وعدّلها
- المستندات (.docx) والجداول (.xlsx) والعروض التقديمية (.pptx)، وعرض ملفات PDF وتعبئة نماذجها والتعليق عليها
- افتح من Finder أو iCloud Drive أو التنزيلات أو مرفقات البريد
- احفظ بنفس الصيغة لتشاركها مع زملائك الذين يستخدمون برامج مكتبية أخرى

دعم حقيقي للعربية
- فقرات وجداول وشرائح من اليمين إلى اليسار تظهر بشكل صحيح
- اكتب بالعربية والإنجليزية في نفس المستند

محرر كامل وليس مجرد عارض
- أنماط النصوص والعناوين والقوائم والجداول والصور والألوان وتخطيط الصفحة
- الصيغ وتنسيق الخلايا وأوراق العمل المتعددة
- شرائح بتخطيطات وسمات وانتقالات
- تبويبات: عدة مستندات مفتوحة في نافذة واحدة

الخصوصية أولاً
- ملفاتك تبقى على جهازك، وبلا تتبّع
- سجّل الدخول بحساب Xrero مجاني

إكسريرو أوفيس مبني على ONLYOFFICE Desktop Editors.""",
        "promotionalText": "مجاني ومصمم للعربية أولاً: المستندات والجداول والعروض وملفات PDF في تطبيق واحد. افتح ملفات أوفيس وعدّلها واحفظها على جهاز Mac.",
        "keywords": "docx,xlsx,pptx,pdf,أوفيس,مستندات,جداول,عروض,محرر,عربي,مكتب",
        "whatsNew": WHATS_NEW_AR,
        "supportUrl": "https://xrero.com/office/support",
        "marketingUrl": "https://xrero.com/office",
    },
}
# the listing's order (16 Nov 2026 review): the Arabic + English document first (the app's point, and the picture search
# results show), then spreadsheet + chart, presentation, PDF form + annotations, and the start page last (round 4: as
# the second picture the start page - a file list and four cards - was the set's weakest; its line still carries the
# account, beside the account pill)
SHOTS = {"en-US": ["mac_en_editor.png", "mac_en_sheet.png", "mac_en_slides.png", "mac_en_pdf.png", "mac_en_start.png"],
         "ar-SA": ["mac_ar_editor.png", "mac_ar_sheet.png", "mac_ar_slides.png", "mac_ar_pdf.png", "mac_ar_start.png"]}

NOTES = """XRERO OFFICE FOR MAC - APP REVIEW INFORMATION

PURPOSE AND AUDIENCE
Xrero Office is a free office suite (documents, spreadsheets, presentations) for Mac, iPhone and iPad. It is made for Arabic-speaking users, mainly in the United Arab Emirates and the Gulf, and for anyone who needs to open, edit and save Microsoft Office files (.docx, .xlsx, .pptx) with correct right-to-left Arabic. A free Xrero account is required (the same account as Xrero Office for Windows and iPhone); no subscription, no in-app purchases.

SIGN-IN (demo account in the App Review fields)
1. Launch the app: the Xrero account card opens. Sign in with the demo account, or create a new account in the app (Create account tab: name, email, password).
2. The account can be deleted inside the app: click the account name (top corner of the start page) > Delete account. The privacy policy is linked on the card.

HOW TO USE
1. The start page shows the four apps as cards: Document, Spreadsheet, Presentation and PDF.
2. Click a card to create a file, or Open local file / drag a .docx, .xlsx, .pptx or .pdf file onto the window.
3. Edit with the toolbar (bold, fonts, alignment, right-to-left paragraphs, tables, formulas, slides) and save with Command-S. Each document opens in a tab.
Sample files: https://github.com/xrero01/xrero-office-ios/tree/main/store/samples

THIS MAC VERSION
The Mac app is the ONLYOFFICE Desktop Editors 9.4.0 app (AGPL-3.0) with the Xrero interface, sandboxed for the Mac App Store. It has no self-updater (updates come only from the App Store). Apple silicon Macs, macOS 12 or later.

EXTERNAL SERVICES
Sign-in uses xrero.com (https://xrero.com/office/api, email and password only, no third-party sign-in). Editing and file conversion run on the Mac. Optional features contact a service only when the user chooses to: connecting the app to the user's own document server (ownCloud, Nextcloud) from the start page, and editor plugins that the user opens (for example an AI assistant plugin, which works only with the user's own provider key). There is no analytics, advertising or tracking.

REGIONAL DIFFERENCES
None. The app works the same in all regions; the interface is available in English and Arabic.

REGULATED INDUSTRY / THIRD-PARTY MATERIAL
Not a regulated industry. Built on open-source software it is licensed to redistribute (ONLYOFFICE Desktop Editors, AGPL-3.0, Ascensio System SIA). The complete source of this build is published at https://github.com/xrero01/xrero-office-mac as the AGPL requires."""


def token():
    now = int(time.time())
    return jwt.encode({"iss": os.environ["ASC_ISSUER"], "iat": now, "exp": now + 1100, "aud": "appstoreconnect-v1"},
                      os.environ["ASC_KEY"], algorithm="ES256", headers={"kid": os.environ["ASC_KEY_ID"], "typ": "JWT"})


def call(method, path, body=None):
    url = path if path.startswith("http") else API + path
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit("ASC %s %s -> %s %s" % (method, path, e.code, e.read().decode(errors="replace")[:1500]))


EDITABLE = ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED", "INVALID_BINARY")


def versions():
    """(macOS version VERSION, the newest macOS version before it) - the one to fill must still be editable"""
    vs = [v for v in call("GET", "/v1/apps/%s/appStoreVersions?filter[platform]=MAC_OS&limit=20" % APP_ID)["data"]
          if v["attributes"]["platform"] == "MAC_OS"]
    mac = [v for v in vs if v["attributes"]["versionString"] == VERSION]
    if not mac:
        raise SystemExit("no macOS version %s - run build-mas first (asc_mas.py macos-version makes it)" % VERSION)
    mac = mac[0]
    if mac["attributes"]["appStoreState"] not in EDITABLE:
        raise SystemExit("macOS %s is %s - not editable, nothing changed" % (VERSION, mac["attributes"]["appStoreState"]))
    prev = sorted([v for v in vs if v["id"] != mac["id"]], key=lambda v: v["attributes"].get("createdDate") or "")
    return mac, (prev[-1] if prev else None)


def localizations(mac):
    have = {l["attributes"]["locale"]: l for l in
            call("GET", "/v1/appStoreVersions/%s/appStoreVersionLocalizations" % mac["id"])["data"]}
    out = {}
    for loc, t in TEXT.items():
        a = {k: t[k] for k in ("description", "promotionalText", "keywords", "whatsNew", "supportUrl", "marketingUrl")}
        if len(a["keywords"]) > 100 or len(a["whatsNew"]) > 4000 or len(a["promotionalText"]) > 170:
            raise SystemExit("%s: a field is over its App Store limit" % loc)
        if loc in have:
            r = call("PATCH", "/v1/appStoreVersionLocalizations/%s" % have[loc]["id"],
                     {"data": {"type": "appStoreVersionLocalizations", "id": have[loc]["id"], "attributes": a}})
        else:
            a["locale"] = loc
            r = call("POST", "/v1/appStoreVersionLocalizations", {"data": {"type": "appStoreVersionLocalizations",
                     "attributes": a, "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": mac["id"]}}}}})
        out[loc] = r["data"]["id"]
        print("text", loc, "ok (description %d, What's New %d, keywords %d chars)"
              % (len(t["description"]), len(t["whatsNew"]), len(t["keywords"])))
    return out


def screenshots(locs):
    for loc, lid in locs.items():
        sets = call("GET", "/v1/appStoreVersionLocalizations/%s/appScreenshotSets" % lid)["data"]
        desk = [s for s in sets if s["attributes"]["screenshotDisplayType"] == "APP_DESKTOP"]
        if desk:
            sid = desk[0]["id"]
            for old in call("GET", "/v1/appScreenshotSets/%s/appScreenshots" % sid)["data"]:
                call("DELETE", "/v1/appScreenshots/%s" % old["id"])
        else:
            sid = call("POST", "/v1/appScreenshotSets", {"data": {"type": "appScreenshotSets",
                       "attributes": {"screenshotDisplayType": "APP_DESKTOP"},
                       "relationships": {"appStoreVersionLocalization": {"data": {"type": "appStoreVersionLocalizations", "id": lid}}}}})["data"]["id"]
        for name in SHOTS[loc]:
            data = open(os.path.join(ROOT, "store", name), "rb").read()
            r = call("POST", "/v1/appScreenshots", {"data": {"type": "appScreenshots",
                     "attributes": {"fileName": name, "fileSize": len(data)},
                     "relationships": {"appScreenshotSet": {"data": {"type": "appScreenshotSets", "id": sid}}}}})["data"]
            for op in r["attributes"]["uploadOperations"]:
                chunk = data[op["offset"]:op["offset"] + op["length"]]
                req = urllib.request.Request(op["url"], method=op["method"], data=chunk,
                                             headers={h["name"]: h["value"] for h in op["requestHeaders"]})
                urllib.request.urlopen(req, timeout=120).read()
            call("PATCH", "/v1/appScreenshots/%s" % r["id"], {"data": {"type": "appScreenshots", "id": r["id"],
                 "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(data).hexdigest()}}})
            print("screenshot", loc, name, "uploaded")


def review_detail(version_id):
    try:
        return call("GET", "/v1/appStoreVersions/%s/appStoreReviewDetail" % version_id)["data"]
    except SystemExit:
        return None


def review(mac, prev):
    cur = review_detail(mac["id"])
    old = review_detail(prev["id"]) if prev else None
    src = (old or {}).get("attributes", {})
    a = {k: src.get(k) for k in ("contactFirstName", "contactLastName", "contactPhone", "contactEmail") if src.get(k)}
    # the account is required - the demo account (name + password) lives only in App Store Connect, never in this repo.
    # A version made through the API can start without it: then the previous macOS version's own entry is carried over
    # unchanged (never printed, never changed). An entry the new version already has is left as it is.
    a.update({"demoAccountRequired": True, "notes": NOTES})
    ca = (cur or {}).get("attributes", {})
    if ca.get("demoAccountName") and ca.get("demoAccountPassword"):
        print("demo account: already set on macOS %s (kept)" % VERSION)
    elif src.get("demoAccountName") and src.get("demoAccountPassword"):
        a["demoAccountName"], a["demoAccountPassword"] = src["demoAccountName"], src["demoAccountPassword"]
        print("demo account: carried over unchanged from macOS %s" % prev["attributes"]["versionString"])
    else:
        print("WARNING: no demo account entry found - App Review needs one before submission")
    if cur:
        call("PATCH", "/v1/appStoreReviewDetails/%s" % cur["id"], {"data": {"type": "appStoreReviewDetails", "id": cur["id"], "attributes": a}})
    else:
        call("POST", "/v1/appStoreReviewDetails", {"data": {"type": "appStoreReviewDetails", "attributes": a,
             "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": mac["id"]}}}}})
    print("review details ok (notes %d chars)" % len(NOTES))


def release_type(mac):
    """automatic release once Apple approves it (PM decision for 21.0)"""
    call("PATCH", "/v1/appStoreVersions/%s" % mac["id"], {"data": {"type": "appStoreVersions", "id": mac["id"],
         "attributes": {"releaseType": "AFTER_APPROVAL"}}})
    print("release type: AFTER_APPROVAL")


def build(mac, wait_min=60):
    """the newest macOS build uploaded for THIS version (preReleaseVersion = VERSION), once Apple has processed it"""
    for i in range(wait_min * 2):
        bs = call("GET", "/v1/builds?filter[app]=%s&filter[preReleaseVersion.platform]=MAC_OS&filter[preReleaseVersion.version]=%s"
                  "&sort=-uploadedDate&limit=5" % (APP_ID, VERSION))["data"]
        if bs:
            b = bs[0]
            st = b["attributes"]["processingState"]
            print("newest macOS %s build" % VERSION, b["attributes"]["version"], st, flush=True)
            if st == "VALID":
                call("PATCH", "/v1/appStoreVersions/%s/relationships/build" % mac["id"], {"data": {"type": "builds", "id": b["id"]}})
                print("build", b["attributes"]["version"], "attached to macOS", mac["attributes"]["versionString"])
                return
            if st in ("FAILED", "INVALID"):
                raise SystemExit("build processing " + st)
        time.sleep(30)
    raise SystemExit("no processed macOS %s build after %d minutes" % (VERSION, wait_min))


if __name__ == "__main__":
    mac, prev = versions()
    print("macOS version", mac["attributes"]["versionString"], mac["attributes"]["appStoreState"],
          "| previous:", prev["attributes"]["versionString"] if prev else None)
    locs = localizations(mac)
    screenshots(locs)
    review(mac, prev)
    release_type(mac)
    build(mac)
    print("DONE - not submitted for review")
