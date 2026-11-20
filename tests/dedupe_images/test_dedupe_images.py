"""在临时目录中验证 dedupe_images.py 的命名解析、分组判定、计划与执行，回收站指向临时 XDG_DATA_HOME。"""

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills/dedupe-images/scripts/dedupe_images.py"

_spec = importlib.util.spec_from_file_location("dedupe_images", SCRIPT)
assert _spec is not None and _spec.loader is not None
dedupe = importlib.util.module_from_spec(_spec)
sys.modules["dedupe_images"] = dedupe
_spec.loader.exec_module(dedupe)


@pytest.mark.parametrize(
    ("name", "base", "numbers"),
    [
        ("000c01.jpg", "000c01", ()),
        ("000c01 (2).jpg", "000c01", (2,)),
        ("a(3).png", "a", (3,)),
        ("a （4）.JPG", "a", (4,)),
        ("a - Copy (2).jpg", "a", (2, 1)),
        ("a - 副本.jpg", "a", (1,)),
        ("Copy (2) of a.jpg", "a", (2,)),
        ("复件 a.jpg", "a", (1,)),
        ("a copy 3.jpg", "a", (3,)),
        ("a 副本 2.jpg", "a", (2,)),
        ("a (another copy).jpg", "a", (2,)),
        ("a (3rd copy).jpg", "a", (3,)),
        ("a (第 4 个副本).jpg", "a", (4,)),
        ("a_copy.jpg", "a", (1,)),
        ("a (Tom's conflicted copy 2026-01-01).jpg", "a", (1,)),
        ("a.jpg.2", "a", (2,)),
        ("a (1) (1).jpg", "a", (1, 1)),
    ],
)
def test_strong_markers(name: str, base: str, numbers: tuple[int, ...]) -> None:
    parsed = dedupe.parse_name(name, weak=False)
    assert parsed is not None
    assert (parsed.base, parsed.numbers) == (base, numbers)


def test_non_image_is_ignored() -> None:
    assert dedupe.parse_name("a (1).txt") is None


def test_weak_markers_need_bare_file() -> None:
    with_bare = {p.name: p for p in dedupe.parse_directory(["photo.png", "photo 2.png", "x-1.png"])}
    assert with_bare["photo 2.png"].key == with_bare["photo.png"].key
    assert with_bare["x-1.png"].base == "x-1"


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def run(*args: str, xdg: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "XDG_DATA_HOME": str(xdg)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, check=False
    )


def healthy_bytes() -> bytes:
    return b"\xff\xd8" + b"\x01" * 8188 + b"\xff\xd9"


@pytest.fixture
def library(tmp_path: Path) -> Path:
    root = tmp_path / "lib"
    write(root / "s1/a.jpg", b"AAAA")
    write(root / "s1/a (1).jpg", b"AAAA")
    write(root / "s1/a (2).jpg", b"BBBBBB")  # 体积不同，不动
    write(root / "s1/nested/e.jpg", b"E")
    write(root / "s1/nested/e (1).jpg", b"E")  # 递归处理，只与同目录比较
    write(root / "s1/.a (3).jpg", b"AAAA")  # 隐藏文件
    write(root / "a (1).jpg", b"AAAA")  # 总目录本身也是处理单元：单独副本改回原名
    write(root / "s5/h.jpg", b"\xff\xd8" + b"\x01" * 4094 + bytes(4096))  # 原名文件损坏
    write(root / "s5/h (1).jpg", healthy_bytes())  # 同体积完好：留它并改回原名
    write(root / ".hid/g (1).png", b"G")  # 隐藏目录不进入
    write(root / "game/game.exe", b"MZ")
    write(root / "game/f (1).png", b"F")  # 软件目录连同子目录跳过
    write(root / "game/data/f (1).png", b"F")
    write(root / "s2/b (2).JPG", b"X")
    write(root / "s2/b (1).jpeg", b"X")  # 都带序号，留最小者并改回原名
    write(root / "s3/c.jpg", b"CC")
    write(root / "s3/c (1).jpg", b"DD")  # 同体积不同内容，交人工确认
    write(root / "s3/IMG_0001.jpg", b"Q")
    write(root / "s3/IMG_0002.jpg", b"Q")  # 弱标记且无主名文件，不分组
    write(root / "s4/d (3).png", b"D")  # 单独存在的副本，改回原名
    write(root / "s4/Trip (2019).png", b"T")  # 序号像年份，不改名
    return root


def test_plan_and_apply(library: Path, tmp_path: Path) -> None:
    xdg = tmp_path / "xdg"
    plan_path = tmp_path / "plan.json"
    planned = run("plan", str(library), "--out", str(plan_path), xdg=xdg)
    assert planned.returncode == 0, planned.stderr
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    dirs = {d["dir"]: d for d in plan["dirs"]}
    assert set(dirs) == {".", "s1", "s1/nested", "s2", "s3", "s4", "s5"}
    damaged = dirs["s5"]["groups"][0]
    assert damaged["keep"]["name"] == "h (1).jpg" and damaged["rename_to"] == "h.jpg"
    assert [(r["name"], r["damaged"]) for r in damaged["remove"]] == [("h.jpg", True)]
    assert plan["skipped_program_dirs"] == ["game"]
    assert [
        (g["keep"]["name"], [r["name"] for r in g["remove"]]) for g in dirs["s1"]["groups"]
    ] == [("a.jpg", ["a (1).jpg"])]
    assert dirs["s2"]["groups"][0]["keep"]["name"] == "b (1).jpeg"
    assert dirs["s2"]["groups"][0]["rename_to"] == "b.jpeg"
    assert dirs["s3"]["groups"] == []
    assert [f["name"] for f in dirs["s3"]["review"][0]["files"]] == ["c (1).jpg", "c.jpg"]

    applied = run("apply", str(plan_path), xdg=xdg)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert sorted(p.name for p in (library / "s1").iterdir()) == [
        ".a (3).jpg",
        "a (2).jpg",
        "a.jpg",
        "nested",
    ]
    assert sorted(p.name for p in (library / "s1/nested").iterdir()) == ["e.jpg"]
    assert sorted(p.name for p in (library / "s2").iterdir()) == ["b.jpeg"]
    assert sorted(p.name for p in (library / "s5").iterdir()) == ["h.jpg"]
    assert (library / "s5/h.jpg").read_bytes() == healthy_bytes()
    assert (library / "a.jpg").exists() and not (library / "a (1).jpg").exists()
    assert (library / "game/f (1).png").exists() and (library / "game/data/f (1).png").exists()
    assert (library / ".hid/g (1).png").exists()
    assert sorted(p.name for p in (library / "s4").iterdir()) == ["Trip (2019).png", "d.png"]
    assert (library / "s3/c (1).jpg").exists() and (library / "s3/IMG_0002.jpg").exists()
    trash = xdg / "Trash"
    assert sorted(p.name for p in (trash / "files").iterdir()) == [
        "a (1).jpg",
        "b (2).JPG",
        "e (1).jpg",
        "h.jpg",
    ]
    info = (trash / "info/a (1).jpg.trashinfo").read_text(encoding="utf-8")
    assert info.startswith("[Trash Info]\nPath=/")
    assert "/s1/a%20%281%29.jpg\nDeletionDate=" in info


def test_apply_skips_stale_group(library: Path, tmp_path: Path) -> None:
    xdg = tmp_path / "xdg"
    plan_path = tmp_path / "plan.json"
    assert run("plan", str(library), "--out", str(plan_path), xdg=xdg).returncode == 0
    (library / "s1/a (1).jpg").write_bytes(b"ZZZZ")  # 计划之后内容变化
    applied = run("apply", str(plan_path), xdg=xdg)
    assert applied.returncode == 0
    assert "a (1).jpg 内容已变化" in applied.stdout
    assert (library / "s1/a (1).jpg").read_bytes() == b"ZZZZ"


def test_topdir_trash_on_other_mount(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_mount, data_mount = tmp_path / "home", tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(home_mount / "share"))
    write(data_mount / "s/a (1).jpg", b"A")

    def mount_of(path: Path) -> Path:
        return data_mount if path.is_relative_to(data_mount) else home_mount

    target = data_mount / "s/a (1).jpg"
    dedupe.freedesktop_trash(target, mount_of)
    own = data_mount / f".Trash-{os.getuid()}"
    assert (own / "files/a (1).jpg").exists()
    assert stat.S_IMODE(own.stat().st_mode) == 0o700
    assert "Path=s/a%20%281%29.jpg\n" in (own / "info/a (1).jpg.trashinfo").read_text()
