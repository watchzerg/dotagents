#!/usr/bin/env python3
"""使用 Python 3.14+ 标准库初始化项目 Beads。"""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    project = Path.cwd()
    try:
        git = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"错误：无法检查 Git 工作区：{exc}", file=sys.stderr)
        return 1
    if git.returncode != 0 or git.stdout.strip() != "true":
        print("错误：当前目录不在 Git 工作区内，请先初始化 Git。", file=sys.stderr)
        return 1
    bd = shutil.which("bd")
    if bd is None:
        print("错误：PATH 中未找到 bd，请先安装 Beads。", file=sys.stderr)
        return 1
    if (project / ".beads").exists():
        print("已有 .beads，跳过初始化。")
        return 0
    try:
        return subprocess.run(
            [
                bd,
                "init",
                "--non-interactive",
                "--init-if-missing",
                "--role",
                "maintainer",
                "--skip-agents",
                "--skip-hooks",
            ],
            cwd=project,
            check=False,
        ).returncode
    except OSError as exc:
        print(f"错误：无法执行 bd：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
