"""在临时目录中验证 check_docs.py 的链接解析、可达性、索引、体量与标题骨架，不触碰真实项目。"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / (
    "skills/setup-project/toolchain/common/scripts/check_docs.py"
)
ROOT_DOCUMENTS = ("README.md", "AGENTS.md", "GLOSSARY.md", "CODING_STANDARDS.md")

TARGET = """# 目标

## 中文标题

## 使用 `just test`

## `just gate-core`

## 重复

## 重复
"""


def linked(*names: str) -> str:
    return "".join(f"- [x]({name})\n" for name in names)


def check(
    root: Path, readme: str, files: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """AGENTS.md 链接其余根文档与 docs/target.md（4 个本地链接），再写入 README 与额外文件。"""
    files = {
        **{name: f"# {name}\n" for name in ROOT_DOCUMENTS},
        "AGENTS.md": linked("README.md", "GLOSSARY.md", "CODING_STANDARDS.md", "docs/target.md"),
        "docs/target.md": TARGET,
        "README.md": readme,
        **(files or {}),
    }
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(content)
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(root)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def test_heading_anchors_follow_github_rules(tmp_path: Path) -> None:
    readme = "\n".join(
        f"- [x](docs/target.md#{anchor})"
        for anchor in ("中文标题", "使用-just-test", "just-gate-core", "重复", "重复-1")
    )
    result = check(tmp_path, readme + "\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "9 个本地链接" in result.stdout


def test_missing_anchor_is_reported(tmp_path: Path) -> None:
    result = check(tmp_path, "[x](docs/target.md#重复-2)\n[y](docs/target.md#使用)\n")
    assert result.returncode == 1
    assert "README.md:1 章节不存在：docs/target.md#重复-2" in result.stdout
    assert "README.md:2 章节不存在：docs/target.md#使用" in result.stdout


def test_reference_definitions_and_titles_are_checked(tmp_path: Path) -> None:
    readme = (
        "见 [引用][r] 与 [单引号](missing-single.md 'title')、[括号](missing-paren.md (title))。\n"
        "\n"
        '   [r]: missing-ref.md "title"\n'
        "[^1]: 脚注不是链接定义\n"
    )
    result = check(tmp_path, readme)
    assert result.returncode == 1
    assert "README.md:1 链接目标不存在：missing-single.md" in result.stdout
    assert "README.md:1 链接目标不存在：missing-paren.md" in result.stdout
    assert "README.md:3 链接目标不存在：missing-ref.md" in result.stdout
    assert "脚注" not in result.stdout


def test_code_is_not_scanned_for_links(tmp_path: Path) -> None:
    readme = (
        "- 列表项\n"
        "\n"
        "      ```md\n"
        "      [坏链接](missing-in-fence.md)\n"
        "      ```\n"
        "\n"
        "行内 `[坏链接](missing-inline.md)` 不算。\n"
    )
    result = check(tmp_path, readme)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 个本地链接" in result.stdout


def test_every_document_must_be_reachable_from_agents(tmp_path: Path) -> None:
    files = {"docs/a.md": linked("b.md"), "docs/b.md": "# b\n", "docs/orphan.md": "# o\n"}
    result = check(tmp_path, linked("docs/a.md"), files)
    assert result.returncode == 1
    assert result.stdout.splitlines() == ["入口不可达：docs/orphan.md（从 AGENTS.md 沿链接到不了）"]


def test_indexed_directories_link_every_file_directly(tmp_path: Path) -> None:
    files = {
        "docs/research/INDEX.md": linked("a.md"),
        "docs/research/a.md": linked("acceptance/x.md"),
        "docs/research/acceptance/x.md": "# x\n",
        "docs/adr/0001.md": "# adr\n",
    }
    result = check(tmp_path, linked("docs/research/INDEX.md", "docs/adr/0001.md"), files)
    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        "缺少索引：docs/adr/INDEX.md",
        "索引未登记：docs/research/acceptance/x.md（应由 docs/research/INDEX.md 直接链接）",
    ]
    files["docs/research/INDEX.md"] = linked("a.md", "acceptance/x.md")
    files["docs/adr/INDEX.md"] = linked("0001.md")
    result = check(tmp_path, linked("docs/research/INDEX.md", "docs/adr/INDEX.md"), files)
    assert result.returncode == 0, result.stdout + result.stderr


def test_page_paragraph_and_cell_budgets(tmp_path: Path) -> None:
    lines = [
        "a" * 400,
        "b" * 401 + "  ",
        "| " + " | ".join(["c" * 400] * 3) + " |",
        "| x | " + "d" * 401 + " |",
        "| " + "e" * 300 + "\\|" + "e" * 99 + " |",
        "| `" + "f" * 200 + "|" + "f" * 198 + "` |",
        "```",
        "g" * 500,
        "```",
    ]
    files = {
        "docs/lines.md": "\n".join(lines) + "\n",
        "docs/big.md": "h\n" * 8193,
        "docs/research/INDEX.md": "i" * 20000 + "\n",
    }
    result = check(
        tmp_path, linked("docs/lines.md", "docs/big.md", "docs/research/INDEX.md"), files
    )
    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        "docs/big.md 超出单页预算：16386 字节 > 16384",
        "docs/lines.md:2 段落超出预算：401 字符 > 400",
        "docs/lines.md:4 表格单元格超出预算：401 字符 > 400",
        "docs/lines.md:5 表格单元格超出预算：401 字符 > 400",
        "docs/lines.md:6 表格单元格超出预算：401 字符 > 400",
    ]


MODULE = "".join(
    f"## {title}\n"
    for title in ("定位与阅读", "当前行为规格", "实现设计", "接口与依赖", "代码与验证入口")
)
SKELETON = "二级标题应依次为：定位与阅读、当前行为规格、实现设计、接口与依赖、代码与验证入口、变更与决策来源"


def test_module_and_behavior_heading_skeletons(tmp_path: Path) -> None:
    modules = "docs/architecture/modules"
    files = {
        f"{modules}/good.md": "# 模块\n" + MODULE + "## `变更与决策来源`\n\n### 小节\n",
        f"{modules}/missing.md": MODULE,
        f"{modules}/extra.md": MODULE + "## 变更与决策来源\n## 其他\n",
        f"{modules}/order.md": "## 变更与决策来源\n" + MODULE,
        f"{modules}/good/child.md": "## 自由结构\n",
        "docs/behaviors/INDEX.md": "## 自由结构\n",
        "docs/behaviors/good.md": "## 场景与前提\n## 操作与可观察结果\n## 边界与错误情况\n## 相关模块\n",
        "docs/behaviors/bad.md": "```\n## 场景与前提\n```\n",
    }
    result = check(tmp_path, linked(*files), files)
    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        "docs/architecture/modules/extra.md "
        + SKELETON
        + "；实际：定位与阅读、当前行为规格、实现设计、接口与依赖、代码与验证入口、变更与决策来源、其他",
        "docs/architecture/modules/missing.md "
        + SKELETON
        + "；实际：定位与阅读、当前行为规格、实现设计、接口与依赖、代码与验证入口",
        "docs/architecture/modules/order.md "
        + SKELETON
        + "；实际：变更与决策来源、定位与阅读、当前行为规格、实现设计、接口与依赖、代码与验证入口",
        "docs/behaviors/bad.md 二级标题应依次为：场景与前提、操作与可观察结果、边界与错误情况、相关模块；实际：无",
    ]
