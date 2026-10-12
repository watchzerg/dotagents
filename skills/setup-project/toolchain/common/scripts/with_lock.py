#!/usr/bin/env python3
"""持有主机级文件锁运行一条命令；只依赖标准库。

full 测试会占用端口、桌面焦点等主机资源，不同 worktree 甚至不同项目同时运行会互相干扰。
`gate-full` 与 `test-full` 都经本脚本串行：锁文件默认在 ~/.cache/gate-full.lock，可用环境变量
GATE_LOCK_FILE 覆盖。使用 flock，持有进程退出即释放，不会留下死锁文件。

用法：with_lock.py [--timeout 秒] 命令 [参数...]
等待时每 30 秒打印持有者；超时退出码 75（稍后重试），不视为命令失败。
"""

import argparse
import fcntl
import os
import sys
import time
from pathlib import Path

EXIT_TEMPFAIL = 75
REPORT_EVERY = 30


def main() -> int:
    parser = argparse.ArgumentParser(description="持有主机级文件锁运行命令。")
    parser.add_argument("--timeout", type=float, help="等待秒数，默认一直等待")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="要运行的命令")
    args = parser.parse_args()
    if not args.command:
        parser.error("缺少要运行的命令")

    lock_path = Path(os.environ.get("GATE_LOCK_FILE") or Path.home() / ".cache/gate-full.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    os.set_inheritable(fd, True)

    started = time.monotonic()
    last_report = started - REPORT_EVERY
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            pass
        waited = time.monotonic() - started
        if args.timeout is not None and waited >= args.timeout:
            print(
                f"错误：等待 {lock_path} 超过 {args.timeout:g} 秒；{holder(fd)}。稍后重试。",
                file=sys.stderr,
            )
            return EXIT_TEMPFAIL
        if time.monotonic() - last_report >= REPORT_EVERY:
            print(f"等待主机锁 {lock_path}（已等 {waited:.0f} 秒）；{holder(fd)}", flush=True)
            last_report = time.monotonic()
        time.sleep(1)

    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, f"pid={os.getpid()} cwd={os.getcwd()} cmd={' '.join(args.command)}\n".encode())
    try:
        os.execvp(args.command[0], args.command)
    except OSError as exc:
        print(f"错误：无法执行 {args.command[0]}：{exc}", file=sys.stderr)
        return 1


def holder(fd: int) -> str:
    os.lseek(fd, 0, os.SEEK_SET)
    info = os.read(fd, 4096).decode(errors="replace").strip()
    return f"持有者 {info}" if info else "持有者未知"


if __name__ == "__main__":
    sys.exit(main())
