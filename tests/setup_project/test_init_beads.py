"""通过临时项目与替身 CLI 验证初始化边界，不调用真实 Beads。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills/setup-project/scripts/init_beads.py"


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


def test_existing_beads_is_untouched(project: Path, bin_dir: Path) -> None:
    beads = project / ".beads"
    beads.mkdir()
    (beads / "config.yaml").write_text("existing configuration\n")
    fake_bd(bin_dir, "echo unexpected > invoked\nexit 42\n")
    result = run_script(project, bin_dir)
    assert result.returncode == 0
    assert not (project / "invoked").exists()
    assert (beads / "config.yaml").read_text() == "existing configuration\n"


def test_init_runs_in_current_directory(project: Path, bin_dir: Path) -> None:
    fake_bd(bin_dir, 'printf "%s\\n" "$@" > invoked\necho cli-output\necho cli-error >&2\n')
    result = run_script(project, bin_dir)
    assert result.returncode == 0
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
