# ---- {{LABEL}}：{{HOME_DIR}} ----

# 工具链检查：mise 存在，mise.lock 存在，Bun 实际版本符合根 mise.toml 的版本 line。
# 不安装：MISE_AUTO_INSTALL=0 关掉 mise exec 的自动安装（只关 exec_auto_install 不够，PATH 上的 mise shim 仍会触发安装）。
[private]
bun-check-toolchain:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v mise >/dev/null || { echo '错误：缺少 mise；macOS 请运行 brew install mise。' >&2; exit 1; }
    [ -f mise.lock ] || { echo '错误：缺少 mise.lock，请运行 mise lock。' >&2; exit 1; }
    line="$(sed -n 's/^bun *= *"\(.*\)".*/\1/p' mise.toml)"
    actual="$(MISE_AUTO_INSTALL=0 mise exec -- bun --version)" || { echo "错误：mise 尚未安装 Bun line ${line}；请运行 just install。" >&2; exit 1; }
    case "$actual" in
      "$line"|"$line".*) echo "Bun=${actual}；工具链检查通过" ;;
      *) echo "错误：Bun 版本 ${actual} 不属于 line ${line}；请运行 mise install。" >&2; exit 1 ;;
    esac

# 按 lock 安装 Bun 与依赖；不升级宿主工具。
[private]
bun-install:
    mise install
    cd {{HOME_DIR}} && mise exec -- bun install --frozen-lockfile

[private]
bun-fmt *paths=".":
    cd {{HOME_DIR}} && mise exec -- bun x --bun --no-install biome check --write "$@"

[private]
bun-lint:
    cd {{HOME_DIR}} && mise exec -- bun run lint

[private]
bun-typecheck:
    cd {{HOME_DIR}} && mise exec -- bun run typecheck

# 默认运行 tests/core；可传 bun test 参数定向。bun test 的位置参数是并集筛选，所以参数中有已存在的路径时
# 不再追加 tests/core，只运行给出的路径；只有 -t 等选项时在 tests/core 内筛选。
[private]
bun-test *args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    for arg in "$@"; do
      if [ -e "$arg" ]; then exec mise exec -- bun test "$@"; fi
    done
    exec mise exec -- bun test tests/core "$@"

# 全部 core 测试，不接受筛选参数；没有匹配的测试文件时 bun test 自身非零退出。
[private]
bun-test-core:
    cd {{HOME_DIR}} && mise exec -- bun test tests/core

# tests/full 下出现 bun 测试文件（*.test.ts、*_test.ts、*.spec.ts、*_spec.ts 及 .tsx/.js/.jsx）即纳入，此时
# 零匹配由 bun test 判为失败；目录不存在或只有其他 stack 的文件时打印提示并通过。路径参数规则同 bun-test。
# 只经 test-full 或 gate-full 调用。
[private]
bun-test-full *args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    if [ ! -d tests/full ] || [ -z "$(find tests/full -type f \( -name '*[._]test.[jt]s' -o -name '*[._]test.[jt]sx' -o -name '*[._]spec.[jt]s' -o -name '*[._]spec.[jt]sx' \) -print -quit)" ]; then
      echo '提示：{{HOME}}tests/full 下没有 bun 测试文件，{{LABEL}} 尚无 full 测试。'
      exit 0
    fi
    for arg in "$@"; do
      if [ -e "$arg" ]; then exec mise exec -- bun test "$@"; fi
    done
    exec mise exec -- bun test tests/full "$@"
