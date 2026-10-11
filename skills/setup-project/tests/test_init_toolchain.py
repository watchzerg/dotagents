"""在临时 Git 项目中验证工具链初始化：判定、缺失才创建、justfile 拼合、文档替换与命令顺序；外部工具用替身。"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
INIT_DOCS = SKILL / "scripts/init_docs.py"
SCRIPT = SKILL / "scripts/init_toolchain.py"
TOOLS = ("uv", "mise", "bun", "just", "swift")


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    git = shutil.which("git")
    assert git is not None
    (directory / "git").symlink_to(git)
    for tool in TOOLS:
        fake = directory / tool
        fake.write_text(f'#!/bin/sh\nprintf "%s %s | %s\\n" "{tool}" "$*" "$PWD" >> "$FAKE_LOG"\n')
        fake.chmod(0o755)
    return directory


@pytest.fixture
def project(tmp_path: Path, bin_dir: Path) -> Path:
    directory = tmp_path / "my project"
    subprocess.run([str(bin_dir / "git"), "init", "-q", str(directory)], check=True)
    (directory / "docs/agents").mkdir(parents=True)
    (directory / "docs/agents/issue-tracker.md").write_text("tracker\n")
    (directory / "docs/agents/domain.md").write_text("domain\n")
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(INIT_DOCS)],
        cwd=directory,
        env={**os.environ, "PATH": str(bin_dir)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return directory


def run_script(project: Path, bin_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT), *args],
        cwd=project,
        env={**os.environ, "PATH": str(bin_dir), "FAKE_LOG": str(project.parent / "fake.log")},
        capture_output=True,
        text=True,
        check=False,
    )


def invocations(project: Path) -> list[str]:
    log = project.parent / "fake.log"
    return log.read_text().splitlines() if log.exists() else []


def stage3_markers(project: Path) -> dict[str, int]:
    return {
        path.relative_to(project).as_posix(): path.read_text().count("<待填 阶段3")
        for path in list(project.rglob("*.md"))
        if ".git" not in path.parts and "<待填 阶段3" in path.read_text()
    }


def recipe_names(justfile: Path) -> set[str]:
    return set(re.findall(r"^([A-Za-z_][\w-]*)[^:\n]*:", justfile.read_text(), re.M))


def test_empty_project_asks_for_stacks(project: Path, bin_dir: Path) -> None:
    before = {p.relative_to(project).as_posix() for p in project.rglob("*") if p.is_file()}
    result = run_script(project, bin_dir)
    assert result.returncode == 3
    assert "--stacks" in result.stderr and "swift" in result.stderr
    assert {p.relative_to(project).as_posix() for p in project.rglob("*") if p.is_file()} == before
    assert invocations(project) == []


def test_none_cannot_combine_with_stacks(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--stacks", "none", "uv")
    assert result.returncode == 2
    assert not (project / "justfile").exists()


def test_requires_phase_two_docs(tmp_path: Path, bin_dir: Path) -> None:
    directory = tmp_path / "bare"
    subprocess.run([str(bin_dir / "git"), "init", "-q", str(directory)], check=True)
    result = run_script(directory, bin_dir, "--stacks", "uv")
    assert result.returncode != 0
    assert "init_docs.py" in result.stderr


def test_new_uv_project(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--stacks", "uv")
    assert result.returncode == 0, result.stderr
    assert "stacks：uv；模式：new" in result.stdout
    for path in (
        "pyproject.toml",
        ".python-version",
        "justfile",
        "scripts/check_docs.py",
        "tests/core/test_toolchain.py",
    ):
        assert (project / path).is_file(), path
    assert 'name = "my-project"' in (project / "pyproject.toml").read_text()
    assert ".venv/" in (project / ".gitignore").read_text()
    assert not (project / "mise.toml").exists()
    justfile = project / "justfile"
    names = recipe_names(justfile)
    assert {"check-toolchain", "install", "fmt", "lint", "typecheck", "test", "docs-check"} <= names
    assert {"uv-check-toolchain", "uv-test-core", "uv-test-full"} <= names
    text = justfile.read_text()
    assert "gate-core: check-toolchain docs-check lint typecheck uv-test-core" in text
    assert "gate-full: gate-core uv-test-full" in text
    assert 'test *args:\n    @just uv-test "$@"' in text
    assert "{{" not in text
    assert stage3_markers(project) == {}
    workflow = (project / "docs/development/workflow.md").read_text()
    assert "## 命令与门禁" in workflow and "`just gate-core`" in workflow
    assert "`uv`（Homebrew）、`just`（Homebrew）" in workflow
    assert "Python 解释器由 uv" in workflow and "### " not in workflow
    assert "<待填 按需：有发布流程时" in workflow
    assert "core：`tests/core/`" in (project / "docs/agents/testing.md").read_text()
    assert "just install" in (project / "README.md").read_text()
    stack = (project / "docs/development/technology-stack.md").read_text()
    assert "typer" in stack and "beautifulsoup4" in stack
    calls = invocations(project)
    assert calls[0].startswith("uv sync |")
    assert calls[-1].startswith("just gate-core |")
    assert len(calls) == 2


def test_new_uv_project_rerun_is_noop(project: Path, bin_dir: Path) -> None:
    assert run_script(project, bin_dir, "--stacks", "uv", "--skip-install").returncode == 0
    workflow = (project / "docs/development/workflow.md").read_text()
    second = run_script(project, bin_dir, "--stacks", "uv", "--skip-install")
    assert second.returncode == 0, second.stderr
    assert "模式：existing" in second.stdout
    assert "已创建" not in second.stdout
    assert (project / "docs/development/workflow.md").read_text() == workflow
    assert (project / ".gitignore").read_text().count(".venv/") == 1
    assert invocations(project) == []


def test_new_uv_bun_project_layout_commands_and_scopes(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--stacks", "bun", "uv")
    assert result.returncode == 0, result.stderr
    assert "stacks：uv、bun；模式：new" in result.stdout
    assert (project / "mise.toml").is_file()
    assert (project / "frontend/package.json").is_file()
    assert "../mise.toml" in (project / "frontend/scripts/check-bun.ts").read_text()
    assert "../mise.toml" in (project / "frontend/tests/core/toolchain.test.ts").read_text()
    assert "node_modules/" in (project / ".gitignore").read_text()
    text = (project / "justfile").read_text()
    assert "check-toolchain: uv-check-toolchain bun-check-toolchain" in text
    assert "gate-full: gate-core uv-test-full bun-test-full" in text
    assert 'uv|bun) scope="$1"; shift; just "${scope}-test" "$@" ;;' in text
    assert "cd frontend && mise exec -- bun install --frozen-lockfile" in text
    assert "{{" not in text
    testing = (project / "docs/agents/testing.md").read_text()
    assert "Bun：`frontend/tests/core/`" in testing and "Python（uv）：`tests/core/`" in testing
    workflow = (project / "docs/development/workflow.md").read_text()
    assert "布局：Python（uv） 在仓库根目录、Bun 在 `frontend/`。" in workflow
    assert "scope（`uv`、`bun`）" in workflow and "### Bun" in workflow
    stack = (project / "docs/development/technology-stack.md").read_text()
    assert stack.index("### Python（uv）") < stack.index("### Bun")
    assert "typer" in stack and "zod" in stack
    calls = invocations(project)
    commands = [call.split(" | ")[0] for call in calls]
    assert commands == [
        "uv sync",
        "mise trust",
        "mise install",
        "mise lock",
        "mise exec -- bun install",
        "just gate-core",
    ]
    assert calls[4].endswith("/frontend")


def test_new_bun_project_places_bun_at_root(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--stacks", "bun", "--skip-install")
    assert result.returncode == 0, result.stderr
    assert (project / "package.json").is_file()
    assert (project / "mise.toml").is_file()
    assert 'readFileSync("./mise.toml"' in (project / "scripts/check-bun.ts").read_text()
    assert "cd . && mise exec -- bun run lint" in (project / "justfile").read_text()
    assert not (project / "pyproject.toml").exists()


def test_new_swift_project(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--stacks", "swift")
    assert result.returncode == 0, result.stderr
    for path in (
        "Package.swift",
        ".swift-format",
        ".xcode-version",
        "Sources/MyProject/MyProject.swift",
        "tests/core/ToolchainTests.swift",
        "justfile",
    ):
        assert (project / path).is_file(), path
    assert 'name: "MyProject"' in (project / "Package.swift").read_text()
    assert "public enum MyProject" in (project / "Sources/MyProject/MyProject.swift").read_text()
    assert ".build/" in (project / ".gitignore").read_text()
    text = (project / "justfile").read_text()
    assert (
        "swift-run-tests" in text
        and "gate-core: check-toolchain docs-check lint typecheck swift-test-core" in text
    )
    assert "{{" not in text
    assert stage3_markers(project) == {}
    workflow = (project / "docs/development/workflow.md").read_text()
    assert "Xcode（App Store" in workflow and "`CoreTests` target" in workflow
    assert "Package.resolved" in (project / "docs/development/technology-stack.md").read_text()
    commands = [call.split(" | ")[0] for call in invocations(project)]
    assert commands == ["swift package resolve", "just gate-core"]


def test_existing_swift_project_gets_dependency_policy_only(project: Path, bin_dir: Path) -> None:
    (project / "Package.swift").write_text("// swift\n")
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    assert "stacks：swift；模式：existing" in result.stdout
    assert not (project / "justfile").exists()
    assert not (project / "scripts/check_docs.py").exists()
    assert not (project / ".swift-format").exists()
    stack = (project / "docs/development/technology-stack.md").read_text()
    assert "Package.resolved" in stack and "<待填 阶段3：语言版本" in stack
    assert "docs/development/workflow.md" in stage3_markers(project)
    assert "没有 justfile" in result.stdout
    assert invocations(project) == []


def test_other_toolchain_without_stack_is_existing_and_untouched(
    project: Path, bin_dir: Path
) -> None:
    (project / "Cargo.toml").write_text("[package]\n")
    before = {p: p.read_text() for p in project.rglob("*.md") if ".git" not in p.parts}
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    assert "stacks：无预置；模式：existing" in result.stdout
    assert {p: p.read_text() for p in project.rglob("*.md") if ".git" not in p.parts} == before
    assert not (project / "justfile").exists()


def test_none_new_project_installs_contract_justfile(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--stacks", "none", "--skip-install")
    assert result.returncode == 0, result.stderr
    assert "stacks：无预置；模式：new" in result.stdout
    justfile = (project / "justfile").read_text()
    assert "尚未接入" in justfile and "gate-full: gate-core" in justfile
    assert (project / "scripts/check_docs.py").is_file()
    workflow = (project / "docs/development/workflow.md").read_text()
    assert "<待填 阶段3：宿主工具与安装方式>" in workflow
    assert "`just gate-core`" in workflow and "<待填 按需：接入工具链后" in workflow
    assert "<待填 按需：本项目各层的位置" in (project / "docs/agents/testing.md").read_text()
    assert "<待填 阶段3" in (project / "docs/development/technology-stack.md").read_text()


def test_detects_stacks_from_lockfiles(project: Path, bin_dir: Path) -> None:
    (project / "uv.lock").write_text("")
    (project / "frontend").mkdir()
    (project / "frontend/bun.lock").write_text("")
    result = run_script(project, bin_dir, "--skip-install")
    assert result.returncode == 0, result.stderr
    assert "stacks：uv、bun；模式：existing" in result.stdout


def test_existing_project_only_gets_dependency_preferences(project: Path, bin_dir: Path) -> None:
    (project / "uv.lock").write_text("")
    (project / "justfile").write_text("default:\n    @just --list\n\ntest *args:\n    pytest\n")
    before_workflow = (project / "docs/development/workflow.md").read_text()
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    assert not (project / "pyproject.toml").exists()
    assert not (project / "scripts/check_docs.py").exists()
    assert (project / "justfile").read_text().startswith("default:\n")
    assert (project / "docs/development/workflow.md").read_text() == before_workflow
    stack = (project / "docs/development/technology-stack.md").read_text()
    assert "typer" in stack and "<待填 阶段3：语言版本" in stack
    assert (
        "缺少契约 recipe：check-toolchain、install、fmt、lint、typecheck、docs-check、gate-core、gate-full"
        in result.stdout
    )
    assert invocations(project) == []


def test_check_docs_passes_on_initialized_project_and_catches_broken_links(
    project: Path, bin_dir: Path
) -> None:
    assert run_script(project, bin_dir, "--stacks", "uv", "--skip-install").returncode == 0
    check = project / "scripts/check_docs.py"
    ok = subprocess.run(
        [sys.executable, "-I", str(check)], cwd=project, capture_output=True, text=True
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    (project / "docs/architecture/modules").mkdir()
    (project / "docs/architecture/modules/orphan.md").write_text("# 孤儿\n\n[坏链接](missing.md)\n")
    bad = subprocess.run(
        [sys.executable, "-I", str(check)], cwd=project, capture_output=True, text=True
    )
    assert bad.returncode == 1
    assert "链接目标不存在" in bad.stdout
    assert "架构入口不可达" in bad.stdout
