import AppKit
import ApplicationServices
import Foundation

// Read-only, Calculator-only. AXValue is read only after a unique reviewed binding.
let input = FileHandle.standardInput.readData(ofLength: 8193)
// JSONSerialization keeps the last duplicate key. Scan this flat descriptor first
// and decode each key string, so escaped spellings cannot hide a duplicate.
func uniqueTopLevelKeys(_ data: Data) -> Bool {
    let bytes = Array(data)
    var index = 0
    func space() { while index < bytes.count && [9, 10, 13, 32].contains(bytes[index]) { index += 1 } }
    space()
    guard index < bytes.count && bytes[index] == 123 else { return false }
    index += 1
    var keys = Set<String>()
    while true {
        space()
        guard index < bytes.count else { return false }
        if bytes[index] == 125 { index += 1; space(); return index == bytes.count }
        guard bytes[index] == 34 else { return false }
        let start = index
        index += 1
        var escaped = false
        while index < bytes.count {
            let byte = bytes[index]
            index += 1
            if escaped { escaped = false; continue }
            if byte == 92 { escaped = true; continue }
            if byte == 34 { break }
        }
        guard index <= bytes.count && bytes[index-1] == 34 else { return false }
        let keyToken = Data([91] + bytes[start..<index] + [93])
        guard let decoded = try? JSONSerialization.jsonObject(with: keyToken) as? [String],
              decoded.count == 1, keys.insert(decoded[0]).inserted else { return false }
        space()
        guard index < bytes.count && bytes[index] == 58 else { return false }
        index += 1
        space()
        guard index < bytes.count else { return false }
        if bytes[index] == 34 {
            index += 1
            escaped = false
            while index < bytes.count {
                let byte = bytes[index]
                index += 1
                if escaped { escaped = false; continue }
                if byte == 92 { escaped = true; continue }
                if byte == 34 { break }
            }
            guard bytes[index-1] == 34 else { return false }
        } else {
            guard bytes[index] != 91 && bytes[index] != 123 else { return false }
            while index < bytes.count && bytes[index] != 44 && bytes[index] != 125 {
                index += 1
            }
        }
        space()
        guard index < bytes.count else { return false }
        if bytes[index] == 125 { index += 1; space(); return index == bytes.count }
        guard bytes[index] == 44 else { return false }
        index += 1
    }
}
guard input.count <= 8192,
      uniqueTopLevelKeys(input),
      let request = try? JSONSerialization.jsonObject(with: input) as? [String: Any],
      let version = request["version"] as? NSNumber,
      CFGetTypeID(version) == CFNumberGetTypeID(),
      ["c","i","s","l","q","C","I","S","L","Q"].contains(String(cString: version.objCType)),
      version.intValue == 1,
      let mode = request["mode"] as? String,
      ["capture","capture_entry","diagnose"].contains(mode) else { exit(2) }
func emit(_ row: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: row), data.count <= 16384 else { exit(2) }
    FileHandle.standardOutput.write(data)
}
let bundle = "com.apple.calculator"
let apps = NSRunningApplication.runningApplications(withBundleIdentifier: bundle)
let app = apps.count == 1 && !apps[0].isTerminated ? apps[0] : nil
let marker = app?.launchDate.map { String(format: "%.6f", $0.timeIntervalSince1970) }
var result: [String: Any] = [
    "version": 1, "status": "unknown", "reason": "APP_NOT_RUNNING",
    "pid": app.map { Int($0.processIdentifier) } ?? 0,
    "process_marker": marker ?? NSNull(), "permission": AXIsProcessTrusted(),
    "region_unique": NSNull(), "value": NSNull(), "diagnostic": []
]
guard let app else { emit(result); exit(0) }
guard AXIsProcessTrusted() else {
    result["reason"] = "AX_PERMISSION_REQUIRED"; emit(result); exit(0)
}
let role: String
let identifier: String
let parentRole: String
let parentIdentifier: String
if mode == "capture" || mode == "capture_entry" {
    let consentKey = mode == "capture_entry" ? "include_current_entry" : "include_result"
    guard request.count == 7, let includeResult = request[consentKey] as? NSNumber,
          CFGetTypeID(includeResult) == CFBooleanGetTypeID(), includeResult.boolValue,
          let r = request["role"] as? String,
          ["AXTextField", "AXStaticText", "AXTextArea"].contains(r),
          let i = request["identifier"] as? String, i.count <= 80,
          let pr = request["parent_role"] as? String, !pr.isEmpty, pr.count <= 80,
          let pi = request["parent_identifier"] as? String, !pi.isEmpty, pi.count <= 80 else { exit(2) }
    if mode == "capture_entry" {
        guard r == "AXStaticText", i.isEmpty, pr == "AXScrollArea", pi == "StandardInputView" else { exit(2) }
    } else {
        guard pi != "StandardInputView",
              !i.isEmpty || (r == "AXStaticText" && pr == "AXScrollArea" && pi == "StandardResultView") else { exit(2) }
    }
    role = r; identifier = i; parentRole = pr; parentIdentifier = pi
} else {
    guard request.count == 2 else { exit(2) }
    role = ""; identifier = ""; parentRole = ""; parentIdentifier = ""
}
func attribute(_ node: AXUIElement, _ key: String) -> CFTypeRef? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(node, key as CFString, &value) == .success ? value : nil
}
func text(_ node: AXUIElement, _ key: String) -> String? {
    guard let value = attribute(node, key), CFGetTypeID(value) == CFStringGetTypeID() else { return nil }
    return value as? String
}
func children(_ node: AXUIElement) -> [AXUIElement] {
    return (attribute(node, kAXChildrenAttribute as String) ??
            attribute(node, kAXWindowsAttribute as String)) as? [AXUIElement] ?? []
}
let deadline = ProcessInfo.processInfo.systemUptime + 4.0
let root = AXUIElementCreateApplication(app.processIdentifier)
AXUIElementSetMessagingTimeout(root, 0.4)
var queue: [(AXUIElement, AXUIElement?, AXUIElement?, Int)] = [(root, nil, nil, 0)]
var seen: [AXUIElement] = []
var windows: [AXUIElement] = []
var matches: [AXUIElement] = []
var diagnostic: [[String: String]] = []
var index = 0
var complete = true
while index < queue.count {
    if seen.count >= 300 || ProcessInfo.processInfo.systemUptime >= deadline { complete = false; break }
    let (node, parent, inheritedWindow, depth) = queue[index]
    index += 1
    if seen.contains(where: { CFEqual($0, node) }) { continue }
    seen.append(node)
    AXUIElementSetMessagingTimeout(node, 0.4)
    let nodeRole = text(node, kAXRoleAttribute as String)
    let nodeID = text(node, kAXIdentifierAttribute as String)
    let window = nodeRole == "AXWindow" ? node : inheritedWindow
    if nodeRole == "AXWindow" { windows.append(node) }
    if mode == "diagnose", let nodeRole,
       ["AXTextField", "AXStaticText", "AXTextArea"].contains(nodeRole),
       diagnostic.count < 8 {
        diagnostic.append(["role": nodeRole, "identifier": String((nodeID ?? "").prefix(80)),
            "parent_role": parent.flatMap { text($0, kAXRoleAttribute as String) } ?? "",
            "parent_identifier": parent.flatMap { text($0, kAXIdentifierAttribute as String) } ?? "",
            "window_role": window.flatMap { text($0, kAXRoleAttribute as String) } ?? ""])
    }
    if mode != "diagnose", let window, parent != nil,
       nodeRole == role, (nodeID ?? "") == identifier,
       text(parent!, kAXRoleAttribute as String) == parentRole,
       text(parent!, kAXIdentifierAttribute as String) == parentIdentifier {
        matches.append(node)
        if !windows.contains(where: { CFEqual($0, window) }) { windows.append(window) }
    }
    let kids = children(node)
    if depth >= 12 { if !kids.isEmpty { complete = false } }
    else { for kid in kids { queue.append((kid, node, window, depth + 1)) } }
}
if !complete {
    result["reason"] = "AX_TRAVERSAL_INCOMPLETE"
} else if mode == "diagnose" {
    result["status"] = "diagnostic"
    result["reason"] = "STRUCTURE_ONLY"
    result["diagnostic"] = diagnostic
} else if windows.count != 1 || matches.count != 1 {
    result["reason"] = mode == "capture_entry" ?
        (matches.isEmpty ? "ENTRY_REGION_NOT_FOUND" : "ENTRY_REGION_AMBIGUOUS") :
        (matches.isEmpty ? "RESULT_REGION_NOT_FOUND" : "RESULT_REGION_AMBIGUOUS")
    result["region_unique"] = false
} else if let value = attribute(matches[0], kAXValueAttribute as String),
          CFGetTypeID(value) == CFStringGetTypeID(), let raw = value as? String,
          !raw.isEmpty, raw.count <= 64 {
    result["status"] = "observed"
    result["reason"] = mode == "capture_entry" ? "ENTRY_VALUE_READ" : "RESULT_VALUE_READ"
    result["region_unique"] = true
    result["value"] = raw
} else {
    result["reason"] = mode == "capture_entry" ? "ENTRY_VALUE_UNAVAILABLE" : "RESULT_VALUE_UNAVAILABLE"
    result["region_unique"] = true
}
// A process restart during collection invalidates the evidence.
let current = NSRunningApplication.runningApplications(withBundleIdentifier: bundle)
if current.count != 1 || current[0].processIdentifier != app.processIdentifier ||
   current[0].launchDate != app.launchDate || !AXIsProcessTrusted() {
    result["status"] = "unknown"; result["reason"] = "PROCESS_OR_PERMISSION_CHANGED"
    result["value"] = NSNull(); result["region_unique"] = NSNull()
}
emit(result)
