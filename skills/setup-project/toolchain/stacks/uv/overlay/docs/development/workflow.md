## 环境

Python 解释器由 uv 按 `{{HOME}}.python-version` 的版本 line 管理，依赖由 `pyproject.toml` 与 `uv.lock` 锁定。仓库内的 Python 一律通过 `uv run --locked` 执行，不直接调用系统解释器，也不手动激活 `.venv`。
