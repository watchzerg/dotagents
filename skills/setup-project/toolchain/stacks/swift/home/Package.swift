// swift-tools-version: 6.0
import Foundation
import PackageDescription

/// 测试目录可能与 uv 共用（tests/core 里会有 .py 与 __pycache__）：排除其中的非 Swift 文件，
/// 避免 SwiftPM 告警 unhandled files。按实际存在的文件计算，不会因路径缺失再告警 Invalid Exclude；
/// recipe 用 --manifest-cache none 让新增文件即时生效。
func nonSwiftFiles(in directory: String) -> [String] {
    let root = Context.packageDirectory + "/" + directory
    return (FileManager.default.subpaths(atPath: root) ?? []).filter { path in
        var isDirectory: ObjCBool = false
        FileManager.default.fileExists(atPath: root + "/" + path, isDirectory: &isDirectory)
        return !isDirectory.boolValue && !path.hasSuffix(".swift")
    }
}

let package = Package(
    name: "{{MODULE_NAME}}",
    platforms: [.macOS(.v15)],
    targets: [
        .target(name: "{{MODULE_NAME}}"),
        .testTarget(
            name: "CoreTests",
            dependencies: ["{{MODULE_NAME}}"],
            path: "tests/core",
            exclude: nonSwiftFiles(in: "tests/core")
        ),
        // 创建 tests/full/ 时在此追加 FullTests 测试 target（path: "tests/full"，exclude: nonSwiftFiles(in: "tests/full")）。
    ],
    swiftLanguageModes: [.v6]
)
