## 运行时与工具链

Homebrew → uv → Python。uv 管理解释器版本（`.python-version` 固定 minor line）、虚拟环境、依赖与 lockfile：`uv add` / `uv remove` 是修改依赖的唯一方式，`uv sync --locked` 是标准安装步骤。Ruff 负责格式化、lint（recommended 规则起步）与 import 排序，ty 负责类型检查，pytest 是测试 runner。`pyproject.toml` 的 `[tool.uv]` 设 `prerelease = "disallow"`。优先使用这些工具已有的能力，没有等价能力时再按当前需求引入专门工具。

## 依赖政策

只在当前需求需要时引入依赖，先用标准库和已选工具。新增依赖用 `uv add`，提交更新后的 `uv.lock`，不手改 lock；不引入预发布版本。本机 uv 由 Homebrew 维护，不在项目内锁定。升级集中进行并跑完整门禁。

需要相应能力时优先选用：`typer`（CLI）、`pydantic-settings`（配置）、`fastapi` + `uvicorn`（HTTP 服务）、`httpx`（HTTP 客户端）、`beautifulsoup4` + `lxml`（HTML 解析）、`sqlalchemy` 2.x + `psycopg` 3 + `alembic`（关系数据库）、`structlog`（结构化日志）。不要仅因清单存在而安装。

## 已选依赖

开发依赖：pytest、ruff、ty。运行依赖按需添加，并在此登记选择理由或 ADR 链接。
