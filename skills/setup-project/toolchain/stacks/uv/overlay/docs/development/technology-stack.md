## 运行时与工具链

mise → uv → Python。根 `mise.toml` 钉 uv 的兼容版本 line，`mise.lock` 锁定精确版本；升级 uv 时更新 line 并运行 `mise lock`。

uv 管理解释器版本（`.python-version` 固定 minor line）、虚拟环境、依赖与 lockfile，`pyproject.toml` 的 `[tool.uv]` 设 `prerelease = "disallow"`。Ruff 负责格式化、lint（recommended 规则起步）与 import 排序，ty 负责类型检查，pytest 是测试 runner。

## 依赖政策

依赖只用 `uv add` / `uv remove` 修改，提交更新后的 `uv.lock`，不手改 lock，不引入预发布版本。

优先选型：`typer`（CLI）、`pydantic-settings`（配置）、`fastapi` + `uvicorn`（HTTP 服务）、`httpx`（HTTP 客户端）、`beautifulsoup4` + `lxml`（HTML 解析）、`sqlalchemy` 2.x + `psycopg` 3 + `alembic`（关系数据库）、`structlog`（结构化日志）。

## 已选依赖

开发依赖：pytest、ruff、ty。
