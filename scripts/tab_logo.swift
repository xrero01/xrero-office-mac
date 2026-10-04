// tab_logo.swift <Xrero Office.app> <icon png> <diag dir>
// Makes the start-tab logo files the patched binary loads (xrero-tab-lite / xrero-tabdark, see patch_bundle.py):
// same point size as ONLYOFFICE's logo-tab-light / logo-tab-dark in Assets.car and the same text colour,
// drawn as the Xrero icon + "Xrero Office" in the system font, 1x + 2x in one TIFF.
import AppKit

let args = CommandLine.arguments
let app = args[1], iconPath = args[2], diag = args[3]
let bundle = Bundle(path: app)!
let res = app + "/Contents/Resources/"
let icon = NSImage(contentsOfFile: iconPath)!

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

func make(original: String, output: String) {
    guard let orig = bundle.image(forResource: original) else {
        fputs("asset \(original) not found in the bundle\n", stderr); exit(2)
    }
    let size = orig.size
    // the original's text colour = mean colour of its opaque pixels
    let o = bitmap(size, 2) { orig.draw(in: NSRect(origin: .zero, size: size)) }
    try? o.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: diag + "/orig-\(original).png"))
    var r = 0.0, g = 0.0, b = 0.0, n = 0.0
    for y in 0..<o.pixelsHigh { for x in 0..<o.pixelsWide {
        if let c = o.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB), c.alphaComponent > 0.7 {
            r += Double(c.redComponent); g += Double(c.greenComponent); b += Double(c.blueComponent); n += 1
        }
    } }
    let ink = n > 0 ? NSColor(deviceRed: r / n, green: g / n, blue: b / n, alpha: 1) : NSColor.secondaryLabelColor
    print("\(original): \(size.width)x\(size.height) pt, template=\(orig.isTemplate), ink=\(ink), opaque px=\(Int(n))")

    let h = size.height
    let gap = max(2, (h * 0.35).rounded())
    var font = NSFont.systemFont(ofSize: h * 0.92, weight: .semibold)
    var text = NSAttributedString(string: "Xrero Office", attributes: [.font: font, .foregroundColor: ink])
    while h + gap + text.size().width > size.width && font.pointSize > 6 {   // must fit the original's box
        font = NSFont.systemFont(ofSize: font.pointSize - 0.25, weight: .semibold)
        text = NSAttributedString(string: "Xrero Office", attributes: [.font: font, .foregroundColor: ink])
    }
    var reps: [NSBitmapImageRep] = []
    for scale: CGFloat in [1, 2] {
        reps.append(bitmap(size, scale) {
            NSGraphicsContext.current?.imageInterpolation = .high
            icon.draw(in: NSRect(x: 0, y: 0, width: h, height: h))
            let ts = text.size()
            text.draw(at: NSPoint(x: h + gap, y: ((h - ts.height) / 2).rounded(.down) + 0.5))
        })
    }
    let tiff = NSBitmapImageRep.tiffRepresentationOfImageReps(reps, using: .lzw, factor: 0)!
    try! tiff.write(to: URL(fileURLWithPath: res + output + ".tiff"))
    try? reps[1].representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: diag + "/new-\(output)@2x.png"))
    print("  -> \(output).tiff, font \(font.pointSize) pt, text width \(text.size().width) of \(size.width - h - gap)")
}

make(original: "logo-tab-light", output: "xrero-tab-lite")
make(original: "logo-tab-dark", output: "xrero-tabdark")
