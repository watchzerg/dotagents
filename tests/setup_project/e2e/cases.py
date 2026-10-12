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

CONTRACT_RECIPES = (
    "check-toolchain",
    "install",
    "fmt",
    "lint",
    "typecheck",
    "test",
    "test-full",
    "docs-check",
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
    notes: str = ""


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


def build_uv_existing(project: Path) -> None:
    """已有 uv 工程、旧文档、同义节 AGENTS.md、有内容的 CLAUDE.md、缺 recipe 的 justfile。"""
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
        project / "justfile",
        """# 运行测试
test:
    uv run pytest

# 静态检查
lint:
    uv run ruff check .
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


def build_bun_new_with_code(project: Path) -> None:
    """有 TypeScript 源码但没有任何工具链文件：判定退出码 3，选 bun 后走 new 模式并补写模块页。"""
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
    """已有 SwiftPM package：existing 模式、没有 justfile。"""
    run(["swift", "package", "init", "--type", "library", "--name", "DemoSwift"], project)


def build_uv_bun_new(project: Path) -> None:
    """空项目选 uv+bun 两个 stack。"""


def build_none_empty(project: Path) -> None:
    """空项目选 none，且 Matt 产物不含 triage。"""


# ---------------------------------------------------------------- 用例表

DESCRIPTION = "一个给个人用的命令行记账工具，记录收支并计算余额"

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
            "justfile",
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
        ),
        absent=("scripts/with_lock.py", "tests/core/test_toolchain.py", "docs/setup.md"),
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
        notes="existing 模式：同义节合并、CLAUDE.md 收口、旧文档收敛、从代码补写模块页、补齐 recipe。",
    ),
    "bun-new-with-code": Case(
        name="bun-new-with-code",
        build=build_bun_new_with_code,
        description="一个计数器示例库，给前端项目做演示",
        stacks=("bun",),
        expect_mode="new",
        expect_stacks=("bun",),
        present=(
            ".beads",
            "justfile",
            "package.json",
            "biome.json",
            "tsconfig.json",
            "bun.lock",
            "tests/core/toolchain.test.ts",
            "src/counter.ts",
        ),
        untouched=("src/counter.ts", "src/index.ts"),
        notes="有代码但无工具链：退出码 3 后选 bun，new 模式同时补写模块页。",
    ),
    "swift-existing": Case(
        name="swift-existing",
        build=build_swift_existing,
        description="一个 Swift 示例库，验证 SwiftPM 项目的初始化",
        stacks=None,
        expect_mode="existing",
        expect_stacks=("swift",),
        present=(".beads", "AGENTS.md", "docs/INDEX.md", "Package.swift", "scripts/check_docs.py"),
        absent=("justfile", ".swift-format", "tests/core/ToolchainTests.swift"),
        untouched=("Package.swift",),
        description_targets=("GLOSSARY.md",),
        notes="existing 模式且无 justfile：只补依赖偏好，报告写明没有 justfile。",
    ),
    "uv-bun-new": Case(
        name="uv-bun-new",
        build=build_uv_bun_new,
        description="一个带 Python 后端和 TypeScript 前端的示例应用",
        stacks=("uv", "bun"),
        expect_mode="new",
        expect_stacks=("uv", "bun"),
        present=(
            ".beads",
            "justfile",
            "pyproject.toml",
            "uv.lock",
            "frontend/package.json",
            "frontend/bun.lock",
            "frontend/tests/core/toolchain.test.ts",
            "tests/core/test_toolchain.py",
        ),
        notes="多 stack 新项目：justfile 拼合与 scope 化的 fmt/test。",
    ),
    "none-empty": Case(
        name="none-empty",
        build=build_none_empty,
        description="一个只有文档的流程仓库，不含代码",
        stacks=("none",),
        expect_mode="new",
        expect_stacks=("none",),
        triage=False,
        present=(".beads", "justfile", "AGENTS.md", "docs/INDEX.md"),
        absent=("pyproject.toml", "package.json", "docs/agents/triage-labels.md"),
        notes="none stack：契约 recipe 非零退出；Matt 产物不含 triage，触发表不应有分诊行。",
    ),
}
