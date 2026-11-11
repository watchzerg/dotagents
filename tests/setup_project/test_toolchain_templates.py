"""渲染临时项目后用真实 just 运行生成的 recipe，验证模板行为：full 测试按 stack 文件判定、定向参数转发、none 模式不留阶段3 标记、各 stack 组合渲染出的文档通过文档检查。

uv、mise 用替身记录参数，不安装依赖；swift 只走不调用编译器的分支。
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2] / "skills/setup-project"
INIT_DOCS = SKILL / "scripts/init_docs.py"
INIT_TOOLCHAIN = SKILL / "scripts/init_toolchain.py"


@pytest.fixture
def stub_path(tmp_path: Path) -> str:
    directory = tmp_path / "bin"
    directory.mkdir()
    for tool in ("uv", "mise"):
        stub = directory / tool
        stub.write_text(f'#!/bin/sh\necho "STUB {tool} $*"\n')
        stub.chmod(0o755)
    just = shutil.which("just")
    assert just is not None, "需要宿主 just"
    return f"{directory}{os.pathsep}{os.environ['PATH']}"


def render(tmp_path: Path, *stacks: str) -> Path:
    project = tmp_path / "proj"
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "docs/agents").mkdir(parents=True)
    (project / "docs/agents/issue-tracker.md").write_text("tracker\n")
    (project / "docs/agents/domain.md").write_text("domain\n")
    for script, args in (
        (INIT_DOCS, []),
        (INIT_TOOLCHAIN, ["--stacks", *stacks, "--skip-install"]),
    ):
        result = subprocess.run(
            [sys.executable, "-I", str(script), *args],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    return project


def just(project: Path, path: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["just", *args],
        cwd=project,
        env={**os.environ, "PATH": path, "GATE_LOCK_FILE": str(project.parent / "gate.lock")},
        capture_output=True,
        text=True,
        check=False,
    )


def test_full_detection_ignores_other_stacks_files(tmp_path: Path, stub_path: str) -> None:
    project = render(tmp_path, "uv", "swift")
    (project / "tests/full").mkdir()
    (project / "tests/full/helper.txt").write_text("")
    result = just(project, stub_path, "test-full")
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("尚无 full 测试") == 2

    (project / "tests/full/test_slow.py").write_text("")
    result = just(project, stub_path, "test-full", "uv", "-k", "slow")
    assert "STUB uv run --locked python -m pytest -o testpaths=tests/full -k slow" in result.stdout
    assert "尚无 full 测试" in just(project, stub_path, "test-full", "swift").stdout

    (project / "tests/full/SlowTests.swift").write_text("")
    result = just(project, stub_path, "test-full", "swift")
    assert result.returncode != 0
    assert "未声明 FullTests" in result.stderr


def test_node_path_argument_replaces_default_directory(tmp_path: Path, stub_path: str) -> None:
    project = render(tmp_path, "node")
    assert (
        "STUB mise exec -- pnpm exec vitest run tests/core -t name"
        in just(project, stub_path, "test", "-t", "name").stdout
    )
    target = "tests/core/toolchain.test.ts"
    assert (
        f"STUB mise exec -- pnpm exec vitest run {target}\n"
        in just(project, stub_path, "test", target).stdout
    )

    (project / "tests/full").mkdir()
    assert "尚无 full 测试" in just(project, stub_path, "test-full").stdout
    (project / "tests/full/slow.test.ts").write_text("")
    assert (
        "STUB mise exec -- pnpm exec vitest run tests/full\n"
        in just(project, stub_path, "test-full").stdout
    )


def test_none_mode_leaves_no_stage3_markers(tmp_path: Path) -> None:
    project = render(tmp_path, "none")
    leftovers = [
        path.relative_to(project).as_posix()
        for path in project.rglob("*.md")
        if ".git" not in path.parts and "<待填 阶段3" in path.read_text()
    ]
    assert leftovers == []


@pytest.mark.parametrize(
    "stacks", [("none",), ("uv",), ("node",), ("swift",), ("uv", "node", "swift")]
)
def test_rendered_docs_pass_docs_check(tmp_path: Path, stacks: tuple[str, ...]) -> None:
    """模板与拼合后的正文自己要守住可达性、索引登记、体量预算与标题骨架。"""
    project = render(tmp_path, *stacks)
    result = subprocess.run(
        [sys.executable, "-I", "scripts/check_docs.py"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_common_scripts_pass_uv_template_lint() -> None:
    """公共脚本原样复制进 uv 项目并受其 Ruff 配置检查；本仓库忽略 E501，模板不忽略。"""
    for command in (["check"], ["format", "--check"]):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                *command,
                "--config",
                str(SKILL / "toolchain/stacks/uv/home/pyproject.toml"),
                str(SKILL / "toolchain/common/scripts"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
