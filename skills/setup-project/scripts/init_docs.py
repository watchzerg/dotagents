#!/usr/bin/env python3
"""使用 Python 3.10+ 标准库把标准化文档结构复制到当前项目。

除 AGENTS.md 外的文件缺失才创建，已有文件一律不覆盖。AGENTS.md 按二级标题合并：
缺少的节追加，已有的节与标题外内容原样保留，Matt setup 写入的 `## Agent skills` 节移除。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
PLACEHOLDER = "{{PROJECT_NAME}}"
MATT_SETUP_FILES = ("docs/agents/issue-tracker.md", "docs/agents/domain.md")
TRIAGE_DOC = "docs/agents/triage-labels.md"
AGENTS = "AGENTS.md"
MATT_SECTION = "Agent skills"

Section = tuple[str, str]


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


def merge_agents(existing: str, template: str) -> tuple[str, list[str], str | None]:
    """返回合并结果、追加的节标题、被移除的 Matt 节正文（无则 None）。无变化时原样返回。"""
    preamble, sections = split_sections(existing)
    _, template_sections = split_sections(template)
    present = {title for title, _ in sections}
    removed = next((body for title, body in sections if title == MATT_SECTION), None)
    kept = [body for title, body in sections if title != MATT_SECTION]
    added = [(title, body) for title, body in template_sections if title not in present]
    if removed is None and not added:
        return existing, [], None
    parts = [preamble, *kept, *(body for _, body in added)]
    merged = "\n\n".join(part.strip("\n") for part in parts if part.strip("\n")) + "\n"
    return merged, [title for title, _ in added], removed


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化标准化文档结构。")
    parser.add_argument("--name", help="项目名，默认取当前目录名")
    args = parser.parse_args()

    project = Path.cwd()
    name = args.name or project.name
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
        relative = source.relative_to(TEMPLATES).as_posix()
        target = project / relative
        content = source.read_text(encoding="utf-8").replace(PLACEHOLDER, name)
        if relative == AGENTS and not has_triage:
            content = "".join(
                line for line in content.splitlines(keepends=True) if TRIAGE_DOC not in line
            )
        if relative == AGENTS and target.exists():
            merged, added, removed = merge_agents(target.read_text(encoding="utf-8"), content)
            if not added and removed is None:
                skipped.append(relative)
                continue
            target.write_text(merged, encoding="utf-8")
            if added:
                print(f"已合并 {relative}：追加节 " + "、".join(added))
            if removed is not None:
                print(f"已从 {relative} 移除 `## {MATT_SECTION}` 节，原内容如下：")
                print(removed.rstrip("\n"))
            continue
        if target.exists():
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
