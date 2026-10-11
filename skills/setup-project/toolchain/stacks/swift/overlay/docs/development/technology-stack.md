## 运行时与工具链

使用完整 Xcode 及其附带的 Swift compiler、SwiftPM、swift-format 与 Swift Testing，不另外安装独立 Swift 工具链，也不引入 mise、SwiftLint 或工程生成器。`.xcode-version` 声明采用的 Xcode 版本 line，`check-toolchain` 核对实际版本；Xcode 由系统侧安装和更新，项目命令不下载或切换 Xcode。代码以 SwiftPM package 组织（`Package.swift`，Swift 6 language mode）；需要应用壳时在 Xcode 创建工程并把 package 作为本地依赖，共享 scheme 纳入版本控制，再把 justfile 的 `swift-*` recipe 切到 `xcodebuild`。swift-format 负责格式化与 lint，`swift build` 的编译结果即类型检查，Swift Testing 承担 core 测试与原生集成；UI 自动化用 XCTest + XCUIAutomation 并归入 full。工具链版本、语言模式与最低系统分别维护，以 `.xcode-version` 与 `Package.swift` 为可执行依据。

## 依赖政策

只在当前需求需要时引入依赖，先用系统框架与标准库。外部 Swift 包在 `Package.swift` 用 `from:` 声明版本下限，遵循 SwiftPM 的同主版本升级范围；首次解析后提交 `Package.resolved`，没有外部依赖时不创建空锁文件；声明与锁定不一致时明确失败，不静默升级。原生动态库（如 Homebrew 安装的 C 库）不由 SwiftPM 锁定，其来源、版本、头文件与链接配置单独管理并写入本文。升级集中进行并跑完整门禁。

需要相应能力时优先选用：macOS 主界面 AppKit，辅助界面按需 SwiftUI 且不复制共享业务状态；设置与缓存用 JSON 原子写入 Application Support 或 `UserDefaults`，不预建数据库；媒体解码优先系统框架（Image I/O、AVFoundation），不足时再评估原生库。不要仅因清单存在而采用。

## 已选依赖

当前无外部 Swift 包；测试依赖 Xcode 自带的 Swift Testing。引入依赖时在此登记选择理由或 ADR 链接。
