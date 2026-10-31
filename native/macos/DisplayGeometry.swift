import AppKit
import CoreGraphics
import Foundation

// Read display bounds only. No screenshot, focus change, cursor or input event.
let screens = NSScreen.screens
let mainID = CGMainDisplayID()
func id(_ screen: NSScreen) -> CGDirectDisplayID? {
    return (screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value
}
func emit(_ status: String, _ reason: String?, _ displays: [[String: Any]] = []) {
    let envelope: [String: Any] = ["version": 1, "status": status,
        "reason": reason ?? NSNull(), "displays": displays]
    guard let data = try? JSONSerialization.data(withJSONObject: envelope),
          data.count <= 65536 else { exit(2) }
    FileHandle.standardOutput.write(data)
}
guard screens.count > 0, screens.count <= 16,
      let main = screens.first(where: { id($0) == mainID }) else {
    emit("unavailable", "DISPLAY_LAYOUT_UNAVAILABLE"); exit(0)
}
var rows: [[String: Any]] = []
for screen in screens {
    guard let number = id(screen) else { emit("unavailable", "DISPLAY_ID_UNAVAILABLE"); exit(0) }
    let ns = screen.frame
    let ax = CGRect(x: ns.minX - main.frame.minX, y: main.frame.maxY - ns.maxY,
                    width: ns.width, height: ns.height)
    let cg = CGDisplayBounds(number)
    let deltas = [ax.minX-cg.minX, ax.minY-cg.minY, ax.width-cg.width, ax.height-cg.height]
    guard deltas.allSatisfy({ $0.isFinite && abs($0) <= 0.5 }),
          ax.width > 0, ax.height > 0, screen.backingScaleFactor > 0 else {
        emit("unavailable", "DISPLAY_COORDINATE_MISMATCH"); exit(0)
    }
    rows.append(["id": Int(number), "bbox": [Double(ax.minX), Double(ax.minY),
        Double(ax.width), Double(ax.height)], "scale": Double(screen.backingScaleFactor)])
}
emit("observed", nil, rows)
