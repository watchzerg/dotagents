# ---- {{LABEL}}：{{HOME_DIR}} ----

# 工具链检查：mise 存在，mise.lock 存在，PATH 上的 uv（由 mise 按目录切换）符合根 mise.toml 的版本 line，
# 解释器符合 .python-version 的版本 line。不安装依赖，也不下载解释器；MISE_AUTO_INSTALL=0 关掉 shim 的自动安装。
[private]
uv-check-toolchain:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v mise >/dev/null || { echo '错误：缺少 mise；用系统包管理器安装（macOS 运行 brew install mise，Ubuntu 添加 mise 官方 apt 源后运行 sudo apt install mise）。' >&2; exit 1; }
    [ -f mise.lock ] || { echo '错误：缺少 mise.lock，请运行 mise lock。' >&2; exit 1; }
    export MISE_AUTO_INSTALL=0
    line="$(sed -n 's/^uv *= *"\(.*\)".*/\1/p' mise.toml)"
    command -v uv >/dev/null || { echo "错误：PATH 上没有 uv；请运行 just install，并确认 shell 已启用 mise activate 或 mise shims。" >&2; exit 1; }
    actual="$(uv --version)"
    actual="$(echo "$actual" | cut -d' ' -f2)"
    case "$actual" in
      "$line"|"$line".*) echo "uv=${actual}" ;;
      *) echo "错误：uv 版本 ${actual} 不属于 line ${line}；请运行 just install，并确认 shell 已启用 mise activate 或 mise shims。" >&2; exit 1 ;;
    esac
    cd {{HOME_DIR}}
    uv run --no-project --no-env-file --no-python-downloads --python "$(cat .python-version)" python -B - <<'PY'
    import pathlib
    import sys

    pin = pathlib.Path(".python-version").read_text().strip()
    actual = ".".join(map(str, sys.version_info[:3]))
    if actual != pin and not actual.startswith(pin + "."):
        sys.exit(f"错误：预期 Python {pin}，实际 {actual}；请运行 just install")
    print(f"Python={actual}；工具链检查通过")
    PY

# 按 lock 安装 uv 与开发依赖；不升级全局工具。刚安装的 uv 可能还不在当前 PATH 上，sync 经 mise exec 调用。
[private]
uv-install:
    mise install
    cd {{HOME_DIR}} && mise exec -- uv sync --locked

[private]
uv-fmt *paths=".":
    cd {{HOME_DIR}} && uv run --locked ruff check --fix "$@" && uv run --locked ruff format "$@"

[private]
uv-lint:
    cd {{HOME_DIR}} && uv run --locked ruff check . && uv run --locked ruff format --check .

[private]
uv-typecheck:
    cd {{HOME_DIR}} && uv run --locked ty check .

# 默认运行 tests/core（pytest testpaths）；可传 pytest 参数定向，给出路径时只运行该路径。
[private]
uv-test *args:
    cd {{HOME_DIR}} && uv run --locked python -m pytest "$@"

# 全部 core 测试，不接受筛选参数，清除外部 PYTEST_ADDOPTS。
[private]
uv-test-core:
    cd {{HOME_DIR}} && env -u PYTEST_ADDOPTS uv run --locked python -m pytest

# tests/full 下出现 pytest 测试文件（test_*.py、*_test.py）即纳入，此时零收集视为失败；目录不存在或只有
# 其他 stack 的文件时打印提示并通过。默认范围用 -o testpaths=tests/full 指定，所以 -k 等参数在 tests/full
# 内筛选，给出路径时只运行该路径。只经 test-full 或 gate-full 调用。
[private]
uv-test-full *args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    if [ ! -d tests/full ] || [ -z "$(find tests/full -type f \( -name 'test_*.py' -o -name '*_test.py' \) -print -quit)" ]; then
      echo '提示：{{HOME}}tests/full 下没有 pytest 测试文件，{{LABEL}} 尚无 full 测试。'
      exit 0
    fi
    env -u PYTEST_ADDOPTS uv run --locked python -m pytest -o testpaths=tests/full "$@"
