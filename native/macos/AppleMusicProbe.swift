import AppKit
import Foundation

// Read-only native probe for Apple Music on macOS.
// Queries NSRunningApplication and Apple Events without launching the app if closed.

let bundleID = "com.apple.Music"
let apps = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID)
var pids: [Int] = []

for app in apps {
    if !app.isTerminated {
        pids.append(Int(app.processIdentifier))
    }
}

var result: [String: Any] = [
    "bundle_id": bundleID,
    "running": !pids.isEmpty,
    "pids": pids,
]

if !pids.isEmpty {
    let scriptSource = """
    tell application "Music"
        set pState to player state as string
        set pVol to sound volume
        set hasTrack to false
        set trName to ""
        set trArtist to ""
        set trPersistentID to ""
        try
            set cur to current track
            set trName to name of cur
            set trArtist to artist of cur
            set trPersistentID to persistent ID of cur
            set hasTrack to true
        end try
        return pState & "|||" & pVol & "|||" & hasTrack & "|||" & trName & "|||" & trArtist & "|||" & trPersistentID
    end tell
    """

    if let appleScript = NSAppleScript(source: scriptSource) {
        var errorDict: NSDictionary?
        let descriptor = appleScript.executeAndReturnError(&errorDict)
        if errorDict == nil, let output = descriptor.stringValue {
            let parts = output.components(separatedBy: "|||")
            if parts.count >= 6 {
                result["player_state"] = parts[0]
                result["volume"] = Int(parts[1]) ?? 100
                let hasTrack = (parts[2] == "true")
                result["has_track"] = hasTrack
                if hasTrack {
                    result["current_track"] = [
                        "name": parts[3],
                        "artist": parts[4],
                        "persistent_id": parts[5],
                    ]
                }
            }
        } else {
            result["apple_events_error"] = true
        }
    }
}

if let jsonData = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
   let jsonString = String(data: jsonData, encoding: .utf8) {
    print(jsonString)
} else {
    print("{\"running\":false,\"error\":\"JSON_SERIALIZATION_FAILED\"}")
}
