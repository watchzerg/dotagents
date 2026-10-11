# ---- {{LABEL}}：{{HOME_DIR}} ----

# 工具链检查：xcodebuild 存在，Xcode 版本符合 .xcode-version 的版本 line。
[private]
swift-check-toolchain:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    command -v xcodebuild >/dev/null || { echo '错误：缺少 Xcode；请安装 Xcode 并用 xcode-select 指向它。' >&2; exit 1; }
    line="$(tr -d '[:space:]' < .xcode-version)"
    actual="$(xcodebuild -version | sed -n '1s/^Xcode //p')"
    case "$actual" in
      "$line"|"$line".*) echo "Xcode=${actual}；工具链检查通过" ;;
      *) echo "错误：Xcode 版本 ${actual} 不属于 line ${line}；请安装对应 Xcode 或更新 .xcode-version。" >&2; exit 1 ;;
    esac

# 按 Package.resolved 解析依赖；不安装或切换 Xcode。
[private]
swift-install:
    cd {{HOME_DIR}} && swift package resolve

# 默认处理 Sources、tests 与 Package.swift。
[private]
swift-fmt *paths:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    if [ "$#" -eq 0 ]; then set -- Sources tests Package.swift; fi
    xcrun swift format format --in-place --recursive --configuration .swift-format "$@"

[private]
swift-lint:
    cd {{HOME_DIR}} && xcrun swift format lint --strict --recursive --configuration .swift-format Sources tests Package.swift

# 编译全部 target（含测试）即类型检查。
[private]
swift-typecheck:
    cd {{HOME_DIR}} && swift build --build-tests

# 运行 swift test 并把零匹配视为失败；无参数时等于 --filter CoreTests。
[private]
swift-run-tests *args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    if [ "$#" -eq 0 ]; then set -- --filter CoreTests; fi
    log="$(mktemp)"
    trap 'rm -f "$log"' EXIT
    swift test "$@" 2>&1 | tee "$log"
    if grep -q 'No matching test cases were run' "$log"; then
      echo '错误：没有匹配的测试；零匹配不是通过。' >&2
      exit 1
    fi

# 默认运行 CoreTests；可传 swift test 参数定向。
[private]
swift-test *args:
    @just swift-run-tests "$@"

# 全部 core 测试，不接受筛选参数。
[private]
swift-test-core:
    @just swift-run-tests --filter CoreTests

# tests/full 目录出现即纳入；目录存在但 Package.swift 未声明 FullTests 或零匹配视为失败。
[private]
swift-test-full:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -d {{HOME}}tests/full ]; then
      echo '提示：{{HOME}}tests/full 不存在，{{LABEL}} 尚无 full 测试。'
      exit 0
    fi
    grep -q 'name: "FullTests"' {{HOME}}Package.swift || { echo '错误：{{HOME}}tests/full 已存在，但 Package.swift 未声明 FullTests target。' >&2; exit 1; }
    just swift-run-tests --filter FullTests
