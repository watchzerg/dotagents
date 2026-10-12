"""在临时 Git 项目中验证文档结构初始化，不触碰真实项目。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2] / "skills/setup-project"
SCRIPT = SKILL / "scripts/init_docs.py"
TEMPLATES = SKILL / "templates"
TEMPLATE_FILES = sorted(
    path.relative_to(TEMPLATES).as_posix()
    for path in TEMPLATES.rglob("*")
    if path.is_file() and path.name != ".DS_Store"
)
MATT_FILES = ("docs/agents/issue-tracker.md", "docs/agents/domain.md")


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
    for path in MATT_FILES:
        (directory / path).parent.mkdir(parents=True, exist_ok=True)
        (directory / path).write_text("matt setup 产出\n")
    return directory


def run_script(project: Path, bin_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT), *args],
        cwd=project,
        env={**os.environ, "PATH": str(bin_dir)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_templates_cover_core_structure() -> None:
    assert {
        "AGENTS.md",
        "GLOSSARY.md",
        "CODING_STANDARDS.md",
        "README.md",
        "docs/INDEX.md",
        "docs/agents/documentation.md",
        "docs/agents/testing.md",
        "docs/architecture/INDEX.md",
        "docs/architecture/module-boundaries.md",
        "docs/research/INDEX.md",
        "docs/development/workflow.md",
        "docs/development/technology-stack.md",
    } <= set(TEMPLATE_FILES)
    assert not any(name.startswith("docs/agents/issue-tracker") for name in TEMPLATE_FILES)
    assert "## Agent skills" not in (TEMPLATES / "AGENTS.md").read_text()


def test_missing_git_workspace_stops(tmp_path: Path, bin_dir: Path) -> None:
    directory = tmp_path / "plain directory"
    directory.mkdir()
    result = run_script(directory, bin_dir)
    assert result.returncode != 0
    assert "请先初始化 Git" in result.stderr
    assert list(directory.iterdir()) == []


def test_missing_matt_setup_stops_without_creating_files(tmp_path: Path, bin_dir: Path) -> None:
    directory = tmp_path / "fresh"
    subprocess.run([str(bin_dir / "git"), "init", "-q", str(directory)], check=True)
    (directory / "docs/agents").mkdir(parents=True)
    (directory / "docs/agents/domain.md").write_text("只有一个\n")
    result = run_script(directory, bin_dir)
    assert result.returncode != 0
    assert "docs/agents/issue-tracker.md" in result.stderr
    assert "setup-matt-pocock-skills" in result.stderr
    assert not (directory / "AGENTS.md").exists()
    assert not (directory / "docs/INDEX.md").exists()


def test_creates_every_template_with_project_name(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    for relative in TEMPLATE_FILES:
        target = project / relative
        assert target.is_file(), relative
        assert "{{PROJECT_NAME}}" not in target.read_text()
        assert f"已创建 {relative}" in result.stdout
    assert (project / "AGENTS.md").read_text().startswith("# project with spaces\n")
    assert (project / "docs/agents/domain.md").read_text() == "matt setup 产出\n"


def test_stray_system_files_are_not_copied(tmp_path: Path, project: Path, bin_dir: Path) -> None:
    skill = tmp_path / "skill"
    shutil.copytree(SKILL / "scripts", skill / "scripts")
    shutil.copytree(TEMPLATES, skill / "templates")
    (skill / "templates/.DS_Store").write_bytes(b"\x00\x05\x16\x07\xff\xfe")
    (skill / "templates/docs/.DS_Store").write_bytes(b"\xff\x00")
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(skill / "scripts/init_docs.py")],
        cwd=project,
        env={**os.environ, "PATH": str(bin_dir)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (project / "docs/INDEX.md").is_file()
    assert not list(project.rglob(".DS_Store"))


def test_name_override(project: Path, bin_dir: Path) -> None:
    result = run_script(project, bin_dir, "--name", "custom-name")
    assert result.returncode == 0, result.stderr
    assert (project / "README.md").read_text().startswith("# custom-name\n")


def test_existing_files_are_never_overwritten(project: Path, bin_dir: Path) -> None:
    (project / "docs/architecture").mkdir(parents=True)
    (project / "docs/architecture/INDEX.md").write_text("已有架构\n")
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    assert (project / "docs/architecture/INDEX.md").read_text() == "已有架构\n"
    assert "已存在，跳过 docs/architecture/INDEX.md" in result.stdout
    assert (project / "docs/architecture/module-boundaries.md").is_file()


MATT_BLOCK = """## Agent skills

### Issue tracker

Issues live in Beads. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context. See `docs/agents/domain.md`.
"""


def test_agents_merge_keeps_user_content_and_removes_matt_block(
    project: Path, bin_dir: Path
) -> None:
    existing = (
        "# 我的项目\n\n自定义说明。\n\n## 常驻约束\n\n- 用户自己的约束\n\n"
        "## 自定义节\n\n```md\n## 代码块里的假标题\n```\n\n" + MATT_BLOCK
    )
    (project / "AGENTS.md").write_text(existing)
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    merged = (project / "AGENTS.md").read_text()
    assert merged.startswith("# 我的项目\n\n自定义说明。\n\n## 常驻约束\n\n- 用户自己的约束\n\n")
    assert "## 自定义节\n\n```md\n## 代码块里的假标题\n```\n" in merged
    assert merged.count("## 常驻约束") == 1
    assert "## 按任务读取" in merged
    assert "## Agent skills" not in merged
    assert "Issues live in Beads" not in merged
    assert "已合并 AGENTS.md：追加节 按任务读取" in result.stdout
    assert "Issues live in Beads" in result.stdout
    assert "已创建 AGENTS.md" not in result.stdout


def test_agents_with_only_matt_block_gets_template_head(project: Path, bin_dir: Path) -> None:
    (project / "AGENTS.md").write_text(MATT_BLOCK)
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    merged = (project / "AGENTS.md").read_text()
    assert merged.startswith("# project with spaces\n\n<待填 初始化：")
    assert "## Agent skills" not in merged and "## 常驻约束" in merged
    assert "已为 AGENTS.md 补上模板开头" in result.stdout
    second = run_script(project, bin_dir)
    assert second.returncode == 0 and (project / "AGENTS.md").read_text() == merged


def test_project_name_comes_from_agents_heading(project: Path, bin_dir: Path) -> None:
    (project / "AGENTS.md").write_text("# 我的项目\n\n" + MATT_BLOCK)
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    assert (project / "README.md").read_text().startswith("# 我的项目\n")
    assert (project / "GLOSSARY.md").read_text().startswith("# 我的项目\n")


def test_blank_existing_file_is_filled_from_template(project: Path, bin_dir: Path) -> None:
    (project / "README.md").write_text("")
    (project / "GLOSSARY.md").write_text(" \n\n")
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    assert (project / "README.md").read_text().startswith("# project with spaces\n")
    assert "<待填 初始化" in (project / "GLOSSARY.md").read_text()
    assert "已创建 README.md" in result.stdout and "跳过 README.md" not in result.stdout
    assert "仍含 初始化 标记：AGENTS.md、README.md、GLOSSARY.md" in result.stdout


def test_reports_no_pending_init_markers_when_filled(project: Path, bin_dir: Path) -> None:
    (project / "AGENTS.md").write_text("# 我的项目\n\n已有描述。\n\n" + MATT_BLOCK)
    (project / "README.md").write_text("# 我的项目\n\n已有说明。\n")
    (project / "GLOSSARY.md").write_text("# 我的项目\n\n已有词汇表。\n")
    result = run_script(project, bin_dir)
    assert result.returncode == 0, result.stderr
    assert "仍含 初始化 标记：无" in result.stdout


def test_agents_merge_is_idempotent(project: Path, bin_dir: Path) -> None:
    (project / "AGENTS.md").write_text("# 我的项目\n\n" + MATT_BLOCK)
    assert run_script(project, bin_dir).returncode == 0
    after_first = (project / "AGENTS.md").read_text()
    second = run_script(project, bin_dir)
    assert second.returncode == 0, second.stderr
    assert (project / "AGENTS.md").read_text() == after_first
    assert "已存在，跳过 AGENTS.md" in second.stdout


def test_triage_row_follows_triage_doc(project: Path, bin_dir: Path) -> None:
    assert run_script(project, bin_dir).returncode == 0
    assert "triage-labels.md" not in (project / "AGENTS.md").read_text()
    (project / "AGENTS.md").unlink()
    (project / "docs/agents/triage-labels.md").write_text("labels\n")
    assert run_script(project, bin_dir).returncode == 0
    assert (
        "| 分类票据或调整分诊标签 | [标签映射](docs/agents/triage-labels.md) |"
        in (project / "AGENTS.md").read_text()
    )


def test_second_run_is_noop(project: Path, bin_dir: Path) -> None:
    first = run_script(project, bin_dir)
    assert first.returncode == 0, first.stderr
    snapshot = {
        path.relative_to(project).as_posix(): path.read_text()
        for path in project.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    second = run_script(project, bin_dir)
    assert second.returncode == 0, second.stderr
    assert f"创建 0 个，跳过 {len(TEMPLATE_FILES)} 个" in second.stdout
    assert {
        path.relative_to(project).as_posix(): path.read_text()
        for path in project.rglob("*")
        if path.is_file() and ".git" not in path.parts
    } == snapshot
