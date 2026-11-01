import Foundation
import AVFoundation

func emitError(_ code: String) -> Never {
    let msg = "{\"event\": \"error\", \"code\": \"\(code)\"}\n"
    if let data = msg.data(using: .utf8) {
        FileHandle.standardError.write(data)
    }
    exit(1)
}

// 1. Check or request microphone permission
let status = AVCaptureDevice.authorizationStatus(for: .audio)
if status == .denied || status == .restricted {
    emitError("MIC_PERMISSION_DENIED")
} else if status == .notDetermined {
    let semaphore = DispatchSemaphore(value: 0)
    var granted = false
    AVCaptureDevice.requestAccess(for: .audio) { allowed in
        granted = allowed
        semaphore.signal()
    }
    _ = semaphore.wait(timeout: .now() + 20)
    if !granted {
        emitError("MIC_PERMISSION_DENIED")
    }
}

// 2. Initialize AVAudioEngine
let engine = AVAudioEngine()
let inputNode = engine.inputNode
let inputFormat = inputNode.inputFormat(forBus: 0)

// Target format: 16000 Hz, 1 channel, Int16 (Linear PCM)
guard let targetFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true) else {
    emitError("FORMAT_CREATION_FAILED")
}

guard let converter = AVAudioConverter(from: inputFormat, to: targetFormat) else {
    emitError("CONVERTER_INIT_FAILED")
}

// 3. Install tap on inputNode
inputNode.installTap(onBus: 0, bufferSize: 2048, format: inputFormat) { (buffer, time) in
    let frameCapacity = AVAudioFrameCount(Double(buffer.frameLength) * 16000.0 / inputFormat.sampleRate + 128)
    guard let convertedBuffer = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: frameCapacity) else { return }

    var error: NSError?
    var allRead = false
    let inputBlock: AVAudioConverterInputBlock = { inNumPackets, outStatus in
        if allRead {
            outStatus.pointee = .noDataNow
            return nil
        }
        allRead = true
        outStatus.pointee = .haveData
        return buffer
    }

    let status = converter.convert(to: convertedBuffer, error: &error, withInputFrom: inputBlock)
    if (status == .haveData || status == .inputRanDry) && convertedBuffer.frameLength > 0 {
        if let channels = convertedBuffer.int16ChannelData {
            let dataSize = Int(convertedBuffer.frameLength) * MemoryLayout<Int16>.size
            let rawPtr = UnsafeRawPointer(channels.pointee)
            FileHandle.standardOutput.write(Data(bytes: rawPtr, count: dataSize))
        }
    }
}

// 4. Start audio engine
do {
    try engine.start()
    let readyMsg = "{\"event\": \"stream_ready\"}\n"
    if let data = readyMsg.data(using: .utf8) {
        FileHandle.standardError.write(data)
    }
} catch {
    emitError("ENGINE_START_FAILED")
}

// 5. Run until stdin closes
DispatchQueue.global().async {
    _ = readLine()
    engine.stop()
    exit(0)
}

RunLoop.current.run()
