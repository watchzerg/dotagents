#!/usr/bin/env python3
"""使用 Python 3.14+ 标准库把标准化文档结构复制到当前项目。

文件缺失才创建，已有文件一律不覆盖；AGENTS.md 与 docs/agents/testing.md 例外，按二级标题合并：
缺少的节追加，已有的节与标题外内容原样保留，标题前没有内容时补模板开头，AGENTS.md 里 Matt setup
写入的 `## Agent skills` 节移除。testing.md 也合并是因为模板里 CODING_STANDARDS.md 链接它的 `#分层`，
项目自带的 testing.md 没有这一节时文档检查一开始就红。只有空白的文件视为缺失。
项目名取 --name、AGENTS.md 一级标题或目录名。
"""

import argparse
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
PLACEHOLDER = "{{PROJECT_NAME}}"
MATT_SETUP_FILES = ("docs/agents/issue-tracker.md", "docs/agents/domain.md")
TRIAGE_DOC = "docs/agents/triage-labels.md"
AGENTS = "AGENTS.md"
# 按二级标题合并而非整文件跳过的模板文件。
MERGED_FILES = (AGENTS, "docs/agents/testing.md")
# 模板目录里混入的系统或缓存文件，复制时跳过；其余点文件照常复制。
IGNORED_NAMES = {".DS_Store", "Thumbs.db"}
MATT_SECTION = "Agent skills"
INIT_MARKER = "<待填 初始化："

Section = tuple[str, str]


def ignored(relative: Path) -> bool:
    return (
        relative.name in IGNORED_NAMES
        or relative.suffix == ".pyc"
        or "__pycache__" in relative.parts
    )


def in_git_work_tree() -> bool:
    try:
        git = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"错误：无法检查 Git 工作区：{exc}", file=sys.stderr)
        return False
    return git.returncode == 0 and git.stdout.strip() == "true"


def split_sections(text: str) -> tuple[str, list[Section]]:
    """按二级标题切分，返回标题前的内容和 (标题, 含标题行的正文) 列表；代码块内的标题不算。"""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    fenced = False
    for line in text.splitlines(keepends=True):
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            sections.append((line[3:].strip(), [line]))
            continue
        (sections[-1][1] if sections else preamble).append(line)
    return "".join(preamble), [(title, "".join(body)) for title, body in sections]


def heading_title(text: str) -> str | None:
    """二级标题之前的一级标题，没有则 None；代码块内的不算。"""
    preamble, _ = split_sections(text)
    fenced = False
    for line in preamble.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("# "):
            return line[2:].strip() or None
    return None


def project_name(project: Path, override: str | None) -> str:
    """项目名：--name，否则 AGENTS.md 的一级标题，否则目录名。"""
    if override:
        return override
    agents = project / AGENTS
    if agents.is_file():
        title = heading_title(agents.read_text(encoding="utf-8"))
        if title:
            return title
    return project.name


def has_content(path: Path) -> bool:
    """只有空白的文件视为不存在，模板可以直接写入。"""
    return path.is_file() and path.read_text(encoding="utf-8").strip() != ""


def merge_agents(existing: str, template: str) -> tuple[str, list[str], str | None, bool]:
    """返回合并结果、追加的节标题、被移除的 Matt 节正文（无则 None）、是否补了模板开头。

    原文件二级标题之前没有内容时（Matt setup 在空项目上只写 `## Agent skills` 节）
    用模板开头补上标题与 `初始化` 标记。无变化时原样返回。
    """
    preamble, sections = split_sections(existing)
    template_preamble, template_sections = split_sections(template)
    present = {title for title, _ in sections}
    removed = next((body for title, body in sections if title == MATT_SECTION), None)
    kept = [body for title, body in sections if title != MATT_SECTION]
    added = [(title, body) for title, body in template_sections if title not in present]
    head_added = not preamble.strip()
    if head_added:
        preamble = template_preamble
    if removed is None and not added and not head_added:
        return existing, [], None, False
    parts = [preamble, *kept, *(body for _, body in added)]
    merged = "\n\n".join(part.strip("\n") for part in parts if part.strip("\n")) + "\n"
    return merged, [title for title, _ in added], removed, head_added


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化标准化文档结构。")
    parser.add_argument("--name", help="项目名，默认取当前目录名")
    args = parser.parse_args()

    project = Path.cwd()
    name = project_name(project, args.name)
    if not in_git_work_tree():
        print("错误：当前目录不在 Git 工作区内，请先初始化 Git。", file=sys.stderr)
        return 1
    missing = [path for path in MATT_SETUP_FILES if not (project / path).is_file()]
    if missing:
        print(
            "错误：缺少 " + "、".join(missing) + "，请先执行 setup-matt-pocock-skills。",
            file=sys.stderr,
        )
        return 1
    if not TEMPLATES.is_dir():
        print(f"错误：模板目录不存在：{TEMPLATES}", file=sys.stderr)
        return 1

    has_triage = (project / TRIAGE_DOC).is_file()
    created: list[str] = []
    skipped: list[str] = []
    for source in sorted(path for path in TEMPLATES.rglob("*") if path.is_file()):
        if ignored(source.relative_to(TEMPLATES)):
            continue
        relative = source.relative_to(TEMPLATES).as_posix()
        target = project / relative
        content = source.read_text(encoding="utf-8").replace(PLACEHOLDER, name)
        if relative == AGENTS and not has_triage:
            content = "".join(
                line for line in content.splitlines(keepends=True) if TRIAGE_DOC not in line
            )
        if relative in MERGED_FILES and has_content(target):
            merged, added, removed, head_added = merge_agents(
                target.read_text(encoding="utf-8"), content
            )
            if not added and removed is None and not head_added:
                skipped.append(relative)
                continue
            target.write_text(merged, encoding="utf-8")
            if head_added:
                print(f"已为 {relative} 补上模板开头（原文件二级标题前没有内容）")
            if added:
                print(f"已合并 {relative}：追加节 " + "、".join(added))
            if removed is not None:
                print(f"已从 {relative} 移除 `## {MATT_SECTION}` 节，原内容如下：")
                print(removed.rstrip("\n"))
            continue
        if has_content(target):
            skipped.append(relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        created.append(relative)

    for path in created:
        print(f"已创建 {path}")
    for path in skipped:
        print(f"已存在，跳过 {path}")
    print(f"完成：创建 {len(created)} 个，跳过 {len(skipped)} 个。")
    pending = [
        path
        for path in ("AGENTS.md", "README.md", "GLOSSARY.md")
        if INIT_MARKER in (project / path).read_text(encoding="utf-8")
    ]
    print("仍含 初始化 标记：" + ("、".join(pending) if pending else "无"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
