# ---- {{LABEL}}：{{HOME_DIR}} ----

# 工具链检查：mise 存在，mise.lock 存在，Bun 实际版本符合根 mise.toml 的版本 line。
[private]
bun-check-toolchain:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v mise >/dev/null || { echo '错误：缺少 mise；macOS 请运行 brew install mise。' >&2; exit 1; }
    [ -f mise.lock ] || { echo '错误：缺少 mise.lock，请运行 mise lock。' >&2; exit 1; }
    line="$(sed -n 's/^bun *= *"\(.*\)".*/\1/p' mise.toml)"
    actual="$(mise exec -- bun --version)"
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

# 默认运行 tests/core；可传 bun test 参数定向。
[private]
bun-test *args:
    cd {{HOME_DIR}} && mise exec -- bun run test "$@"

# 全部 core 测试，不接受筛选参数。
[private]
bun-test-core:
    cd {{HOME_DIR}} && mise exec -- bun run test

# tests/full 目录出现即纳入，存在而无测试视为失败。
[private]
bun-test-full:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    if [ -d tests/full ]; then
      mise exec -- bun test --fail-on-empty tests/full
    else
      echo '提示：{{HOME}}tests/full 不存在，{{LABEL}} 尚无 full 测试。'
    fi
