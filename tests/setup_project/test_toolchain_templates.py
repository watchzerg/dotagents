"""渲染临时项目后用真实 mise 运行生成的 task，验证模板行为：full 测试按 stack 文件判定且持主机锁运行、docs-affected 转发基准参数、渲染出的文档通过 docs-check、公共脚本通过 uv 模板的 lint。

不执行 mise trust（会写用户的全局 trust 记录）：用 MISE_TRUSTED_CONFIG_PATHS 信任临时项目，MISE_STATE_DIR 指向临时目录；
MISE_DISABLE_TOOLS 让 mise 不安装、不提供项目钉住的工具，uv 用 PATH 上的替身记录参数；swift 只走不调用编译器的分支，
渲染时用 xcodebuild 替身通过平台检查。
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2] / "skills/setup-project"
INIT_DOCS = SKILL / "scripts/init_docs.py"
INIT_TOOLCHAIN = SKILL / "scripts/init_toolchain.py"
# 用户自定义的 mise 目录保留；外层 mise task 注入的 MISE_CONFIG_ROOT、MISE_TASK_* 等不能漏进临时项目。
KEPT_MISE_VARS = {"MISE_DATA_DIR", "MISE_CONFIG_DIR", "MISE_CACHE_DIR"}


@pytest.fixture
def stub_dir(tmp_path: Path) -> Path:
    assert shutil.which("mise") is not None, "需要宿主 mise"
    directory = tmp_path / "bin"
    directory.mkdir()
    # 新建 swift 项目要求 PATH 上有 xcodebuild；替身让非 macOS 也能渲染。
    (directory / "xcodebuild").write_text("#!/bin/sh\n")
    # uv 替身输出参数，以及运行时主机锁的上一个持有者是否已结束（见 MARKER）。
    (directory / "uv").write_text(
        '#!/bin/sh\necho "STUB uv $* marker=$(cat "$MARKER" 2>/dev/null || echo none)"\n'
    )
    for stub in directory.iterdir():
        stub.chmod(0o755)
    return directory


def task_env(project: Path, stub_dir: Path) -> dict[str, str]:
    base = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("MISE_") or key in KEPT_MISE_VARS
    }
    tmp = project.parent
    return {
        **base,
        "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
        "MISE_TRUSTED_CONFIG_PATHS": str(project),
        "MISE_STATE_DIR": str(tmp / "mise-state"),
        "MISE_DISABLE_TOOLS": "uv,node,pnpm",
        "MISE_YES": "1",
        "GATE_LOCK_FILE": str(tmp / "gate.lock"),
        "MARKER": str(tmp / "marker"),
    }


def render(tmp_path: Path, stub_dir: Path, *stacks: str) -> Path:
    project = tmp_path / "proj"
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "docs/agents").mkdir(parents=True)
    (project / "docs/agents/issue-tracker.md").write_text("tracker\n")
    (project / "docs/agents/domain.md").write_text("domain\n")
    env = {**os.environ, "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}"}
    for script, args in (
        (INIT_DOCS, []),
        (INIT_TOOLCHAIN, ["--stacks", *stacks, "--skip-install"]),
    ):
        result = subprocess.run(
            [sys.executable, "-I", str(script), *args],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    return project


def mise_run(project: Path, stub_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["mise", "run", *args],
        cwd=project,
        env=task_env(project, stub_dir),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_full_detection_and_gate_lock(tmp_path: Path, stub_dir: Path) -> None:
    """各 stack 只认自己的 full 测试文件；有测试时 test-full 在主机锁内运行并原样转发 runner 参数。"""
    project = render(tmp_path, stub_dir, "uv", "swift")
    (project / "tests/full").mkdir()
    (project / "tests/full/helper.txt").write_text("")
    result = mise_run(project, stub_dir, "test-full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("尚无 full 测试") == 2

    (project / "tests/full/test_slow.py").write_text("")
    assert "尚无 full 测试" in mise_run(project, stub_dir, "swift:test-full").stdout
    # 另一个持锁进程先占住主机锁，结束前写入 marker；uv 替身看到 marker 才说明 test-full 排队等到了锁。
    env = task_env(project, stub_dir)
    lock = Path(env["GATE_LOCK_FILE"])
    holder = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "scripts/with_lock.py",
            "sh",
            "-c",
            'sleep 1; echo released > "$MARKER"',
        ],
        cwd=project,
        env=env,
    )
    try:
        deadline = time.monotonic() + 5
        while not (lock.exists() and "pid=" in lock.read_text()):
            assert time.monotonic() < deadline, "持有者未写入锁文件"
            time.sleep(0.05)
        result = mise_run(project, stub_dir, "uv:test-full", "-k", "slow")
    finally:
        holder.wait(timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "STUB uv run --locked python -m pytest -o testpaths=tests/full -k slow marker=released"
        in result.stdout
    )
    assert "mise-tasks/uv/test-full -k slow" in lock.read_text()

    (project / "tests/full/SlowTests.swift").write_text("")
    result = mise_run(project, stub_dir, "swift:test-full")
    assert result.returncode != 0
    assert "未声明 FullTests" in result.stdout + result.stderr


@pytest.mark.parametrize("stacks", [("none",), ("uv", "node", "swift")])
def test_rendered_docs_pass_docs_check(
    tmp_path: Path, stub_dir: Path, stacks: tuple[str, ...]
) -> None:
    """模板与拼合后的正文自己要守住可达性、索引登记、体量预算与标题骨架。"""
    project = render(tmp_path, stub_dir, *stacks)
    result = mise_run(project, stub_dir, "docs-check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_affected_task_reports_changed_pages(tmp_path: Path, stub_dir: Path) -> None:
    """生成的 docs-affected task 把基准参数传给 check_docs.py --affected。"""
    project = render(tmp_path, stub_dir, "uv")
    page = project / "docs/architecture/modules/core.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\ncovers:\n  - src/core.py\n---\n# core\n")
    (project / "src").mkdir(exist_ok=True)
    (project / "src/core.py").write_text("")

    def commit(message: str) -> None:
        subprocess.run(["git", "add", "-A"], cwd=project, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@example.com",
                "commit",
                "-qm",
                message,
            ],
            cwd=project,
            check=True,
        )

    commit("init")
    (project / "src/core.py").write_text("x = 1\n")
    result = mise_run(project, stub_dir, "docs-affected")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "- docs/architecture/modules/core.md（本次未修改）" in result.stdout
    commit("change")
    assert "没有命中" in mise_run(project, stub_dir, "docs-affected").stdout
    result = mise_run(project, stub_dir, "docs-affected", "HEAD~1")
    assert "core.md（本次未修改）" in result.stdout


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
