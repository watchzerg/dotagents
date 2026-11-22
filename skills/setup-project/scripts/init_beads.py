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
        print(
            "错误：PATH 中未找到 bd，请先用全局 mise 配置安装 Beads（mise use -g github:gastownhall/beads）。",
            file=sys.stderr,
        )
        return 1
    beads = project / ".beads"
    if beads.exists():
        # 新 clone 只有 .beads 配置、没有本地数据库；bootstrap 只补缺，数据库已在时仅校验。
        print("已有 .beads，执行 bd bootstrap 补齐本地数据库。")
        command = [bd, "bootstrap", "--yes"]
    else:
        command = [
            bd,
            "init",
            "--non-interactive",
            "--init-if-missing",
            "--role",
            "maintainer",
            "--skip-agents",
            "--skip-hooks",
        ]
    try:
        returncode = subprocess.run(command, cwd=project, check=False).returncode
    except OSError as exc:
        print(f"错误：无法执行 bd：{exc}", file=sys.stderr)
        return 1
    if returncode == 0 and beads.is_dir():
        # bd 每次调用都提示 .beads 宜为 0700，提示会混进 agent 读到的输出。
        beads.chmod(0o700)
    return returncode


if __name__ == "__main__":
    sys.exit(main())
