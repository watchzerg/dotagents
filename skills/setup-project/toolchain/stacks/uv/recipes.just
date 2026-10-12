# ---- {{LABEL}}：{{HOME_DIR}} ----

# 工具链检查：uv 存在，解释器符合 .python-version 的版本 line；不安装依赖。
[private]
uv-check-toolchain:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    command -v uv >/dev/null || { echo '错误：缺少 uv；macOS 请运行 brew install uv。' >&2; exit 1; }
    uv run --no-project --no-env-file --python "$(cat .python-version)" python -B - <<'PY'
    import pathlib
    import sys

    pin = pathlib.Path(".python-version").read_text().strip()
    actual = ".".join(map(str, sys.version_info[:3]))
    if actual != pin and not actual.startswith(pin + "."):
        sys.exit(f"错误：预期 Python {pin}，实际 {actual}；请运行 just install")
    print(f"Python={actual}；工具链检查通过")
    PY

# 按 lock 同步开发依赖；不升级宿主工具。
[private]
uv-install:
    cd {{HOME_DIR}} && uv sync --locked

[private]
uv-fmt *paths=".":
    cd {{HOME_DIR}} && uv run --locked ruff check --fix "$@" && uv run --locked ruff format "$@"

[private]
uv-lint:
    cd {{HOME_DIR}} && uv run --locked ruff check . && uv run --locked ruff format --check .

[private]
uv-typecheck:
    cd {{HOME_DIR}} && uv run --locked ty check .

# 默认运行 tests/core；可传 pytest 参数定向。
[private]
uv-test *args:
    cd {{HOME_DIR}} && uv run --locked python -m pytest "$@"

# 全部 core 测试，不接受筛选参数，清除外部 PYTEST_ADDOPTS。
[private]
uv-test-core:
    cd {{HOME_DIR}} && env -u PYTEST_ADDOPTS uv run --locked python -m pytest

# tests/full 目录出现即纳入，存在而无测试视为失败；可传 pytest 参数定向。只经 test-full 或 gate-full 调用。
[private]
uv-test-full *args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{HOME_DIR}}
    if [ -d tests/full ]; then
      env -u PYTEST_ADDOPTS uv run --locked python -m pytest tests/full "$@"
    else
      echo '提示：{{HOME}}tests/full 不存在，{{LABEL}} 尚无 full 测试。'
    fi
