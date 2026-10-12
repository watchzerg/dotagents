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

# 按 Package.resolved 解析依赖，不升级已锁定的版本；不安装或切换 Xcode。
[private]
swift-install:
    cd {{HOME_DIR}} && swift package --force-resolved-versions resolve

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

# 编译全部 target（含测试）即类型检查。--manifest-cache none 让 Package.swift 按当前文件重新计算 exclude。
[private]
swift-typecheck:
    cd {{HOME_DIR}} && swift build --build-tests --manifest-cache none

# 运行 swift test 并把零匹配视为失败；参数原样转发，由调用方决定 --filter 与 --skip。
[private]
swift-run-tests *args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    log="$(mktemp)"
    trap 'rm -f "$log"' EXIT
    swift test --manifest-cache none "$@" 2>&1 | tee "$log"
    if grep -q 'No matching test cases were run' "$log"; then
      echo '错误：没有匹配的测试；零匹配不是通过。' >&2
      exit 1
    fi

# 默认运行 CoreTests；可传 swift test 参数定向，未给 --filter 时补 --filter CoreTests。
# 始终跳过 FullTests，full 测试只经 test-full 在主机锁内运行。
[private]
swift-test *args:
    #!/usr/bin/env bash
    set -euo pipefail
    case " $* " in
      *" --filter "*|*" --filter="*) ;;
      *) set -- --filter '^CoreTests\.' "$@" ;;
    esac
    exec just swift-run-tests "$@" --skip '^FullTests\.'

# 全部 core 测试，不接受筛选参数。
[private]
swift-test-core:
    @just swift-run-tests --filter '^CoreTests\.'

# tests/full 下出现 Swift 文件即纳入；此时 Package.swift 未声明 FullTests 或零匹配视为失败。
# 目录不存在或只有其他 stack 的文件时打印提示并通过。可传 swift test 参数定向，未给 --filter 时补
# --filter FullTests，并始终跳过 CoreTests。只经 test-full 或 gate-full 调用。
[private]
swift-test-full *args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    if [ ! -d tests/full ] || [ -z "$(find tests/full -type f -name '*.swift' -print -quit)" ]; then
      echo '提示：{{HOME}}tests/full 下没有 Swift 测试文件，{{LABEL}} 尚无 full 测试。'
      exit 0
    fi
    grep -q 'name: "FullTests"' Package.swift || { echo '错误：{{HOME}}tests/full 已有 Swift 测试文件，但 Package.swift 未声明 FullTests target。' >&2; exit 1; }
    case " $* " in
      *" --filter "*|*" --filter="*) ;;
      *) set -- --filter '^FullTests\.' "$@" ;;
    esac
    exec just swift-run-tests "$@" --skip '^CoreTests\.'
