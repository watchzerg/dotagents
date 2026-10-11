import Foundation
import Testing

@testable import {{MODULE_NAME}}

@Test func moduleExposesName() {
    #expect({{MODULE_NAME}}.name == "{{DIST_NAME}}")
}

@Test func xcodeMatchesDeclaredVersionLine() throws {
    let root = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
    let pin = try String(contentsOf: root.appendingPathComponent(".xcode-version"), encoding: .utf8)
        .trimmingCharacters(in: .whitespacesAndNewlines)
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/xcodebuild")
    process.arguments = ["-version"]
    let pipe = Pipe()
    process.standardOutput = pipe
    try process.run()
    process.waitUntilExit()
    let output = String(decoding: pipe.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
    let actual =
        output.split(separator: "\n").first.map { String($0).replacingOccurrences(of: "Xcode ", with: "") } ?? ""
    #expect(actual == pin || actual.hasPrefix(pin + "."), "预期 Xcode \(pin)，实际 \(actual)")
}
