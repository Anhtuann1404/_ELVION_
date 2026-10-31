import AppKit
import ApplicationServices
import Foundation

let input = FileHandle.standardInput.readData(ofLength: 65_537)
guard input.count <= 65_536,
      let request = try? JSONSerialization.jsonObject(with: input) as? [String: Any],
      request.count <= 14,
      (request["version"] as? Int) == 1,
      let mode = request["mode"] as? String,
      ["begin", "probe"].contains(mode) else { exit(2) }
func output(_ value: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: value), data.count <= 65_536 else { exit(2) }
    FileHandle.standardOutput.write(data)
}
let bundle = "com.apple.calculator"
func marker(_ app: NSRunningApplication?) -> String? {
    guard let app, !app.isTerminated, app.bundleIdentifier == bundle,
          let date = app.launchDate else { return nil }
    return String(format: "%.6f", date.timeIntervalSince1970)
}
if mode == "begin" {
    let apps = NSRunningApplication.runningApplications(withBundleIdentifier: bundle)
    let app = apps.count == 1 ? apps[0] : nil
    output(["version": 1, "pid": app.map { Int($0.processIdentifier) } ?? 0,
            "process_marker": marker(app) ?? NSNull(), "permission": AXIsProcessTrusted()])
    exit(0)
}
guard request.count == 12,
      let pid = request["pid"] as? Int, pid > 0, pid <= Int(Int32.max),
      request["bundle_id"] as? String == bundle,
      request["scope"] as? String == "calculator_content",
      let label = request["label"] as? String, !label.isEmpty, label.count <= 256,
      let subroleValue = request["subrole"],
      let targetNumbers = request["target_bbox"] as? [Double], targetNumbers.count == 4,
      let windowNumbers = request["window_bbox"] as? [Double], windowNumbers.count == 4,
      let displayNumbers = request["display_bbox"] as? [Double], displayNumbers.count == 4,
      let displayScale = request["display_scale"] as? Double, displayScale.isFinite, displayScale > 0,
      let expectedMarker = request["process_marker"] as? String, !expectedMarker.isEmpty else { exit(2) }
let subrole = subroleValue as? String
let targetRect = CGRect(x: targetNumbers[0], y: targetNumbers[1], width: targetNumbers[2], height: targetNumbers[3])
let windowRect = CGRect(x: windowNumbers[0], y: windowNumbers[1], width: windowNumbers[2], height: windowNumbers[3])
let displayRect = CGRect(x: displayNumbers[0], y: displayNumbers[1], width: displayNumbers[2], height: displayNumbers[3])
guard [targetRect, windowRect, displayRect].allSatisfy({
    $0.minX.isFinite && $0.minY.isFinite && $0.width.isFinite && $0.height.isFinite && $0.width > 0 && $0.height > 0
}), displayRect.contains(targetRect), windowRect.contains(targetRect) else { exit(2) }
let start = ProcessInfo.processInfo.systemUptime
let deadline = start + 1.8
func attr(_ node: AXUIElement, _ key: String) -> CFTypeRef? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(node, key as CFString, &value) == .success ? value : nil
}
func text(_ node: AXUIElement, _ key: String) -> String? {
    guard let value = attr(node, key), CFGetTypeID(value) == CFStringGetTypeID() else { return nil }
    return value as? String
}
func boolean(_ node: AXUIElement, _ key: String) -> Bool? {
    guard let value = attr(node, key), CFGetTypeID(value) == CFBooleanGetTypeID() else { return nil }
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
func box(_ node: AXUIElement) -> CGRect? {
    guard let p = point(attr(node, kAXPositionAttribute as String)),
          let s = size(attr(node, kAXSizeAttribute as String)),
          p.x.isFinite, p.y.isFinite, s.width.isFinite, s.height.isFinite,
          s.width > 0, s.height > 0 else { return nil }
    return CGRect(origin: p, size: s)
}
func same(_ a: CGRect?, _ b: CGRect) -> Bool {
    guard let a else { return false }
    return abs(a.minX-b.minX) <= 0.5 && abs(a.minY-b.minY) <= 0.5 &&
           abs(a.width-b.width) <= 0.5 && abs(a.height-b.height) <= 0.5
}
func children(_ node: AXUIElement) -> [AXUIElement] {
    return (attr(node, kAXChildrenAttribute as String) ?? attr(node, kAXWindowsAttribute as String)) as? [AXUIElement] ?? []
}
func scan() -> (Int?, AXUIElement?, AXUIElement?, Bool?) {
    let root = AXUIElementCreateApplication(pid_t(pid))
    AXUIElementSetMessagingTimeout(root, 0.25)
    var queue: [(AXUIElement, AXUIElement?, AXUIElement?, Int)] = [(root, nil, nil, 0)]
    var seen: [AXUIElement] = []
    var matches: [(AXUIElement, AXUIElement)] = []
    var count = 0
    var windows: [AXUIElement] = []
    var index = 0
    var complete = true
    while index < queue.count {
        if seen.count >= 300 || ProcessInfo.processInfo.systemUptime >= deadline { complete = false; break }
        let (node, parent, inheritedWindow, depth) = queue[index]
        index += 1
        if seen.contains(where: { CFEqual($0, node) }) { continue }
        seen.append(node)
        AXUIElementSetMessagingTimeout(node, 0.25)
        let role = text(node, kAXRoleAttribute as String)
        let window: AXUIElement? = role == "AXWindow" ? node : inheritedWindow
        if role == "AXWindow", same(box(node), windowRect) { windows.append(node) }
        if role == "AXButton" {
            let raw = text(node, kAXTitleAttribute as String) ?? text(node, kAXDescriptionAttribute as String)
            let windowControl = parent != nil && text(parent!, kAXRoleAttribute as String) == "AXWindow" &&
                ["AXCloseButton", "AXMinimizeButton", "AXZoomButton", "AXFullScreenButton"].contains(
                    text(node, kAXSubroleAttribute as String) ?? "")
            if !windowControl && raw == label {
                count += 1
                if let window, same(box(node), targetRect),
                   text(node, kAXSubroleAttribute as String) == subrole {
                    matches.append((node, window))
                }
            }
        }
        let kids = children(node)
        if depth >= 12 { if !kids.isEmpty { complete = false } }
        else { for child in kids { queue.append((child, node, window, depth + 1)) } }
    }
    if !complete { return (nil, nil, nil, nil) }
    let bound = count == 1 && matches.count == 1 && windows.count == 1 && CFEqual(matches[0].1, windows[0])
    return (count, bound ? matches[0].0 : nil, bound ? matches[0].1 : nil, bound)
}
var result: [String: Any] = ["version": 1, "pid": pid,
    "process_marker": NSNull(), "permission_before": AXIsProcessTrusted(), "permission_after": NSNull(),
    "target_count_before": NSNull(), "target_count_after": NSNull(),
    "binding_before": NSNull(), "binding_after": NSNull(),
    "target_enabled_before": NSNull(), "target_enabled_after": NSNull(),
    "target_bbox_stable": NSNull(), "window_bbox_stable": NSNull(),
    "app_hidden_before": NSNull(), "app_hidden_after": NSNull(),
    "window_minimized_before": NSNull(), "window_minimized_after": NSNull(),
    "hit_test_supported": false, "hits": [], "duration_ns": 0]
func finish() {
    result["permission_after"] = AXIsProcessTrusted()
    let currentApps = NSRunningApplication.runningApplications(withBundleIdentifier: bundle)
    let current = currentApps.count == 1 ? currentApps[0] : nil
    result["pid"] = current.map { Int($0.processIdentifier) } ?? 0
    result["process_marker"] = marker(current) ?? NSNull()
    result["app_hidden_after"] = current.map { $0.isHidden } ?? NSNull()
    result["duration_ns"] = Int64((ProcessInfo.processInfo.systemUptime-start) * 1_000_000_000)
    output(result)
}
let app = NSRunningApplication(processIdentifier: pid_t(pid))
result["process_marker"] = marker(app) ?? NSNull()
result["app_hidden_before"] = app.map { $0.isHidden } ?? NSNull()
guard result["permission_before"] as? Bool == true, marker(app) == expectedMarker else { finish(); exit(0) }
let before = scan()
result["target_count_before"] = before.0 ?? NSNull()
result["binding_before"] = before.3 ?? NSNull()
if let target = before.1, let window = before.2 {
    result["target_enabled_before"] = boolean(target, kAXEnabledAttribute as String) ?? NSNull()
    result["window_minimized_before"] = boolean(window, kAXMinimizedAttribute as String) ?? NSNull()
    let system = AXUIElementCreateSystemWide()
    AXUIElementSetMessagingTimeout(system, 0.25)
    let fractions: [(Double, Double)] = [(0.5,0.5),(0.25,0.25),(0.75,0.25),(0.25,0.75),(0.75,0.75)]
    var hits: [String] = []
    var supported = true
    for (fx, fy) in fractions {
        if ProcessInfo.processInfo.systemUptime >= deadline { supported = false; break }
        var hit: AXUIElement?
        let error = AXUIElementCopyElementAtPosition(system,
            Float(targetRect.minX + targetRect.width*fx), Float(targetRect.minY + targetRect.height*fy), &hit)
        if error == .notImplemented { supported = false; break }
        guard error == .success, let hit else { hits.append("unknown"); continue }
        var cursor: AXUIElement? = hit
        var onTarget = false
        var hitWindow: AXUIElement?
        for _ in 0...12 {
            guard let current = cursor else { break }
            if CFEqual(current, target) { onTarget = true; break }
            if text(current, kAXRoleAttribute as String) == "AXWindow" { hitWindow = current; break }
            if let parent = attr(current, kAXParentAttribute as String), CFGetTypeID(parent) == AXUIElementGetTypeID() {
                cursor = (parent as! AXUIElement)
            } else { cursor = nil }
        }
        if onTarget { hits.append("target_or_child"); continue }
        var hitPID: pid_t = 0
        if AXUIElementGetPid(hit, &hitPID) == .success && hitPID != pid_t(pid) { hits.append("other_pid") }
        else if let hitWindow, !CFEqual(hitWindow, window) { hits.append("other_window") }
        else if let hitWindow, CFEqual(hitWindow, window) { hits.append("ancestor_only") }
        else { hits.append("unknown") }
    }
    result["hits"] = hits
    result["hit_test_supported"] = supported && hits.count == 5
    // The retained references are valid only in this helper process, during this probe.
    result["target_bbox_stable"] = same(box(target), targetRect)
    result["window_bbox_stable"] = same(box(window), windowRect)
    result["target_enabled_after"] = boolean(target, kAXEnabledAttribute as String) ?? NSNull()
    result["window_minimized_after"] = boolean(window, kAXMinimizedAttribute as String) ?? NSNull()
    let after = scan()
    result["target_count_after"] = after.0 ?? NSNull()
    if let postBound = after.3 {
        result["binding_after"] = (postBound && after.1 != nil && after.2 != nil &&
            CFEqual(after.1!, target) && CFEqual(after.2!, window))
    } else { result["binding_after"] = NSNull() }
} else {
    let after = scan()
    result["target_count_after"] = after.0 ?? NSNull()
    result["binding_after"] = after.3 ?? NSNull()
}
finish()
