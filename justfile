set positional-arguments
set export
UV_MANAGED_PYTHON := "1"

# 列出开发命令。
default:
    @just --list

# 按 mise.lock 安装 uv，再安装项目 Python 并按锁文件同步开发依赖；不升级全局工具。
install:
    mise install
    mise exec -- uv python install "$(cat .python-version)"
    mise exec -- uv sync --locked --managed-python --python "$(cat .python-version)"

# 检查 mise、PATH 上的 uv 版本 line 与项目 Python 版本 line，不下载或安装。
# uv 由 mise 按目录切换（mise activate 或 shims），这里核对实际解析到的版本；MISE_AUTO_INSTALL=0 关掉 shim 的自动安装。
check-toolchain:
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
    just --version
    uv run --no-project --offline --no-python-downloads --no-env-file --managed-python --python "$(cat .python-version)" python -B - <<'PY'
    import pathlib
    import sys

    pin = pathlib.Path(".python-version").read_text().strip()
    actual = ".".join(map(str, sys.version_info[:3]))
    if actual != pin and not actual.startswith(pin + "."):
        sys.exit(f"错误：预期 Python {pin}，实际 {actual}；请运行 just install")
    print(f"Python={actual}；工具链检查通过")
    PY

# 格式化并修复可自动修复的 lint；会修改文件。
fmt *paths=".":
    uv run --locked ruff format "$@"
    uv run --locked ruff check --fix "$@"

# 检查仓库内 Python 文件，自动覆盖新增 skill 脚本。
lint:
    uv run --locked ruff check .
    uv run --locked ruff format --check .

# 用 ty 做类型检查。
typecheck:
    uv run --locked ty check .

# 默认运行所有测试；可用 just -- test <pytest-args> 传入筛选参数。
test *args:
    uv run --locked python -m pytest "$@"

# 完整门禁不接受测试筛选参数，并清除外部 PYTEST_ADDOPTS。
gate-full:
    just check-toolchain
    git diff --check
    just lint
    just typecheck
    env -u PYTEST_ADDOPTS uv run --locked python -m pytest

# 在临时项目上用 headless Claude Code 真实执行 /setup-project 并检查产物；不属于门禁，需要网络与模型额度。
e2e-setup-project *args:
    uv run --locked python -m tests.setup_project.e2e.run "$@"
