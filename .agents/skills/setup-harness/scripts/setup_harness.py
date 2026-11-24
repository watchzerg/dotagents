#!/usr/bin/env python3
"""把 harness/ 下的 statusline 脚本链接到各 harness，并写入对应配置项。只用 Python 3.14+ 标准库。

用法：setup_harness.py [--force]
只处理 PATH 上能找到 CLI 的 harness。先检查全部目标：有冲突且未加 --force 时报告并退出，不做任何修改。
"""

import json
import os
import re
import shlex
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Harness:
    label: str
    executable: str
    source: Path  # 仓库中的 statusline 脚本
    link: Path  # 用户目录中指向 source 的软链接
    config: Path  # 写入配置项的文件
    entry: dict[str, object]  # 期望的配置项整体


def display_path(path: Path, home: Path) -> str:
    """配置里的命令路径：家目录下写成 ~/...，换机器也能用；否则写绝对路径。"""
    if path.is_relative_to(home):
        return "~/" + shlex.quote(str(path.relative_to(home)))
    return shlex.quote(str(path))


def harnesses(repo_root: Path, home: Path, claude_dir: Path) -> list[Harness]:
    content = repo_root / "harness"
    agy_dir = home / ".gemini/antigravity-cli"
    grok_dir = home / ".grok"
    claude_link = claude_dir / "statusline.sh"
    agy_link = agy_dir / "statusline.sh"
    grok_link = grok_dir / "statusline.sh"
    return [
        Harness(
            "Claude Code",
            "claude",
            content / "claude/statusline.sh",
            claude_link,
            claude_dir / "settings.json",
            {"type": "command", "command": display_path(claude_link, home), "refreshInterval": 30},
        ),
        Harness(
            "Antigravity CLI",
            "agy",
            content / "antigravity/statusline.sh",
            agy_link,
            agy_dir / "settings.json",
            {"type": "command", "command": display_path(agy_link, home)},
        ),
        Harness(
            "Grok Build",
            "grok",
            content / "grok/statusline.sh",
            grok_link,
            grok_dir / "config.toml",
            {"type": "command", "command": display_path(grok_link, home)},
        ),
    ]


class Unfixable(ValueError):
    """--force 也无法自动处理的问题。"""


def read_entry(harness: Harness) -> object | None:
    """读出配置文件中现有的 statusline 配置项；文件不存在时为 None。"""
    if not harness.config.exists():
        return None
    text = harness.config.read_text(encoding="utf-8")
    try:
        if harness.config.suffix == ".toml":
            ui = tomllib.loads(text).get("ui", {})
            return ui.get("status_line") if isinstance(ui, dict) else ui
        data = json.loads(text) if text.strip() else {}
    except (tomllib.TOMLDecodeError, json.JSONDecodeError) as error:
        raise Unfixable(f"{harness.config} 解析失败：{error}") from error
    if not isinstance(data, dict):
        raise Unfixable(f"{harness.config} 顶层不是对象")
    return data.get("statusLine")


TOML_HEADER = re.compile(r"^\s*\[\s*ui\s*\.\s*status_line\s*\]\s*(#.*)?$")
TOML_ANY_HEADER = re.compile(r"^\s*\[")


def toml_block(entry: dict[str, object]) -> list[str]:
    # json.dumps 的字符串与整数写法都是合法的 TOML 值。
    return ["[ui.status_line]", *(f"{key} = {json.dumps(value)}" for key, value in entry.items())]


def write_entry(harness: Harness, current: object | None) -> None:
    config = harness.config
    text = config.read_text(encoding="utf-8") if config.exists() else ""
    if config.suffix != ".toml":
        data = json.loads(text) if text.strip() else {}
        data["statusLine"] = harness.entry
        config.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    lines = text.splitlines()
    block = toml_block(harness.entry)
    if current is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(block)
    else:
        start = next((i for i, line in enumerate(lines) if TOML_HEADER.match(line)), None)
        if start is None:
            raise Unfixable(
                f"{config} 中的 ui.status_line 不是独立的 [ui.status_line] 段，请手动修改"
            )
        end = next(
            (i for i in range(start + 1, len(lines)) if TOML_ANY_HEADER.match(lines[i])),
            len(lines),
        )
        # 保留段尾空行，让下一段与之前一样隔开。
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        lines[start:end] = block
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tomllib.loads(config.read_text(encoding="utf-8"))


def link_ok(harness: Harness) -> bool:
    return harness.link.is_symlink() and os.readlink(harness.link) == str(harness.source)


def setup(repo_root: Path, home: Path, claude_dir: Path, force: bool) -> int:
    if not home.is_absolute() or not claude_dir.is_absolute():
        raise ValueError("HOME 和 CLAUDE_CONFIG_DIR 必须为绝对路径。")

    selected: list[Harness] = []
    for harness in harnesses(repo_root, home, claude_dir):
        if shutil.which(harness.executable) is None:
            print(f"跳过 {harness.label}：PATH 中没有 {harness.executable}")
            continue
        if not os.access(harness.source, os.X_OK):
            raise ValueError(f"缺少仓库脚本或没有执行权限：{harness.source}")
        selected.append(harness)
    if not selected:
        print("没有检测到可配置的 harness，未做任何修改。")
        return 0

    conflicts: list[str] = []
    errors: list[str] = []
    currents: dict[str, object | None] = {}
    for harness in selected:
        link = harness.link
        if not link_ok(harness) and (link.exists() or link.is_symlink()):
            if link.is_dir() and not link.is_symlink():
                errors.append(f"{link} 是目录；期望链接到 {harness.source}")
            else:
                target = os.readlink(link) if link.is_symlink() else "普通文件"
                conflicts.append(f"{link} 已存在（{target}）；期望链接到 {harness.source}")
        try:
            currents[harness.label] = current = read_entry(harness)
        except Unfixable as error:
            errors.append(str(error))
            continue
        if current is not None and current != harness.entry:
            conflicts.append(
                f"{harness.config} 的 statusline 配置与仓库不同\n"
                f"  现值：{json.dumps(current, ensure_ascii=False)}\n"
                f"  期望：{json.dumps(harness.entry, ensure_ascii=False)}"
            )

    for error in errors:
        print(f"错误：{error}", file=sys.stderr)
    for conflict in conflicts:
        print(f"冲突：{conflict}", file=sys.stderr)
    if errors:
        print("存在无法自动处理的问题，未做任何修改。", file=sys.stderr)
        return 1
    if conflicts and not force:
        print("未做任何修改；确认以仓库为准后加 --force 重新执行。", file=sys.stderr)
        return 1

    for harness in selected:
        harness.link.parent.mkdir(parents=True, exist_ok=True)
        if link_ok(harness):
            print(f"已存在：{harness.link} -> {harness.source}")
        else:
            if harness.link.exists() or harness.link.is_symlink():
                harness.link.unlink()
            harness.link.symlink_to(harness.source)
            print(f"已创建：{harness.link} -> {harness.source}")
        current = currents[harness.label]
        if current == harness.entry:
            print(f"已存在：{harness.config} 的 statusline 配置")
        else:
            write_entry(harness, current)
            print(f"已写入：{harness.config} 的 statusline 配置")
        if (
            not link_ok(harness)
            or not harness.link.exists()
            or read_entry(harness) != harness.entry
        ):
            raise ValueError(f"核验失败：{harness.label}")

    if shutil.which("jq") is None:
        print(
            "提醒：statusline 脚本依赖 jq，当前 PATH 中没有。"
            "macOS：brew install jq；Ubuntu：sudo apt install jq"
        )
    labels = "、".join(harness.label for harness in selected)
    print(f"全部核验通过。开启新的 {labels} 会话后生效；图标需要终端使用 Nerd Font。")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args not in ([], ["--force"]):
        print("用法：setup_harness.py [--force]", file=sys.stderr)
        return 2
    try:
        home = os.environ.get("HOME")
        if not home:
            raise ValueError("缺少 HOME。")
        user_home = Path(home)
        claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or user_home / ".claude")
        return setup(Path(__file__).resolve().parents[4], user_home, claude_dir, bool(args))
    except (OSError, ValueError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
