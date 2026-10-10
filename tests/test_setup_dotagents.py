"""在临时 checkout 和 HOME 中验证加载入口安装。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".claude/skills/setup-dotagents/scripts/setup.py"


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout with spaces"
    script = root / ".claude/skills/setup-dotagents/scripts/setup.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(SCRIPT, script)
    (root / "global").mkdir()
    (root / "global/AGENTS.md").write_text("全局规则\n")
    for name in ("commit", "prune-tests", "another skill"):
        skill = root / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("测试 skill\n")
    (root / "skills/not-a-skill").mkdir()
    return root


def run_setup(
    root: Path, home: Path, claude_dir: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    # 只提供 Python 解释器绝对路径，验证不调用 just、Bash、uv 等外部命令。
    env["PATH"] = ""
    env.pop("CLAUDE_CONFIG_DIR", None)
    if claude_dir is not None:
        env["CLAUDE_CONFIG_DIR"] = str(claude_dir)
    return subprocess.run(
        [sys.executable, "-I", "-S", str(root / ".claude/skills/setup-dotagents/scripts/setup.py")],
        cwd=root.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def tree_snapshot(root: Path) -> dict[str, tuple[str, str | bytes]]:
    entries: dict[str, tuple[str, str | bytes]] = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            relative = str(path.relative_to(root))
            if path.is_symlink():
                entries[relative] = ("link", os.readlink(path))
            elif path.is_dir():
                entries[relative] = ("directory", "")
            else:
                entries[relative] = ("file", path.read_bytes())
    return entries


@pytest.mark.parametrize("custom_claude_dir", [False, True])
def test_install_is_idempotent_and_preserves_third_party(
    checkout: Path, tmp_path: Path, custom_claude_dir: bool
) -> None:
    home = tmp_path / "home with spaces"
    claude = home / ("custom claude" if custom_claude_dir else ".claude")
    third_party = home / ".agents/skills/third-party"
    third_party.mkdir(parents=True)
    (third_party / "SKILL.md").write_text("原有第三方内容\n")
    claude_third_party = claude / "skills/third-party"
    claude_third_party.mkdir(parents=True)
    (claude_third_party / "SKILL.md").write_text("原有 Claude 内容\n")
    requested_claude = claude if custom_claude_dir else None

    result = run_setup(checkout, home, requested_claude)
    assert result.returncode == 0, result.stdout + result.stderr
    links = {
        claude / "CLAUDE.md": checkout / "global/AGENTS.md",
    }
    for name in ("commit", "prune-tests", "another skill"):
        links[home / ".agents/skills" / name] = checkout / "skills" / name
        links[claude / "skills" / name] = home / ".agents/skills" / name
    for target, source in links.items():
        assert target.is_symlink()
        assert os.readlink(target) == str(source)
    for parent in (home / ".agents", home / ".agents/skills", claude, claude / "skills"):
        assert parent.is_dir() and not parent.is_symlink()
    assert not (home / ".agents/skills/not-a-skill").exists()
    assert not (home / ".agents/AGENTS.md").exists()
    assert (third_party / "SKILL.md").read_text() == "原有第三方内容\n"
    assert (claude_third_party / "SKILL.md").read_text() == "原有 Claude 内容\n"
    if custom_claude_dir:
        assert not (home / ".claude").exists()
    before = tree_snapshot(home)
    result = run_setup(checkout, home, requested_claude)
    assert result.returncode == 0, result.stdout + result.stderr
    assert tree_snapshot(home) == before


@pytest.mark.parametrize(
    "relative_target",
    [".claude/CLAUDE.md", ".agents/skills/commit", ".claude/skills/commit"],
)
@pytest.mark.parametrize("kind", ["file", "directory", "wrong-link", "dangling-link"])
def test_target_conflicts_reject_before_any_changes(
    checkout: Path, tmp_path: Path, relative_target: str, kind: str
) -> None:
    home = tmp_path / "home"
    target = home / relative_target
    target.parent.mkdir(parents=True)
    if kind == "file":
        target.write_text("不可覆盖\n")
    elif kind == "directory":
        target.mkdir()
        (target / "keep").write_text("不可删除\n")
    else:
        destination = home / "other destination"
        if kind == "wrong-link":
            destination.mkdir()
        target.symlink_to(destination)
    before = tree_snapshot(home)
    result = run_setup(checkout, home)
    assert result.returncode != 0
    assert tree_snapshot(home) == before


@pytest.mark.parametrize(
    "relative_parent", [".agents", ".agents/skills", ".claude", ".claude/skills"]
)
@pytest.mark.parametrize("kind", ["file", "link"])
def test_parent_conflicts_reject_before_any_changes(
    checkout: Path, tmp_path: Path, relative_parent: str, kind: str
) -> None:
    home = tmp_path / "home"
    target = home / relative_parent
    target.parent.mkdir(parents=True)
    if kind == "file":
        target.write_text("不可覆盖\n")
    else:
        destination = home / "existing directory"
        destination.mkdir()
        target.symlink_to(destination)
    before = tree_snapshot(home)
    result = run_setup(checkout, home)
    assert result.returncode != 0
    assert tree_snapshot(home) == before


def test_overlapping_claude_dir_rejects_before_any_changes(checkout: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    before = tree_snapshot(home)
    result = run_setup(checkout, home, home / ".agents")
    assert result.returncode != 0
    assert "CLAUDE_CONFIG_DIR" in result.stderr
    assert tree_snapshot(home) == before
