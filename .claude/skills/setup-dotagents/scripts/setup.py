#!/usr/bin/env python3
"""使用 Python 3.10+ 标准库建立并核验用户级加载入口。"""

import os
import sys
from pathlib import Path


def setup(repo_root: Path, user_home: Path, claude_dir: Path) -> None:
    if not user_home.is_absolute() or not claude_dir.is_absolute():
        raise ValueError("HOME 和 CLAUDE_CONFIG_DIR 必须为绝对路径。")
    if not (repo_root / "global/AGENTS.md").is_file() or not (repo_root / "skills").is_dir():
        raise ValueError(f"缺少 dotagents 源文件：{repo_root}")

    agents_dir = user_home / ".agents"
    if claude_dir.resolve() == agents_dir.resolve():
        raise ValueError("CLAUDE_CONFIG_DIR 与 ~/.agents 重合，无法建立 skills 两级链接。")
    links = {
        claude_dir / "CLAUDE.md": repo_root / "global/AGENTS.md",
    }
    parents = (agents_dir, agents_dir / "skills", claude_dir, claude_dir / "skills")
    for skill in sorted((repo_root / "skills").iterdir()):
        if skill.name.startswith(".") or not skill.is_dir() or not (skill / "SKILL.md").is_file():
            continue
        links[agents_dir / "skills" / skill.name] = skill
        links[claude_dir / "skills" / skill.name] = agents_dir / "skills" / skill.name

    conflicts = []
    for parent in parents:
        ancestor = parent
        while ancestor != user_home and ancestor != ancestor.parent:
            if ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir()):
                conflicts.append(f"父路径不是普通目录：{ancestor}")
                break
            ancestor = ancestor.parent
    for target, source in links.items():
        if target.is_symlink() and os.readlink(target) == str(source):
            continue
        if target.exists() or target.is_symlink():
            conflicts.append(f"{target} 已存在；期望链接到 {source}")
    if conflicts:
        for conflict in conflicts:
            print(f"冲突：{conflict}", file=sys.stderr)
        raise ValueError("检查失败，未创建任何链接；请先处理以上冲突。")

    for parent in parents:
        parent.mkdir(parents=True, exist_ok=True)
    for target, source in links.items():
        if target.is_symlink() and os.readlink(target) == str(source):
            print(f"已存在：{target} -> {source}")
        else:
            # 创建期间出现的新冲突直接失败，不覆盖现有内容。
            target.symlink_to(source)
            print(f"已创建：{target} -> {source}")
    for target, source in links.items():
        if not target.is_symlink() or os.readlink(target) != str(source) or not target.exists():
            raise ValueError(f"链接核验失败：{target}")
    print("全部链接核验通过。请开启新的 Claude Code 会话验证规则和 skills 加载。")


def main() -> int:
    try:
        home = os.environ.get("HOME")
        if not home:
            raise ValueError("缺少 HOME。")
        user_home = Path(home)
        claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or user_home / ".claude")
        setup(Path(__file__).resolve().parents[4], user_home, claude_dir)
    except (OSError, ValueError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
