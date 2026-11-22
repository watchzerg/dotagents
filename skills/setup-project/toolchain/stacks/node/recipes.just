# ---- {{LABEL}}：{{HOME_DIR}} ----

# 工具链检查：mise 存在，mise.lock 存在，PATH 上的 Node 与 pnpm（由 mise 按目录切换）符合根 mise.toml 的版本 line。
# 不安装：MISE_AUTO_INSTALL=0 关掉 mise shim 遇到缺失版本时的自动安装。
[private]
node-check-toolchain:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v mise >/dev/null || { echo '错误：缺少 mise；用系统包管理器安装（macOS 运行 brew install mise，Ubuntu 添加 mise 官方 apt 源后运行 sudo apt install mise）。' >&2; exit 1; }
    [ -f mise.lock ] || { echo '错误：缺少 mise.lock，请运行 mise lock。' >&2; exit 1; }
    export MISE_AUTO_INSTALL=0
    for tool in node pnpm; do
      line="$(sed -n "s/^${tool} *= *\"\(.*\)\".*/\1/p" mise.toml)"
      actual="$("$tool" --version)" || { echo "错误：PATH 上没有可用的 ${tool} line ${line}；请运行 just install，并确认 shell 已启用 mise activate 或 mise shims。" >&2; exit 1; }
      actual="${actual#v}"
      case "$actual" in
        "$line"|"$line".*) echo "${tool}=${actual}" ;;
        *) echo "错误：${tool} 版本 ${actual} 不属于 line ${line}；请运行 just install，并确认 shell 已启用 mise activate 或 mise shims。" >&2; exit 1 ;;
      esac
    done
    echo '工具链检查通过'

# 按 lock 安装 Node、pnpm 与依赖；不升级全局工具。刚安装的 pnpm 可能还不在当前 PATH 上，安装依赖经 mise exec 调用。
[private]
node-install:
    mise install
    cd {{HOME_DIR}} && mise exec -- pnpm install --frozen-lockfile

[private]
node-fmt *paths=".":
    cd {{HOME_DIR}} && pnpm exec biome check --write "$@"

[private]
node-lint:
    cd {{HOME_DIR}} && pnpm run lint

[private]
node-typecheck:
    cd {{HOME_DIR}} && pnpm run typecheck

# 默认运行 tests/core；可传 vitest run 参数定向。vitest 的位置参数是并集筛选，所以参数中有已存在的路径时
# 不再追加 tests/core，只运行给出的路径；只有 -t 等选项时在 tests/core 内筛选。
[private]
node-test *args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    for arg in "$@"; do
      if [ -e "$arg" ]; then exec pnpm exec vitest run "$@"; fi
    done
    exec pnpm exec vitest run tests/core "$@"

# 全部 core 测试，不接受筛选参数；没有匹配的测试文件时 vitest 自身非零退出。
[private]
node-test-core:
    cd {{HOME_DIR}} && pnpm exec vitest run tests/core

# tests/full 下出现 Vitest 测试文件（*.test.ts、*.spec.ts 及 .tsx/.js/.jsx）即纳入，此时
# 零匹配由 vitest 判为失败；目录不存在或只有其他 stack 的文件时打印提示并通过。路径参数规则同 node-test。
# 只经 test-full 或 gate-full 调用。
[private]
node-test-full *args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    if [ ! -d tests/full ] || [ -z "$(find tests/full -type f \( -name '*.test.[jt]s' -o -name '*.test.[jt]sx' -o -name '*.spec.[jt]s' -o -name '*.spec.[jt]sx' \) -print -quit)" ]; then
      echo '提示：{{HOME}}tests/full 下没有 Vitest 测试文件，{{LABEL}} 尚无 full 测试。'
      exit 0
    fi
    for arg in "$@"; do
      if [ -e "$arg" ]; then exec pnpm exec vitest run "$@"; fi
    done
    exec pnpm exec vitest run tests/full "$@"
