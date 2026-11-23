#!/usr/bin/env python3
"""使用 Python 3.14+ 标准库初始化项目工具链、mise task 与开发文档。

项目由零到多个 stack 组成（uv、node、swift），每个 stack 是 `toolchain/stacks/<name>/` 下的自包含模块：
`stack.json`（标签、布局、mise 钉住的工具版本 line、安装命令、文档表格单元）、`root/`（复制到仓库根，含
`mise-tasks/<name>/` 下的 file task）与 `home/`（复制到 stack 目录）、`gitignore`、`overlay/`（镜像项目根的文档正文片段）。
脚本按文件证据判定 stack 集合；已有工具链的项目不改动工具链与 mise 配置，只补缺 `scripts/check_docs.py`、
`scripts/with_lock.py` 并把各 stack 的依赖偏好补进文档；新项目复制 stack 文件、生成根 `mise.toml`（钉版本的工具、
`[env]` 与聚合各 stack task 的公开 task）、运行安装命令，并用拼合后的正文替换 init_docs.py 留下的 `<待填 阶段3：…>`
标记。所有文件缺失才创建。`--detect-only` 只打印判定结果，供初始化流程在落地前一次性收集需要用户回答的问题；
门禁不在本脚本内运行。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TOOLCHAIN = SKILL / "toolchain"
STACKS = ("uv", "node", "swift")
NONE = "none"
EXIT_UNDETERMINED = 3
STAGE3_MARKER = "<待填 阶段3"
# 公开 task 及其 description；前 7 个由各 stack 的同名 file task（`<stack>:<name>`）聚合。
PUBLIC_TASKS = {
    "check-toolchain": "核对各运行时与版本声明",
    "install": "按 lock 安装依赖；不升级宿主工具",
    "fmt": "格式化并修复可自动修复的 lint；会修改文件，不属于门禁",
    "lint": "静态检查，不修改源码",
    "typecheck": "类型检查，不修改源码",
    "test": "运行全部 core 测试；定向运行用 <stack>:test 加 runner 参数",
    "test-full": "在主机锁内运行全部 full 测试；定向运行用 <stack>:test-full 加 runner 参数",
    "docs-check": "检查文档链接、锚点、可达性、索引登记、体量预算、标题骨架与 covers，不联网",
    "docs-affected": "改动提示：列出相对基准（默认 HEAD，可传参）的改动命中 covers 的文档页；总是成功，不属于门禁",
    "gate-core": "可跨 worktree 并行：工具链、文档、静态检查与全部 core 测试，彼此并行",
    "gate-full": "完整门禁：gate-core 通过后在主机锁内运行各 stack 的 tests/full",
}
REQUIRED_TASKS = tuple(PUBLIC_TASKS)
STACK_TASKS = REQUIRED_TASKS[:7]
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
# 模板目录里混入的系统或缓存文件，复制时跳过；其余点文件（.python-version 等）照常复制。
IGNORED_NAMES = {".DS_Store", "Thumbs.db"}
# mise 读取 task 的位置：配置文件的 [tasks] 与 file task 目录（子目录名成为 `:` 分隔的命名空间）。
MISE_CONFIGS = ("mise.toml", ".mise.toml", ".config/mise.toml", "mise/config.toml")
MISE_TASK_DIRS = ("mise-tasks", ".mise-tasks", "mise/tasks", ".mise/tasks", ".config/mise/tasks")
MISE_HEADER = """\
# 项目命令契约：check-toolchain、install、fmt、lint、typecheck、test、test-full、docs-check、docs-affected、gate-core、gate-full 是必需的公开 task，名称与职责保持稳定。
# 公开 task 聚合各 stack 在 mise-tasks/<stack>/ 下的 file task（task 名 <stack>:<name>），depends 中的 task 并行执行；
# 定向运行直接调用 stack task 并传 runner 参数，如 mise run uv:test -k 名称。验证不修改源码，fmt 是修改文件的入口；
# 缺失能力须非零退出，不能用空命令冒充通过。门禁定义见 docs/development/workflow.md，测试分层见 docs/development/test-layers.md。
# [tools] 只钉对版本敏感的工具的兼容版本 line，精确版本由 mise.lock 记录。
"""
MISE_ENV = """\
[env]
# 项目环境变量写在这里；本机私有值写 mise.local.toml（不提交）。
"""
# 新项目落地后在根目录执行：trust 让 mise 读取生成的 mise.toml；有钉住的工具时再安装并生成 mise.lock。
MISE_TRUST = ["mise", "trust"]
MISE_PIN_STEPS: tuple[list[str], ...] = (["mise", "install"], ["mise", "lock"])

Section = tuple[str, str]


class Stack:
    def __init__(self, name: str, shared: bool) -> None:
        self.name = name
        self.dir = TOOLCHAIN / "stacks" / name
        manifest = json.loads((self.dir / "stack.json").read_text(encoding="utf-8"))
        self.label: str = manifest["label"]
        self.host_tools: str = manifest["host_tools"]
        self.mise: dict[str, str] = manifest.get("mise", {})
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
    pnpm_locks = [
        path
        for pattern in ("pnpm-lock.yaml", "*/pnpm-lock.yaml")
        for path in project.glob(pattern)
        if "node_modules" not in path.parts
    ]
    if pnpm_locks:
        found.add("node")
        evidence.extend(path.relative_to(project).as_posix() for path in pnpm_locks)
    else:
        package_json = [p for p in project.glob("*/package.json") if "node_modules" not in p.parts]
        if (project / "package.json").is_file():
            package_json.append(project / "package.json")
        evidence.extend(
            f"{p.relative_to(project).as_posix()}（无 pnpm-lock.yaml）" for p in package_json
        )
    swift_files = [p.name for p in project.glob("*.xcodeproj")] + [
        p.name for p in project.glob("*.xcworkspace")
    ]
    if (project / "Package.swift").is_file():
        swift_files.insert(0, "Package.swift")
    if swift_files:
        found.add("swift")
        evidence.extend(swift_files)
    evidence.extend(name for name in OTHER_MARKERS if (project / name).exists())
    evidence.extend(name for name in MISE_CONFIGS if (project / name).is_file())
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


def mise_tools(stacks: list[Stack]) -> dict[str, str]:
    return {tool: line for stack in stacks for tool, line in stack.mise.items()}


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
    pinned = "、".join(f"`{tool}`" for tool in mise_tools(stacks))
    return {
        "{{HOST_TOOLS}}": "、".join(dict.fromkeys(["`mise`"] + [s.host_tools for s in stacks])),
        "{{PIN_NOTE}}": f"项目根 `mise.toml` 钉住对版本敏感的 {pinned} 的版本 line，`mise.lock` 锁定精确版本。"
        if pinned
        else "",
        "{{LAYOUT}}": layout,
        "{{STACK}}": "<stack>" if multi else stacks[0].name,
        "{{SCOPE_NOTE}}": f"`<stack>` 取 {names}。" if multi else "",
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


def render_mise_toml(stacks: list[Stack]) -> str:
    """根 mise.toml：钉版本的 [tools]、[env] 与聚合各 stack file task 的公开 task。"""
    pins = "".join(f'{tool} = "{line}"\n' for tool, line in mise_tools(stacks).items())
    parts = [MISE_HEADER, "[tools]\n" + pins, MISE_ENV]

    def task(name: str, description: str, body: str) -> None:
        parts.append(f'[tasks.{name}]\ndescription = "{description}"\n{body}')

    def deps(names: list[str]) -> str:
        return "depends = [" + ", ".join(f'"{n}"' for n in names) + "]\n"

    for name in STACK_TASKS:
        task(name, PUBLIC_TASKS[name], deps([f"{s.name}:{name}" for s in stacks]))
    task("docs-check", PUBLIC_TASKS["docs-check"], 'run = "python3 scripts/check_docs.py"\n')
    task(
        "docs-affected",
        PUBLIC_TASKS["docs-affected"],
        'run = "python3 scripts/check_docs.py --affected"\n',
    )
    task(
        "gate-core",
        PUBLIC_TASKS["gate-core"],
        deps(["check-toolchain", "docs-check", "lint", "typecheck", "test"]),
    )
    task(
        "gate-full",
        PUBLIC_TASKS["gate-full"],
        deps(["gate-core"]) + 'run = [{ task = "test-full" }]\n',
    )
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


def ignored(relative: Path) -> bool:
    return (
        relative.name in IGNORED_NAMES
        or relative.suffix == ".pyc"
        or "__pycache__" in relative.parts
    )


def copy_tree(source_dir: Path, dest_dir: Path, placeholders: dict[str, str], report: dict) -> None:
    if not source_dir.is_dir():
        return
    for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
        if ignored(source.relative_to(source_dir)):
            continue
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
    shutil.copymode(source, target)  # mise 只把可执行文件当作 file task
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


def report_tasks(project: Path) -> None:
    """已有工具链时提示 mise 配置缺少的契约 task，或项目还没有 mise task。"""
    names = mise_task_names(project)
    if names is None:
        print(
            "提示：项目已有工具链但没有 mise task；可参考 toolchain/stacks/*/root/mise-tasks/ 与"
            " toolchain/none/mise.toml 建立命令契约。"
        )
        return
    missing = [name for name in REQUIRED_TASKS if name not in names]
    if not missing:
        return
    print("提示：mise 配置缺少契约 task：" + "、".join(missing) + "；建议补齐。")
    check_docs = project / "scripts/check_docs.py"
    if (
        "docs-affected" in missing
        and check_docs.is_file()
        and "--affected" not in check_docs.read_text(encoding="utf-8")
    ):
        # 旧模板或项目改写的 check_docs.py 缺失才复制，不会被升级；给出可直接照做的写法，免得 agent 另行设计。
        print(
            "提示：项目已有的 scripts/check_docs.py 不支持 --affected；docs-affected 写成非零退出并说明原因，"
            f"报告列为票据候选，实现可从 {TOOLCHAIN / 'common/scripts/check_docs.py'} 移植。"
        )


def mise_task_names(project: Path) -> set[str] | None:
    """按文件读取 mise task 名：配置文件的 [tasks] 表与 file task 目录；都没有时返回 None。

    不调用 mise，因为未 trust 的配置会被拒绝读取；include 等间接来源看不到，由 agent 用 `mise tasks` 复核。
    """
    names: set[str] = set()
    found = False
    for config in MISE_CONFIGS:
        path = project / config
        if path.is_file():
            found = True
            try:
                names.update(tomllib.loads(path.read_text(encoding="utf-8")).get("tasks", {}))
            except tomllib.TOMLDecodeError as exc:
                print(f"提示：{config} 不是合法 TOML（{exc}），无法列出其中的 task。")
    for directory in MISE_TASK_DIRS:
        root = project / directory
        if root.is_dir():
            found = True
            names.update(
                path.relative_to(root).with_suffix("").as_posix().replace("/", ":")
                for path in root.rglob("*")
                if path.is_file() and not ignored(path.relative_to(root))
            )
    return names if found else None


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
    """项目名：--name，否则 AGENTS.md 的一级标题，否则目录名；与 init_docs.py 一致。"""
    if override:
        return override
    agents = project / "AGENTS.md"
    if agents.is_file():
        title = heading_title(agents.read_text(encoding="utf-8"))
        if title:
            return title
    return project.name


def dist_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return cleaned or "project"


def module_name(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", name)
    joined = "".join(part[:1].upper() + part[1:] for part in parts) or "Project"
    return joined if not joined[0].isdigit() else "App" + joined


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化项目工具链、mise task 与开发文档。")
    parser.add_argument(
        "--stacks",
        nargs="+",
        choices=STACKS + (NONE,),
        metavar="STACK",
        help=f"项目使用的 stack，可多选：{' '.join(STACKS)}；没有预置 stack 时写 {NONE}。无法自动判定时必须指定",
    )
    parser.add_argument("--name", help="项目名，默认取当前目录名")
    parser.add_argument("--skip-install", action="store_true", help="不运行安装命令")
    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="只打印 stack、模式、证据与 mise 配置缺少的契约 task，不写任何文件",
    )
    args = parser.parse_args()

    project = Path.cwd()
    if not in_git_work_tree():
        print("错误：当前目录不在 Git 工作区内，请先初始化 Git。", file=sys.stderr)
        return 1
    if (
        not (project / "docs/INDEX.md").is_file()
        or not (project / "docs/agents/testing.md").is_file()
    ):
        print("错误：缺少文档结构，请先运行 init_docs.py。", file=sys.stderr)
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
    if mode == "new" and "swift" in names and shutil.which("xcodebuild") is None:
        print(
            "错误：swift stack 依赖 Xcode，仅支持 macOS；未找到 xcodebuild，未写入任何文件。",
            file=sys.stderr,
        )
        return 1
    print(
        f"stacks：{'、'.join(names) or '无预置'}；模式：{mode}；证据：{'、'.join(evidence) or '空项目'}"
    )
    if args.detect_only:
        if mode == "existing":
            report_tasks(project)
        return 0

    stacks = [Stack(name, shared=len(names) > 1) for name in names]
    name = project_name(project, args.name)
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
        append_gitignore(project, TOOLCHAIN / "gitignore", report)
        if stacks:
            mise_toml = render_mise_toml(stacks)
        else:
            mise_toml = (TOOLCHAIN / "none/mise.toml").read_text(encoding="utf-8")
        write_generated(project / "mise.toml", mise_toml, report)
    else:
        # 已有工具链的项目不碰工具链文件，唯一例外是 common 下的两个脚本：只用标准库、与 stack 无关，
        # 缺失才补。check_docs.py 供 agent 写出可用的 docs-check task；with_lock.py 供 agent 把已有的
        # full 测试入口包进主机锁，否则这类项目的 test-full / gate-full 永远拿不到锁。
        copy_tree(TOOLCHAIN / "common", project, placeholders, report)

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
        report_tasks(project)
        return 0

    if args.skip_install:
        print("已跳过安装。")
        return 0
    steps = [(MISE_TRUST, project)]
    if mise_tools(stacks):
        steps.extend((command, project) for command in MISE_PIN_STEPS)
    for stack in stacks:
        for step in stack.install:
            cwd = project if step["cwd"] == "root" else project / stack.home
            steps.append((step["args"], cwd))
    for command, cwd in steps:
        code = run(command, cwd)
        if code != 0:
            print(
                f"错误：{' '.join(command)} 退出码 {code}。修复宿主工具后在项目根目录运行"
                " mise run install；重跑本脚本会判定为 existing 并跳过安装。",
                file=sys.stderr,
            )
            return 1
    print("安装完成；门禁由初始化流程末尾统一运行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
