import Foundation
import CoreGraphics
import ImageIO

// Bounded PNG-only presentation resize. No OCR, network, files, or input events.
let args = CommandLine.arguments
guard args.count == 2, let factor = Int(args[1]), [2, 4].contains(factor) else { exit(2) }
let data = FileHandle.standardInput.readDataToEndOfFile()
guard data.count <= 5 * 1024 * 1024,
      let source = CGImageSourceCreateWithData(data as CFData, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil),
      image.width > 0, image.height > 0,
      image.width <= 4096 / factor, image.height <= 4096 / factor,
      let context = CGContext(data: nil, width: image.width * factor, height: image.height * factor,
        bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(2) }
context.interpolationQuality = .high
context.draw(image, in: CGRect(x: 0, y: 0, width: image.width * factor, height: image.height * factor))
guard let scaled = context.makeImage() else { exit(2) }
let output = NSMutableData()
guard let destination = CGImageDestinationCreateWithData(output, "public.png" as CFString, 1, nil) else { exit(2) }
CGImageDestinationAddImage(destination, scaled, nil)
guard CGImageDestinationFinalize(destination), output.length <= 5 * 1024 * 1024 else { exit(2) }
FileHandle.standardOutput.write(output as Data)
