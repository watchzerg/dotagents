## 环境

Xcode 按 `{{HOME}}.xcode-version` 的版本 line 核对，SwiftPM 按 `Package.swift` 解析依赖并提交 `Package.resolved`。工具一律用 Xcode 自带的 `swift` 与 `xcrun swift format`，不安装独立 Swift 工具链。
