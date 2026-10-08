"""通过宿主官方 validator 校验仓库内的全部个人 skills。"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted(
    path
    for parent in (ROOT / "skills", ROOT / ".agents/skills")
    for path in parent.iterdir()
    if path.is_dir()
)
VALIDATOR = Path.home() / ".codex/skills/.system/skill-creator/scripts/quick_validate.py"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda skill: skill.name)
def test_skill_validation(skill: Path) -> None:
    assert VALIDATOR.is_file(), f"缺少宿主 skill validator：{VALIDATOR}"
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(skill)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"{skill.name}:\n{result.stdout}\n{result.stderr}"
