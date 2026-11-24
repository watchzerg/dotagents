"""在临时目录中验证 roam.py 的 push、pull 主流程与冲突回滚。

远端是临时 bare 仓库；`bd` 换成 PATH 上的替身脚本，把收到的参数记进日志。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills/roam/scripts/roam.py"

FAKE_BD = """#!/bin/sh
echo "$PWD $*" >> "$BD_LOG"
"""


def sh(cwd: Path, *args: str) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "bd"
    fake.write_text(FAKE_BD)
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("BD_LOG", str(tmp_path / "bd.log"))
    for key, value in {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
    }.items():
        monkeypatch.setenv(key, value)
    return tmp_path


def commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text)
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", f"edit {name}")


def make_pair(base: Path, name: str) -> tuple[Path, Path]:
    """建 bare 远端和两台“机器”上的 clone，返回 (old, new)。"""
    remote = base / "remotes" / f"{name}.git"
    sh(base, "git", "init", "-q", "--bare", "-b", "main", str(remote))
    old = base / "old" / name
    old.parent.mkdir(exist_ok=True)
    sh(base, "git", "clone", "-q", str(remote), str(old))
    sh(old, "git", "checkout", "-qb", "main")
    commit(old, "a.txt", "1\n")
    sh(old, "git", "push", "-qu", "origin", "main")
    new = base / "new" / name
    new.parent.mkdir(exist_ok=True)
    sh(base, "git", "clone", "-q", str(remote), str(new))
    return old, new


def roam(action: str, root: Path) -> tuple[int, dict]:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), action, "--root", str(root)],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return r.returncode, json.loads(r.stdout)


def by_name(report: dict) -> dict[str, dict]:
    return {p["name"]: p for p in report["projects"]}


def test_push_pushes_ahead_branches_and_runs_dolt_only_with_beads(env: Path) -> None:
    old, _ = make_pair(env, "plain")
    beads_old, _ = make_pair(env, "beads")
    (beads_old / ".beads/embeddeddolt").mkdir(parents=True)
    commit(old, "a.txt", "2\n")
    (env / "old/not-git").mkdir()

    code, report = roam("push", env / "old")

    projects = by_name(report)
    assert code == 0
    assert projects["plain"]["pushed"] == ["main（1 个提交）"]
    assert sh(old, "git", "rev-parse", "origin/main") == sh(old, "git", "rev-parse", "main")
    assert projects["not-git"]["result"] == "skipped"
    assert (env / "bd.log").read_text().splitlines() == [f"{beads_old} dolt push"]


def test_push_reports_dirty_and_unpushed_side_branch(env: Path) -> None:
    old, _ = make_pair(env, "p")
    sh(old, "git", "checkout", "-qb", "feature")
    commit(old, "f.txt", "x\n")
    sh(old, "git", "checkout", "-q", "main")
    (old / "untracked.txt").write_text("x")

    code, report = roam("push", env / "old")

    p = by_name(report)["p"]
    assert code == 1
    assert p["problems"] == ["仍有 1 项未提交改动"]
    assert p["other_branches"] == [{"branch": "feature", "upstream": None}]


def test_pull_fast_forwards_and_bootstraps_missing_beads_db(env: Path) -> None:
    old, new = make_pair(env, "p")
    (old / ".beads").mkdir()
    (old / ".beads/config.yaml").write_text("x\n")
    commit(old, "uv.lock", "x\n")
    sh(old, "git", "push", "-q")

    code, report = roam("pull", env / "new")

    p = by_name(report)["p"]
    assert code == 0
    assert p["done"] == ["main 快进 1 个提交"]
    assert (new / "uv.lock").exists()
    assert any("uv.lock" in h for h in p["hints"])
    assert (env / "bd.log").read_text().splitlines() == [f"{new} bootstrap --yes"]


def test_pull_rebases_clean_divergence(env: Path) -> None:
    old, new = make_pair(env, "p")
    commit(old, "remote.txt", "r\n")
    sh(old, "git", "push", "-q")
    commit(new, "local.txt", "l\n")

    code, report = roam("pull", env / "new")

    assert code == 0
    assert "rebase" in by_name(report)["p"]["done"][0]
    assert (new / "remote.txt").exists() and (new / "local.txt").exists()


def test_pull_conflict_rolls_back_and_reports(env: Path) -> None:
    old, new = make_pair(env, "p")
    commit(old, "a.txt", "remote\n")
    sh(old, "git", "push", "-q")
    commit(new, "a.txt", "local\n")
    head = sh(new, "git", "rev-parse", "HEAD")

    code, report = roam("pull", env / "new")

    assert code == 1
    assert "冲突" in by_name(report)["p"]["problems"][0]
    assert sh(new, "git", "rev-parse", "HEAD") == head
    assert sh(new, "git", "status", "--porcelain") == ""
    assert not (new / ".git/rebase-merge").exists()


def test_pull_skips_dirty_repo_and_fast_forwards_non_current_main(env: Path) -> None:
    old, new = make_pair(env, "dirty")
    commit(old, "a.txt", "2\n")
    sh(old, "git", "push", "-q")
    (new / "a.txt").write_text("local edit\n")
    old2, new2 = make_pair(env, "side")
    commit(old2, "a.txt", "2\n")
    sh(old2, "git", "push", "-q")
    sh(new2, "git", "checkout", "-qb", "work")

    code, report = roam("pull", env / "new")

    projects = by_name(report)
    assert code == 1
    assert "未提交改动" in projects["dirty"]["problems"][0]
    assert (new / "a.txt").read_text() == "local edit\n"
    assert projects["side"]["done"] == ["main 快进 1 个提交"]
    assert sh(new2, "git", "rev-parse", "main") == sh(new2, "git", "rev-parse", "origin/main")
