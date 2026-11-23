## 环境

Python 解释器由 uv 按 `{{HOME}}.python-version` 管理；仓库内的 Python 一律经 `uv run --locked` 执行，不直接调用系统解释器，也不手动激活 `.venv`。
