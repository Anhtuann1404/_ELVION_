import AppKit
import ApplicationServices
import CoreGraphics
import Foundation
import Darwin

// Private parent-owned pipes. This is not an authentication service for other callers.
func readObject(_ timeout: Double) -> [String: Any]? {
    let end = ProcessInfo.processInfo.systemUptime + timeout
    var data = Data()
    while data.count < 16384 {
        let remaining = end - ProcessInfo.processInfo.systemUptime
        if remaining <= 0 { return nil }
        var descriptor = pollfd(fd: STDIN_FILENO, events: Int16(POLLIN), revents: 0)
        if poll(&descriptor, 1, Int32(remaining * 1000)) <= 0 { return nil }
        let byte = FileHandle.standardInput.readData(ofLength: 1)
        if byte.isEmpty { return nil }
        if byte.first == 10 {
            return (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        }
        data.append(byte)
    }
    return nil
}
func integer(_ value: Any?) -> Int? {
    guard let n = value as? NSNumber, CFGetTypeID(n) != CFBooleanGetTypeID(),
          n.doubleValue.isFinite, n.doubleValue == Double(n.int64Value) else { return nil }
    return Int(exactly: n.int64Value)
}
func rectangle(_ value: Any?) -> CGRect? {
    guard let a = value as? [NSNumber], a.count == 4,
          a.allSatisfy({ CFGetTypeID($0) != CFBooleanGetTypeID() && $0.doubleValue.isFinite }),
          a[2].doubleValue > 0, a[3].doubleValue > 0 else { return nil }
    return CGRect(x:a[0].doubleValue,y:a[1].doubleValue,width:a[2].doubleValue,height:a[3].doubleValue)
}
guard let request = readObject(2), Set(request.keys) == Set([
    "version","nonce","digest","expires_at","pid","process_marker","target_bbox","window_bbox","displays"]),
    integer(request["version"]) == 1,
    let nonce = request["nonce"] as? String, UUID(uuidString:nonce) != nil,
    let digest = request["digest"] as? String, digest.count == 64,
    digest.allSatisfy({ "0123456789abcdef".contains($0) }),
    let expiry = request["expires_at"] as? NSNumber, CFGetTypeID(expiry) != CFBooleanGetTypeID(),
    expiry.doubleValue.isFinite,
    let pid = integer(request["pid"]), pid > 0, pid <= Int(Int32.max),
    let expectedMarker = request["process_marker"] as? String, !expectedMarker.isEmpty,
    let targetRect = rectangle(request["target_bbox"]), let windowRect = rectangle(request["window_bbox"]),
    let displays = request["displays"] as? [[String:Any]], !displays.isEmpty, displays.count <= 16,
    windowRect.contains(targetRect) else { exit(2) }
let bundle = "com.apple.calculator"
let label = "7"
let subrole: String? = nil
let expiresAt = expiry.doubleValue
var deadline = ProcessInfo.processInfo.systemUptime + 1.8
var finalPhase = false
func emit(_ status:String, _ reason:String, _ code:Int = 0) {
    var row:[String:Any] = ["version":1,"nonce":nonce,"status":status,"reason":reason]
    if finalPhase { row["native_error"] = code }
    if let data = try? JSONSerialization.data(withJSONObject:row) {
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([10]))
    }
}
func stop(_ reason:String) -> Never { emit("blocked",reason); exit(0) }
func marker(_ app:NSRunningApplication?) -> String? {
    guard let app, !app.isTerminated, app.bundleIdentifier == bundle,
          let date = app.launchDate else { return nil }
    return String(format:"%.6f",date.timeIntervalSince1970)
}
func authorizedTime() -> Bool {
    let now = Date().timeIntervalSince1970
    return now < expiresAt && expiresAt-now <= 65
}
func layoutMatches() -> Bool {
    var ids = [CGDirectDisplayID](repeating:0,count:16)
    var count:UInt32 = 0
    guard CGGetActiveDisplayList(16,&ids,&count) == .success, count == displays.count else { return false }
    var expected = Set<UInt32>()
    var containing = 0
    for row in displays {
        guard Set(row.keys) == Set(["id","bbox","scale"]),
              let id = integer(row["id"]), id > 0, id <= Int(UInt32.max),
              let rect = rectangle(row["bbox"]),
              let scale = row["scale"] as? NSNumber, CFGetTypeID(scale) != CFBooleanGetTypeID(),
              scale.doubleValue.isFinite, scale.doubleValue > 0,
              let screen = NSScreen.screens.first(where: {
                  ($0.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value == UInt32(id)
              }), abs(screen.backingScaleFactor-scale.doubleValue) <= 0.001 else { return false }
        let native = CGDisplayBounds(UInt32(id))
        guard abs(native.minX-rect.minX)<=0.5, abs(native.minY-rect.minY)<=0.5,
              abs(native.width-rect.width)<=0.5, abs(native.height-rect.height)<=0.5 else { return false }
        expected.insert(UInt32(id))
        if rect.contains(targetRect) { containing += 1 }
    }
    return expected.count == displays.count && expected == Set(ids.prefix(Int(count))) && containing == 1
}
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
        guard let role = text(node, kAXRoleAttribute as String) else { return (nil,nil,nil,nil) }
        let window: AXUIElement? = role == "AXWindow" ? node : inheritedWindow
        if role == "AXWindow", same(box(node), windowRect) { windows.append(node) }
        if role == "AXButton" {
            let raw = text(node, kAXTitleAttribute as String) ?? text(node, kAXDescriptionAttribute as String)
            let windowControl = parent != nil && text(parent!, kAXRoleAttribute as String) == "AXWindow" &&
                ["AXCloseButton", "AXMinimizeButton", "AXZoomButton", "AXFullScreenButton"].contains(
                    text(node, kAXSubroleAttribute as String) ?? "")
            if !windowControl && (raw == nil || raw!.isEmpty) { return (nil,nil,nil,nil) }
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

func processMatches() -> Bool {
    let apps = NSRunningApplication.runningApplications(withBundleIdentifier:bundle)
    return apps.count == 1 && apps[0].processIdentifier == pid_t(pid) &&
        marker(apps[0]) == expectedMarker && !apps[0].isHidden
}
func validState(_ target:AXUIElement,_ window:AXUIElement) -> Bool {
    return processMatches() && AXIsProcessTrusted() &&
        text(target,kAXRoleAttribute as String) == "AXButton" &&
        (text(target,kAXTitleAttribute as String) ?? text(target,kAXDescriptionAttribute as String)) == "7" &&
        boolean(target,kAXEnabledAttribute as String) == true &&
        boolean(window,kAXMinimizedAttribute as String) == false &&
        same(box(target),targetRect) && same(box(window),windowRect)
}
func fivePoints(_ target:AXUIElement) -> Bool {
    let system = AXUIElementCreateSystemWide()
    AXUIElementSetMessagingTimeout(system,0.25)
    for (fx,fy) in [(0.5,0.5),(0.25,0.25),(0.75,0.25),(0.25,0.75),(0.75,0.75)] {
        if ProcessInfo.processInfo.systemUptime >= deadline { return false }
        var hit:AXUIElement?
        guard AXUIElementCopyElementAtPosition(system,Float(targetRect.minX+targetRect.width*fx),
            Float(targetRect.minY+targetRect.height*fy),&hit) == .success, let hit else { return false }
        var cursor:AXUIElement? = hit
        var found = false
        for _ in 0...12 {
            guard let current = cursor else { break }
            AXUIElementSetMessagingTimeout(current,0.25)
            if CFEqual(current,target) { found = true; break }
            guard let parent = attr(current,kAXParentAttribute as String),
                  CFGetTypeID(parent) == AXUIElementGetTypeID() else { break }
            cursor = (parent as! AXUIElement)
        }
        if !found { return false }
    }
    return true
}
if !authorizedTime() { stop("AUTHORIZATION_EXPIRED") }
if !AXIsProcessTrusted() { stop("AX_PERMISSION_UNAVAILABLE") }
if !layoutMatches() { stop("DISPLAY_LAYOUT_CHANGED") }
let before = scan()
guard before.3 == true, let target = before.1, let window = before.2,
      validState(target,window) else { stop("TARGET_CHANGED") }
func supportsPress(_ node:AXUIElement) -> Bool {
    var names:CFArray?
    guard AXUIElementCopyActionNames(node,&names) == .success,
          let actions = names as? [String] else { return false }
    return actions.contains(kAXPressAction as String)
}
if !supportsPress(target) { stop("AXPRESS_UNSUPPORTED") }
if !fivePoints(target) { stop("SAMPLED_VISIBILITY_UNCERTAIN") }
if !validState(target,window) || !layoutMatches() { stop("TARGET_CHANGED") }
if ProcessInfo.processInfo.systemUptime >= deadline { stop("PROBE_TOO_LONG") }
emit("prepared","PREPARED")
let preparedAt = ProcessInfo.processInfo.systemUptime
guard let commit = readObject(1), Set(commit.keys) == Set(["version","command","nonce","digest"]),
      integer(commit["version"]) == 1, commit["command"] as? String == "commit",
      commit["nonce"] as? String == nonce, commit["digest"] as? String == digest,
      ProcessInfo.processInfo.systemUptime-preparedAt <= 1 else { exit(0) }
finalPhase = true
deadline = ProcessInfo.processInfo.systemUptime + 1.8
if !authorizedTime() { stop("AUTHORIZATION_EXPIRED") }
let after = scan()
guard after.3 == true, let again = after.1, let againWindow = after.2,
      CFEqual(again,target), CFEqual(againWindow,window), validState(target,window) else { stop("TARGET_CHANGED") }
if !layoutMatches() { stop("DISPLAY_LAYOUT_CHANGED") }
if !fivePoints(target) { stop("SAMPLED_VISIBILITY_UNCERTAIN") }
if !authorizedTime() { stop("AUTHORIZATION_EXPIRED") }
if !validState(target,window) || !layoutMatches() { stop("TARGET_CHANGED") }
if ProcessInfo.processInfo.systemUptime >= deadline { stop("PROBE_TOO_LONG") }
if !supportsPress(target) { stop("AXPRESS_UNSUPPORTED") }
// Sole mutation site. An AX error does not prove that no effect occurred.
AXUIElementSetMessagingTimeout(target,0.75)
if !authorizedTime() { stop("AUTHORIZATION_EXPIRED") }
if ProcessInfo.processInfo.systemUptime >= deadline { stop("PROBE_TOO_LONG") }
let actionError = AXUIElementPerformAction(target,kAXPressAction as CFString)
emit(actionError == .success ? "dispatched" : "uncertain",
     actionError == .success ? "AXPRESS_RETURNED" : "AXPRESS_ERROR",Int(actionError.rawValue))
