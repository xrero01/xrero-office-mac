# Mac App Store pictures - notes (16 Nov 2026)

Five pictures per language, in the listing's order (`mas/mas_metadata.py` SHOTS):

| # | en-US | ar-SA | What it shows |
|---|-------|-------|---------------|
| 1 | mac_en_start.png | mac_ar_start.png | the start page with the four demo files under Recent files |
| 2 | mac_en_editor.png | mac_ar_editor.png | the document editor, an Arabic-led report, caret in the Arabic summary |
| 3 | mac_en_sheet.png | mac_ar_sheet.png | the spreadsheet editor: E5 selected (`=SUM(B5:D5)` in the formula bar), the file's column chart |
| 4 | mac_en_slides.png | mac_ar_slides.png | the presentation editor: caret after slide 1's title, the four slides in the side panel |
| 5 | mac_en_pdf.png | mac_ar_pdf.png | the PDF editor: Comment tab, a form filled in the app, a highlight, an ink circle and a sticky note |

All ten are real captures of the App Store variant (sandboxed test copy, ad hoc) on the CI Mac:
`build-mac.yml` with `test_only=true` runs `mas/store_capture.py`. The pictures here come from run 27
(43797343195, every capture check green). They are composed with
`v20/mac/store_new_icons` (`prep.py` + `compose.js`, Cairo, the same background and window place for all ten).
English pictures come from the app in en-US, Arabic pictures from the app in ar-SA. Demo files only
(`mas/store_demo.py`): neutral UAE content, counts and dates, no money amounts, no names, no e-mail addresses.

How each new picture is made (and what is not done in the app):
- **Sheet**: the table's totals are SUM formulas. E5 is selected the way the name box does it (`asc_findCell`).
  The chart is the file's own chart part, drawn by the editor.
- **Slides**: a real click into slide 1's title. The caret is then put after the title's last letter with the
  editor's own `MoveCursorToEndPos`, because the End key does not do that on macOS.
- **PDF**: the Comment tab is clicked, then the form is filled the way a user does it: Tab to each field, type, and
  Enter to tick the boxes. The highlight, ink circle and sticky note are stored in the demo file (made by
  `store_demo.py` with PyMuPDF). The app shows them, and its Comment tab has the tools to make them, but the picture
  does not show them being drawn.
- **Caret**: for the window and Retina captures of pictures 2, 4 and 5, the editor's caret blink timer is paused
  with its caret shown, then started again. This shows the editor's own caret at its own place, not an added one.

## Real-UI issues found while making them

Fixed in the Mac app (`scripts/patch_bundle.py`, Mac bundle only; the Windows payload is unchanged):
- **Arabic PDF editor**: the Collaboration ribbon tab was in English. The payload's `pdfeditor` `ar.json` keeps
  "Collaboration", while the document and presentation editors say "التعاون". Now "التعاون".
- **Arabic spreadsheet formula bar**: a formula took the right-to-left direction of the interface, so
  `=SUM(B5:D5)` read `SUM(B5:D5)=`. Each line now takes its direction from its own text
  (`unicode-bidi: plaintext`) and stays right aligned (`XR-FBIDI`).

Not fixed (engine behaviour; the capture works around it or avoids it):
- **Arabic PDF form, first letter lost** (runs 23-27): in the right-to-left form, the first input typed into the
  date field after tabbing into it does not arrive. Typed letter by letter, "2" was lost and "4/11/2026" stayed.
  Typed as one piece, the whole piece was lost. The capture reads the value back and types the missing start
  again, as a user would on seeing it. The English form and the Arabic fields that start with letters keep
  everything. This needs a separate look at sdkjs `pdf/src/forms` (font loading on the first digit is suspected,
  not proven).
- **Backspace in that field** (run 25): Backspace sent by the capture (a DevTools key event) deleted nothing. This
  may be specific to synthetic key events. It was not checked with a real keyboard.
- **Presentation status bar language**: Arabic slide text written as `lang="ar-AE"` is reported as "العربية –
  المملكة العربية السعودية". The document editor reports the same kind of text as "...الإمارات العربية المتحدة".
  The Arabic slides picture shows the Saudi Arabia wording.
- **Caret on the dark title slide** (picture 4): the caret is held shown (checked), but the editor draws it dark,
  so it does not stand out on the ink-coloured slide. The title's selection frame and the ribbon (its font, 54,
  Bold) show the edit.
- **Caret in the Arabic Notes field** (picture 5, ar): the field is right aligned, and the engine draws the caret
  at the right edge of its Arabic line after typing, not at the line's left end.
- **Spreadsheet chart with a reversed category axis** (right-to-left chart, `orientation maxMin`): the editor
  turned the first category label on its side and dropped the others. The Arabic chart's categories therefore
  run left to right, the same as in the English chart.
- **Tab titles** are cut after about 14 Latin characters ("Projects 2026...."), and a file name with digits
  displays out of order right to left. The demo files are opened under short names.
- **Window chrome**: the CI display has no 2x mode (`mas/hidpi.swift` lists the modes in
  `out/store/display.log`). The title bar is the 1x capture scaled 2x in all ten pictures. The page below it is
  the app's own Retina render.
- **CI host prompt**: run 26's 1x capture of the Arabic start page caught the runner's own macOS prompt ("Allow
  hosted-compute- to find devices on local networks?") over the page. That prompt is not from Xrero, and it is not
  in the pictures, which take only the title bar from that capture.
- The editors are opened with the CI account's name in their address (`username=Anka`). That name is not shown
  anywhere on screen; the capture checks the visible text and the title bars for user names and e-mail addresses.

Store text to look at (not changed here): the description in `mas_metadata.py` says "plus PDF viewing", while
picture 5 shows a PDF form being filled and annotated in the app.
