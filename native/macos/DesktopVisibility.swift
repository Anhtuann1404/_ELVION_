import AppKit
import ApplicationServices
import Foundation

// One read-only probe. No focus, action, event, screenshot or window-list dump.
let input = FileHandle.standardInput.readData(ofLength: 65_537)
guard input.count <= 65_536,
      let json = try? JSONSerialization.jsonObject(with: input) as? [String: Any],
      (json["version"] as? Int) == 1,
      let pid = json["pid"] as? Int, pid > 0, pid <= Int(Int32.max),
      let bundle = json["bundle_id"] as? String, bundle == "com.apple.calculator",
      let snapshotID = json["snapshot_id"] as? String,
      let nodeID = json["target_node_id"] as? String,
      let scope = json["target_scope"] as? String,
      let label = json["target_label"] as? String,
      let targetNumbers = json["target_bbox"] as? [Double], targetNumbers.count == 4,
      let windowNumbers = json["window_bbox"] as? [Double], windowNumbers.count == 4,
      let displayNumbers = json["display_bbox"] as? [Double], displayNumbers.count == 4,
      let displayScale = json["display_scale"] as? Double, displayScale.isFinite, displayScale > 0,
      let snapshotNS = json["snapshot_ns"] as? Int64, snapshotNS > 0,
      let sameHostClock = json["same_host_clock"] as? Bool else { exit(2) }
let subrole = json["target_subrole"] as? String
let targetRect = CGRect(x: targetNumbers[0], y: targetNumbers[1],
                        width: targetNumbers[2], height: targetNumbers[3])
let windowRect = CGRect(x: windowNumbers[0], y: windowNumbers[1],
                        width: windowNumbers[2], height: windowNumbers[3])
let displayRect = CGRect(x: displayNumbers[0], y: displayNumbers[1],
                         width: displayNumbers[2], height: displayNumbers[3])
guard [targetRect, windowRect, displayRect].allSatisfy({
    $0.minX.isFinite && $0.minY.isFinite && $0.width.isFinite && $0.height.isFinite &&
    $0.width > 0 && $0.height > 0
}) else { exit(2) }

var fields: [String: Any] = [
    "schema_version": 1, "reference_id": UUID().uuidString,
    "snapshot_id": snapshotID, "bundle_id": bundle, "pid": pid,
    "target_node_id": nodeID, "target_scope": scope,
    "target_bbox": targetNumbers, "window_bbox": windowNumbers,
    "display_scale": displayScale,
    "snapshot_ns": snapshotNS, "probe_ns": Int64(ProcessInfo.processInfo.systemUptime * 1_000_000_000),
    "same_host_clock": sameHostClock, "permission_granted": NSNull(),
    "target_bound": false, "window_bound": false, "unique_target": false,
    "layout_unchanged": false, "state_unchanged": false,
    "display_contains_target": displayRect.contains(targetRect),
    "window_contains_target": windowRect.contains(targetRect),
    "app_hidden": NSNull(), "window_minimized": NSNull(), "frontmost": NSNull(),
    "hit_test_supported": false, "hits": []
]
func emit() {
    fields["probe_ns"] = Int64(ProcessInfo.processInfo.systemUptime * 1_000_000_000)
    guard let output = try? JSONSerialization.data(withJSONObject: fields),
          output.count <= 65_536 else { exit(2) }
    FileHandle.standardOutput.write(output)
}
guard AXIsProcessTrusted() else { fields["permission_granted"] = false; emit(); exit(0) }
fields["permission_granted"] = true
guard let app = NSRunningApplication(processIdentifier: pid_t(pid)),
      !app.isTerminated, app.bundleIdentifier == bundle else { emit(); exit(0) }
fields["app_hidden"] = app.isHidden
fields["frontmost"] = app.isActive

func attribute(_ node: AXUIElement, _ name: String) -> CFTypeRef? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(node, name as CFString, &value) == .success ? value : nil
}
func text(_ node: AXUIElement, _ name: String) -> String? {
    guard let value = attribute(node, name), CFGetTypeID(value) == CFStringGetTypeID() else { return nil }
    return value as? String
}
func boolean(_ node: AXUIElement, _ name: String) -> Bool? {
    guard let value = attribute(node, name), CFGetTypeID(value) == CFBooleanGetTypeID() else { return nil }
    return CFBooleanGetValue((value as! CFBoolean))
}
func point(_ value: CFTypeRef?) -> CGPoint? {
    guard let value, CFGetTypeID(value) == AXValueGetTypeID() else { return nil }
    let ax = value as! AXValue
    guard AXValueGetType(ax) == .cgPoint else { return nil }
    var result = CGPoint.zero
    return AXValueGetValue(ax, .cgPoint, &result) ? result : nil
}
func size(_ value: CFTypeRef?) -> CGSize? {
    guard let value, CFGetTypeID(value) == AXValueGetTypeID() else { return nil }
    let ax = value as! AXValue
    guard AXValueGetType(ax) == .cgSize else { return nil }
    var result = CGSize.zero
    return AXValueGetValue(ax, .cgSize, &result) ? result : nil
}
func bbox(_ node: AXUIElement) -> CGRect? {
    guard let p = point(attribute(node, kAXPositionAttribute as String)),
          let s = size(attribute(node, kAXSizeAttribute as String)),
          p.x.isFinite, p.y.isFinite, s.width.isFinite, s.height.isFinite,
          s.width > 0, s.height > 0 else { return nil }
    return CGRect(origin: p, size: s)
}
func sameBox(_ a: CGRect?, _ b: CGRect) -> Bool {
    guard let a else { return false }
    return abs(a.minX-b.minX) <= 0.5 && abs(a.minY-b.minY) <= 0.5 &&
        abs(a.width-b.width) <= 0.5 && abs(a.height-b.height) <= 0.5
}
func children(_ node: AXUIElement) -> [AXUIElement] {
    let raw = attribute(node, kAXChildrenAttribute as String)
        ?? attribute(node, kAXWindowsAttribute as String)
    return raw as? [AXUIElement] ?? []
}

let deadline = ProcessInfo.processInfo.systemUptime + 4.0
let root = AXUIElementCreateApplication(pid_t(pid))
AXUIElementSetMessagingTimeout(root, 0.5)
var queue: [(AXUIElement, AXUIElement?, Int, AXUIElement?)] = [(root, nil, 0, nil)]
var seen: [AXUIElement] = []
var windows: [AXUIElement] = []
var matches: [(AXUIElement, AXUIElement)] = []
var labelCount = 0
var index = 0
var traversalComplete = true
while index < queue.count {
    if seen.count >= 300 || ProcessInfo.processInfo.systemUptime >= deadline {
        traversalComplete = false; break
    }
    let (node, parent, depth, inheritedWindow) = queue[index]
    index += 1
    if seen.contains(where: { CFEqual($0, node) }) { continue }
    seen.append(node)
    AXUIElementSetMessagingTimeout(node, 0.5)
    let role = text(node, kAXRoleAttribute as String)
    let window: AXUIElement? = role == "AXWindow" ? node : inheritedWindow
    if role == "AXWindow", sameBox(bbox(node), windowRect) { windows.append(node) }
    if role == "AXButton" {
        let rawLabel = text(node, kAXTitleAttribute as String) ?? text(node, kAXDescriptionAttribute as String)
        let isWindowControl = scope == "calculator_content" && parent != nil &&
            text(parent!, kAXRoleAttribute as String) == "AXWindow" &&
            ["AXCloseButton", "AXMinimizeButton", "AXZoomButton", "AXFullScreenButton"].contains(
                text(node, kAXSubroleAttribute as String) ?? "")
        if !isWindowControl && rawLabel == label {
            labelCount += 1
            if let window, sameBox(bbox(node), targetRect),
               boolean(node, kAXEnabledAttribute as String) == true,
               text(node, kAXSubroleAttribute as String) == subrole {
                matches.append((node, window))
            }
        }
    }
    let kids = children(node)
    if depth >= 12 {
        if !kids.isEmpty { traversalComplete = false }
    } else {
        for child in kids {
            queue.append((child, node, depth + 1, window))
        }
    }
}
let bound = traversalComplete && windows.count == 1 && matches.count == 1 && labelCount == 1 &&
    CFEqual(matches[0].1, windows[0])
fields["window_bound"] = traversalComplete && windows.count == 1
fields["target_bound"] = bound
fields["unique_target"] = traversalComplete && labelCount == 1
fields["layout_unchanged"] = bound
fields["state_unchanged"] = bound
if let window = windows.first, windows.count == 1 {
    fields["window_minimized"] = boolean(window, kAXMinimizedAttribute as String) ?? NSNull()
}
guard bound else { emit(); exit(0) }
let target = matches[0].0
let targetWindow = matches[0].1
let system = AXUIElementCreateSystemWide()
AXUIElementSetMessagingTimeout(system, 0.5)
let fractions: [(Double, Double)] = [(0.5,0.5),(0.25,0.25),(0.75,0.25),(0.25,0.75),(0.75,0.75)]
var hits: [String] = []
var supported = true
for (fx, fy) in fractions {
    if ProcessInfo.processInfo.systemUptime >= deadline { supported = false; break }
    var hit: AXUIElement?
    let x = Float(targetRect.minX + targetRect.width * fx)
    let y = Float(targetRect.minY + targetRect.height * fy)
    let err = AXUIElementCopyElementAtPosition(system, x, y, &hit)
    if err == .notImplemented { supported = false; break }
    guard err == .success, let hit else { hits.append("unknown"); continue }
    var cursor: AXUIElement? = hit
    var targetAncestry = false
    var hitWindow: AXUIElement?
    for _ in 0...12 {
        guard let current = cursor else { break }
        if CFEqual(current, target) { targetAncestry = true; break }
        if text(current, kAXRoleAttribute as String) == "AXWindow" { hitWindow = current; break }
        if let parent = attribute(current, kAXParentAttribute as String),
           CFGetTypeID(parent) == AXUIElementGetTypeID() {
            cursor = (parent as! AXUIElement)
        } else { cursor = nil }
    }
    if targetAncestry { hits.append("target_or_child"); continue }
    var hitPID: pid_t = 0
    if AXUIElementGetPid(hit, &hitPID) == .success && hitPID != pid_t(pid) {
        hits.append("other_pid")
    } else if let hitWindow, !CFEqual(hitWindow, targetWindow) {
        hits.append("other_window")
    } else if let hitWindow, CFEqual(hitWindow, targetWindow) {
        hits.append("ancestor_only")
    } else { hits.append("unknown") }
}
fields["hit_test_supported"] = supported && hits.count == 5
fields["hits"] = hits
emit()
