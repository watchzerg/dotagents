"""端到端用例定义：每个用例描述目标项目怎么构造、非交互问答的预置答案与期望。"""

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

E2E_DIR = Path(__file__).resolve().parent
FIXTURES = E2E_DIR / "fixtures"
REPO_ROOT = E2E_DIR.parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "setup-project"

CONTRACT_TASKS = (
    "check-toolchain",
    "install",
    "fmt",
    "lint",
    "typecheck",
    "test",
    "test-full",
    "docs-check",
    "docs-affected",
    "gate-core",
    "gate-full",
)


@dataclass(frozen=True)
class Case:
    name: str
    build: Callable[[Path], None]
    description: str | None
    stacks: tuple[str, ...] | None
    expect_mode: str
    expect_stacks: tuple[str, ...]
    triage: bool = True
    present: tuple[str, ...] = ()
    absent: tuple[str, ...] = ()
    untouched: tuple[str, ...] = ()
    sentinels: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # (glob, 片段, 应存在)：glob 相对项目根；应存在时任一匹配文件含片段即可，不应存在时所有匹配文件都不得含。
    text_rules: tuple[tuple[str, str, bool], ...] = ()
    # 描述应出现在哪些文件：已有开头的 AGENTS.md 或已存在的 README.md 不留 初始化 标记，不会被填。
    description_targets: tuple[str, ...] = ("AGENTS.md", "README.md", "GLOSSARY.md")
    # fixture 的 AGENTS.md 已有描述时流程不提问，其余文件由这句展开；描述检查改用它取片段。
    existing_description: str | None = None
    # 除 run.COMMON_TOOLS 外，构造 fixture 或跑门禁还需要的命令。
    tools: tuple[str, ...] = ()
    notes: str = ""


GIT_AS_E2E = ("git", "-c", "user.name=e2e", "-c", "user.email=e2e@example.invalid")
BEADS_SENTINEL = "修复导出时标签含逗号的转义 BEADS-CLONE-SENTINEL"


def run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def apply_matt(project: Path, triage: bool) -> None:
    """模拟 setup-matt-pocock-skills 的产物：docs/agents 三件套加 Agent skills 块。"""
    tracker = (FIXTURES / "matt/docs/agents/issue-tracker.md").read_text(encoding="utf-8")
    if not triage:
        # 没装 triage 时 Matt setup 不会写标签映射，tracker 文件里也不会引用它。
        tracker = "".join(
            line for line in tracker.splitlines(keepends=True) if "triage-labels.md" not in line
        )
    write(_mk(project / "docs/agents") / "issue-tracker.md", tracker)
    shutil.copy(FIXTURES / "matt/docs/agents/domain.md", project / "docs/agents")
    if triage:
        shutil.copy(FIXTURES / "matt/docs/agents/triage-labels.md", project / "docs/agents")
    block_name = "agent-skills.md" if triage else "agent-skills-no-triage.md"
    block = (FIXTURES / "matt" / block_name).read_text(encoding="utf-8")
    # Matt 的规则：CLAUDE.md 存在则编辑它，否则编辑 AGENTS.md，都没有时由用户选（这里选 AGENTS.md）。
    target = project / "CLAUDE.md"
    if not target.exists():
        target = project / "AGENTS.md"
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    sep = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
    write(target, existing + sep + block)


def _mk(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------- 构造器


def build_empty(project: Path) -> None:
    """空项目：只有 Matt 产物。"""


def _ledger_package(project: Path) -> None:
    """uv 包 demo_uv：账本模块、入口与一个测试。"""
    run(["uv", "init", "--package", "--name", "demo_uv", "--no-workspace", "-q", "."], project)
    write(
        project / "src/demo_uv/ledger.py",
        '''"""简单账本：记录收支并计算余额。"""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Entry:
    label: str
    amount: Decimal


@dataclass
class Ledger:
    entries: list[Entry] = field(default_factory=list)

    def add(self, label: str, amount: str) -> None:
        self.entries.append(Entry(label, Decimal(amount)))

    def balance(self) -> Decimal:
        return sum((e.amount for e in self.entries), Decimal("0"))
''',
    )
    write(
        project / "src/demo_uv/__init__.py",
        """from demo_uv.ledger import Ledger


def main() -> None:
    ledger = Ledger()
    ledger.add("salary", "100")
    ledger.add("rent", "-40")
    print(ledger.balance())
""",
    )
    write(
        project / "tests/test_ledger.py",
        """from decimal import Decimal

from demo_uv.ledger import Ledger


def test_balance() -> None:
    ledger = Ledger()
    ledger.add("a", "1.5")
    ledger.add("b", "-0.5")
    assert ledger.balance() == Decimal("1.0")
""",
    )


def build_uv_existing(project: Path) -> None:
    """已有 uv 工程、旧文档、同义节 AGENTS.md、有内容的 CLAUDE.md、缺契约 task 的 mise.toml。"""
    _ledger_package(project)
    write(
        project / "docs/old-notes.md",
        """# 设计笔记

## 为什么用 Decimal

账本金额用 `Decimal` 而不是 float，避免 0.1 + 0.2 的累计误差。曾经试过 float，月末对账差 3 分钱。

## 待办

- 支持多币种（暂不做）
- 导出 CSV
""",
    )
    write(
        project / "docs/setup.md",
        """# 本地环境

1. 安装 uv：`brew install uv`
2. 同步依赖：`uv sync`
3. 运行测试：`uv run pytest`

发布前手动跑一遍 `uv build`。
""",
    )
    write(
        project / "mise.toml",
        """[tasks.test]
description = "运行测试"
run = "uv run pytest"

[tasks.lint]
description = "静态检查"
run = "uv run ruff check ."
""",
    )
    write(
        project / "AGENTS.md",
        """# demo_uv

个人记账小工具，命令行使用。

## 约束

- 金额一律用 Decimal，禁止 float。
- 不引入 ORM，持久化只用 JSON 文件。

## 发布流程

打 tag 后由 GitHub Actions 构建 wheel，不手动上传。
""",
    )
    write(
        project / "CLAUDE.md",
        """# Claude 说明

## 代码风格

- 函数不超过 40 行。
- 公共函数必须有类型标注。
""",
    )
    run(["uv", "sync", "-q"], project)


def build_node_new_with_code(project: Path) -> None:
    """有 TypeScript 源码但没有任何工具链文件：判定退出码 3，选 node 后走 new 模式并补写模块页。"""
    write(
        project / "src/counter.ts",
        """export class Counter {
  private value = 0;

  increment(step = 1): number {
    this.value += step;
    return this.value;
  }

  reset(): void {
    this.value = 0;
  }
}
""",
    )
    write(
        project / "src/index.ts",
        """import { Counter } from "./counter";

const counter = new Counter();
counter.increment(2);
console.log(counter.increment());
""",
    )


def build_swift_existing(project: Path) -> None:
    """已有 SwiftPM package：existing 模式、没有 mise 配置。"""
    run(["swift", "package", "init", "--type", "library", "--name", "DemoSwift"], project)


def build_uv_large_docs(project: Path) -> None:
    """uv 工程加 30 多份散落在多个顶层目录的旧文档、附件、超预算页、骨架不符的模块页与被忽略的仓库副本。"""
    _ledger_package(project)
    shutil.copytree(FIXTURES / "large-docs", project, dirs_exist_ok=True)
    write(project / "AGENTS.md", f"# demo_uv\n\n{UV_EXISTING_DESCRIPTION}。\n")
    # 被忽略的仓库副本与原始输出：收敛不得扫描或改动它们（git grep 而不是 grep -r）。
    with (project / ".gitignore").open("a", encoding="utf-8") as f:
        f.write(".worktrees/\noutput/\n")
    shutil.copytree(FIXTURES / "large-docs/docs", project / ".worktrees/old/docs")
    write(project / "output/raw-notes.md", "# 原始输出\n\n" + "debug line\n" * 2000)
    run(["uv", "sync", "-q"], project)


def build_beads_clone(project: Path) -> None:
    """另一台机器上已初始化 Beads 并推送了票据的仓库，在这里重新 clone：只有 .beads/ 配置，没有本地数据库。"""
    origin = (project.parent / "origin.git").resolve()
    seed = project.parent / "seed" / project.name
    seed.mkdir(parents=True)
    run(["git", "init", "-q", "--bare", str(origin)], project.parent)
    run(["git", "init", "-q", "-b", "main"], seed)
    run(["git", "remote", "add", "origin", str(origin)], seed)
    run([*GIT_AS_E2E, "commit", "-q", "--allow-empty", "-m", "base"], seed)
    run(
        [
            "bd",
            "init",
            "--non-interactive",
            "--init-if-missing",
            "--role",
            "maintainer",
            "--skip-agents",
            "--skip-hooks",
        ],
        seed,
    )
    run(["bd", "create", BEADS_SENTINEL, "-t", "task", "-p", "2"], seed)
    run(["git", "push", "-q", "origin", "main"], seed)
    run(["bd", "dolt", "push"], seed)
    run(["git", "remote", "add", "origin", str(origin)], project)
    run(["git", "fetch", "-q", "origin"], project)
    run(["git", "reset", "-q", "--hard", "origin/main"], project)


def build_uv_node_new(project: Path) -> None:
    """空项目选 uv+node 两个 stack。"""


def build_none_empty(project: Path) -> None:
    """空项目选 none，且 Matt 产物不含 triage。"""


# ---------------------------------------------------------------- 用例表

DESCRIPTION = "一个给个人用的命令行记账工具，记录收支并计算余额"
# build_uv_existing 写进 AGENTS.md 的已有描述，两处保持一致。
UV_EXISTING_DESCRIPTION = "个人记账小工具，命令行使用"

# uv-large-docs 的内容哨兵：(源文件, 片段, 应在哪里)。where 取 any（任一未被忽略的文件）、
# ticket（票据或任一文件）、glossary（GLOSSARY.md）、operations（docs/operations/ 下）。
LARGE_DOCS_SENTINELS: tuple[tuple[str, str, str], ...] = (
    ("ARCHITECTURE.md", "LEDGER_HOME", "any"),
    ("HACKING.md", "LEDGER_DEBUG", "any"),
    ("TODO.md", "--by-label", "ticket"),
    ("TODO.md", "--currency", "ticket"),
    ("docs/overview.md", "--reverse-of", "any"),
    ("docs/data-model.md", "amount_str", "any"),
    ("docs/decision-json-storage.md", "ledger.json.tmp", "any"),
    ("docs/decision-no-orm.md", "迁移成本", "any"),
    ("docs/terms.md", "影子余额", "glossary"),
    ("docs/terms.md", "冻结段", "glossary"),
    ("docs/glossary.md", "结转点", "glossary"),
    ("docs/testing-notes.md", "pytest.mark.slow", "any"),
    ("docs/release.md", "check_version.sh", "any"),
    ("docs/deploy-config.md", "com.demo.ledger.backup", "any"),
    ("docs/style.md", "_parse_amount", "any"),
    ("docs/benchmark-2025.md", "balance_bench.py", "any"),
    ("docs/import-csv-plan.md", "--csv", "ticket"),
    ("docs/faq.md", "(-)", "any"),
    ("docs/research/m1-integration.md", "m1-sample.json", "any"),
    ("docs/research/float-vs-decimal.md", "float_drift.py", "any"),
    ("docs/adr/0001-use-decimal.md", "prec=28", "any"),
    ("docs/architecture/modules/ledger.md", 'Decimal("0")', "any"),
    ("design/modules.md", "load_ledger", "any"),
    ("design/import-flow.md", "validate_rows", "any"),
    ("design/currency.md", "人民币", "any"),
    ("design/glossary-notes.md", "回拨单", "glossary"),
    ("design/error-handling.md", "InvalidAmountError", "any"),
    ("design/cli-ux.md", "--raw", "any"),
    ("design/perf-experiment.md", "orjson", "any"),
    ("design/persistence.md", ".bak3", "any"),
    ("notes/roadmap.md", "--format csv", "ticket"),
    ("notes/roadmap.md", "--until", "ticket"),
    ("notes/terms-more.md", "期初条目", "glossary"),
    ("notes/dev-setup.txt", "demo_uv --help", "any"),
    ("notes/meeting-2025-03.md", "LEDGER_LANG", "any"),
    ("notes/ci.md", "workflows/ci.yml", "any"),
    ("notes/review-checklist.md", "负数金额", "any"),
    ("notes/backup.rst", "demo_uv verify", "any"),
    *(("docs/operations/runbook.md", f"--step {i:02d}", "operations") for i in range(1, 37)),
)
LARGE_DOCS_ATTACHMENTS = ("design/import-flow.png", "design/sample-import.json")

CASES: dict[str, Case] = {
    "empty": Case(
        name="empty",
        build=build_empty,
        description="一个给维护者个人用的占位项目，用来验证初始化流程",
        stacks=("uv",),
        expect_mode="new",
        expect_stacks=("uv",),
        present=(
            ".beads",
            "AGENTS.md",
            "README.md",
            "GLOSSARY.md",
            "CODING_STANDARDS.md",
            "docs/INDEX.md",
            "mise.toml",
            "mise-tasks/uv/test",
            "pyproject.toml",
            "uv.lock",
            "scripts/check_docs.py",
            "scripts/with_lock.py",
            "tests/core/test_toolchain.py",
        ),
        absent=("CLAUDE.md",),
        notes="主用例：判定退出码 3，提问一次收集描述与 stack。",
    ),
    "uv-existing": Case(
        name="uv-existing",
        build=build_uv_existing,
        description=DESCRIPTION,
        existing_description=UV_EXISTING_DESCRIPTION,
        stacks=None,
        expect_mode="existing",
        expect_stacks=("uv",),
        present=(
            ".beads",
            "AGENTS.md",
            "CLAUDE.md",
            "README.md",
            "GLOSSARY.md",
            "docs/INDEX.md",
            "docs/architecture/INDEX.md",
            "scripts/check_docs.py",
            "scripts/with_lock.py",
        ),
        absent=("tests/core/test_toolchain.py", "docs/setup.md"),
        untouched=("pyproject.toml", "uv.lock", ".python-version", "src/demo_uv/ledger.py"),
        sentinels={
            "AGENTS.md": (
                "金额一律用 Decimal，禁止 float",
                "不引入 ORM，持久化只用 JSON 文件",
                "函数不超过 40 行",
                "公共函数必须有类型标注",
            ),
        },
        text_rules=(
            # 细则节 `## 发布流程` 应迁入 docs/operations/，AGENTS.md 留路由行，workflow 的发布标记用链接填掉。
            ("docs/operations/*.md", "打 tag 后由 GitHub Actions 构建 wheel", True),
            ("AGENTS.md", "## 发布流程", False),
            ("AGENTS.md", "docs/operations/", True),
            ("docs/development/workflow.md", "<待填 按需：有发布流程", False),
            ("docs/development/workflow.md", "operations/", True),
        ),
        description_targets=("GLOSSARY.md",),
        notes="existing 模式：同义节合并、CLAUDE.md 收口、旧文档收敛、从代码补写模块页、补齐契约 task。",
    ),
    "node-new-with-code": Case(
        name="node-new-with-code",
        build=build_node_new_with_code,
        description="一个计数器示例库，给前端项目做演示",
        stacks=("node",),
        expect_mode="new",
        expect_stacks=("node",),
        present=(
            ".beads",
            "mise.toml",
            "mise-tasks/node/test",
            "package.json",
            "biome.json",
            "tsconfig.json",
            "pnpm-lock.yaml",
            "tests/core/toolchain.test.ts",
            "src/counter.ts",
        ),
        untouched=("src/counter.ts", "src/index.ts"),
        notes="有代码但无工具链：退出码 3 后选 node，new 模式同时补写模块页。",
    ),
    "swift-existing": Case(
        name="swift-existing",
        build=build_swift_existing,
        description="一个 Swift 示例库，验证 SwiftPM 项目的初始化",
        stacks=None,
        expect_mode="existing",
        expect_stacks=("swift",),
        present=(
            ".beads",
            "AGENTS.md",
            "docs/INDEX.md",
            "Package.swift",
            "scripts/check_docs.py",
            "scripts/with_lock.py",
        ),
        absent=("mise.toml", "mise-tasks", ".swift-format", "tests/core/ToolchainTests.swift"),
        untouched=("Package.swift",),
        description_targets=("GLOSSARY.md",),
        tools=("swift", "xcodebuild"),
        notes="existing 模式且无 mise 配置：只补依赖偏好与两个公共脚本，报告写明没有 mise task。",
    ),
    "uv-node-new": Case(
        name="uv-node-new",
        build=build_uv_node_new,
        description="一个带 Python 后端和 TypeScript 前端的示例应用",
        stacks=("uv", "node"),
        expect_mode="new",
        expect_stacks=("uv", "node"),
        present=(
            ".beads",
            "mise.toml",
            "mise-tasks/uv/test",
            "mise-tasks/node/test",
            "pyproject.toml",
            "uv.lock",
            "frontend/package.json",
            "frontend/pnpm-lock.yaml",
            "frontend/tests/core/toolchain.test.ts",
            "tests/core/test_toolchain.py",
        ),
        notes="多 stack 新项目：公开 task 聚合两个 stack 的 file task。",
    ),
    "none-empty": Case(
        name="none-empty",
        build=build_none_empty,
        description="一个只有文档的流程仓库，不含代码",
        stacks=("none",),
        expect_mode="new",
        expect_stacks=("none",),
        triage=False,
        present=(".beads", "mise.toml", "AGENTS.md", "docs/INDEX.md"),
        absent=("pyproject.toml", "package.json", "mise-tasks", "docs/agents/triage-labels.md"),
        notes="none stack：契约 task 非零退出；Matt 产物不含 triage，触发表不应有分诊行。",
    ),
    "uv-large-docs": Case(
        name="uv-large-docs",
        build=build_uv_large_docs,
        description=DESCRIPTION,
        existing_description=UV_EXISTING_DESCRIPTION,
        stacks=None,
        expect_mode="existing",
        expect_stacks=("uv",),
        present=(
            ".beads",
            "GLOSSARY.md",
            "docs/INDEX.md",
            "docs/adr/INDEX.md",
            "docs/research/INDEX.md",
        ),
        absent=("ARCHITECTURE.md", "docs/glossary.md"),
        untouched=(
            "pyproject.toml",
            "src/demo_uv/ledger.py",
            ".worktrees/old/docs/overview.md",
            "output/raw-notes.md",
        ),
        description_targets=("GLOSSARY.md",),
        notes=(
            "大批量收敛：docs/、design/、notes/ 与根目录共 30 多个候选，应按顶层目录分批、全部分类完再执行，"
            "目标重叠的批（GLOSSARY.md、architecture/INDEX.md）串行；附件随文档迁移；超 16 KiB 的运维手册按拆页规则原样拆分；"
            "骨架不符的模块页按模板重排；未登记的 ADR 与调研登记索引；验收记录迁入 research/acceptance/；计划项建票；"
            "被忽略的 .worktrees/ 与 output/ 不得扫描或改动。reviewer 重点看分批与串行是否按规则执行、拆页与重排是否删减内容。"
        ),
    ),
    "beads-clone": Case(
        name="beads-clone",
        build=build_beads_clone,
        description="一个已在别的机器上初始化过 Beads 的仓库，重新 clone 后补齐初始化",
        stacks=("none",),
        expect_mode="new",
        expect_stacks=("none",),
        present=(".beads", "AGENTS.md", "docs/INDEX.md"),
        notes="新 clone 只有 .beads 配置、没有本地数据库：应走 bd bootstrap 从 origin 的 Dolt 数据恢复原有票据，而不是另起空库。",
    ),
}
