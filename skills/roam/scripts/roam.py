#!/usr/bin/env python3
"""换机同步：批量检查、推送、拉取一个总目录下各项目的 git 与 Beads(Dolt) 状态。

只处理总目录下第一层子目录；每个项目只处理当前分支与 main（无 main 时用 master）。
输出 JSON 汇总到 stdout；push/pull 有项目存在问题时退出码为 1（未被 git 管理的跳过不算），参数或总目录错误为 2。
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# 这些文件变化后，新机器上通常要重新安装依赖。
INSTALL_HINT_FILES = {
    "mise.toml",
    "mise.lock",
    ".python-version",
    "uv.lock",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "Package.resolved",
}


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], repo)


def out(repo: Path, *args: str) -> str | None:
    r = git(repo, *args)
    return r.stdout.strip() if r.returncode == 0 else None


def tail(r: subprocess.CompletedProcess[str]) -> str:
    text = (r.stderr.strip() or r.stdout.strip()).splitlines()
    return "\n".join(text[-5:])


def find_root(given: str | None) -> Path | None:
    if given:
        p = Path(given).expanduser().resolve()
        return p if p.is_dir() else None
    for parent in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if parent.name == "projects":
            return parent
    for candidate in (Path.home() / "projects", Path("/data/projects")):
        if candidate.is_dir():
            return candidate
    return None


def projects(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def in_progress(repo: Path) -> str | None:
    gitdir = out(repo, "rev-parse", "--absolute-git-dir")
    if gitdir is None:
        return "unknown"
    marks = {
        "MERGE_HEAD": "merge",
        "rebase-merge": "rebase",
        "rebase-apply": "rebase",
        "CHERRY_PICK_HEAD": "cherry-pick",
        "REVERT_HEAD": "revert",
    }
    for name, op in marks.items():
        if (Path(gitdir) / name).exists():
            return op
    return None


def main_branch(repo: Path) -> str | None:
    for name in ("main", "master"):
        if git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{name}").returncode == 0:
            return name
    return None


def branch_info(repo: Path, branch: str) -> dict:
    """分支相对 upstream 的状态；ahead/behind 基于本地已有的远端跟踪引用。"""
    upstream = out(repo, "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}")
    info: dict = {"branch": branch, "upstream": upstream}
    if upstream:
        counts = out(repo, "rev-list", "--left-right", "--count", f"{branch}...{upstream}")
        ahead, behind = (int(n) for n in (counts or "0 0").split())
        info |= {"ahead": ahead, "behind": behind}
    return info


def target_branches(repo: Path, current: str | None) -> list[str]:
    names = [b for b in (current, main_branch(repo)) if b]
    return list(dict.fromkeys(names))


def other_branches(repo: Path, targets: list[str]) -> list[dict]:
    names = (out(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads") or "").split()
    return [branch_info(repo, b) for b in names if b not in targets]


def beads_state(path: Path) -> dict | None:
    beads = path / ".beads"
    if not beads.is_dir():
        return None
    has_db = any((beads / d).is_dir() for d in ("embeddeddolt", "dolt"))
    return {"db": has_db}


def inspect(path: Path) -> dict:
    info: dict = {"name": path.name, "path": str(path)}
    if not (path / ".git").exists():
        info["git"] = False
        return info
    current = out(path, "symbolic-ref", "--quiet", "--short", "HEAD")
    targets = target_branches(path, current)
    porcelain = out(path, "status", "--porcelain") or ""
    info |= {
        "git": True,
        "current": current,
        "detached": current is None,
        "in_progress": in_progress(path),
        "dirty": [line for line in porcelain.splitlines() if line],
        "branches": [branch_info(path, b) for b in targets],
        "other_branches": other_branches(path, targets),
        "beads": beads_state(path),
    }
    return info


def blocked(info: dict) -> str | None:
    if info["in_progress"]:
        return f"仓库处于 {info['in_progress']} 中途"
    if info["detached"]:
        return "处于 detached HEAD"
    return None


def bd(path: Path, *args: str) -> dict:
    try:
        r = run(["bd", *args], path)
    except FileNotFoundError:
        return {"ok": False, "detail": "未找到 bd 命令"}
    return {"ok": r.returncode == 0, "detail": tail(r)}


def push_project(path: Path) -> dict:
    info = inspect(path)
    if not info["git"]:
        return info | {"result": "skipped", "reason": "未被 git 管理"}
    problems: list[str] = []
    pushed: list[str] = []
    reason = blocked(info)
    if reason:
        problems.append(reason)
    else:
        for b in info["branches"]:
            if not b["upstream"]:
                problems.append(f"{b['branch']} 没有 upstream")
                continue
            if b["ahead"] == 0:
                continue
            remote, _, remote_branch = b["upstream"].partition("/")
            r = git(path, "push", remote, f"refs/heads/{b['branch']}:refs/heads/{remote_branch}")
            if r.returncode == 0:
                pushed.append(f"{b['branch']}（{b['ahead']} 个提交）")
            else:
                problems.append(f"{b['branch']} push 失败：{tail(r)}")
    if info["dirty"]:
        problems.append(f"仍有 {len(info['dirty'])} 项未提交改动")
    if info["beads"] is not None:
        info["dolt"] = bd(path, "dolt", "push")
        if not info["dolt"]["ok"]:
            problems.append("bd dolt push 失败")
    return info | {"pushed": pushed, "problems": problems, "result": result(problems)}


def changed_files(path: Path, before: str, after: str) -> list[str]:
    if before == after:
        return []
    diff = out(path, "diff", "--name-only", before, after)
    return diff.splitlines() if diff else []


def hints(path: Path, files: list[str]) -> list[str]:
    found: list[str] = []
    deps = sorted({f for f in files if Path(f).name in INSTALL_HINT_FILES})
    if deps:
        found.append(f"依赖或工具链文件有变化（{', '.join(deps)}），可能需要重新安装")
    if (path / ".agents/skills/setup-dotagents").is_dir() and any(
        f.startswith("skills/") and f.endswith("/SKILL.md") for f in files
    ):
        found.append("skills/ 有 SKILL.md 变化；如有新增 skill，需重新执行 setup-dotagents")
    return found


def pull_current(path: Path, b: dict) -> tuple[str | None, str | None]:
    """把当前分支前进到 upstream；返回 (完成说明, 问题)。冲突时回滚到原状态。"""
    upstream = b["upstream"]
    if b["behind"] == 0:
        return None, None
    if b["ahead"] == 0:
        r = git(path, "merge", "--ff-only", upstream)
        return (
            (f"{b['branch']} 快进 {b['behind']} 个提交", None)
            if r.returncode == 0
            else (
                None,
                f"{b['branch']} 快进失败：{tail(r)}",
            )
        )
    r = git(path, "rebase", upstream)
    if r.returncode == 0:
        return f"{b['branch']} 已 rebase 到 {upstream}（本地 {b['ahead']} 个提交待 push）", None
    git(path, "rebase", "--abort")
    return None, f"{b['branch']} 与 {upstream} 分叉且 rebase 有冲突，已回滚，需手动处理"


def pull_other(path: Path, b: dict) -> tuple[str | None, str | None]:
    """非当前分支只做快进：直接移动分支引用，不检出。"""
    if b["behind"] == 0:
        return None, None
    if b["ahead"] > 0:
        return None, f"{b['branch']} 与 {b['upstream']} 分叉（非当前分支），需手动处理"
    old = out(path, "rev-parse", f"refs/heads/{b['branch']}")
    new = out(path, "rev-parse", b["upstream"])
    r = git(path, "update-ref", f"refs/heads/{b['branch']}", new or "", old or "")
    if r.returncode == 0:
        return f"{b['branch']} 快进 {b['behind']} 个提交", None
    return None, f"{b['branch']} 快进失败：{tail(r)}"


def pull_project(path: Path) -> dict:
    info = inspect(path)
    if not info["git"]:
        return info | {"result": "skipped", "reason": "未被 git 管理"}
    problems: list[str] = []
    done: list[str] = []
    files: list[str] = []
    reason = blocked(info) or (
        f"有 {len(info['dirty'])} 项未提交改动（上次离开那台机器时可能漏推）"
        if info["dirty"]
        else None
    )
    if reason:
        problems.append(reason)
    else:
        fetch = git(path, "fetch", "--all", "--quiet")
        if fetch.returncode != 0:
            problems.append(f"git fetch 失败：{tail(fetch)}")
        else:
            before = out(path, "rev-parse", "HEAD") or ""
            for name in target_branches(path, info["current"]):
                b = branch_info(path, name)
                if not b["upstream"]:
                    problems.append(f"{name} 没有 upstream")
                    continue
                step = pull_current if name == info["current"] else pull_other
                note, problem = step(path, b)
                if note:
                    done.append(note)
                if problem:
                    problems.append(problem)
            files = changed_files(path, before, out(path, "rev-parse", "HEAD") or before)
            info["branches"] = [branch_info(path, b["branch"]) for b in info["branches"]]
            info["other_branches"] = other_branches(path, [b["branch"] for b in info["branches"]])
    # .beads 配置随 git 走（可能刚被拉下来），数据库不进 git；没有本地库时从远端恢复。
    info["beads"] = beads_state(path)
    if info["beads"] is not None:
        args = ("dolt", "pull") if info["beads"]["db"] else ("bootstrap", "--yes")
        info["dolt"] = bd(path, *args) | {"command": "bd " + " ".join(args)}
        if not info["dolt"]["ok"]:
            problems.append(f"{info['dolt']['command']} 失败")
    return info | {
        "done": done,
        "hints": hints(path, files),
        "problems": problems,
        "result": result(problems),
    }


def result(problems: list[str]) -> str:
    return "problem" if problems else "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "push", "pull"])
    parser.add_argument("--root", help="包含各项目的总目录；不给则自动查找")
    args = parser.parse_args()

    root = find_root(args.root)
    if root is None:
        where = args.root or "当前路径的 projects 祖先目录、~/projects、/data/projects"
        print(f"错误：找不到总目录（{where}）", file=sys.stderr)
        return 2
    handler = {"status": inspect, "push": push_project, "pull": pull_project}[args.action]
    os.environ.setdefault("BD_NON_INTERACTIVE", "1")
    reports = [handler(p) for p in projects(root)]
    print(json.dumps({"root": str(root), "projects": reports}, ensure_ascii=False, indent=2))
    failed = any(r.get("result") == "problem" for r in reports)
    return 1 if args.action != "status" and failed else 0


if __name__ == "__main__":
    sys.exit(main())
