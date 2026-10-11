"""核对运行中的解释器与 .python-version 的版本 line 一致。"""

import sys
from pathlib import Path


def test_python_matches_pinned_line() -> None:
    pin = (Path(__file__).resolve().parents[2] / ".python-version").read_text().strip()
    actual = ".".join(map(str, sys.version_info[:3]))
    assert actual == pin or actual.startswith(pin + ".")
