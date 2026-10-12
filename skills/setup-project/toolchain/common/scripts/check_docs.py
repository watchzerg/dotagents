"""检查仓库文档的本地链接、章节锚点与模块可达性；只依赖标准库，不联网。

检查范围：根目录 README、AGENTS、GLOSSARY、CODING_STANDARDS 与 docs/ 下全部 Markdown。
模块页（docs/architecture/modules/*.md）必须能从 docs/architecture/INDEX.md 沿链接到达。
"""

import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT_DOCUMENTS = ("README.md", "AGENTS.md", "GLOSSARY.md", "CODING_STANDARDS.md")
ARCHITECTURE_INDEX = Path("docs/architecture/INDEX.md")
MODULES = Path("docs/architecture/modules")
LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)(?:\s+\"[^\"\n]*\")?\s*\)")
INLINE_CODE = re.compile(r"`[^`\n]*`")


def prose_lines(text: str) -> list[tuple[int, str]]:
    """去掉围栏代码块与行内代码后的正文行。"""
    lines = []
    fence = ""
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            value = marker.group(1)
            if not fence:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = ""
            continue
        if not fence:
            lines.append((number, INLINE_CODE.sub("", line)))
    return lines


def anchors(lines: list[tuple[int, str]]) -> set[str]:
    result: set[str] = set()
    for _, line in lines:
        result.update(re.findall(r'<(?:a|h[1-6])\b[^>]*(?:id|name)="([^"]+)"', line))
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)(?:\s+#+)?$", line)
        if not heading:
            continue
        title = re.sub(r"<[^>]+>", "", heading.group(1)).lower()
        title = LINK.sub(lambda match: match.group(0).split("]", 1)[0].lstrip("!["), title)
        slug = "".join(
            char for char in title if char in "-_ " or unicodedata.category(char)[0] in "LNM"
        ).replace(" ", "-")
        candidate = slug
        suffix = 0
        while candidate in result:
            suffix += 1
            candidate = f"{slug}-{suffix}"
        result.add(candidate)
    return result


def check_documents(root: Path) -> tuple[list[str], int, int]:
    root = root.resolve()
    files = {root / name for name in ROOT_DOCUMENTS} | set((root / "docs").rglob("*.md"))
    errors = []
    documents = {}
    for path in sorted(files):
        if not path.is_file():
            errors.append(f"缺少文档：{path.relative_to(root)}")
        else:
            documents[path] = prose_lines(path.read_text(encoding="utf-8"))
    sections = {path: anchors(lines) for path, lines in documents.items()}
    graph: dict[Path, set[Path]] = {path: set() for path in documents}
    links = 0
    for source, lines in documents.items():
        for number, line in lines:
            for match in LINK.finditer(line):
                destination = match.group(1).strip("<>")
                url = urlsplit(destination)
                if url.scheme or url.netloc:
                    continue
                links += 1
                target = (source.parent / unquote(url.path)).resolve() if url.path else source
                location = f"{source.relative_to(root)}:{number}"
                if not target.is_relative_to(root):
                    errors.append(f"{location} 链接越出仓库：{destination}")
                    continue
                if not target.exists():
                    errors.append(f"{location} 链接目标不存在：{destination}")
                    continue
                if target in documents:
                    graph[source].add(target)
                if url.fragment and target.suffix == ".md":
                    if target not in sections:
                        sections[target] = anchors(prose_lines(target.read_text(encoding="utf-8")))
                    if unquote(url.fragment) not in sections[target]:
                        errors.append(f"{location} 章节不存在：{destination}")
    visited: set[Path] = set()
    pending = [root / ARCHITECTURE_INDEX]
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(graph.get(current, set()) - visited)
    for module in sorted(set((root / MODULES).rglob("*.md")) - visited):
        errors.append(f"架构入口不可达：{module.relative_to(root)}")
    return errors, len(documents), links


def main() -> int:
    errors, documents, links = check_documents(Path(__file__).resolve().parents[1])
    if errors:
        print("\n".join(errors))
        return 1
    print(f"文档检查通过：{documents} 篇，{links} 个本地链接；模块页均可从架构入口到达。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
