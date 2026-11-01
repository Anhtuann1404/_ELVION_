import Foundation
import Vision
import ImageIO

// PNG stdin; bounded OCR JSON or --crop PNG stdout. No files or network access.
do {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard data.count <= 5 * 1024 * 1024,
          let source = CGImageSourceCreateWithData(data as CFData, nil),
          let original = CGImageSourceCreateImageAtIndex(source, 0, nil),
          original.width <= 4096, original.height <= 4096 else { exit(2) }
    if CommandLine.arguments.count >= 2 && ["--crop", "--crop-mark"].contains(CommandLine.arguments[1]) {
        let mark = CommandLine.arguments[1] == "--crop-mark"
        guard CommandLine.arguments.count == (mark ? 10 : 6),
              let x = Int(CommandLine.arguments[2]), let y = Int(CommandLine.arguments[3]),
              let width = Int(CommandLine.arguments[4]), let height = Int(CommandLine.arguments[5]),
              x >= 0, y >= 0, width > 0, height > 0,
              x <= original.width, y <= original.height,
              width <= original.width - x, height <= original.height - y,
              let cropped = original.cropping(to: CGRect(x: x, y: y, width: width, height: height)) else { exit(2) }
        var outputImage = cropped
        if mark {
            guard let bx = Double(CommandLine.arguments[6]), let by = Double(CommandLine.arguments[7]),
                  let bw = Double(CommandLine.arguments[8]), let bh = Double(CommandLine.arguments[9]),
                  bx.isFinite, by.isFinite, bw.isFinite, bh.isFinite,
                  bx >= 0, by >= 0, bw > 0, bh > 0,
                  bx + bw <= Double(width), by + bh <= Double(height),
                  let context = CGContext(data: nil, width: width, height: height,
                    bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
                    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(2) }
            context.draw(cropped, in: CGRect(x: 0, y: 0, width: width, height: height))
            context.setStrokeColor(CGColor(red: 1, green: 0, blue: 0, alpha: 1))
            context.setLineWidth(1)
            // Outside the OCR text box; never replace or mask its glyph pixels.
            context.stroke(CGRect(x: bx-3, y: Double(height)-by-bh-3, width: bw+6, height: bh+6))
            guard let image = context.makeImage() else { exit(2) }
            outputImage = image
        }
        let output = NSMutableData()
        guard let destination = CGImageDestinationCreateWithData(output, "public.png" as CFString, 1, nil) else { exit(2) }
        CGImageDestinationAddImage(destination, outputImage, nil)
        guard CGImageDestinationFinalize(destination), output.length <= 5 * 1024 * 1024 else { exit(2) }
        FileHandle.standardOutput.write(output as Data)
        exit(0)
    }
    let profile = CommandLine.arguments.count >= 2 ? CommandLine.arguments[1] : "native-v1"
    let segments = CommandLine.arguments.count == 3 && CommandLine.arguments[2] == "--segments"
    let label = CommandLine.arguments.count == 4 && CommandLine.arguments[2] == "--label" ? CommandLine.arguments[3] : nil
    guard (CommandLine.arguments.count <= 2 || segments || label != nil),
          ["native-v1", "upscale2x-v2"].contains(profile) else { exit(2) }
    if let label = label {
        guard !label.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              label.count <= 256, !label.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) else { exit(2) }
    }
    var image = original
    if profile == "upscale2x-v2" && original.width <= 2048 && original.height <= 2048 {
        guard let context = CGContext(data: nil, width: original.width * 2, height: original.height * 2,
            bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(2) }
        context.interpolationQuality = .high
        context.draw(original, in: CGRect(x: 0, y: 0, width: original.width * 2, height: original.height * 2))
        guard let enlarged = context.makeImage() else { exit(2) }
        image = enlarged
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["en-US"]
    request.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    let results = request.results ?? []
    guard results.count <= 512 else { exit(2) }
    var rows: [[String: Any]] = []
    for observation in results {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let b = observation.boundingBox
        rows.append(["text": candidate.string, "confidence": Double(candidate.confidence),
                "bbox": [b.minX * Double(original.width),
                         (1 - b.maxY) * Double(original.height),
                         b.width * Double(original.width), b.height * Double(original.height)]])
        if label != nil || (segments && candidate.string.contains(where: { "•·|".contains($0) })) {
            let text = candidate.string
            var start = text.startIndex
            var ranges: [Range<String.Index>] = []
            if let label = label {
                // Native substring geometry only. Preserve attached punctuation so
                // extracting Publish from Publish. cannot manufacture an exact label.
                var search = text.startIndex..<text.endIndex
                while let match = text.range(of: label, options: [.caseInsensitive, .diacriticInsensitive], range: search) {
                    let beforeOK = match.lowerBound == text.startIndex || text[text.index(before: match.lowerBound)].isWhitespace || "•·|".contains(text[text.index(before: match.lowerBound)])
                    let afterOK = match.upperBound == text.endIndex || !text[match.upperBound].isLetter && !text[match.upperBound].isNumber
                    if beforeOK && afterOK {
                        var end = match.upperBound
                        while end < text.endIndex && !text[end].isWhitespace && !"•·|".contains(text[end]) { end = text.index(after: end) }
                        ranges.append(match.lowerBound..<end)
                    }
                    search = match.upperBound..<text.endIndex
                }
            } else {
                for index in text.indices where "•·|".contains(text[index]) {
                    ranges.append(start..<index)
                    start = text.index(after: index)
                }
                ranges.append(start..<text.endIndex)
            }
            for range in ranges {
                var lo = range.lowerBound
                var hi = range.upperBound
                while lo < hi && text[lo].isWhitespace { lo = text.index(after: lo) }
                while lo < hi && text[text.index(before: hi)].isWhitespace { hi = text.index(before: hi) }
                guard lo < hi, let rectangle = try candidate.boundingBox(for: lo..<hi) else { continue }
                let s = rectangle.boundingBox
                // Some providers return the full line for a subrange. Never use that
                // as the location of an individual label, or invent a proportional box.
                guard s.width > 0, s.height > 0, s.width < b.width * 0.95,
                      s.minX >= b.minX - 0.0001, s.maxX <= b.maxX + 0.0001 else { continue }
                rows.append(["text": String(text[lo..<hi]), "confidence": Double(candidate.confidence),
                    "bbox": [s.minX * Double(original.width), (1-s.maxY) * Double(original.height),
                             s.width * Double(original.width), s.height * Double(original.height)]])
            }
        }
    }
    guard rows.count <= 512 else { exit(2) }
    let output = try JSONSerialization.data(withJSONObject: ["version": 1, "lines": rows])
    guard output.count <= 256 * 1024 else { exit(2) }
    FileHandle.standardOutput.write(output)
} catch { exit(2) }
