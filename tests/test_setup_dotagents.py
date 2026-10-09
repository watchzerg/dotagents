"""在临时 checkout 和 HOME 中验证加载入口安装。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".agents/skills/setup-dotagents/scripts/setup.py"


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout with spaces"
    script = root / ".agents/skills/setup-dotagents/scripts/setup.py"
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
    root: Path, home: Path, codex_home: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    # 只提供 Python 解释器绝对路径，验证不调用 just、Bash、uv 等外部命令。
    env["PATH"] = ""
    env.pop("CODEX_HOME", None)
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    return subprocess.run(
        [sys.executable, "-I", "-S", str(root / ".agents/skills/setup-dotagents/scripts/setup.py")],
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


@pytest.mark.parametrize("custom_codex_home", [False, True])
def test_install_is_idempotent_and_preserves_third_party(
    checkout: Path, tmp_path: Path, custom_codex_home: bool
) -> None:
    home = tmp_path / "home with spaces"
    codex = home / ("custom codex" if custom_codex_home else ".codex")
    third_party = home / ".agents/skills/third-party"
    third_party.mkdir(parents=True)
    (third_party / "SKILL.md").write_text("原有第三方内容\n")
    codex_third_party = codex / "skills/third-party"
    codex_third_party.mkdir(parents=True)
    (codex_third_party / "SKILL.md").write_text("原有 Codex 内容\n")
    requested_codex = codex if custom_codex_home else None

    result = run_setup(checkout, home, requested_codex)
    assert result.returncode == 0, result.stdout + result.stderr
    links = {
        home / ".agents/AGENTS.md": checkout / "global/AGENTS.md",
        codex / "AGENTS.md": home / ".agents/AGENTS.md",
        codex / "skills/prune-tests": checkout / "skills/prune-tests",
        home / ".agents/skills/commit": checkout / "skills/commit",
        home / ".agents/skills/another skill": checkout / "skills/another skill",
    }
    for target, source in links.items():
        assert target.is_symlink()
        assert os.readlink(target) == str(source)
    for parent in (home / ".agents", home / ".agents/skills", codex, codex / "skills"):
        assert parent.is_dir() and not parent.is_symlink()
    assert not (home / ".agents/skills/not-a-skill").exists()
    assert not (home / ".agents/skills/prune-tests").exists()
    assert (third_party / "SKILL.md").read_text() == "原有第三方内容\n"
    assert (codex_third_party / "SKILL.md").read_text() == "原有 Codex 内容\n"
    if custom_codex_home:
        assert not (home / ".codex").exists()
    before = tree_snapshot(home)
    result = run_setup(checkout, home, requested_codex)
    assert result.returncode == 0, result.stdout + result.stderr
    assert tree_snapshot(home) == before


@pytest.mark.parametrize(
    "relative_target",
    [".agents/AGENTS.md", ".codex/AGENTS.md", ".agents/skills/commit", ".codex/skills/prune-tests"],
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
    "relative_parent", [".agents", ".agents/skills", ".codex", ".codex/skills"]
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


def test_overlapping_codex_home_rejects_before_any_changes(checkout: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    before = tree_snapshot(home)
    result = run_setup(checkout, home, home / ".agents")
    assert result.returncode != 0
    assert "CODEX_HOME" in result.stderr
    assert tree_snapshot(home) == before
