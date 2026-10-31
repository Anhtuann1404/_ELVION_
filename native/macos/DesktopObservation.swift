import AppKit
import ApplicationServices
import Foundation

// Read-only AX helper. Never request permission or perform an AX action.
let args = CommandLine.arguments
let includeLabels = args.count == 3 && args[2] == "--include-labels"

func emit(_ status: String, _ snapshot: [String: Any]? = nil, _ reason: String? = nil) {
    let envelope: [String: Any] = [
        "version": 1, "status": status,
        "snapshot": snapshot ?? NSNull(), "reason": reason ?? NSNull()
    ]
    guard let data = try? JSONSerialization.data(withJSONObject: envelope),
          data.count <= 1_048_576 else { exit(2) }
    FileHandle.standardOutput.write(data)
}

guard (args.count == 2 || includeLabels), args[1] == "com.apple.calculator" else {
    emit("unsupported", nil, "UNSUPPORTED_REQUEST")
    exit(0)
}
guard AXIsProcessTrusted() else {
    emit("permission_required", nil, "AX_PERMISSION_REQUIRED")
    exit(0)
}
guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: args[1])
    .first(where: { !$0.isTerminated }) else {
    emit("app_not_running", nil, "APP_NOT_RUNNING")
    exit(0)
}

func attribute(_ node: AXUIElement, _ name: String) -> CFTypeRef? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(node, name as CFString, &value) == .success ? value : nil
}

func stringAttribute(_ node: AXUIElement, _ name: String) -> String? {
    guard let value = attribute(node, name), CFGetTypeID(value) == CFStringGetTypeID(),
          let text = value as? String, !text.isEmpty else { return nil }
    let clean = String(text.prefix(256)).filter {
        !$0.unicodeScalars.contains(where: CharacterSet.controlCharacters.contains)
    }
    return clean.isEmpty ? nil : clean
}

func enabledAttribute(_ node: AXUIElement) -> Any {
    guard let value = attribute(node, kAXEnabledAttribute as String),
          CFGetTypeID(value) == CFBooleanGetTypeID() else { return NSNull() }
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

func box(_ node: AXUIElement) -> Any {
    guard let p = point(attribute(node, kAXPositionAttribute as String)),
          let s = size(attribute(node, kAXSizeAttribute as String)),
          p.x.isFinite, p.y.isFinite, s.width.isFinite, s.height.isFinite,
          s.width > 0, s.height > 0 else { return NSNull() }
    return [Double(p.x), Double(p.y), Double(s.width), Double(s.height)]
}

func children(_ node: AXUIElement) -> [AXUIElement] {
    let raw = attribute(node, kAXChildrenAttribute as String)
        ?? attribute(node, kAXWindowsAttribute as String)
    return raw as? [AXUIElement] ?? []
}

let started = ProcessInfo.processInfo.systemUptime
let deadline = started + 4.0
let root = AXUIElementCreateApplication(app.processIdentifier)
AXUIElementSetMessagingTimeout(root, 1.0)
guard stringAttribute(root, kAXRoleAttribute as String) != nil else {
    emit("error", nil, "AX_ROOT_UNREADABLE")
    exit(0)
}
var queue: [(AXUIElement, String?, Int)] = [(root, nil, 0)]
var seen: [AXUIElement] = []
var rows: [[String: Any]] = []
var truncatedReason: String? = nil
var index = 0

while index < queue.count {
    if ProcessInfo.processInfo.systemUptime >= deadline {
        truncatedReason = "TIME_BUDGET"
        break
    }
    if rows.count >= 300 {
        truncatedReason = "NODE_LIMIT"
        break
    }
    let (node, parent, depth) = queue[index]
    index += 1
    if seen.contains(where: { CFEqual($0, node) }) { continue }
    seen.append(node)
    AXUIElementSetMessagingTimeout(node, 1.0)
    let id = "n\(rows.count)"
    var row: [String: Any] = [
        "id": id, "parent_id": parent ?? NSNull(),
        "role": stringAttribute(node, kAXRoleAttribute as String) ?? NSNull(),
        "subrole": stringAttribute(node, kAXSubroleAttribute as String) ?? NSNull(),
        "enabled": enabledAttribute(node), "bbox": box(node), "label": NSNull()
    ]
    if includeLabels {
        row["label"] = stringAttribute(node, kAXTitleAttribute as String)
            ?? stringAttribute(node, kAXDescriptionAttribute as String) ?? NSNull()
    }
    rows.append(row)
    let kids = children(node)
    if depth >= 12 {
        if !kids.isEmpty { truncatedReason = "DEPTH_LIMIT" }
        continue
    }
    for child in kids { queue.append((child, id, depth + 1)) }
}

let iso = ISO8601DateFormatter()
iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
let snapshot: [String: Any] = [
    "schema_version": 1, "id": UUID().uuidString,
    "bundle_id": args[1], "pid": Int(app.processIdentifier),
    "captured_at_utc": iso.string(from: Date()),
    "captured_at_monotonic_ns": Int64(ProcessInfo.processInfo.systemUptime * 1_000_000_000),
    "elements": rows, "truncated": truncatedReason != nil,
    "truncation_reason": truncatedReason ?? NSNull()
]
emit("observed", snapshot)
