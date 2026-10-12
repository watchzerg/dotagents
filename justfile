set positional-arguments
set export
UV_MANAGED_PYTHON := "1"

# 列出开发命令。
default:
    @just --list

# 安装项目 Python，并按锁文件同步开发依赖；不升级宿主工具。
install:
    uv python install "$(cat .python-version)"
    uv sync --locked --managed-python --python "$(cat .python-version)"

# 检查宿主工具和项目 Python 补丁版本，不下载或安装。
check-toolchain:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v uv >/dev/null || { echo '错误：请先通过 Homebrew 安装 uv。' >&2; exit 1; }
    command -v just >/dev/null || { echo '错误：请先通过 Homebrew 安装 just。' >&2; exit 1; }
    uv --version
    just --version
    uv run --no-project --offline --no-python-downloads --no-env-file --managed-python --python "$(cat .python-version)" python -B - <<'PY'
    import pathlib
    import sys

    pin = pathlib.Path(".python-version").read_text().strip()
    actual = ".".join(map(str, sys.version_info[:3]))
    if actual != pin:
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
