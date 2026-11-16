// tab_logo.swift <Xrero Office.app> <assets/icons/small dir> <diag dir>
// Makes the title-bar pictures the patched binary loads (see patch_bundle.py BIN_SWAPS), 1x + 2x in one TIFF each:
//  - the start tab's logo (xrero-tab-lite / xrero-tabdark): same point size as ONLYOFFICE's logo-tab-light /
//    logo-tab-dark in Assets.car and the same text colour, drawn as the Xrero app icon (the approved kit's artwork,
//    small/tab-app.png - a rounded app icon, not a lone "x" in a circle that reads as a close button) + "Xrero Office"
//    in the system font;
//  - the document tabs' kind icons (xrero_tab_<de|se|pe|pdf>_<active|inactive>): the kit's Doc / Sheet / Slide / PDF
//    pictures (small/tab-*.png) at the size and place of ONLYOFFICE's icon_tabs_* glyphs; an inactive glyph follows
//    the original's dimming (alpha, colour) the same way.
// <diag dir> gets the originals and the new pictures as PNG (run evidence).
import AppKit

let args = CommandLine.arguments
let app = args[1], small = args[2], diag = args[3]
let bundle = Bundle(path: app)!
let res = app + "/Contents/Resources/"

func bitmap(_ size: NSSize, _ scale: CGFloat, _ draw: () -> Void) -> NSBitmapImageRep {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size.width * scale), pixelsHigh: Int(size.height * scale),
                               bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                               colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    rep.size = size
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    draw()
    NSGraphicsContext.restoreGraphicsState()
    return rep
}

func png(_ rep: NSBitmapImageRep, _ name: String) {
    try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: diag + "/" + name + ".png"))
}

func load(_ name: String) -> NSImage {
    guard let im = NSImage(contentsOfFile: small + "/" + name + ".png") else {
        fputs("missing \(small)/\(name).png\n", stderr); exit(2)
    }
    return im
}

struct Stats { var r = 0.0, g = 0.0, b = 0.0, alpha = 0.0, sat = 0.0, n = 0.0; var box = NSRect.zero }

// opaque pixels of a 2x bitmap: mean colour, mean alpha, mean saturation, bounding box (points)
func stats(_ o: NSBitmapImageRep) -> Stats {
    var s = Stats()
    var minX = Int.max, minY = Int.max, maxX = -1, maxY = -1
    for y in 0..<o.pixelsHigh { for x in 0..<o.pixelsWide {
        guard let c = o.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB), c.alphaComponent > 0.08 else { continue }
        s.r += Double(c.redComponent); s.g += Double(c.greenComponent); s.b += Double(c.blueComponent)
        s.alpha += Double(c.alphaComponent); s.sat += Double(c.saturationComponent); s.n += 1
        minX = min(minX, x); minY = min(minY, y); maxX = max(maxX, x); maxY = max(maxY, y)
    } }
    if s.n > 0 {
        s.r /= s.n; s.g /= s.n; s.b /= s.n; s.alpha /= s.n; s.sat /= s.n
        let k = o.size.width / CGFloat(o.pixelsWide)
        // colorAt's y runs from the top; NSRect's from the bottom
        s.box = NSRect(x: CGFloat(minX) * k, y: o.size.height - CGFloat(maxY + 1) * k,
                       width: CGFloat(maxX - minX + 1) * k, height: CGFloat(maxY - minY + 1) * k)
    }
    return s
}

func original(_ name: String) -> (NSImage, NSBitmapImageRep, Stats) {
    guard let orig = bundle.image(forResource: name) else {
        fputs("asset \(name) not found in the bundle\n", stderr); exit(2)
    }
    let o = bitmap(orig.size, 2) { orig.draw(in: NSRect(origin: .zero, size: orig.size)) }
    png(o, "orig-" + name)
    return (orig, o, stats(o))
}

func writeTIFF(_ reps: [NSBitmapImageRep], _ output: String) {
    let tiff = NSBitmapImageRep.tiffRepresentationOfImageReps(in: reps, using: .lzw, factor: 0)!
    try! tiff.write(to: URL(fileURLWithPath: res + output + ".tiff"))
    png(reps[reps.count - 1], "new-\(output)@2x")
}

// ---------------------------------------------------------------- start tab logo
func logo(original name: String, output: String) {
    let (orig, _, st) = original(name)
    let size = orig.size
    let ink = st.n > 0 ? NSColor(deviceRed: st.r, green: st.g, blue: st.b, alpha: 1) : NSColor.secondaryLabelColor
    print("\(name): \(size.width)x\(size.height) pt, template=\(orig.isTemplate), ink=\(ink), opaque px=\(Int(st.n))")
    let icon = load("tab-app")
    let h = size.height
    let side = min(h, 16)                               // the app icon at the size of the document tabs' icons
    let gap = max(4, (h * 0.3).rounded())
    var font = NSFont.systemFont(ofSize: h * 0.62, weight: .semibold)
    var text = NSAttributedString(string: "Xrero Office", attributes: [.font: font, .foregroundColor: ink])
    while side + gap + text.size().width > size.width && font.pointSize > 6 {   // must fit the original's box
        font = NSFont.systemFont(ofSize: font.pointSize - 0.25, weight: .semibold)
        text = NSAttributedString(string: "Xrero Office", attributes: [.font: font, .foregroundColor: ink])
    }
    var reps: [NSBitmapImageRep] = []
    for scale: CGFloat in [1, 2] {
        reps.append(bitmap(size, scale) {
            NSGraphicsContext.current?.imageInterpolation = .high
            icon.draw(in: NSRect(x: 0, y: ((h - side) / 2).rounded(.down), width: side, height: side))
            let ts = text.size()
            text.draw(at: NSPoint(x: side + gap, y: ((h - ts.height) / 2).rounded(.down) + 0.5))
        })
    }
    writeTIFF(reps, output)
    print("  -> \(output).tiff, icon \(side) pt, font \(font.pointSize) pt, text width \(text.size().width) of \(size.width - side - gap)")
}

// ---------------------------------------------------------------- document tab kind icons
func kind(_ code: String, _ picture: String) {
    let (activeImg, _, act) = original("icon_tabs_\(code)_active")
    let (_, _, inact) = original("icon_tabs_\(code)_inactive")
    let icon = load(picture)
    let size = activeImg.size
    // the original glyph's own box (its opaque pixels), as a square centred in it
    var box = act.n > 0 ? act.box : NSRect(origin: .zero, size: size)
    let side = max(box.width, box.height).rounded()
    box = NSRect(x: (box.midX - side / 2).rounded(), y: (box.midY - side / 2).rounded(), width: side, height: side)
    let dimAlpha = act.alpha > 0 ? min(1.0, inact.alpha / act.alpha) : 1.0
    let dimSat = act.sat > 0.05 ? min(1.0, inact.sat / act.sat) : 1.0
    print("icon_tabs_\(code): \(size.width)x\(size.height) pt, glyph box \(act.box), inactive alpha x\(String(format: "%.2f", dimAlpha)) saturation x\(String(format: "%.2f", dimSat))")
    for (state, alpha, sat) in [("active", 1.0, 1.0), ("inactive", dimAlpha, dimSat)] {
        var reps: [NSBitmapImageRep] = []
        for scale: CGFloat in [1, 2] {
            let rep = bitmap(size, scale) {
                NSGraphicsContext.current?.imageInterpolation = .high
                icon.draw(in: box, from: .zero, operation: .sourceOver, fraction: CGFloat(alpha))
            }
            if sat < 0.6 {        // the original dims its colour when inactive: the same, towards grey
                for y in 0..<rep.pixelsHigh { for x in 0..<rep.pixelsWide {
                    guard let c = rep.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB), c.alphaComponent > 0 else { continue }
                    let l = 0.3 * c.redComponent + 0.59 * c.greenComponent + 0.11 * c.blueComponent
                    let k = CGFloat(sat)
                    rep.setColor(NSColor(deviceRed: l + (c.redComponent - l) * k, green: l + (c.greenComponent - l) * k,
                                         blue: l + (c.blueComponent - l) * k, alpha: c.alphaComponent), atX: x, y: y)
                } }
            }
            reps.append(rep)
        }
        writeTIFF(reps, "xrero_tab_\(code)_\(state)")
    }
}

logo(original: "logo-tab-light", output: "xrero-tab-lite")
logo(original: "logo-tab-dark", output: "xrero-tabdark")
kind("de", "tab-doc")
kind("se", "tab-sheet")
kind("pe", "tab-slide")
kind("pdf", "tab-pdf")
// run evidence only: the other title-bar pictures (what the download indicator and the account button draw)
for name in ["progress_download_icon", "icon-login_normal", "change-tab_left_normal", "change-tab_right_normal", "icon_tabs_ve_active"] {
    if let im = bundle.image(forResource: name) {
        png(bitmap(im.size, 2) { im.draw(in: NSRect(origin: .zero, size: im.size)) }, "orig-" + name)
        print("\(name): \(im.size.width)x\(im.size.height) pt")
    }
}
