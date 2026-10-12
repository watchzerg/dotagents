"""在临时目录中验证 check_docs.py 的锚点生成与链接解析，不触碰真实项目。"""

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


def check(root: Path, readme: str) -> subprocess.CompletedProcess[str]:
    for name in ROOT_DOCUMENTS:
        (root / name).write_text(f"# {name}\n")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs/target.md").write_text(TARGET)
    (root / "README.md").write_text(readme)
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
    assert "5 个本地链接" in result.stdout


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
    assert "0 个本地链接" in result.stdout
