import Foundation
import ScreenCaptureKit
import AVFoundation

class AudioRecorder: NSObject, SCStreamOutput, SCStreamDelegate {
    var stream: SCStream?
    var assetWriter: AVAssetWriter?
    var audioInput: AVAssetWriterInput?
    var isRecording = false
    var sessionStarted = false
    let outputURL: URL
    
    init(outputURL: URL) {
        self.outputURL = outputURL
        super.init()
    }
    
    func start() async throws {
        let content = try await SCShareableContent.current
        guard let display = content.displays.first else {
            fputs("ERROR: No display found\n", stderr)
            exit(1)
        }
        
        let config = SCStreamConfiguration()
        config.capturesAudio = true
        config.excludesCurrentProcessAudio = false
        config.width = 2
        config.height = 2
        config.minimumFrameInterval = CMTime(value: 1, timescale: 1)
        
        let filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])
        
        try? FileManager.default.removeItem(at: outputURL)
        let writer = try AVAssetWriter(outputURL: outputURL, fileType: .m4a)
        
        let audioSettings: [String: Any] = [
            AVFormatIDKey: kAudioFormatMPEG4AAC,
            AVNumberOfChannelsKey: 2,
            AVSampleRateKey: 44100,
            AVEncoderBitRateKey: 192000
        ]
        
        let input = AVAssetWriterInput(mediaType: .audio, outputSettings: audioSettings)
        input.expectsMediaDataInRealTime = true
        writer.add(input)
        
        self.assetWriter = writer
        self.audioInput = input
        
        writer.startWriting()
        
        let stream = SCStream(filter: filter, configuration: config, delegate: self)
        try stream.addStreamOutput(self, type: .audio, sampleHandlerQueue: DispatchQueue(label: "audioQueue"))
        self.stream = stream
        
        try await stream.startCapture()
        isRecording = true
        fputs("STARTED\n", stdout)
        fflush(stdout)
    }
    
    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio else { return }
        guard isRecording, let writer = assetWriter, let input = audioInput else { return }
        
        let pts = CMSampleBufferGetPresentationTimeStamp(sampleBuffer)
        if !sessionStarted {
            writer.startSession(atSourceTime: pts)
            sessionStarted = true
        }
        if writer.status == .writing && input.isReadyForMoreMediaData {
            input.append(sampleBuffer)
        }
    }
    
    func stop() async {
        guard isRecording else { return }
        isRecording = false
        if let stream = stream {
            try? await stream.stopCapture()
        }
        audioInput?.markAsFinished()
        await assetWriter?.finishWriting()
        fputs("STOPPED\n", stdout)
        fflush(stdout)
    }
}

guard CommandLine.arguments.count > 1 else {
    fputs("Usage: sck_audio_recorder <output_file.m4a>\n", stderr)
    exit(1)
}

let outputPath = CommandLine.arguments[1]
let outputURL = URL(fileURLWithPath: outputPath)
let recorder = AudioRecorder(outputURL: outputURL)

let sigintSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
sigintSource.setEventHandler {
    Task {
        await recorder.stop()
        exit(0)
    }
}
signal(SIGINT, SIG_IGN)
sigintSource.resume()

let sigtermSource = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
sigtermSource.setEventHandler {
    Task {
        await recorder.stop()
        exit(0)
    }
}
signal(SIGTERM, SIG_IGN)
sigtermSource.resume()

Task {
    do {
        try await recorder.start()
    } catch {
        fputs("START_FAILED: \(error)\n", stderr)
        exit(10)
    }
}

RunLoop.main.run()
