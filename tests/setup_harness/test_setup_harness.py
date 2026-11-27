"""在临时 checkout、HOME 与 PATH 中验证 harness 配置安装。"""

import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / ".agents/skills/setup-harness/scripts/setup_harness.py"
)
CODEX_SNIPPET = SCRIPT.parents[4] / "harness/codex/statusline.toml"
GROK_CONFIG = """[ui]
yolo = false

[ui.status_line]
type = "builtin"

[plugins]
enabled = ["browser-use"]
"""


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    script = root / ".agents/skills/setup-harness/scripts/setup_harness.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(SCRIPT, script)
    for name in ("claude", "antigravity", "grok"):
        source = root / "harness" / name / "statusline.sh"
        source.parent.mkdir(parents=True)
        source.write_text("#!/bin/bash\n")
        source.chmod(0o755)
    codex = root / "harness/codex/statusline.toml"
    codex.parent.mkdir()
    shutil.copyfile(CODEX_SNIPPET, codex)
    return root


def run_setup(
    root: Path, home: Path, executables: tuple[str, ...], *args: str, codex_home: Path | None = None
) -> subprocess.CompletedProcess[str]:
    bin_dir = home.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name in executables:
        (bin_dir / name).write_text("#!/bin/sh\n")
        (bin_dir / name).chmod(0o755)
    env = {"HOME": str(home), "PATH": str(bin_dir)}
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(root / ".agents/skills/setup-harness/scripts/setup_harness.py"),
            *args,
        ],
        cwd=root.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def snapshot(root: Path) -> dict[str, str]:
    entries = {}
    for path in sorted(root.rglob("*")):
        key = str(path.relative_to(root))
        if path.is_symlink():
            entries[key] = "link:" + os.readlink(path)
        elif path.is_file():
            entries[key] = path.read_text()
    return entries


def test_install_merges_configs_and_is_idempotent(checkout: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude/settings.json").write_text('{"model": "opus"}\n')
    (home / ".grok").mkdir()
    (home / ".grok/config.toml").write_text("[ui]\nyolo = false\n")

    result = run_setup(checkout, home, ("claude", "grok"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "跳过 Antigravity CLI" in result.stdout
    assert not (home / ".gemini").exists()

    claude_link = home / ".claude/statusline.sh"
    assert os.readlink(claude_link) == str(checkout / "harness/claude/statusline.sh")
    assert json.loads((home / ".claude/settings.json").read_text()) == {
        "model": "opus",
        "statusLine": {
            "type": "command",
            "command": "~/.claude/statusline.sh",
            "refreshInterval": 30,
        },
    }
    assert os.readlink(home / ".grok/statusline.sh") == str(checkout / "harness/grok/statusline.sh")
    assert tomllib.loads((home / ".grok/config.toml").read_text())["ui"] == {
        "yolo": False,
        "status_line": {"type": "command", "command": "~/.grok/statusline.sh"},
    }

    before = snapshot(home)
    result = run_setup(checkout, home, ("claude", "grok"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot(home) == before


def test_conflicts_change_nothing_until_forced(checkout: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    agy = home / ".gemini/antigravity-cli"
    agy.mkdir(parents=True)
    (agy / "statusline.sh").write_text("本机旧脚本\n")
    (agy / "settings.json").write_text(
        '{"statusLine": {"type": "command", "command": "old"}, "trustedWorkspaces": ["/w"]}'
    )
    (home / ".grok").mkdir()
    (home / ".grok/config.toml").write_text(GROK_CONFIG)

    before = snapshot(home)
    result = run_setup(checkout, home, ("agy", "grok"))
    assert result.returncode == 1
    assert "冲突" in result.stderr
    assert snapshot(home) == before

    result = run_setup(checkout, home, ("agy", "grok"), "--force")
    assert result.returncode == 0, result.stdout + result.stderr
    assert os.readlink(agy / "statusline.sh") == str(checkout / "harness/antigravity/statusline.sh")
    assert json.loads((agy / "settings.json").read_text()) == {
        "statusLine": {"type": "command", "command": "~/.gemini/antigravity-cli/statusline.sh"},
        "trustedWorkspaces": ["/w"],
    }
    grok = tomllib.loads((home / ".grok/config.toml").read_text())
    assert grok["ui"]["status_line"] == {"type": "command", "command": "~/.grok/statusline.sh"}
    assert grok["plugins"] == {"enabled": ["browser-use"]}


def test_codex_merges_native_statusline(checkout: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex_home = tmp_path / "custom-codex"
    codex_home.mkdir()
    config = codex_home / "config.toml"
    existing = (
        '[tui] # terminal\ntheme = "github-dark"\n[tui.keymap.global]\nopen_transcript = "ctrl-t"\n'
    )
    config.write_text(existing)
    expected = tomllib.loads(CODEX_SNIPPET.read_text())["tui"]["status_line"]

    result = run_setup(checkout, home, ("codex",), codex_home=codex_home)
    assert result.returncode == 0, result.stdout + result.stderr
    installed = config.read_text()
    settings = tomllib.loads(installed)
    assert settings["tui"].pop("status_line") == expected
    assert settings == tomllib.loads(existing)
    assert not home.exists()

    result = run_setup(checkout, home, ("codex",), codex_home=codex_home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert config.read_text() == installed

    original = existing.replace("theme =", 'status_line = [\n    "model",\n]\ntheme =')
    config.write_text(original)
    result = run_setup(checkout, home, ("codex", "claude"), codex_home=codex_home)
    assert result.returncode == 1
    assert "冲突" in result.stderr
    assert config.read_text() == original
    assert not home.exists()

    result = run_setup(checkout, home, ("codex", "claude"), "--force", codex_home=codex_home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert config.read_text() == installed
