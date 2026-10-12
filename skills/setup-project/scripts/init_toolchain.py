#!/usr/bin/env python3
"""使用 Python 3.14+ 标准库初始化项目工具链、justfile 与开发文档。

项目由零到多个 stack 组成（uv、bun、swift），每个 stack 是 `toolchain/stacks/<name>/` 下的自包含模块：
`stack.json`（标签、布局、安装命令、文档表格单元）、`recipes.just`（私有 recipe）、`home/` 与 `root/`
（要复制的文件）、`gitignore`、`overlay/`（镜像项目根的文档正文片段）。脚本按文件证据判定 stack 集合；已有工具链的
项目不改动工具链与 justfile，只把各 stack 的依赖偏好补进文档；新项目复制 stack 文件、拼出根
justfile、运行安装命令，并用拼合后的正文替换阶段 2 留下的 `<待填 阶段3：…>` 标记。所有文件缺失才创建。
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TOOLCHAIN = SKILL / "toolchain"
STACKS = ("uv", "bun", "swift")
NONE = "none"
EXIT_UNDETERMINED = 3
STAGE3_MARKER = "<待填 阶段3"
REQUIRED_RECIPES = (
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
LOCK = "python3 scripts/with_lock.py "
AGGREGATED = {
    "check-toolchain": "# 工具链检查：核对各运行时与版本声明，不安装。",
    "install": "# 按 lock 安装依赖；不升级宿主工具。",
    "lint": "# 静态检查，不修改源码。",
    "typecheck": "# 类型检查，不修改源码。",
}
OTHER_MARKERS = (
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "CMakeLists.txt",
)
EXISTING_SECTIONS = {"docs/development/technology-stack.md": {"依赖政策"}}
JUSTFILE_HEADER = """\
# 项目命令契约：check-toolchain、install、fmt、lint、typecheck、test、docs-check、gate-core、gate-full 是必需入口，名称与职责保持稳定。
# 验证不修改源码；fmt 是修改文件的入口。缺失能力须非零退出，不能用空命令冒充通过。
# 公开 recipe 聚合各 stack 的私有 recipe（<stack>-*）；full 测试经 scripts/with_lock.py 的主机锁串行。
# 测试分层与门禁定义见 docs/development/workflow.md。
set positional-arguments

# 列出项目命令。
default:
    @just --list
"""

Section = tuple[str, str]


class Stack:
    def __init__(self, name: str, shared: bool) -> None:
        self.name = name
        self.dir = TOOLCHAIN / "stacks" / name
        manifest = json.loads((self.dir / "stack.json").read_text(encoding="utf-8"))
        self.label: str = manifest["label"]
        self.host_tools: str = manifest["host_tools"]
        self.install: list[dict] = manifest["install"]
        self.cells: dict[str, str] = manifest["cells"]
        self.home: str = manifest.get("home_when_shared", ".") if shared else "."

    @property
    def placeholders(self) -> dict[str, str]:
        at_root = self.home == "."
        return {
            "{{LABEL}}": self.label,
            "{{HOME_DIR}}": self.home,
            "{{HOME}}": "" if at_root else self.home + "/",
            "{{ROOT}}": "." if at_root else os.path.relpath(".", self.home),
        }

    def cell(self, key: str) -> str:
        return expand(self.cells[key], self.placeholders)


def expand(text: str, placeholders: dict[str, str]) -> str:
    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text


def run(args: list[str], cwd: Path) -> int:
    print("$ " + " ".join(args), flush=True)
    try:
        return subprocess.run(args, cwd=cwd, check=False).returncode
    except OSError as exc:
        print(f"错误：无法执行 {args[0]}：{exc}", file=sys.stderr)
        return 1


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


def detect(project: Path) -> tuple[list[str], list[str], bool]:
    """返回 (判定出的 stack 列表, 证据列表, 是否已有工具链)。"""
    evidence: list[str] = []
    found: set[str] = set()
    pyproject = project / "pyproject.toml"
    if (project / "uv.lock").is_file():
        found.add("uv")
        evidence.append("uv.lock")
    if pyproject.is_file():
        if "[tool.uv]" in pyproject.read_text(encoding="utf-8"):
            found.add("uv")
            evidence.append("pyproject.toml 含 [tool.uv]")
        elif "uv" not in found:
            evidence.append("pyproject.toml（无 uv.lock）")
    bun_files = [
        path
        for pattern in ("bun.lock", "*/bun.lock", "bunfig.toml", "*/bunfig.toml")
        for path in project.glob(pattern)
        if "node_modules" not in path.parts
    ]
    if bun_files:
        found.add("bun")
        evidence.extend(path.relative_to(project).as_posix() for path in bun_files)
    else:
        package_json = [p for p in project.glob("*/package.json") if "node_modules" not in p.parts]
        if (project / "package.json").is_file():
            package_json.append(project / "package.json")
        evidence.extend(f"{p.relative_to(project).as_posix()}（无 bun.lock）" for p in package_json)
    swift_files = [p.name for p in project.glob("*.xcodeproj")] + [
        p.name for p in project.glob("*.xcworkspace")
    ]
    if (project / "Package.swift").is_file():
        swift_files.insert(0, "Package.swift")
    if swift_files:
        found.add("swift")
        evidence.extend(swift_files)
    evidence.extend(name for name in OTHER_MARKERS if (project / name).exists())
    if (project / "justfile").is_file():
        evidence.append("justfile")
    existing = any("（无 " not in item for item in evidence)
    return [name for name in STACKS if name in found], evidence, existing


def split_sections(text: str) -> tuple[str, list[Section]]:
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


def section_bodies(path: Path) -> dict[str, str]:
    """返回文件中每个二级节的正文（不含标题行）。"""
    _, sections = split_sections(path.read_text(encoding="utf-8"))
    return {title: body.partition("\n")[2].strip("\n") for title, body in sections}


def doc_placeholders(stacks: list[Stack]) -> dict[str, str]:
    multi = len(stacks) > 1

    def join(key: str) -> str:
        if not multi:
            return stacks[0].cell(key)
        return "；".join(f"{stack.label}：{stack.cell(key)}" for stack in stacks)

    layout = ""
    if multi:
        places = "、".join(
            f"{s.label} 在{'仓库根目录' if s.home == '.' else ' `' + s.home + '/`'}" for s in stacks
        )
        layout = f"布局：{places}。"
    names = "、".join(f"`{s.name}`" for s in stacks)
    return {
        "{{HOST_TOOLS}}": "、".join([s.host_tools for s in stacks] + ["`just`（Homebrew）"]),
        "{{LAYOUT}}": layout,
        "{{ARGS}}": "[scope] [参数]" if multi else "[参数]",
        "{{SCOPE_NOTE}}": f"定向参数先写 scope（{names}），再写各自 runner 的参数。"
        if multi
        else "",
        **{f"{{{{{key.upper()}}}}}": join(key) for key in stacks[0].cells},
    }


def compose_docs(stacks: list[Stack], placeholders: dict[str, str]) -> dict[str, dict[str, str]]:
    """拼出每个文档路径下各节的正文：公共正文在前，各 stack 片段在后（多 stack 时加三级标题）。"""
    common_root = TOOLCHAIN / "overlay"
    docs: dict[str, dict[str, list[str]]] = {}
    for path in sorted(common_root.rglob("*.md")):
        relative = path.relative_to(common_root).as_posix()
        for title, body in section_bodies(path).items():
            docs.setdefault(relative, {}).setdefault(title, []).append(expand(body, placeholders))
    for stack in stacks:
        fragments = stack.dir / "overlay"
        for path in sorted(fragments.rglob("*.md")):
            relative = path.relative_to(fragments).as_posix()
            for title, body in section_bodies(path).items():
                body = expand(body, {**placeholders, **stack.placeholders})
                if len(stacks) > 1:
                    body = f"### {stack.label}\n\n{body}"
                docs.setdefault(relative, {}).setdefault(title, []).append(body)
    return {
        relative: {title: "\n\n".join(parts) for title, parts in sections.items()}
        for relative, sections in docs.items()
    }


def all_target(name: str, stacks: list[Stack]) -> str:
    """无参数时要运行的目标：单 stack 是其私有 recipe，多 stack 是私有聚合 recipe `<name>-all`。"""
    return f"{stacks[0].name}-{name}" if len(stacks) == 1 else f"{name}-all"


def dispatch_recipe(name: str, stacks: list[Stack], comment: str, prefix: str = "") -> str:
    """公开 recipe 转发到各 stack 的私有 `<stack>-<name>`；多 stack 时第一个参数是 scope。

    可变参数 recipe 会把命令行上后续的 recipe 名当作参数，所以多 stack 的"全部"路径经依赖式聚合
    recipe 执行，而不是 `just a-x b-x`。
    """
    names = [stack.name for stack in stacks]
    if len(names) == 1:
        return f'{comment}\n{name} *args:\n    {prefix}just {names[0]}-{name} "$@"\n'
    aggregate = f"[private]\n{name}-all: {' '.join(f'{n}-{name}' for n in names)}\n"
    return (
        f"{comment}\n"
        f"{name} *args:\n"
        "    #!/usr/bin/env bash\n"
        "    set -euo pipefail\n"
        '    if [ "$#" -eq 0 ]; then\n'
        f"      exec {prefix}just {name}-all\n"
        "    fi\n"
        '    case "$1" in\n'
        f'      {"|".join(names)}) scope="$1"; shift; exec {prefix}just "${{scope}}-{name}" "$@" ;;\n'
        f"      *) echo '错误：scope 必须是 {' 或 '.join(names)}。' >&2; exit 2 ;;\n"
        "    esac\n\n"
        f"{aggregate}"
    )


def render_justfile(stacks: list[Stack], placeholders: dict[str, str]) -> str:
    def deps(suffix: str) -> str:
        return " ".join(f"{stack.name}-{suffix}" for stack in stacks)

    parts = [JUSTFILE_HEADER]
    for recipe in REQUIRED_RECIPES:
        if recipe in AGGREGATED:
            parts.append(f"{AGGREGATED[recipe]}\n{recipe}: {deps(recipe)}\n")
        elif recipe == "fmt":
            parts.append(
                dispatch_recipe(
                    "fmt", stacks, "# 格式化并修复可自动修复的 lint；会修改文件，不属于门禁。"
                )
            )
        elif recipe == "test":
            parts.append(dispatch_recipe("test", stacks, "# 默认运行全部 core 测试；传参可定向。"))
        elif recipe == "test-full":
            parts.append(
                dispatch_recipe(
                    "test-full",
                    stacks,
                    "# 运行 full 测试，经主机锁串行；默认全部，传参可定向。目录不存在时只打印提示。",
                    LOCK,
                )
            )
        elif recipe == "docs-check":
            parts.append(
                "# 检查本地文档链接、锚点与模块可达性，不联网。\ndocs-check:\n    python3 scripts/check_docs.py\n"
            )
        elif recipe == "gate-core":
            parts.append(
                "# 可跨 worktree 并行：工具链、文档、静态检查与全部 core 测试；不接受筛选参数。\n"
                f"gate-core: check-toolchain docs-check lint typecheck {deps('test-core')}\n"
            )
        elif recipe == "gate-full":
            parts.append(
                "# 完整验收：gate-core 后在主机锁内串行运行各 stack 的 tests/full；目录出现即纳入，存在而无测试视为失败。\n"
                f"gate-full: gate-core\n    {LOCK}just {all_target('test-full', stacks)}\n"
            )
    for stack in stacks:
        recipes = (stack.dir / "recipes.just").read_text(encoding="utf-8")
        parts.append(expand(recipes, {**placeholders, **stack.placeholders}))
    return "\n".join(parts)


def apply_overlay(target: Path, bodies: dict[str, str], only: set[str] | None) -> list[str]:
    """把 bodies 中同名节的正文替换进 target 中仍含阶段3 标记的节，返回替换的节名。"""
    if not target.is_file():
        return []
    preamble, sections = split_sections(target.read_text(encoding="utf-8"))
    replaced: list[str] = []
    rebuilt: list[str] = [preamble]
    for title, body in sections:
        if STAGE3_MARKER in body and title in bodies and (only is None or title in only):
            lines = [line for line in body.splitlines(keepends=True) if STAGE3_MARKER not in line]
            body = "".join(lines).rstrip("\n") + "\n\n" + bodies[title] + "\n\n"
            replaced.append(title)
        rebuilt.append(body)
    if replaced:
        target.write_text("".join(rebuilt).rstrip("\n") + "\n", encoding="utf-8")
    return replaced


def copy_tree(source_dir: Path, dest_dir: Path, placeholders: dict[str, str], report: dict) -> None:
    if not source_dir.is_dir():
        return
    for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
        relative = expand(source.relative_to(source_dir).as_posix(), placeholders)
        copy_file(source, dest_dir / relative, placeholders, report)


def copy_file(source: Path, target: Path, placeholders: dict[str, str], report: dict) -> None:
    shown = target.relative_to(report["project"]).as_posix()
    if target.exists():
        report["skipped"].append(shown)
        return
    content = expand(source.read_text(encoding="utf-8"), placeholders)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    report["created"].append(shown)


def write_generated(target: Path, content: str, report: dict) -> None:
    shown = target.relative_to(report["project"]).as_posix()
    if target.exists():
        report["skipped"].append(shown)
        return
    target.write_text(content, encoding="utf-8")
    report["created"].append(shown)


def append_gitignore(project: Path, fragment: Path, report: dict) -> None:
    if not fragment.is_file():
        return
    target = project / ".gitignore"
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    present = {line.strip() for line in existing.splitlines()}
    missing = [
        line
        for line in fragment.read_text(encoding="utf-8").splitlines()
        if line.strip() not in present
    ]
    if not missing:
        return
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    target.write_text(existing + prefix + "\n".join(missing) + "\n", encoding="utf-8")
    report["gitignore"].extend(missing)


def missing_recipes(justfile: Path) -> list[str]:
    names = set(
        re.findall(r"^([A-Za-z_][\w-]*)[^:\n]*:", justfile.read_text(encoding="utf-8"), re.M)
    )
    return [name for name in REQUIRED_RECIPES if name not in names]


def dist_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return cleaned or "project"


def module_name(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", name)
    joined = "".join(part[:1].upper() + part[1:] for part in parts) or "Project"
    return joined if not joined[0].isdigit() else "App" + joined


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化项目工具链、justfile 与开发文档。")
    parser.add_argument(
        "--stacks",
        nargs="+",
        choices=STACKS + (NONE,),
        metavar="STACK",
        help=f"项目使用的 stack，可多选：{' '.join(STACKS)}；没有预置 stack 时写 {NONE}。无法自动判定时必须指定",
    )
    parser.add_argument("--name", help="项目名，默认取当前目录名")
    parser.add_argument("--skip-install", action="store_true", help="不运行安装命令与 gate-core")
    args = parser.parse_args()

    project = Path.cwd()
    if not in_git_work_tree():
        print("错误：当前目录不在 Git 工作区内，请先初始化 Git。", file=sys.stderr)
        return 1
    if (
        not (project / "docs/INDEX.md").is_file()
        or not (project / "docs/agents/testing.md").is_file()
    ):
        print("错误：缺少阶段 2 的文档结构，请先运行 init_docs.py。", file=sys.stderr)
        return 1

    detected, evidence, existing = detect(project)
    if args.stacks:
        if NONE in args.stacks and len(args.stacks) > 1:
            print(f"错误：{NONE} 不能与其他 stack 同时指定。", file=sys.stderr)
            return 2
        names = [name for name in STACKS if name in args.stacks]
        if detected and names != detected:
            print(
                f"提示：自动判定为 {'、'.join(detected)}，按指定使用 {'、'.join(names) or NONE}。"
            )
    elif detected or existing:
        names = detected
    else:
        print(
            "无法判定项目类型。证据：" + ("、".join(evidence) or "空项目") + "。", file=sys.stderr
        )
        print(f"请用 --stacks 指定后重试，可多选：{' '.join(STACKS)}，或 {NONE}。", file=sys.stderr)
        return EXIT_UNDETERMINED
    mode = "existing" if existing else "new"
    print(
        f"stacks：{'、'.join(names) or '无预置'}；模式：{mode}；证据：{'、'.join(evidence) or '空项目'}"
    )

    stacks = [Stack(name, shared=len(names) > 1) for name in names]
    name = args.name or project.name
    placeholders = {
        "{{PROJECT_NAME}}": name,
        "{{DIST_NAME}}": dist_name(name),
        "{{MODULE_NAME}}": module_name(name),
    }
    report: dict = {"project": project, "created": [], "skipped": [], "gitignore": [], "docs": []}

    if mode == "new":
        for stack in stacks:
            stack_placeholders = {**placeholders, **stack.placeholders}
            copy_tree(stack.dir / "root", project, stack_placeholders, report)
            copy_tree(stack.dir / "home", project / stack.home, stack_placeholders, report)
            append_gitignore(project, stack.dir / "gitignore", report)
        copy_tree(TOOLCHAIN / "common", project, placeholders, report)
        if stacks:
            justfile = render_justfile(stacks, placeholders)
        else:
            justfile = (TOOLCHAIN / "none/justfile").read_text(encoding="utf-8")
        write_generated(project / "justfile", justfile, report)

    if stacks:
        docs = compose_docs(stacks, {**placeholders, **doc_placeholders(stacks)})
    elif mode == "new":
        none_root = TOOLCHAIN / "none/overlay"
        docs = {
            path.relative_to(none_root).as_posix(): section_bodies(path)
            for path in sorted(none_root.rglob("*.md"))
        }
    else:
        docs = {}
    for relative, bodies in docs.items():
        only = EXISTING_SECTIONS.get(relative, set()) if mode == "existing" else None
        if mode == "existing" and not only:
            continue
        replaced = apply_overlay(project / relative, bodies, only)
        report["docs"].extend(f"{relative}：{title}" for title in replaced)

    for path in report["created"]:
        print(f"已创建 {path}")
    for path in report["skipped"]:
        print(f"已存在，跳过 {path}")
    if report["gitignore"]:
        print("已追加 .gitignore：" + "、".join(report["gitignore"]))
    for item in report["docs"]:
        print(f"已填写 {item}")

    if mode == "existing":
        justfile_path = project / "justfile"
        if justfile_path.is_file():
            missing = missing_recipes(justfile_path)
            if missing:
                print("提示：justfile 缺少契约 recipe：" + "、".join(missing) + "；建议补齐。")
        else:
            print(
                "提示：项目已有工具链但没有 justfile；可参考 toolchain/stacks/*/recipes.just 建立命令契约。"
            )
        return 0

    if args.skip_install:
        print("已跳过安装与 gate-core。")
        return 0
    for stack in stacks:
        for step in stack.install:
            cwd = project if step["cwd"] == "root" else project / stack.home
            code = run(step["args"], cwd)
            if code != 0:
                print(f"错误：{' '.join(step['args'])} 退出码 {code}。", file=sys.stderr)
                return code
    code = run(["just", "gate-core"], project)
    print("gate-core 通过。" if code == 0 else f"gate-core 失败，退出码 {code}。")
    return code


if __name__ == "__main__":
    sys.exit(main())
