"""在临时 Git 项目中验证工具链初始化：判定、缺失才创建、mise.toml 与 stack task 生成、文档替换与命令顺序；外部工具用替身。"""

import os
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2] / "skills/setup-project"
INIT_DOCS = SKILL / "scripts/init_docs.py"
SCRIPT = SKILL / "scripts/init_toolchain.py"
TOOLS = ("uv", "mise", "pnpm", "swift", "xcodebuild")
# 公开 task 中由各 stack 同名 file task 聚合的 7 个。
STACK_TASKS = ("check-toolchain", "install", "fmt", "lint", "typecheck", "test", "test-full")


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


def mise_config(project: Path) -> dict:
    return tomllib.loads((project / "mise.toml").read_text())


def assert_stack_contract(project: Path, stacks: tuple[str, ...]) -> None:
    """根 mise.toml 的公开 task 聚合各 stack 的 file task，file task 齐全、可执行且无残留占位符。"""
    tasks = mise_config(project)["tasks"]
    for name in STACK_TASKS:
        assert tasks[name]["depends"] == [f"{stack}:{name}" for stack in stacks], name
        for stack in stacks:
            task = project / "mise-tasks" / stack / name
            assert task.is_file() and os.access(task, os.X_OK), task
            assert "{{" not in task.read_text(), task
    assert tasks["docs-check"]["run"] == "python3 scripts/check_docs.py"
    assert tasks["docs-affected"]["run"] == "python3 scripts/check_docs.py --affected"
    assert tasks["gate-core"]["depends"] == [
        "check-toolchain",
        "docs-check",
        "lint",
        "typecheck",
        "test",
    ]
    assert tasks["gate-full"]["depends"] == ["gate-core"]
    assert tasks["gate-full"]["run"] == [{"task": "test-full"}]
    assert "{{" not in (project / "mise.toml").read_text()


def test_empty_project_asks_for_stacks(project: Path, bin_dir: Path) -> None:
    before = {p.relative_to(project).as_posix() for p in project.rglob("*") if p.is_file()}
    result = run_script(project, bin_dir)
    assert result.returncode == 3
    assert "--stacks" in result.stderr and "swift" in result.stderr
    assert {p.relative_to(project).as_posix() for p in project.rglob("*") if p.is_file()} == before
    assert invocations(project) == []


def test_new_uv_project(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--stacks", "uv")
    assert result.returncode == 0, result.stderr
    assert "stacks：uv；模式：new" in result.stdout
    for path in (
        "pyproject.toml",
        ".python-version",
        "mise.toml",
        "scripts/check_docs.py",
        "tests/core/test_toolchain.py",
    ):
        assert (project / path).is_file(), path
    assert 'name = "my-project"' in (project / "pyproject.toml").read_text()
    gitignore = (project / ".gitignore").read_text()
    assert ".venv/" in gitignore and "mise.local.toml" in gitignore
    assert mise_config(project)["tools"] == {"uv": "0.13"}
    assert_stack_contract(project, ("uv",))
    assert "PYTEST_ADDOPTS" in (project / "mise-tasks/uv/test").read_text()
    assert "with_lock.py" in (project / "mise-tasks/uv/test-full").read_text()
    assert (project / "scripts/with_lock.py").is_file()
    assert stage3_markers(project) == {}
    workflow = (project / "docs/development/workflow.md").read_text()
    assert "## 命令与门禁" in workflow and "`mise run gate-core`" in workflow
    assert "宿主工具：`mise`。" in workflow and "钉住对版本敏感的 `uv`" in workflow
    assert "`mise run uv:test [参数]`" in workflow and "<stack>" in workflow
    assert "mise run install\nmise run gate-core" in (project / "README.md").read_text()
    assert "Python 解释器由 uv" in workflow and "### " not in workflow
    assert "<待填 按需：有发布流程时" in workflow
    assert "测试分层与资源边界" not in workflow and "local-acceptance.md" in workflow
    layers = (project / "docs/development/test-layers.md").read_text()
    assert (
        "## 分层与资源边界" in layers
        and "`tests/core/`（pytest `testpaths`）；由 `mise run test`" in layers
    )
    assert "<待填 按需：第一次用 `/prune-tests`" in layers
    testing = (project / "docs/agents/testing.md").read_text()
    assert "core：`tests/core/`" in testing
    assert "../development/test-layers.md#分层与资源边界" in testing
    stack = (project / "docs/development/technology-stack.md").read_text()
    assert "typer" in stack and "beautifulsoup4" in stack
    calls = invocations(project)
    commands = [call.split(" | ")[0] for call in calls]
    assert commands == ["mise install", "mise lock", "mise exec -- uv sync"]
    assert "门禁由初始化流程末尾统一运行" in result.stdout


def test_new_uv_project_rerun_is_noop(project: Path, bin_dir: Path) -> None:
    assert run_script(project, bin_dir, "--stacks", "uv", "--skip-install").returncode == 0
    workflow = (project / "docs/development/workflow.md").read_text()
    mise = (project / "mise.toml").read_text()
    second = run_script(project, bin_dir, "--stacks", "uv", "--skip-install")
    assert second.returncode == 0, second.stderr
    assert "模式：existing" in second.stdout
    assert "已创建" not in second.stdout
    assert (project / "docs/development/workflow.md").read_text() == workflow
    assert (project / "mise.toml").read_text() == mise
    gitignore = (project / ".gitignore").read_text()
    assert gitignore.count(".venv/") == 1 and gitignore.count("mise.local.toml") == 1
    assert "缺少契约 task" not in second.stdout
    assert invocations(project) == []


def test_new_uv_node_project_layout_commands_and_scopes(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--stacks", "node", "uv")
    assert result.returncode == 0, result.stderr
    assert "stacks：uv、node；模式：new" in result.stdout
    assert list(mise_config(project)["tools"].items()) == [
        ("uv", "0.13"),
        ("node", "26"),
        ("pnpm", "12"),
    ]
    assert_stack_contract(project, ("uv", "node"))
    assert 'cd "$MISE_CONFIG_ROOT/frontend"' in (project / "mise-tasks/node/test-full").read_text()
    assert (project / "frontend/package.json").is_file()
    assert "../mise.toml" in (project / "frontend/scripts/check-node.ts").read_text()
    assert "../mise.toml" in (project / "frontend/tests/core/toolchain.test.ts").read_text()
    assert "node_modules/" in (project / ".gitignore").read_text()
    testing = (project / "docs/agents/testing.md").read_text()
    assert (
        "Node（pnpm）：`frontend/tests/core/`" in testing
        and "Python（uv）：`tests/core/`" in testing
    )
    workflow = (project / "docs/development/workflow.md").read_text()
    assert "布局：Python（uv） 在仓库根目录、Node（pnpm） 在 `frontend/`。" in workflow
    assert (
        "`mise run <stack>:test [参数]`" in workflow and "`<stack>` 取 `uv`、`node`。" in workflow
    )
    assert "### Node（pnpm）" in workflow
    stack = (project / "docs/development/technology-stack.md").read_text()
    assert stack.index("### Python（uv）") < stack.index("### Node（pnpm）")
    assert "typer" in stack and "zod" in stack
    calls = invocations(project)
    commands = [call.split(" | ")[0] for call in calls]
    assert commands == [
        "mise install",
        "mise lock",
        "mise exec -- uv sync",
        "mise exec -- pnpm install",
    ]
    assert calls[3].endswith("/frontend")


def test_new_swift_project(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--stacks", "swift")
    assert result.returncode == 0, result.stderr
    for path in (
        "Package.swift",
        ".swift-format",
        ".xcode-version",
        "Sources/MyProject/MyProject.swift",
        "tests/core/ToolchainTests.swift",
        "mise.toml",
    ):
        assert (project / path).is_file(), path
    assert 'name: "MyProject"' in (project / "Package.swift").read_text()
    assert "public enum MyProject" in (project / "Sources/MyProject/MyProject.swift").read_text()
    assert ".build/" in (project / ".gitignore").read_text()
    assert mise_config(project)["tools"] == {}
    assert_stack_contract(project, ("swift",))
    assert stage3_markers(project) == {}
    workflow = (project / "docs/development/workflow.md").read_text()
    assert "Xcode（仅 macOS" in workflow
    assert "`CoreTests` target" in (project / "docs/development/test-layers.md").read_text()
    assert "Package.resolved" in (project / "docs/development/technology-stack.md").read_text()
    commands = [call.split(" | ")[0] for call in invocations(project)]
    assert commands == ["swift package resolve"]


def test_none_new_project_installs_contract_mise_toml(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--stacks", "none")
    assert result.returncode == 0, result.stderr
    assert "stacks：无预置；模式：new" in result.stdout
    template = SKILL / "toolchain/none/mise.toml"
    assert (project / "mise.toml").read_text() == template.read_text()
    assert not (project / "mise-tasks").exists()
    assert "mise.local.toml" in (project / ".gitignore").read_text()
    assert (project / "scripts/check_docs.py").is_file()
    commands = [call.split(" | ")[0] for call in invocations(project)]
    assert commands == []
    workflow = (project / "docs/development/workflow.md").read_text()
    assert "`mise run gate-core`" in workflow and "<待填 按需：接入工具链后" in workflow
    assert "<待填 按需：本项目各层的位置" in (project / "docs/agents/testing.md").read_text()
    layers = (project / "docs/development/test-layers.md").read_text()
    assert "<待填 按需：本项目各层的目录" in layers and "| core |" in layers
    assert "<待填 按需：接入工具链后" in (project / "README.md").read_text()
    assert "<待填 按需：" in (project / "docs/development/technology-stack.md").read_text()
    assert stage3_markers(project) == {}


def test_existing_project_gets_dependency_preferences_and_common_scripts(
    project: Path, bin_dir: Path
) -> None:
    (project / "uv.lock").write_text("")
    mise = '[tools]\nuv = "0.12"\n\n[tasks.test]\nrun = "pytest"\n'
    (project / "mise.toml").write_text(mise)
    (project / "mise-tasks/uv").mkdir(parents=True)
    (project / "mise-tasks/lint").write_text("#!/bin/sh\n")
    (project / "mise-tasks/uv/test").write_text("#!/bin/sh\n")
    before_workflow = (project / "docs/development/workflow.md").read_text()
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    assert "模式：existing；证据：uv.lock、mise.toml" in result.stdout
    assert not (project / "pyproject.toml").exists()
    assert (project / "scripts/check_docs.py").is_file()
    assert "已创建 scripts/check_docs.py" in result.stdout
    assert (project / "scripts/with_lock.py").is_file()
    assert (project / "mise.toml").read_text() == mise
    assert sorted(p.name for p in (project / "mise-tasks").rglob("*") if p.is_file()) == [
        "lint",
        "test",
    ]
    assert not (project / ".gitignore").exists()
    assert (project / "docs/development/workflow.md").read_text() == before_workflow
    stack = (project / "docs/development/technology-stack.md").read_text()
    assert "typer" in stack and "<待填 阶段3：语言版本" in stack
    assert (
        "mise 配置缺少契约 task：check-toolchain、install、fmt、typecheck、test-full、docs-check、docs-affected、gate-core、gate-full"
        in result.stdout
    )
    assert invocations(project) == []


def test_with_lock_serializes_and_reports_holder(tmp_path: Path) -> None:
    lock = SKILL / "toolchain/common/scripts/with_lock.py"
    env = {**os.environ, "GATE_LOCK_FILE": str(tmp_path / "gate.lock")}
    holder = subprocess.Popen(
        [sys.executable, "-I", str(lock), "sh", "-c", "sleep 3"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 5
        while (
            "pid=" not in (tmp_path / "gate.lock").read_text()
            if (tmp_path / "gate.lock").exists()
            else True
        ):
            assert time.monotonic() < deadline, "持有者未写入锁文件"
            time.sleep(0.05)
        waiter = subprocess.run(
            [sys.executable, "-I", str(lock), "--timeout", "0.5", "sh", "-c", "echo got-lock"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert waiter.returncode == 75
        assert "稍后重试" in waiter.stderr and "cmd=sh -c sleep 3" in waiter.stderr
        assert "got-lock" not in waiter.stdout
    finally:
        holder.wait(timeout=10)
    after = subprocess.run(
        [sys.executable, "-I", str(lock), "sh", "-c", "echo got-lock; exit 7"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert after.returncode == 7 and "got-lock" in after.stdout
