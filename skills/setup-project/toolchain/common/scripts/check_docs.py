"""检查仓库文档的链接、可达性、索引、体量与标题骨架；只依赖标准库，不联网。

规则正文在 docs/agents/documentation.md，本脚本只负责实现。
检查范围：根目录 README、AGENTS、GLOSSARY、CODING_STANDARDS 与 docs/ 下全部 Markdown。
- 本地链接目标与章节锚点必须存在；
- 每篇文档都能从 AGENTS.md 沿文档间链接到达；
- docs/adr、docs/research 下的文档（含子目录）由所在目录的 INDEX.md 直接链接；
- 除 docs/research、docs/adr 外，单页不超过 16 KiB，围栏代码外每段与每个表格单元格不超过 400 字符；
- 模块页与行为规格页的二级标题依次符合固定骨架。
"""

import argparse
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT_DOCUMENTS = ("README.md", "AGENTS.md", "GLOSSARY.md", "CODING_STANDARDS.md")
ENTRY = Path("AGENTS.md")
INDEXED_DIRECTORIES = (Path("docs/adr"), Path("docs/research"))
PAGE_BYTES = 16 * 1024
LINE_CHARS = 400
BUDGET_EXEMPT = (Path("docs/research"), Path("docs/adr"))
MODULES = Path("docs/architecture/modules")
BEHAVIORS = Path("docs/behaviors")
MODULE_HEADINGS = (
    "定位与阅读",
    "当前行为规格",
    "实现设计",
    "接口与依赖",
    "代码与验证入口",
    "变更与决策来源",
)
BEHAVIOR_HEADINGS = ("场景与前提", "操作与可观察结果", "边界与错误情况", "相关模块")
LINK_TITLE = r"""(?:\s+(?:"[^"\n]*"|'[^'\n]*'|\([^)\n]*\)))?"""
LINK = re.compile(
    r"!?\[(?P<text>[^\]\n]*)\]\(\s*(?P<dest><[^>\n]+>|[^\s)]+)" + LINK_TITLE + r"\s*\)"
)
REFERENCE = re.compile(
    r"^ {0,3}\[(?P<label>[^\]\n]+)\]:\s*(?P<dest><[^>\n]+>|\S+)" + LINK_TITLE + r"\s*$"
)
INLINE_CODE = re.compile(r"`[^`\n]*`")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
H2 = re.compile(r"^\s{0,3}##\s+(.+?)(?:\s+#+)?\s*$")


def body_lines(text: str) -> list[tuple[int, str]]:
    """围栏代码块之外的原始行；围栏标记允许任意缩进，覆盖列表项内的代码块。"""
    lines = []
    fence = ""
    for number, line in enumerate(text.splitlines(), 1):
        marker = FENCE.match(line)
        if marker:
            value, rest = marker.groups()
            if not fence:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence) and not rest.strip():
                fence = ""
            continue
        if not fence:
            lines.append((number, line))
    return lines


def link_targets(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """返回 (行号, 链接目标)：行内链接与引用式链接定义；行内代码中的内容不算链接。"""
    targets = []
    for number, line in lines:
        prose = INLINE_CODE.sub("", line)
        targets.extend((number, match.group("dest")) for match in LINK.finditer(prose))
        reference = REFERENCE.match(prose)
        if reference and not reference.group("label").startswith("^"):
            targets.append((number, reference.group("dest")))
    return targets


def heading_title(raw: str) -> str:
    """标题的可见文字：行内代码只去掉反引号保留内容，其余部分去掉 HTML 标签并把链接换成链接文字。"""
    parts = re.split(r"(`[^`\n]*`)", raw)
    visible = []
    for index, part in enumerate(parts):
        if index % 2:
            visible.append(part.strip("`"))
        else:
            part = re.sub(r"<[^>]+>", "", part)
            visible.append(LINK.sub(lambda match: match.group("text"), part))
    return "".join(visible)


def anchors(lines: list[tuple[int, str]]) -> set[str]:
    """按 GitHub 规则生成章节锚点，重名标题依次加 -1、-2 后缀；另收集 HTML 的 id/name。"""
    result: set[str] = set()
    for _, line in lines:
        prose = INLINE_CODE.sub("", line)
        result.update(re.findall(r'<(?:a|h[1-6])\b[^>]*(?:id|name)="([^"]+)"', prose))
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$", line)
        if not heading:
            continue
        title = heading_title(heading.group(1)).lower()
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


def table_cells(line: str) -> list[str]:
    """按未转义且不在行内代码中的 | 切分表格行。"""
    cells = []
    cell = ""
    code = False
    for index, char in enumerate(line):
        if char == "`":
            code = not code
        if char == "|" and not code and (index == 0 or line[index - 1] != "\\"):
            cells.append(cell)
            cell = ""
        else:
            cell += char
    cells.append(cell)
    return [cell.strip() for cell in cells]


def budget_errors(relative: Path, text: str, lines: list[tuple[int, str]]) -> list[str]:
    """单页字节数、段落字符数与表格单元格字符数；围栏代码不计。"""
    errors = []
    size = len(text.encode("utf-8"))
    if size > PAGE_BYTES:
        errors.append(f"{relative} 超出单页预算：{size} 字节 > {PAGE_BYTES}")
    for number, line in lines:
        if line.strip().startswith("|"):
            for cell in table_cells(line.strip()):
                if len(cell) > LINE_CHARS:
                    errors.append(
                        f"{relative}:{number} 表格单元格超出预算：{len(cell)} 字符 > {LINE_CHARS}"
                    )
        elif len(line.rstrip()) > LINE_CHARS:
            errors.append(
                f"{relative}:{number} 段落超出预算：{len(line.rstrip())} 字符 > {LINE_CHARS}"
            )
    return errors


def check_documents(root: Path) -> tuple[list[str], int, int]:
    root = root.resolve()
    files = {root / name for name in ROOT_DOCUMENTS} | set((root / "docs").rglob("*.md"))
    errors = []
    texts = {}
    for path in sorted(files):
        if not path.is_file():
            errors.append(f"缺少文档：{path.relative_to(root)}")
        else:
            texts[path] = path.read_text(encoding="utf-8")
    documents = {path: body_lines(text) for path, text in texts.items()}
    sections = {path: anchors(lines) for path, lines in documents.items()}
    graph: dict[Path, set[Path]] = {path: set() for path in documents}
    links = 0
    for source, lines in documents.items():
        for number, raw in link_targets(lines):
            destination = raw.strip("<>")
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
                    sections[target] = anchors(body_lines(target.read_text(encoding="utf-8")))
                if unquote(url.fragment) not in sections[target]:
                    errors.append(f"{location} 章节不存在：{destination}")
    visited: set[Path] = set()
    pending = [root / ENTRY]
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(graph.get(current, set()) - visited)
    for path in sorted(set(documents) - visited):
        errors.append(f"入口不可达：{path.relative_to(root)}（从 AGENTS.md 沿链接到不了）")
    for directory in INDEXED_DIRECTORIES:
        index = root / directory / "INDEX.md"
        entries = sorted(set((root / directory).rglob("*.md")) - {index})
        if not entries:
            continue
        if index not in documents:
            errors.append(f"缺少索引：{directory / 'INDEX.md'}")
            continue
        for entry in entries:
            if entry not in graph[index]:
                errors.append(
                    f"索引未登记：{entry.relative_to(root)}"
                    f"（应由 {directory / 'INDEX.md'} 直接链接）"
                )
    for path in sorted(documents):
        relative = path.relative_to(root)
        if not any(relative.is_relative_to(exempt) for exempt in BUDGET_EXEMPT):
            errors.extend(budget_errors(relative, texts[path], documents[path]))
    skeletons: list[tuple[Path, tuple[str, ...]]] = [
        (path, MODULE_HEADINGS) for path in (root / MODULES).glob("*.md")
    ]
    skeletons += [
        (path, BEHAVIOR_HEADINGS)
        for path in (root / BEHAVIORS).glob("*.md")
        if path.name != "INDEX.md"
    ]
    for path, expected in sorted(skeletons):
        actual = tuple(
            heading_title(match.group(1)).strip()
            for _, line in documents[path]
            if (match := H2.match(line))
        )
        if actual != expected:
            errors.append(
                f"{path.relative_to(root)} 二级标题应依次为：{'、'.join(expected)}；"
                f"实际：{'、'.join(actual) or '无'}"
            )
    return errors, len(documents), links


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查文档的本地链接、锚点、可达性、目录索引、体量与标题骨架。"
    )
    parser.add_argument(
        "root",
        nargs="?",
        help="项目根目录；默认是本脚本所在 scripts/ 的上级，从别处调用时传目标项目根",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    errors, documents, links = check_documents(root)
    if errors:
        print("\n".join(errors))
        return 1
    print(
        f"文档检查通过：{documents} 篇，{links} 个本地链接；"
        "全部可从 AGENTS.md 到达，索引、体量与标题骨架符合规则。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
