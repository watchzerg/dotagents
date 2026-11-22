"""在临时目录中验证 dedupe_images.py 的命名解析、分组判定、计划与执行，回收站指向临时 XDG_DATA_HOME。"""

import importlib.util
import json
import os
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
        ("000c01 (2).jpg", "000c01", (2,)),
        ("a - Copy (2).jpg", "a", (2, 1)),
        ("复件 a.jpg", "a", (1,)),
    ],
)
def test_strong_markers(name: str, base: str, numbers: tuple[int, ...]) -> None:
    parsed = dedupe.parse_name(name, weak=False)
    assert parsed is not None
    assert (parsed.base, parsed.numbers) == (base, numbers)


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
    tail_cut = b"\xff\xd8" + b"\x02" * 8190  # 缺结束标记
    write(root / "s6/i.jpg", tail_cut)
    write(root / "s6/i (1).jpg", bytes(4100) + tail_cut[4100:])  # 开头被清零的副本：移走它
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
    write(root / "s4/page - (1).png", b"P")  # 去掉序号只剩 `page -`：序号是页码，不改名
    return root


def test_plan_and_apply(library: Path, tmp_path: Path) -> None:
    xdg = tmp_path / "xdg"
    plan_path = tmp_path / "plan.json"
    planned = run("plan", str(library), "--out", str(plan_path), xdg=xdg)
    assert planned.returncode == 0, planned.stderr
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    dirs = {d["dir"]: d for d in plan["dirs"]}
    assert set(dirs) == {".", "s1", "s1/nested", "s2", "s3", "s4", "s5", "s6"}
    zeroed = dirs["s6"]["groups"][0]
    assert zeroed["keep"]["name"] == "i.jpg"
    assert [(r["name"], r["damaged"]) for r in zeroed["remove"]] == [("i (1).jpg", True)]
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
    assert sorted(p.name for p in (library / "s4").iterdir()) == [
        "Trip (2019).png",
        "d.png",
        "page - (1).png",
    ]
    assert (library / "s3/c (1).jpg").exists() and (library / "s3/IMG_0002.jpg").exists()
    trash = xdg / "Trash"
    assert sorted(p.name for p in (trash / "files").iterdir()) == [
        "a (1).jpg",
        "b (2).JPG",
        "e (1).jpg",
        "h.jpg",
        "i (1).jpg",
    ]
    info = (trash / "info/a (1).jpg.trashinfo").read_text(encoding="utf-8")
    assert info.startswith("[Trash Info]\nPath=/")
    assert "/s1/a%20%281%29.jpg\nDeletionDate=" in info


def summarize(directory: Path) -> tuple[list[tuple[str, list[str], str | None]], list[list[str]]]:
    planned = dedupe.plan_directory(directory, ".", [])
    if planned is None:
        return [], []
    groups = [
        (g["keep"]["name"], [r["name"] for r in g["remove"]], g["rename_to"])
        for g in planned["groups"]
    ]
    return groups, [[f["name"] for f in r["files"]] for r in planned["review"]]


def test_page_series(tmp_path: Path) -> None:
    pages = [f"P{i}".encode() * (10 + i) for i in range(1, 6)]

    # 补零与不补零两套整套重复，编号错开一位：移走不补零的一套，保留补零的一套，不改名；
    # 页面体积相同，同页码两份（如 page (002) 与 page (2)）内容不同，整套移走后不进人工确认
    whole = tmp_path / "whole"
    write(whole / "page (1).jpg", b"cover")
    for i, data in enumerate((f"Q{i}".encode() * 10 for i in range(1, 6)), 1):
        write(whole / f"page ({i:03d}).jpg", data)
        write(whole / f"page ({i + 1}).jpg", data)
    groups, review = summarize(whole)
    assert groups == [(f"page ({i:03d}).jpg", [f"page ({i + 1}).jpg"], None) for i in range(1, 6)]
    assert review == []

    # 两套只零星几页相同，是不同版本：不动
    sporadic = tmp_path / "sporadic"
    for i, data in enumerate(pages, 1):
        write(sporadic / f"page ({i:03d}).jpg", data)
        write(sporadic / f"page ({i}).jpg", pages[0] if i == 2 else data + b"v2")
    assert summarize(sporadic) == ([], [])


def test_cross_name(tmp_path: Path) -> None:
    pages = [f"page-{i}".encode() * (5 + i) for i in range(12)]

    # 只差开头流水号且整套存了两遍：留流水号小的
    index = tmp_path / "index"
    for i, data in enumerate(pages[:4]):
        write(index / f"{i + 1:03d}_hellven_{i:03d}.jpg", data)
        write(index / f"{i + 5:03d}_hellven_{i:03d}.jpg", data)
    groups, _ = summarize(index)
    assert groups == [
        (f"{i + 1:03d}_hellven_{i:03d}.jpg", [f"{i + 5:03d}_hellven_{i:03d}.jpg"], None)
        for i in range(4)
    ]

    # 只差流水号的只有零星一对（每章重复的声明页）：不动
    credit = tmp_path / "credit"
    for i, data in enumerate(pages[:10]):
        write(credit / f"{i + 1:03d}_page.jpg", data)
    write(credit / "001_credit.jpg", b"credit")
    write(credit / "050_credit.jpg", b"credit")
    assert summarize(credit) == ([], [])


def test_dir_duplicates(tmp_path: Path) -> None:
    root = tmp_path / "lib"

    def fill(rel: str, files: dict[str, bytes]) -> None:
        for name, data in files.items():
            write(root / rel / name, data)

    pages = {f"{i:02d}.jpg": f"x{i}".encode() * 5 for i in range(1, 4)}
    fill("X", pages)
    fill("X (2)", pages)  # 内容相同、名字带副本标记：移走
    fill("X (2)", {"01 (1).jpg": pages["01.jpg"]})  # 移走的目录不再做目录内去重
    fill("X", {"01 (1).jpg": pages["01.jpg"]})
    fill("Ren", {"a.jpg": b"ren-a", "b.jpg": b"ren-b"})
    fill("Ren copy", {"x1.jpg": b"ren-a", "x2.jpg": b"ren-b"})  # 内容相同但文件名不同：交模型判断
    part = {f"{i:03d}.jpg": f"part{i}".encode() for i in range(20)}
    fill("full/[L] Part 1", part)
    fill("full/[L] Part 1 more", {**part, "100.jpg": b"extra"})  # 更大的超集
    fill("only/Part 1", dict(list(part.items())[:19]))  # 同名子集（覆盖 90%）：移走，指向最大的超集

    plan = dedupe.build_plan(root)
    removals = {r["dir"]: (r["keep_dir"], r["relation"]) for r in plan["dir_removals"]}
    assert removals == {
        "X (2)": ("X", "equal"),
        "full/[L] Part 1": ("full/[L] Part 1 more", "subset"),
        "only/Part 1": ("full/[L] Part 1 more", "subset"),
    }
    review = {r["dir"]: r["reason"] for r in plan["dir_review"]}
    assert review == {"Ren copy": "内容相同但文件名不同"}
    assert [d["dir"] for d in plan["dirs"]] == ["X"]

    xdg = tmp_path / "xdg"
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    applied = run("apply", str(plan_path), xdg=xdg)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert not (root / "X (2)").exists() and not (root / "full/[L] Part 1").exists()
    assert not (root / "only").exists()  # 移走后变空的上级目录一并删除
    assert sorted(p.name for p in (root / "X").iterdir()) == ["01.jpg", "02.jpg", "03.jpg"]
    assert sorted(p.name for p in (xdg / "Trash/files").iterdir()) == [
        "01 (1).jpg",
        "Part 1",
        "X (2)",
        "[L] Part 1",
    ]


def test_cases_and_decisions(tmp_path: Path) -> None:
    root = tmp_path / "lib"
    for ch in (1, 3, 4):
        write(root / f"Big/ch{ch}/p.jpg", f"chapter{ch}".encode())
    write(root / "Small/ch1/p.jpg", b"chapter1")
    write(root / "Small/ch2/p.jpg", b"chapter2")  # Big 没有的一话
    write(root / "Omni/0001.jpg", b"o1")
    write(root / "Omni/0002.jpg", b"o2")
    write(root / "Ch/1.jpg", b"o2")  # 改名子集
    write(root / "Lone/q.jpg", b"only-here")
    write(root / "s/c.jpg", b"CC")
    write(root / "s/c (1).jpg", b"DD")  # 同名同体积内容不同：文件案例
    xdg = tmp_path / "xdg"
    plan_path = tmp_path / "plan.json"
    assert run("plan", str(root), "--out", str(plan_path), xdg=xdg).returncode == 0
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in plan["cases"]}
    kinds = sorted(
        (c["kind"], [p["dir"] for p in c.get("pairs", [])] or [c["dir"]]) for c in cases.values()
    )
    assert kinds == [("dir", ["Ch"]), ("dir", ["Small/ch1"]), ("file", ["s"])]
    small = next(i for i, c in cases.items() if c.get("pairs", [{}])[0].get("dir") == "Small/ch1")

    shown = run("show", str(plan_path), small, xdg=xdg)
    assert shown.returncode == 0, shown.stderr
    assert "左侧父目录：Small/" in shown.stdout and "ch1/ = ch1/（会拆散所在合集" in shown.stdout
    assert "无对应的子目录 1 个：ch2" in shown.stdout
    all_cases = run("show", str(plan_path), xdg=xdg).stdout
    assert "c (1).jpg" in all_cases and "不同字节 2 个" in all_cases
    assert run("show", str(plan_path), "--sample", "2", xdg=xdg).returncode == 0

    decisions = {
        "root": str(root),
        "actions": [
            # 合并：把 Small 独有的一话移进 Big，再整体移走 Small
            {"case": "merge", "op": "move", "src": "Small/ch2", "dest": "Big"},
            {"case": "merge", "op": "trash", "path": "Small", "keep": ["Big"]},
            # Lone 的内容在 Omni 里没有：整个案例拒绝，连移动也不做
            {"case": "bad", "op": "move", "src": "Ch", "dest": "Omni"},
            {"case": "bad", "op": "trash", "path": "Lone", "keep": ["Omni"]},
            {"case": "inside", "op": "trash", "path": "Big", "keep": ["Big/ch1"]},
            {"case": "noop", "op": "keep"},
        ],
    }
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
    applied = run("apply-decisions", str(decisions_path), xdg=xdg)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert sorted(p.name for p in (root / "Big").iterdir()) == ["ch1", "ch2", "ch3", "ch4"]
    assert not (root / "Small").exists()
    assert (root / "Ch/1.jpg").exists() and (root / "Lone/q.jpg").exists()
    assert "Lone/q.jpg 在保留路径下没有相同内容的文件" in applied.stdout
    assert "保留路径 Big/ch1 在被移走的路径里" in applied.stdout
    assert sorted(p.name for p in (xdg / "Trash/files").iterdir()) == ["Small"]


def test_composed_collection_and_trash_matching(tmp_path: Path) -> None:
    root = tmp_path / "lib"
    for name, data in (("p1", b"A"), ("p2", b"B"), ("p3", b"CC"), ("p4", b"DD")):
        write(root / f"Full/{name}.jpg", data)
    write(root / "Parts/Ch1/01.jpg", b"A")
    write(root / "Parts/Ch1/02.jpg", b"B")
    write(root / "Parts/Ch1 copy/x1.jpg", b"A")  # 与 Ch1 内容相同的重复单章
    write(root / "Parts/Ch1 copy/x2.jpg", b"B")
    write(root / "Loose/Ch2/01.jpg", b"CC")
    write(root / "Loose/Ch2/02.jpg", b"DD")
    write(root / "Pack/a.jpg", b"EEE")  # 杂图包：前两张与独立作品相同
    write(root / "Pack/b.jpg", b"FFF")
    write(root / "Pack/c.jpg", b"GGG")
    write(root / "Work/1.jpg", b"EEE")
    write(root / "Work/2.jpg", b"FFF")
    xdg = tmp_path / "xdg"
    plan_path = tmp_path / "plan.json"
    assert run("plan", str(root), "--out", str(plan_path), xdg=xdg).returncode == 0
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    composed = [c for c in plan["cases"] if "composed" in c]
    assert [c["composed"] for c in composed] == [
        {"dir": "Full", "chapters": ["Loose/Ch2", "Parts/Ch1"], "duplicates": ["Parts/Ch1 copy"]}
    ]
    assert plan["summary"]["composed_cases"] == 1
    shown = run("show", str(plan_path), composed[0]["id"], xdg=xdg).stdout
    assert "合集 Full/ 恰好由 2 个单章拼成" in shown and "分散在 2 个父目录" in shown

    decisions = {
        "root": str(root),
        "actions": [
            # 单章集中到合集目录下，合集自己的图片按内容移走
            {"case": "a", "op": "move", "src": "Parts/Ch1", "dest": "Full"},
            {"case": "a", "op": "move", "src": "Loose/Ch2", "dest": "Full"},
            {
                "case": "a",
                "op": "trash_matching",
                "path": "Full",
                "keep": ["Parts/Ch1", "Loose/Ch2"],
            },
            {"case": "b", "op": "trash_matching", "path": "Pack", "keep": ["Work"]},
        ],
    }
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
    applied = run("apply-decisions", str(decisions_path), xdg=xdg)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert sorted(p.name for p in (root / "Full").iterdir()) == ["Ch1", "Ch2"]
    assert not (root / "Loose").exists()
    assert sorted(p.name for p in (root / "Pack").iterdir()) == ["c.jpg"]
    assert sorted(p.name for p in (root / "Work").iterdir()) == ["1.jpg", "2.jpg"]


def test_clean_junk(tmp_path: Path) -> None:
    root = tmp_path / "lib"
    write(root / "Work/01.jpg", b"A")
    write(root / "Work/02.jpg.bc!", b"B")  # 有下载完成的同名文件
    write(root / "Work/03.jpg.!qB", b"C")  # 没有，移走后缺页
    write(root / "Work/复件 (1) Thumbs.db", b"D")
    write(root / "Work/._01.jpg", b"\x00\x05\x16\x07rest")
    write(root / "Work/._keep.jpg", b"not apple double")
    write(root / "Work/广告.url", b"E")
    write(root / "Work/ComicInfo.xml", b"F")
    write(root / "Work/人物简介.txt", b"G")
    write(root / "Work/book.pdf", b"H")
    write(root / "Work/02.jpg", b"B")
    write(root / "Partial/x.jpg.bc!", b"I")  # 只有残缺文件的目录，清理后变空
    write(root / "Game/game.exe", b"J")
    write(root / "Game/desktop.ini", b"K")  # 软件目录不处理
    xdg = tmp_path / "xdg"
    listed = run("clean", str(root), xdg=xdg)
    assert listed.returncode == 0
    assert "非图片杂项 7 个" in listed.stdout
    assert "Work/03.jpg.!qB" in listed.stdout and "Partial/x.jpg.bc!" in listed.stdout
    assert "Work/02.jpg.bc!" not in listed.stdout
    assert "pdf 1" in listed.stdout and "txt 1" in listed.stdout
    assert (root / "Work/广告.url").exists()  # 不加 --apply 不改动

    applied = run("clean", str(root), "--apply", xdg=xdg)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert sorted(p.name for p in (root / "Work").iterdir()) == [
        "._keep.jpg",
        "01.jpg",
        "02.jpg",
        "book.pdf",
        "人物简介.txt",
    ]
    assert not (root / "Partial").exists()
    assert (root / "Game/desktop.ini").exists()


def test_check_decisions_without_changes(tmp_path: Path) -> None:
    root = tmp_path / "lib"
    write(root / "A/1.jpg", b"A")
    write(root / "A/2.jpg", b"B")
    write(root / "B/1.jpg", b"A")
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps(
            {
                "root": str(root),
                "actions": [
                    {"case": "x", "op": "trash", "path": "A", "keep": ["B"]},
                    {"case": "y", "op": "trash", "path": "B", "keep": ["A"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    checked = run("apply-decisions", str(decisions_path), "--check", xdg=tmp_path / "xdg")
    assert checked.returncode == 1  # 有跳过项
    assert "校验通过（未执行）案例 1 个" in checked.stdout
    assert "A/2.jpg" in checked.stdout  # 列出未覆盖的文件，据此决定先移动哪些
    assert (root / "A/2.jpg").exists() and (root / "B/1.jpg").exists()

    # 两个案例各自都成立、合起来会互相删掉保留处：校验模式按顺序模拟，后一个报冲突
    (root / "A/2.jpg").unlink()
    checked = run("apply-decisions", str(decisions_path), "--check", xdg=tmp_path / "xdg")
    assert checked.returncode == 1
    assert "y：A 与案例 x 冲突" in checked.stdout


def test_move_with_new_name(tmp_path: Path) -> None:
    root = tmp_path / "lib"
    write(root / "Named/001_a.png", b"A")
    write(root / "Named/002_b.png", b"B")
    write(root / "Flat/00000001.png", b"A")
    write(root / "Flat/00000002.png", b"X")  # 只在 Flat 里有，改名插到 001_a 之后
    write(root / "Flat/00000003.png", b"B")
    decisions_path = tmp_path / "decisions.json"

    def decide(name: str) -> subprocess.CompletedProcess[str]:
        decisions_path.write_text(
            json.dumps(
                {
                    "root": str(root),
                    "actions": [
                        {
                            "case": "m",
                            "op": "move",
                            "src": "Flat/00000002.png",
                            "dest": "Named",
                            "name": name,
                        },
                        {"case": "m", "op": "trash", "path": "Flat", "keep": ["Named"]},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return run("apply-decisions", str(decisions_path), xdg=tmp_path / "xdg")

    applied = decide("001_a_00000002.png")
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert sorted(p.name for p in (root / "Named").iterdir()) == [
        "001_a.png",
        "001_a_00000002.png",
        "002_b.png",
    ]
    assert not (root / "Flat").exists()
