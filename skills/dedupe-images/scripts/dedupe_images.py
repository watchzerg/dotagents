#!/usr/bin/env python3
"""递归地按目录对图片库去重，每个目录只比较自己直接包含的图片：同名带副本标记且内容相同的图片只留一张，其余移入回收站。

用法：
  python3 dedupe_images.py plan <总目录> --out <计划.json>
  python3 dedupe_images.py apply <计划.json>

只依赖 Python 3.14+ 标准库。判定规则见 docs/skills/dedupe-images/design.md。
"""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import unicodedata
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

PLAN_VERSION = 3

# 目录里直接有这些文件（或目录名以 .app 结尾）即视为软件目录，连同子目录整体跳过。
PROGRAM_EXTENSIONS = frozenset("exe dll so dylib msi assets pak".split())

# 扩展名 -> 分组用的规范扩展名；不区分大小写。
EXTENSIONS = {
    **dict.fromkeys(("jpg", "jpeg", "jpe", "jfif"), "jpg"),
    **dict.fromkeys(("tif", "tiff"), "tif"),
    **dict.fromkeys(("heic", "heif"), "heic"),
    **{
        ext: ext
        for ext in ("png gif webp bmp avif jxl svg ico dng cr2 cr3 nef arw raf orf rw2".split())
    },
}

_FLAGS = re.IGNORECASE
_REST = r"(?P<rest>.*\S)"

# 强标记：命名本身说明是副本，总是剥离。每项为 (正则, 未写数字时的序号)。
STRONG_MARKERS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(_REST + r"\s*[(（]\s*(?P<n>\d+)\s*[)）]$", _FLAGS), 1),
    (re.compile(_REST + r"\s+-\s+(?:copy|副本)$", _FLAGS), 1),
    (re.compile(_REST + r"\s*\(\s*(?:copy|副本)(?:\s+(?P<n>\d+))?\s*\)$", _FLAGS), 1),
    (re.compile(_REST + r"\s*\(\s*(?:another\s+copy|另一个副本)\s*\)$", _FLAGS), 2),
    (re.compile(_REST + r"\s*\(\s*(?P<n>\d+)(?:st|nd|rd|th)\s+copy\s*\)$", _FLAGS), 1),
    (re.compile(_REST + r"\s*\(\s*第\s*(?P<n>\d+)\s*个副本\s*\)$", _FLAGS), 1),
    (re.compile(_REST + r"\s*\([^()]*(?:conflicted\s+copy|冲突副本)[^()]*\)$", _FLAGS), 1),
    (re.compile(_REST + r"\s+(?:copy|副本)(?:\s+(?P<n>\d+))?$", _FLAGS), 1),
    (re.compile(_REST + r"[_-](?:copy|副本)$", _FLAGS), 1),
    (re.compile(r"^copy(?:\s*\(\s*(?P<n>\d+)\s*\))?\s+of\s+(?P<rest>\S.*)$", _FLAGS), 1),
    (re.compile(r"^复件(?:\s*\(\s*(?P<n>\d+)\s*\))?\s+(?P<rest>\S.*)$", _FLAGS), 1),
]

# 弱标记：同样的写法常见于正常文件名，只有主名文件存在时才算副本。
WEAK_MARKERS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(_REST + r"-(?P<n>\d+)$"), 1),
    (re.compile(_REST + r"_(?P<n>\d+)$"), 1),
    (re.compile(_REST + r"\s+(?P<n>\d+)$"), 1),
]

# 序号达到该值（如 `(2019)`）更像年份等正常命名，不据此改名。
RENAME_NUMBER_LIMIT = 1000

WGET = re.compile(r"^(?P<inner>.+\.(?P<ext>[^.]+))\.(?P<n>\d+)$")


@dataclass(frozen=True)
class Parsed:
    """文件名解析结果。base 保留原始写法，numbers 按从外到内的剥离顺序记录每层序号。"""

    name: str
    base: str
    ext: str
    numbers: tuple[int, ...]
    weak: bool

    @property
    def key(self) -> tuple[str, str]:
        return (unicodedata.normalize("NFC", self.base).casefold(), EXTENSIONS[self.ext.lower()])

    @property
    def original_name(self) -> str:
        return f"{self.base}.{self.ext}"

    @property
    def renamable(self) -> bool:
        return bool(self.numbers) and max(self.numbers) < RENAME_NUMBER_LIMIT

    def rank(self) -> tuple[bool, int, tuple[int, ...], int, str]:
        return (bool(self.numbers), len(self.numbers), self.numbers, len(self.name), self.name)


def _strip(stem: str, markers: list[tuple[re.Pattern[str], int]]) -> tuple[str, int] | None:
    for pattern, default in markers:
        match = pattern.match(stem)
        if match:
            number = match.groupdict().get("n")
            return match["rest"], int(number) if number else default
    return None


def parse_name(name: str, *, weak: bool = True) -> Parsed | None:
    """解析图片文件名；不是图片扩展名时返回 None。weak=False 时只剥离强标记。"""
    numbers: list[int] = []
    wget = WGET.match(name)
    if wget and wget["ext"].lower() in EXTENSIONS:
        numbers.append(int(wget["n"]))
        name_core = wget["inner"]
    else:
        name_core = name
    stem, dot, ext = name_core.rpartition(".")
    if not dot or not stem or ext.lower() not in EXTENSIONS:
        return None
    used_weak = False
    while True:
        stripped = _strip(stem, STRONG_MARKERS)
        if stripped is None and weak:
            stripped = _strip(stem, WEAK_MARKERS)
            used_weak = used_weak or stripped is not None
        if stripped is None:
            break
        stem, number = stripped
        numbers.append(number)
    return Parsed(name, stem, ext, tuple(numbers), used_weak)


def parse_directory(names: list[str]) -> list[Parsed]:
    """解析一个目录内的文件名；弱标记仅在剥离后的主名文件存在时生效。"""
    strong = [p for p in (parse_name(n, weak=False) for n in names) if p is not None]
    bare = {p.key for p in strong if not p.numbers}
    result: list[Parsed] = []
    for fallback in strong:
        full = parse_name(fallback.name)
        assert full is not None
        result.append(full if not full.weak or full.key in bare else fallback)
    return result


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _entry(path: Path, size: int, digest: str | None) -> dict[str, Any]:
    return {"name": path.name, "size": size, "sha256": digest}


# 压缩格式里不会自然出现成片的 0 字节；未压缩格式（bmp、tif、raw 等）的纯黑区域可能是 0，不判定。
COMPRESSED = frozenset("jpg png webp gif heic avif jxl".split())
ZERO_BLOCK = bytes(4096)
END_MARKERS = {"jpg": b"\xff\xd9", "png": b"IEND\xaeB`\x82"}


def looks_damaged(path: Path, ext: str) -> bool:
    """含 4 KiB 对齐的全 0 块，或 JPEG/PNG 去掉末尾 0 后缺结束标记，视为写入不完整。"""
    data = path.read_bytes()
    if any(data[i : i + 4096] == ZERO_BLOCK for i in range(0, len(data) - 4095, 4096)):
        return True
    marker = END_MARKERS.get(ext)
    return marker is not None and not data.rstrip(b"\0").endswith(marker)


def resolve_damaged(directory: Path, clusters: dict[str, list[Parsed]]) -> str | None:
    """同体积不同内容时，若恰有一个内容是完好的、其余都有损坏特征，返回完好者的哈希。"""
    first = next(iter(clusters.values()))[0]
    ext = EXTENSIONS[first.ext.lower()]
    if ext not in COMPRESSED:
        return None
    try:
        healthy = [
            h for h, ps in clusters.items() if not looks_damaged(directory / ps[0].name, ext)
        ]
    except OSError:
        return None
    return healthy[0] if len(healthy) == 1 else None


def plan_directory(directory: Path, rel: str, errors: list[str]) -> dict[str, Any] | None:
    names = [
        entry.name
        for entry in os.scandir(directory)
        if not entry.name.startswith(".") and entry.is_file(follow_symlinks=False)
    ]
    name_groups: dict[tuple[str, str], list[Parsed]] = defaultdict(list)
    for parsed in parse_directory(names):
        name_groups[parsed.key].append(parsed)

    groups: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for members in name_groups.values():
        if len(members) == 1:
            lone = members[0]
            target = directory / lone.original_name
            if lone.renamable and not os.path.lexists(target):
                try:
                    size = (directory / lone.name).stat().st_size
                except OSError as exc:
                    errors.append(f"{directory / lone.name}: {exc}")
                    continue
                groups.append(
                    {
                        "keep": _entry(directory / lone.name, size, None),
                        "remove": [],
                        "rename_to": lone.original_name,
                    }
                )
            continue
        by_size: dict[int, list[Parsed]] = defaultdict(list)
        for parsed in members:
            try:
                by_size[(directory / parsed.name).stat().st_size].append(parsed)
            except OSError as exc:
                errors.append(f"{directory / parsed.name}: {exc}")
        removed = 0
        unresolved = False
        found: list[tuple[Parsed, str, list[tuple[Parsed, str, bool]], int]] = []
        for size, same_size in by_size.items():
            if len(same_size) < 2:
                continue
            by_hash: dict[str, list[Parsed]] = defaultdict(list)
            for parsed in same_size:
                try:
                    by_hash[sha256(directory / parsed.name)].append(parsed)
                except OSError as exc:
                    errors.append(f"{directory / parsed.name}: {exc}")
                    unresolved = True
            clusters = {h: sorted(ps, key=Parsed.rank) for h, ps in by_hash.items()}
            if len(clusters) > 1:
                healthy = resolve_damaged(directory, clusters)
                if healthy is None:
                    unresolved = True
                    review.append(
                        {
                            "size": size,
                            "files": sorted(
                                (
                                    {"name": p.name, "sha256": h}
                                    for h, ps in clusters.items()
                                    for p in ps
                                ),
                                key=lambda f: f["name"],
                            ),
                        }
                    )
                else:
                    keep, *same = clusters[healthy]
                    remove = [(p, healthy, False) for p in same] + [
                        (p, h, True) for h, ps in clusters.items() if h != healthy for p in ps
                    ]
                    found.append((keep, healthy, remove, size))
                    removed += len(remove)
                    continue
            for digest, same in clusters.items():
                if len(same) >= 2:
                    found.append((same[0], digest, [(p, digest, False) for p in same[1:]], size))
                    removed += len(same) - 1
        alone = len(members) - removed == 1 and not unresolved
        for keep, digest, remove, size in found:
            rename_to = None
            target = keep.original_name
            freed = any(p.name == target for p, _, _ in remove)  # 原名文件本身将被移走
            if alone and keep.renamable and (freed or not os.path.lexists(directory / target)):
                rename_to = target
            groups.append(
                {
                    "keep": _entry(directory / keep.name, size, digest),
                    "remove": [
                        {**_entry(directory / p.name, size, h), "damaged": damaged}
                        for p, h, damaged in remove
                    ],
                    "rename_to": rename_to,
                }
            )
    if not groups and not review:
        return None
    groups.sort(key=lambda g: g["keep"]["name"])
    review.sort(key=lambda r: r["files"][0]["name"])
    return {"dir": rel, "groups": groups, "review": review}


def is_program_dir(name: str, files: list[str]) -> bool:
    return name.lower().endswith(".app") or any(
        f.rpartition(".")[2].lower() in PROGRAM_EXTENSIONS for f in files if "." in f
    )


def build_plan(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    dirs: list[dict[str, Any]] = []
    skipped: list[str] = []
    scanned = 0

    def on_error(exc: OSError) -> None:
        errors.append(f"{exc.filename}: {exc.strerror or exc}")

    for current, subdirs, files in os.walk(root, onerror=on_error):
        directory = Path(current)
        rel = directory.relative_to(root).as_posix()
        subdirs[:] = sorted(
            d for d in subdirs if not d.startswith(".") and not (directory / d).is_symlink()
        )
        if is_program_dir(directory.name, files):
            skipped.append(rel)
            subdirs[:] = []
            continue
        scanned += 1
        try:
            planned = plan_directory(directory, rel, errors)
        except OSError as exc:
            errors.append(f"{directory}: {exc}")
            continue
        if planned is not None:
            dirs.append(planned)
    groups = [g for d in dirs for g in d["groups"]]
    removes = [r for g in groups for r in g["remove"]]
    return {
        "version": PLAN_VERSION,
        "root": str(root),
        "created": datetime.now().isoformat(timespec="seconds"),
        "scanned_dirs": scanned,
        "dirs": dirs,
        "skipped_program_dirs": skipped,
        "errors": errors,
        "summary": {
            "groups": sum(1 for g in groups if g["remove"]),
            "remove_files": len(removes),
            "remove_bytes": sum(r["size"] for r in removes),
            "damaged_files": sum(1 for r in removes if r["damaged"]),
            "renames": sum(1 for g in groups if g["rename_to"]),
            "review_sets": sum(len(d["review"]) for d in dirs),
        },
    }


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError


def _top(rel: str) -> str:
    return "（总目录本身）" if rel == "." else rel.split("/", 1)[0] + "/"


def print_plan(plan: dict, out: Path) -> None:
    summary = plan["summary"]
    print(f"总目录：{plan['root']}")
    print(f"扫描目录 {plan['scanned_dirs']} 个，其中 {len(plan['dirs'])} 个有待处理项。")
    print(
        f"重复组 {summary['groups']} 个，待移入回收站 {summary['remove_files']} 个文件"
        f"（{human_size(summary['remove_bytes'])}，其中损坏副本 {summary['damaged_files']} 个），"
        f"改回原名 {summary['renames']} 个。"
    )
    per_top: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for directory in plan["dirs"]:
        counts = per_top[_top(directory["dir"])]
        counts[0] += sum(len(g["remove"]) for g in directory["groups"])
        counts[1] += sum(1 for g in directory["groups"] if g["rename_to"])
    for top, (removes, renames) in sorted(per_top.items()):
        print(f"  {top}：删除 {removes} 个，改名 {renames} 个")
    if summary["review_sets"]:
        print(
            f"需人工确认 {summary['review_sets']} 组（同名同体积、内容不同且无法判定哪个损坏，不会删除）："
        )
        for directory in plan["dirs"]:
            for item in directory["review"]:
                names = "，".join(f["name"] for f in item["files"])
                print(f"  {directory['dir']}/：{names}（{human_size(item['size'])}）")
    if plan["skipped_program_dirs"]:
        print(
            f"跳过软件目录 {len(plan['skipped_program_dirs'])} 个（含程序文件，连同子目录不处理）："
        )
        for rel in plan["skipped_program_dirs"]:
            print(f"  {rel}/")
    if plan["errors"]:
        print(f"读取出错 {len(plan['errors'])} 项（已跳过）：")
        for error in plan["errors"]:
            print(f"  {error}")
    print(f"计划已写入：{out}")


# ---------- 回收站 ----------


def _unescape_mount(path: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), path)


def mount_point(path: Path) -> Path:
    """按 /proc/self/mountinfo 找 path 所在挂载点（最长前缀匹配）。"""
    real = Path(os.path.realpath(path))
    best = Path("/")
    with open("/proc/self/mountinfo", encoding="utf-8", errors="surrogateescape") as handle:
        for line in handle:
            mount = Path(_unescape_mount(line.split()[4]))
            if real.is_relative_to(mount) and len(mount.parts) > len(best.parts):
                best = mount
    return best


def _data_home() -> Path:
    value = os.environ.get("XDG_DATA_HOME", "")
    return Path(value) if os.path.isabs(value) else Path.home() / ".local/share"


def freedesktop_trash_dir(
    path: Path, mount_of: Callable[[Path], Path] = mount_point
) -> tuple[Path, Path | None]:
    """返回 (回收站目录, Path= 相对的 topdir)；home 回收站时 topdir 为 None。"""
    data_home = _data_home()
    data_home.mkdir(parents=True, exist_ok=True)
    topdir = mount_of(path.parent)
    if mount_of(data_home) == topdir:
        return data_home / "Trash", None
    uid = str(os.getuid())
    shared = topdir / ".Trash"
    try:
        info = shared.lstat()
        if stat.S_ISDIR(info.st_mode) and info.st_mode & stat.S_ISVTX:
            (shared / uid).mkdir(mode=0o700, exist_ok=True)
            return shared / uid, topdir
    except OSError:
        pass
    own = topdir / f".Trash-{uid}"
    try:
        own.mkdir(mode=0o700, exist_ok=True)
    except OSError as exc:
        raise OSError(f"无法在挂载点 {topdir} 建立回收站（{exc}），未删除文件") from exc
    return own, topdir


def freedesktop_trash(path: Path, mount_of: Callable[[Path], Path] = mount_point) -> None:
    path = Path(os.path.abspath(path))
    trash, topdir = freedesktop_trash_dir(path, mount_of)
    files, info = trash / "files", trash / "info"
    for directory in (files, info):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    original = path if topdir is None else path.relative_to(topdir)
    content = (
        "[Trash Info]\n"
        f"Path={quote(os.fsencode(original), safe='/')}\n"
        f"DeletionDate={datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n"
    )
    stem, suffix = os.path.splitext(path.name)
    for index in range(1, 10000):
        name = path.name if index == 1 else f"{stem}.{index}{suffix}"
        info_path = info / f"{name}.trashinfo"
        try:
            fd = os.open(info_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        if os.path.lexists(files / name):
            info_path.unlink()
            continue
        try:
            os.rename(path, files / name)
        except OSError:
            info_path.unlink()
            raise
        return
    raise OSError(f"回收站中同名文件过多：{path.name}")


MAC_TRASH = Path("/usr/bin/trash")


def trash_files(paths: list[Path]) -> list[tuple[Path, str]]:
    """把文件移入回收站，返回失败项 (路径, 原因)。"""
    failures: list[tuple[Path, str]] = []
    if sys.platform == "darwin":
        result = subprocess.run(
            [str(MAC_TRASH), *map(str, paths)], capture_output=True, text=True, check=False
        )
        for path in paths:
            if os.path.lexists(path):
                failures.append((path, result.stderr.strip() or f"退出码 {result.returncode}"))
        return failures
    for path in paths:
        try:
            freedesktop_trash(path)
        except OSError as exc:
            failures.append((path, str(exc)))
    return failures


def check_platform() -> str | None:
    if sys.platform == "darwin":
        if not MAC_TRASH.exists():
            return "未找到 /usr/bin/trash（macOS 15 起系统自带），未删除任何文件。"
        return None
    if sys.platform.startswith("linux"):
        return None
    return f"不支持的平台：{sys.platform}，未删除任何文件。"


# ---------- 执行 ----------


def _verify(path: Path, entry: dict) -> str | None:
    try:
        info = path.lstat()
    except OSError as exc:
        return f"{path.name} 不可访问：{exc.strerror or exc}"
    if not stat.S_ISREG(info.st_mode):
        return f"{path.name} 不再是普通文件"
    if info.st_size != entry["size"]:
        return f"{path.name} 体积已变化"
    if entry["sha256"] is None:
        return None
    try:
        if sha256(path) != entry["sha256"]:
            return f"{path.name} 内容已变化"
    except OSError as exc:
        return f"{path.name} 读取失败：{exc}"
    return None


def apply_plan(plan: dict) -> dict[str, list]:
    root = Path(plan["root"])
    result: dict[str, list] = {"trashed": [], "renamed": [], "skipped": [], "failed": []}
    for directory in plan["dirs"]:
        base = root / directory["dir"]
        for group in directory["groups"]:
            keep = base / group["keep"]["name"]
            entries = [(keep, group["keep"])] + [(base / r["name"], r) for r in group["remove"]]
            problems = [p for p in (_verify(path, entry) for path, entry in entries) if p]
            if problems:
                result["skipped"].append({"path": str(keep), "reason": "；".join(problems)})
                continue
            targets = [base / r["name"] for r in group["remove"]]
            failures = trash_files(targets) if targets else []
            failed = {path for path, _ in failures}
            result["failed"] += [{"path": str(p), "error": e} for p, e in failures]
            result["trashed"] += [
                {"path": str(p), "size": group["keep"]["size"]} for p in targets if p not in failed
            ]
            if group["rename_to"] and not failures:
                target = base / group["rename_to"]
                if os.path.lexists(target):
                    result["skipped"].append(
                        {"path": str(keep), "reason": f"改名目标 {target.name} 已存在，未改名"}
                    )
                    continue
                try:
                    os.rename(keep, target)
                    result["renamed"].append({"from": str(keep), "to": str(target)})
                except OSError as exc:
                    result["failed"].append({"path": str(keep), "error": f"改名失败：{exc}"})
    return result


def print_result(result: dict[str, list]) -> None:
    freed = sum(item["size"] for item in result["trashed"])
    print(
        f"移入回收站 {len(result['trashed'])} 个文件（{human_size(freed)}），"
        f"改回原名 {len(result['renamed'])} 个。"
    )
    if result["skipped"]:
        print(f"跳过 {len(result['skipped'])} 项：")
        for item in result["skipped"]:
            print(f"  {item['path']}：{item['reason']}")
    if result["failed"]:
        print(f"失败 {len(result['failed'])} 项：")
        for item in result["failed"]:
            print(f"  {item['path']}：{item['error']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="递归地按目录对图片库去重。")
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan", help="扫描并生成去重计划，不改动文件")
    plan_cmd.add_argument("root", type=Path, help="总目录")
    plan_cmd.add_argument("--out", type=Path, required=True, help="计划 JSON 的输出路径")
    apply_cmd = commands.add_parser("apply", help="复核并执行计划：移入回收站、改回原名")
    apply_cmd.add_argument("plan", type=Path, help="plan 生成的计划 JSON")
    args = parser.parse_args(argv)

    if args.command == "plan":
        root = Path(os.path.abspath(args.root))
        if not root.is_dir():
            print(f"错误：总目录不存在或不是目录：{root}", file=sys.stderr)
            return 2
        plan = build_plan(root)
        args.out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print_plan(plan, args.out)
        return 0

    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"错误：无法读取计划：{exc}", file=sys.stderr)
        return 2
    if plan.get("version") != PLAN_VERSION:
        print("错误：计划版本不符，请重新运行 plan。", file=sys.stderr)
        return 2
    problem = check_platform()
    if problem:
        print(f"错误：{problem}", file=sys.stderr)
        return 2
    result = apply_plan(plan)
    print_result(result)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
