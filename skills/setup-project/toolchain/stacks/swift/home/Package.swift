// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "{{MODULE_NAME}}",
    platforms: [.macOS(.v15)],
    targets: [
        .target(name: "{{MODULE_NAME}}"),
        .testTarget(name: "CoreTests", dependencies: ["{{MODULE_NAME}}"], path: "tests/core"),
        // 创建 tests/full/ 时在此追加 FullTests 测试 target（path: "tests/full"）。
    ],
    swiftLanguageModes: [.v6]
)
