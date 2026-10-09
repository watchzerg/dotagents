"""通过临时项目与替身 CLI 验证初始化边界，不调用真实 Beads。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/init_beads.py"


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    git = shutil.which("git")
    assert git is not None
    (directory / "git").symlink_to(git)
    return directory


@pytest.fixture
def project(tmp_path: Path, bin_dir: Path) -> Path:
    directory = tmp_path / "project with spaces"
    subprocess.run([str(bin_dir / "git"), "init", "-q", str(directory)], check=True)
    return directory


def run_script(project: Path, bin_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT)],
        cwd=project,
        env={**os.environ, "PATH": str(bin_dir)},
        capture_output=True,
        text=True,
        check=False,
    )


def fake_bd(bin_dir: Path, body: str) -> None:
    executable = bin_dir / "bd"
    executable.write_text("#!/bin/sh\n" + body)
    executable.chmod(0o755)


def test_missing_git_workspace_stops(tmp_path: Path, bin_dir: Path) -> None:
    directory = tmp_path / "plain directory"
    directory.mkdir()
    fake_bd(bin_dir, "echo unexpected > invoked\n")
    result = run_script(directory, bin_dir)
    assert result.returncode != 0
    assert "请先初始化 Git" in result.stderr
    assert list(directory.iterdir()) == []


def test_missing_bd_stops_without_creating_files(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir)
    assert result.returncode != 0
    assert "未找到 bd" in result.stderr
    assert {path.name for path in project.iterdir()} == {".git"}


def test_existing_beads_is_untouched(project: Path, bin_dir: Path) -> None:
    beads = project / ".beads"
    beads.mkdir()
    (beads / "config.yaml").write_text("existing configuration\n")
    fake_bd(bin_dir, "echo unexpected > invoked\nexit 42\n")
    result = run_script(project, bin_dir)
    assert result.returncode == 0
    assert not (project / "invoked").exists()
    assert (beads / "config.yaml").read_text() == "existing configuration\n"


@pytest.mark.parametrize("exit_code", [0, 23])
def test_init_runs_in_current_directory_and_preserves_result(
    project: Path, bin_dir: Path, exit_code: int
) -> None:
    fake_bd(
        bin_dir,
        f'printf "%s\\n" "$@" > invoked\necho cli-output\necho cli-error >&2\nexit {exit_code}\n',
    )
    result = run_script(project, bin_dir)
    assert result.returncode == exit_code
    assert "cli-output" in result.stdout
    assert "cli-error" in result.stderr
    assert (project / "invoked").read_text().splitlines() == [
        "init",
        "--non-interactive",
        "--init-if-missing",
        "--role",
        "maintainer",
        "--skip-agents",
        "--skip-hooks",
    ]
