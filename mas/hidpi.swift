// hidpi.swift - the CI Mac's display in a Retina (2x) mode when it offers one, so the store pictures' window chrome
// (title bar, traffic lights, tab titles) is captured at Retina scale like the page under it. Prints every mode the
// display offers; changes nothing when there is no 2x mode. Always exits 0 (the pictures then use the 1x chrome).
import CoreGraphics
import Foundation

let display = CGMainDisplayID()
let opts = [kCGDisplayShowDuplicateLowResolutionModes as String: true] as CFDictionary
let modes = (CGDisplayCopyAllDisplayModes(display, opts) as? [CGDisplayMode]) ?? []
guard let current = CGDisplayCopyDisplayMode(display) else { print("no display mode"); exit(0) }
func describe(_ m: CGDisplayMode) -> String {
    return "\(m.width)x\(m.height) pt = \(m.pixelWidth)x\(m.pixelHeight) px\(m.isUsableForDesktopGUI() ? "" : " (not for the desktop)")"
}
print("current: " + describe(current))
for m in modes { print("mode: " + describe(m)) }
// a 2x mode with at least the current point size; the same point size first (the window keeps its layout)
let retina = modes.filter { $0.pixelWidth == 2 * $0.width && $0.width >= 1024 && $0.height >= 700 && $0.isUsableForDesktopGUI() }
let pick = retina.first { $0.width == current.width && $0.height == current.height }
    ?? retina.sorted { $0.width * $0.height < $1.width * $1.height }.first
guard let mode = pick else { print("no 2x mode: the pictures use the 1x window chrome"); exit(0) }
if current.pixelWidth == 2 * current.width { print("already 2x"); exit(0) }
var config: CGDisplayConfigRef?
CGBeginDisplayConfiguration(&config)
CGConfigureDisplayWithDisplayMode(config, display, mode, nil)
let err = CGCompleteDisplayConfiguration(config, .permanently)
sleep(3)
if let now = CGDisplayCopyDisplayMode(display) {
    print("switched (\(err.rawValue)): " + describe(now))
}
exit(0)
