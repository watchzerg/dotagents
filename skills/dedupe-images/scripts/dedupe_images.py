#!/usr/bin/env python3
"""递归地对图片库去重：有把握的重复写入计划自动处理，拿不准的整理成案例交模型判断。

用法：
  python3 dedupe_images.py plan <总目录> --out <计划.json>
  python3 dedupe_images.py show <计划.json> --sample 5      # 自动处理部分的抽查材料
  python3 dedupe_images.py show <计划.json> [案例编号 ...]  # 案例的判断材料，不给编号则输出全部
  python3 dedupe_images.py apply <计划.json>
  python3 dedupe_images.py apply-decisions <决策.json> [--check]  # --check 只校验不执行
  python3 dedupe_images.py clean <总目录> [--apply]           # 非图片杂项，不加 --apply 只列出

只依赖 Python 3.14+ 标准库。判定规则见 docs/skills/dedupe-images/design.md。
"""

import argparse
import hashlib
import json
import os
import posixpath
import re
import stat
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

PLAN_VERSION = 8

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

# 名称组内最内层序号的不同取值达到该数，视为页码序列（`page (1)…page (95)`），序号是页码而非副本标记。
SERIES_MIN_PAGES = 4
# 页码序列里补零一套（`page (001)`）至少有该比例在不补零一套里有同内容文件，才视为整套重复。
WHOLE_SET_RATIO = 0.9
# 两套命名模板整套对应时，两套文件数之比的下限，避免小套与大画集偶然配上。
SET_SIZE_RATIO = 0.9
# 参与整套对应的命名模板至少要有的文件数；双语版各自的几张封面（`000c01` 与 `k000c01`）不应整套移走。
NAME_SET_MIN_FILES = 10
# 只差开头流水号的同内容文件，待删数至少占目录图片数的该比例才移走（整套存了两遍）；
# 零星几对多是每章重复的声明页，不动。
INDEX_SET_RATIO = 0.25

WGET = re.compile(r"^(?P<inner>.+\.(?P<ext>[^.]+))\.(?P<n>\d+)$")


@dataclass(frozen=True)
class Parsed:
    """文件名解析结果。base 保留原始写法，numbers 按从外到内的剥离顺序记录每层序号。"""

    name: str
    base: str
    ext: str
    numbers: tuple[int, ...]
    weak: bool
    padded: bool = False  # 最内层序号是否补零书写（`(001)`）

    @property
    def page(self) -> int | None:
        """页码序列中的页码：最内层序号；外层序号才是副本标记。"""
        return self.numbers[-1] if self.numbers else None

    @property
    def key(self) -> tuple[str, str]:
        return (unicodedata.normalize("NFC", self.base).casefold(), EXTENSIONS[self.ext.lower()])

    @property
    def original_name(self) -> str:
        return f"{self.base}.{self.ext}"

    @property
    def renamable(self) -> bool:
        """序号小于 1000（不是年份），且原名不以分隔符结尾：`page - (1)` 去掉序号只剩 `page -`，
        说明序号是页码而不是副本标记（整套页码被跨名称匹配移走后常剩这样一张）。"""
        return (
            bool(self.numbers)
            and max(self.numbers) < RENAME_NUMBER_LIMIT
            and not self.base.rstrip().endswith(("-", "_", ".", "~", "#"))
        )

    def rank(self) -> tuple[bool, int, tuple[int, ...], int, str]:
        return (bool(self.numbers), len(self.numbers), self.numbers, len(self.name), self.name)

    def series_rank(self) -> tuple[int, tuple[int, ...], bool, int, str]:
        """页码序列内的保留顺序：副本层少的优先，再优先补零书写，与整套重复时保留补零一套一致。"""
        return (len(self.numbers), self.numbers[:-1], not self.padded, len(self.name), self.name)


def _strip(stem: str, markers: list[tuple[re.Pattern[str], int]]) -> tuple[str, int, str] | None:
    for pattern, default in markers:
        match = pattern.match(stem)
        if match:
            number = match.groupdict().get("n")
            return match["rest"], int(number) if number else default, number or ""
    return None


def parse_name(name: str, *, weak: bool = True) -> Parsed | None:
    """解析图片文件名；不是图片扩展名时返回 None。weak=False 时只剥离强标记。"""
    numbers: list[int] = []
    text = ""
    wget = WGET.match(name)
    if wget and wget["ext"].lower() in EXTENSIONS:
        numbers.append(int(wget["n"]))
        text = wget["n"]
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
        stem, number, text = stripped
        numbers.append(number)
    padded = len(text) > 1 and text.startswith("0")
    return Parsed(name, stem, ext, tuple(numbers), used_weak, padded)


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


def zeroed_copy(good: bytes, other: bytes) -> bool:
    """other 与 good 同长且凡是不同的字节在 other 里都是 0：other 是 good 被局部清零后的损坏副本。"""
    if len(good) != len(other) or good == other:
        return False
    for start in range(0, len(good), 4096):
        a, b = good[start : start + 4096], other[start : start + 4096]
        if a != b and any(y != x and y != 0 for x, y in zip(a, b, strict=True)):
            return False
    return True


def resolve_damaged(directory: Path, clusters: dict[str, list[Parsed]]) -> str | None:
    """同体积不同内容时返回应保留内容的哈希：恰有一个内容完好、其余都有损坏特征；
    或其余每个内容都是同一个内容被局部清零后的副本（该内容自身缺结束标记也保留，它不比副本差）。"""
    first = next(iter(clusters.values()))[0]
    ext = EXTENSIONS[first.ext.lower()]
    if ext not in COMPRESSED:
        return None
    try:
        healthy = [
            h for h, ps in clusters.items() if not looks_damaged(directory / ps[0].name, ext)
        ]
        if len(healthy) == 1:
            return healthy[0]
        data = {h: (directory / ps[0].name).read_bytes() for h, ps in clusters.items()}
    except OSError:
        return None
    sources = [
        h for h in data if all(zeroed_copy(data[h], data[other]) for other in data if other != h)
    ]
    return sources[0] if len(sources) == 1 else None


Found = tuple[Parsed, str, list[tuple[Parsed, str, bool]], int]


def _hash(directory: Path, name: str, cache: dict[str, str]) -> str:
    """缓存以完整路径为键，整个 plan 共用：目录级比对算过的哈希，目录内去重不再重算。"""
    key = os.path.join(directory, name)
    if key not in cache:
        cache[key] = sha256(directory / name)
    return cache[key]


def find_duplicates(
    directory: Path,
    members: list[Parsed],
    sizes: dict[str, int],
    rank: Callable[[Parsed], Any],
    errors: list[str],
    cache: dict[str, str],
) -> tuple[list[Found], int, bool, list[dict[str, Any]]]:
    """在一批候选内按体积、哈希与损坏特征找重复组，按 rank 取保留项。

    返回 (重复组, 待删文件数, 是否有未定项, 需人工确认项)。
    """
    by_size: dict[int, list[Parsed]] = defaultdict(list)
    for parsed in members:
        by_size[sizes[parsed.name]].append(parsed)
    found: list[Found] = []
    review: list[dict[str, Any]] = []
    removed = 0
    unresolved = False
    for size, same_size in by_size.items():
        if len(same_size) < 2:
            continue
        by_hash: dict[str, list[Parsed]] = defaultdict(list)
        for parsed in same_size:
            try:
                by_hash[_hash(directory, parsed.name, cache)].append(parsed)
            except OSError as exc:
                errors.append(f"{directory / parsed.name}: {exc}")
                unresolved = True
        clusters = {h: sorted(ps, key=rank) for h, ps in by_hash.items()}
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
    return found, removed, unresolved, review


def find_series_duplicates(
    directory: Path,
    members: list[Parsed],
    sizes: dict[str, int],
    errors: list[str],
    cache: dict[str, str],
) -> tuple[list[Found], list[dict[str, Any]]]:
    """页码序列：只在同一页码内去重；不同页码的同内容文件只在补零与不补零两套整套重复时移走不补零的一套。"""
    pages: dict[int | None, list[Parsed]] = defaultdict(list)
    for parsed in members:
        pages[parsed.page].append(parsed)
    found: list[Found] = []
    review: list[dict[str, Any]] = []
    for same_page in pages.values():
        if len(same_page) >= 2:
            page_found, _, _, page_review = find_duplicates(
                directory, same_page, sizes, Parsed.series_rank, errors, cache
            )
            found += page_found
            review += page_review
    removed = {p.name for _, _, remove, _ in found for p, _, _ in remove}
    left = [p for p in members if p.numbers and p.name not in removed]
    padded = [p for p in left if p.padded]
    plain = [p for p in left if not p.padded]
    if not padded or not plain:
        return found, review
    plain_sizes = {sizes[p.name] for p in plain}
    by_digest: dict[str, list[Parsed]] = defaultdict(list)
    for parsed in padded:
        if sizes[parsed.name] in plain_sizes:
            try:
                by_digest[_hash(directory, parsed.name, cache)].append(parsed)
            except OSError as exc:
                errors.append(f"{directory / parsed.name}: {exc}")
    padded_sizes = {sizes[p.name] for ps in by_digest.values() for p in ps}
    matches: dict[str, list[Parsed]] = defaultdict(list)
    for parsed in plain:
        if sizes[parsed.name] not in padded_sizes:
            continue
        try:
            digest = _hash(directory, parsed.name, cache)
        except OSError as exc:
            errors.append(f"{directory / parsed.name}: {exc}")
            continue
        if digest in by_digest:
            matches[digest].append(parsed)
    covered = sum(len(by_digest[h]) for h in matches)
    if covered < WHOLE_SET_RATIO * len(padded):
        return found, review
    for digest, duplicates in matches.items():
        keep = min(by_digest[digest], key=Parsed.series_rank)
        remove = [(p, digest, False) for p in sorted(duplicates, key=Parsed.series_rank)]
        found.append((keep, digest, remove, sizes[keep.name]))
        removed.update(p.name for p in duplicates)
    # 整套移走后，同页码里与被移走文件的冲突不再需要人工确认
    review = [r for r in review if sum(f["name"] not in removed for f in r["files"]) >= 2]
    return found, review


def _group(
    directory: Path,
    keep: Parsed,
    digest: str | None,
    size: int,
    remove: list[tuple[Parsed, str, bool]],
    rename_to: str | None,
) -> dict[str, Any]:
    return {
        "keep": _entry(directory / keep.name, size, digest),
        "remove": [
            {**_entry(directory / p.name, size, h), "damaged": damaged} for p, h, damaged in remove
        ],
        "rename_to": rename_to,
        "match": "name",
    }


# ---------- 跨名称匹配：同一批图片以两种文件名各存一份 ----------


def _stem_ext(parsed: Parsed) -> tuple[str, str]:
    stem = parsed.name.rpartition(".")[0]
    return unicodedata.normalize("NFC", stem).casefold(), EXTENSIONS[parsed.ext.lower()]


def zero_pad_key(parsed: Parsed) -> tuple[str, str]:
    """各处数字去掉前导 0 后的名字：`0630_A_76.png` 与 `630_A_76.png` 相同。"""
    stem, ext = _stem_ext(parsed)
    return re.sub(r"\d+", lambda m: str(int(m[0])), stem), ext


LEADING_INDEX = re.compile(r"^(?P<index>\d+)[_ -](?P<rest>.+)$")


def index_key(parsed: Parsed) -> tuple[str, str] | None:
    """去掉开头流水号后的名字（`121_hellven_000.jpg` → `hellven_000`）；剩余部分须含字母。"""
    stem, ext = _stem_ext(parsed)
    match = LEADING_INDEX.match(stem)
    if match is None or not re.search(r"[^\W\d_]", match["rest"]):
        return None
    return match["rest"], ext


def _index_rank(parsed: Parsed) -> tuple[int, str]:
    match = LEADING_INDEX.match(parsed.name)
    return (int(match["index"]) if match else 0, parsed.name)


def template_key(parsed: Parsed) -> tuple[str, str]:
    """数字替换为 # 后的命名模板：`page (001).jpg` 与 `page (74).jpg` 同属 `page (#)`。"""
    stem, ext = _stem_ext(parsed)
    return re.sub(r"\d+", "#", stem), ext


def _digests(
    directory: Path, members: list[Parsed], errors: list[str], cache: dict[str, str]
) -> dict[str, str]:
    result: dict[str, str] = {}
    for parsed in members:
        try:
            result[parsed.name] = _hash(directory, parsed.name, cache)
        except OSError as exc:
            errors.append(f"{directory / parsed.name}: {exc}")
    return result


def match_by_key(
    directory: Path,
    members: list[Parsed],
    sizes: dict[str, int],
    key: Callable[[Parsed], Any],
    rank: Callable[[Parsed], Any],
    errors: list[str],
    cache: dict[str, str],
) -> list[Found]:
    """key 相同、体积与哈希都相同的文件构成重复组，按 rank 取保留项；不做损坏判定，也不产生人工确认项。"""
    buckets: dict[tuple[Any, int], list[Parsed]] = defaultdict(list)
    for parsed in members:
        k = key(parsed)
        if k is not None:
            buckets[(k, sizes[parsed.name])].append(parsed)
    found: list[Found] = []
    for (_, size), bucket in buckets.items():
        if len(bucket) < 2:
            continue
        digests = _digests(directory, bucket, errors, cache)
        by_hash: dict[str, list[Parsed]] = defaultdict(list)
        for parsed in bucket:
            if parsed.name in digests:
                by_hash[digests[parsed.name]].append(parsed)
        for digest, same in by_hash.items():
            if len(same) >= 2:
                keep, *remove = sorted(same, key=rank)
                found.append((keep, digest, [(p, digest, False) for p in remove], size))
    return found


def _has_marker(parsed: Parsed) -> bool:
    strong = parse_name(parsed.name, weak=False)
    return strong is not None and bool(strong.numbers)


def find_whole_sets(
    directory: Path,
    members: list[Parsed],
    sizes: dict[str, int],
    gone: set[str],
    fixed: set[str],
    errors: list[str],
    cache: dict[str, str],
) -> list[Found]:
    """按命名模板分套；某套至少 WHOLE_SET_RATIO 的文件在数量相近的另一套里有同内容文件时，移走这些文件。

    members 是目录内全部图片。gone 是前面规则已移走的文件：它们在别处另有同内容文件，算作已覆盖，
    但不再作保留项；fixed 是前面规则的保留项，可以作保留项但不移走。
    """
    sets: dict[tuple[str, str], list[Parsed]] = defaultdict(list)
    for parsed in members:
        sets[template_key(parsed)].append(parsed)
    # 保留优先：不带副本标记的套、文件多的套
    order = sorted(
        (t for t, ps in sets.items() if len(ps) >= NAME_SET_MIN_FILES),
        key=lambda t: (any(_has_marker(p) for p in sets[t]), -len(sets[t]), t),
    )
    keepers: set[tuple[str, str]] = set()
    dropped: set[tuple[str, str]] = set()
    found: list[Found] = []
    for b_key in reversed(order):
        if b_key in keepers:
            continue
        b_set = sets[b_key]
        b_open = [p for p in b_set if p.name not in gone]
        for a_key in order:
            if a_key == b_key:
                break
            a_set = [p for p in sets[a_key] if p.name not in gone]
            if a_key in dropped or min(len(sets[a_key]), len(b_set)) < SET_SIZE_RATIO * max(
                len(sets[a_key]), len(b_set)
            ):
                continue
            b_sizes = {sizes[p.name] for p in b_open}
            a_digests = _digests(
                directory, [p for p in a_set if sizes[p.name] in b_sizes], errors, cache
            )
            a_sizes = {sizes[n] for n in a_digests}
            b_digests = _digests(
                directory, [p for p in b_open if sizes[p.name] in a_sizes], errors, cache
            )
            by_digest: dict[str, list[Parsed]] = defaultdict(list)
            for parsed in a_set:
                if parsed.name in a_digests:
                    by_digest[a_digests[parsed.name]].append(parsed)
            matched: dict[str, list[Parsed]] = defaultdict(list)
            for parsed in b_open:
                digest = b_digests.get(parsed.name)
                if digest in by_digest:
                    matched[digest].append(parsed)
            covered = len(b_set) - len(b_open) + sum(map(len, matched.values()))
            if covered < WHOLE_SET_RATIO * len(b_set):
                continue
            for digest, duplicates in matched.items():
                remove = sorted(
                    (p for p in duplicates if p.name not in fixed), key=lambda p: p.name
                )
                if remove:
                    keep = min(by_digest[digest], key=lambda p: p.name)
                    found.append(
                        (keep, digest, [(p, digest, False) for p in remove], sizes[keep.name])
                    )
            dropped.add(b_key)
            keepers.add(a_key)
            break
    return found


def find_cross_name(
    directory: Path,
    members: list[Parsed],
    sizes: dict[str, int],
    gone: set[str],
    fixed: set[str],
    errors: list[str],
    cache: dict[str, str],
) -> list[tuple[Parsed, str, list[tuple[Parsed, str, bool]], int, str]]:
    """名称组之外的重复：只差补零、只差开头流水号（须整套）、两套命名模板整套对应，依次匹配。

    members 是目录内全部图片；gone、fixed 是名称组规则移走的文件与保留（含改名）的文件。
    补零与流水号只在两者之外的文件里配对；每一步的结果并入 gone、fixed 供后一步使用。
    """
    result: list[tuple[Parsed, str, list[tuple[Parsed, str, bool]], int, str]] = []
    gone, fixed = set(gone), set(fixed)

    def take(found: list[Found], match: str) -> None:
        gone.update(p.name for f in found for p, _, _ in f[2])
        fixed.update(k.name for k, _, _, _ in found)
        result.extend((k, d, rm, s, match) for k, d, rm, s in found)

    def free() -> list[Parsed]:
        return [p for p in members if p.name not in gone and p.name not in fixed]

    take(
        match_by_key(
            directory, free(), sizes, zero_pad_key, lambda p: (-len(p.name), p.name), errors, cache
        ),
        "zero_pad",
    )
    indexed = match_by_key(directory, free(), sizes, index_key, _index_rank, errors, cache)
    if sum(len(rm) for _, _, rm, _ in indexed) >= INDEX_SET_RATIO * len(members):
        take(indexed, "index_prefix")
    take(find_whole_sets(directory, members, sizes, gone, fixed, errors, cache), "name_set")
    return result


def plan_directory(
    directory: Path, rel: str, errors: list[str], cache: dict[str, str] | None = None
) -> dict[str, Any] | None:
    names = [
        entry.name
        for entry in os.scandir(directory)
        if not entry.name.startswith(".") and entry.is_file(follow_symlinks=False)
    ]
    sizes: dict[str, int] = {}
    name_groups: dict[tuple[str, str], list[Parsed]] = defaultdict(list)
    for parsed in parse_directory(names):
        try:
            sizes[parsed.name] = (directory / parsed.name).stat().st_size
        except OSError as exc:
            errors.append(f"{directory / parsed.name}: {exc}")
            continue
        name_groups[parsed.key].append(parsed)

    cache = {} if cache is None else cache
    groups: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for members in name_groups.values():
        if len({p.page for p in members if p.numbers}) >= SERIES_MIN_PAGES:
            found, series_review = find_series_duplicates(directory, members, sizes, errors, cache)
            review += series_review
            groups += [_group(directory, k, d, s, rm, None) for k, d, rm, s in found]
            continue
        if len(members) == 1:
            lone = members[0]
            if lone.renamable and not os.path.lexists(directory / lone.original_name):
                groups.append(
                    _group(directory, lone, None, sizes[lone.name], [], lone.original_name)
                )
            continue
        found, removed, unresolved, group_review = find_duplicates(
            directory, members, sizes, Parsed.rank, errors, cache
        )
        review += group_review
        alone = len(members) - removed == 1 and not unresolved
        for keep, digest, remove, size in found:
            rename_to = None
            target = keep.original_name
            freed = any(p.name == target for p, _, _ in remove)  # 原名文件本身将被移走
            if alone and keep.renamable and (freed or not os.path.lexists(directory / target)):
                rename_to = target
            groups.append(_group(directory, keep, digest, size, remove, rename_to))
    gone = {r["name"] for g in groups for r in g["remove"]}
    fixed = {g["keep"]["name"] for g in groups}
    everything = [p for ps in name_groups.values() for p in ps]
    for keep, digest, remove, size, match in find_cross_name(
        directory, everything, sizes, gone, fixed, errors, cache
    ):
        groups.append({**_group(directory, keep, digest, size, remove, None), "match": match})
    if not groups and not review:
        return None
    groups.sort(key=lambda g: g["keep"]["name"])
    review.sort(key=lambda r: r["files"][0]["name"])
    return {"dir": rel, "groups": groups, "review": review}


# ---------- 目录级重复 ----------


@dataclass
class DirInfo:
    """一个目录直接包含的内容。leaf 为没有任何子目录；links 为含符号链接。"""

    path: Path
    rel: str
    images: dict[str, int]
    others: dict[str, int]
    leaf: bool
    links: bool


def scan_dir(directory: Path, rel: str, leaf: bool) -> DirInfo:
    images: dict[str, int] = {}
    others: dict[str, int] = {}
    links = False
    for entry in os.scandir(directory):
        if entry.name.startswith("."):
            continue
        if entry.is_symlink():
            links = True
        elif entry.is_file():
            target = images if parse_name(entry.name) is not None else others
            target[entry.name] = entry.stat().st_size
    return DirInfo(directory, rel, images, others, leaf, links)


def _dir_has_marker(name: str) -> bool:
    stripped = _strip(name, STRONG_MARKERS)
    return stripped is not None and stripped[1] < RENAME_NUMBER_LIMIT


def _parent(rel: str) -> str:
    return posixpath.dirname(rel) or "."


def _dir_rank(info: DirInfo, children: dict[str, list[str]]) -> tuple[int, int, bool, int, str]:
    """保留优先：图片多的；同样多时所在父目录子目录多的（更完整的合集，使两个合集之间方向一致），
    再优先目录名不带副本标记的、目录名更长的，最后按路径。"""
    name = info.path.name
    siblings = len(children[_parent(info.rel)]) if info.rel != "." else 0
    return (-len(info.images), -siblings, _dir_has_marker(name), -len(name), info.rel)


@dataclass
class Superset:
    """keep 目录的图片包含 info 目录的全部图片（按哈希）。mapping 为 info 中文件名 -> keep 中同内容文件名。"""

    keep: DirInfo
    equal: bool  # 两边图片内容集合相同
    named: bool  # info 的每个图片文件名在 keep 里原样存在且内容相同
    digests: dict[str, str]
    mapping: dict[str, str]


def _dir_digests(
    info: DirInfo, names: list[str], errors: list[str], cache: dict[str, str]
) -> dict[str, str] | None:
    result: dict[str, str] = {}
    for name in names:
        try:
            result[name] = _hash(info.path, name, cache)
        except OSError as exc:
            errors.append(f"{info.path / name}: {exc}")
            return None
    return result


def find_supersets(
    infos: list[DirInfo], errors: list[str], cache: dict[str, str]
) -> dict[str, list[Superset]]:
    """对每个有图片的目录，找出图片内容包含它全部图片的其他目录：先按体积求交集筛候选，再比哈希。"""
    by_size: dict[int, set[str]] = defaultdict(set)
    for info in infos:
        for size in info.images.values():
            by_size[size].add(info.rel)
    by_rel = {info.rel: info for info in infos}
    result: dict[str, list[Superset]] = defaultdict(list)
    for info in infos:
        if not info.images:
            continue
        sizes = set(info.images.values())
        candidates: set[str] | None = None
        for size in sorted(sizes, key=lambda s: len(by_size[s])):
            candidates = (
                by_size[size] - {info.rel} if candidates is None else candidates & by_size[size]
            )
            if not candidates:
                break
        if not candidates:
            continue
        own = _dir_digests(info, sorted(info.images), errors, cache)
        if own is None:
            continue
        own_set = set(own.values())
        for rel in sorted(candidates):
            keep = by_rel[rel]
            names = sorted(n for n, s in keep.images.items() if s in sizes)
            theirs = _dir_digests(keep, names, errors, cache)
            if theirs is None or not own_set <= set(theirs.values()):
                continue
            by_digest: dict[str, list[str]] = defaultdict(list)
            for name, digest in theirs.items():
                by_digest[digest].append(name)
            mapping = {
                name: name if theirs.get(name) == digest else by_digest[digest][0]
                for name, digest in own.items()
            }
            result[info.rel].append(
                Superset(
                    keep,
                    equal=len(names) == len(keep.images) and set(theirs.values()) == own_set,
                    named=all(mapping[n] == n for n in own),
                    digests=own,
                    mapping=mapping,
                )
            )
    return result


def _others_match(
    info: DirInfo, keep: DirInfo, errors: list[str], cache: dict[str, str]
) -> dict[str, str] | None:
    """info 的非图片文件在 keep 里都有同名同内容的文件时，返回各文件哈希。"""
    digests: dict[str, str] = {}
    for name, size in info.others.items():
        if keep.others.get(name) != size:
            return None
        try:
            digest = _hash(info.path, name, cache)
            if _hash(keep.path, name, cache) != digest:
                return None
        except OSError as exc:
            errors.append(f"{exc.filename}: {exc.strerror or exc}")
            return None
        digests[name] = digest
    return digests


def _pair_stats(mapping: dict[str, str]) -> dict[str, Any]:
    """供模型判断的文件对应概况：图片数、文件名原样相同的数量、几对改名样例。"""
    renamed = sorted((a, b) for a, b in mapping.items() if a != b)
    return {
        "images": len(mapping),
        "same_name": len(mapping) - len(renamed),
        "renamed_samples": [list(pair) for pair in renamed[:3]],
    }


# 同名子集要覆盖保留目录这么多的内容（按去重后的哈希），才算同一份东西的不完整副本；
# 占比低的多是单话与合集、独立作品与杂图包，移走会丢掉作品的独立目录
SUBSET_COVER_RATIO = 0.9


def _covers(superset: Superset, errors: list[str], cache: dict[str, str]) -> bool:
    keep = _dir_digests(superset.keep, sorted(superset.keep.images), errors, cache)
    if keep is None:
        return False
    return len(set(superset.digests.values())) >= SUBSET_COVER_RATIO * len(set(keep.values()))


def find_dir_duplicates(
    infos: list[DirInfo], all_dirs: list[str], errors: list[str], cache: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """目录级重复：按保留优先顺序逐个决定，目录的图片被已保留的目录完全包含、且它的文件名在保留目录里
    原样存在时，整目录移走；其余包含关系（含内容相同但文件名不同的）列入 dir_review，交模型判断。"""
    children: dict[str, list[str]] = defaultdict(list)
    for rel in all_dirs:
        if rel != ".":
            children[_parent(rel)].append(rel)
    supersets = find_supersets(infos, errors, cache)
    ordered = sorted((i for i in infos if i.images), key=lambda i: _dir_rank(i, children))
    position = {info.rel: index for index, info in enumerate(ordered)}
    kept: set[str] = set()
    removals: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for info in ordered:
        options = sorted(
            (s for s in supersets.get(info.rel, []) if s.keep.rel in kept),
            key=lambda s: position[s.keep.rel],
        )
        named = [s for s in options if s.named]
        auto = [s for s in named if s.equal or _covers(s, errors, cache)]
        chosen = (auto or named or options or [None])[0]
        if chosen is None:
            kept.add(info.rel)
            continue
        relation = "equal" if chosen.equal else "subset"
        reason = None
        others = None
        if named and not auto:
            reason = "同名子集只占保留目录一部分"
        elif not auto:
            reason = "内容相同但文件名不同" if chosen.equal else "文件名不同的子集"
        elif not info.leaf:
            reason = "含子目录"
        elif info.links:
            reason = "含符号链接"
        else:
            others = _others_match(info, chosen.keep, errors, cache)
            if others is None:
                reason = "非图片文件不一致"
        if reason is not None or others is None:
            kept.add(info.rel)
            review.append(
                {
                    "dir": info.rel,
                    "keep_dir": chosen.keep.rel,
                    "relation": relation,
                    "reason": reason,
                    **_pair_stats(chosen.mapping),
                }
            )
            continue
        removals.append(
            {
                "dir": info.rel,
                "keep_dir": chosen.keep.rel,
                "relation": relation,
                "files": [
                    {
                        "name": name,
                        "size": info.images[name],
                        "sha256": digest,
                        "keep_name": chosen.mapping[name],
                    }
                    for name, digest in sorted(chosen.digests.items())
                ],
                "others": [
                    {"name": name, "size": info.others[name], "sha256": digest, "keep_name": name}
                    for name, digest in sorted(others.items())
                ],
            }
        )
    # 移走的目录与保留目录不是兄弟、且父目录里还会留下其他子目录时，移走会让那个合集缺一部分，
    # 改为人工确认；降级后父目录多了留下的子目录，反复检查直到稳定
    while True:
        removed = {r["dir"] for r in removals}
        breaking = [
            r
            for r in removals
            if _parent(r["dir"]) != _parent(r["keep_dir"])
            and any(c not in removed for c in children[_parent(r["dir"])])
        ]
        if not breaking:
            break
        for r in breaking:
            removals.remove(r)
            review.append(
                {
                    "dir": r["dir"],
                    "keep_dir": r["keep_dir"],
                    "relation": r["relation"],
                    "reason": "会拆散所在合集",
                    **_pair_stats({f["name"]: f["keep_name"] for f in r["files"]}),
                }
            )
    removals.sort(key=lambda r: r["dir"])
    review.sort(key=lambda r: r["dir"])
    return removals, review


def find_composed(
    review: list[dict[str, Any]], infos: list[DirInfo], errors: list[str], cache: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """合集恰好由单章拼成：dir_review 中被同一保留目录包含的目录，去掉内容完全相同的重复单章后，
    至少两个、图片数之和等于合集图片数且哈希多重集合一致。重复单章优先舍弃与其他单章不同父目录的。"""
    by_rel = {info.rel: info for info in infos}
    members: dict[str, list[str]] = defaultdict(list)
    for item in review:
        members[item["keep_dir"]].append(item["dir"])

    def counted(rel: str) -> Counter[str] | None:
        info = by_rel[rel]
        digests = _dir_digests(info, sorted(info.images), errors, cache)
        return None if digests is None else Counter(digests.values())

    composed: dict[str, dict[str, Any]] = {}
    for keep, dirs in members.items():
        if len(dirs) < 2 or (whole := counted(keep)) is None:
            continue
        parents = Counter(_parent(d) for d in dirs)
        chapters: list[str] = []
        duplicates: list[str] = []
        seen: set[frozenset] = set()
        total: Counter[str] = Counter()
        for rel in sorted(dirs, key=lambda d: (-parents[_parent(d)], d)):
            part = counted(rel)
            if part is None:
                break
            key = frozenset(part.items())
            if key in seen:
                duplicates.append(rel)
                continue
            seen.add(key)
            chapters.append(rel)
            total += part
        else:
            if len(chapters) >= 2 and total == whole:
                composed[keep] = {"chapters": sorted(chapters), "duplicates": sorted(duplicates)}
    return composed


def is_program_dir(name: str, files: list[str]) -> bool:
    return name.lower().endswith(".app") or any(
        f.rpartition(".")[2].lower() in PROGRAM_EXTENSIONS for f in files if "." in f
    )


def build_plan(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    skipped: list[str] = []
    found_dirs: list[tuple[Path, str, bool]] = []

    def on_error(exc: OSError) -> None:
        errors.append(f"{exc.filename}: {exc.strerror or exc}")

    for current, subdirs, files in os.walk(root, onerror=on_error):
        directory = Path(current)
        rel = directory.relative_to(root).as_posix()
        leaf = not subdirs  # 含隐藏子目录与目录链接，整目录移走时它们会一起移走
        subdirs[:] = sorted(
            d for d in subdirs if not d.startswith(".") and not (directory / d).is_symlink()
        )
        if is_program_dir(directory.name, files):
            skipped.append(rel)
            subdirs[:] = []
            continue
        found_dirs.append((directory, rel, leaf))

    cache: dict[str, str] = {}
    infos: list[DirInfo] = []
    for directory, rel, leaf in found_dirs:
        try:
            infos.append(scan_dir(directory, rel, leaf))
        except OSError as exc:
            errors.append(f"{directory}: {exc}")
    all_dirs = [rel for _, rel, _ in found_dirs] + skipped
    dir_removals, dir_review = find_dir_duplicates(infos, all_dirs, errors, cache)
    removed_dirs = {r["dir"] for r in dir_removals}

    dirs: list[dict[str, Any]] = []
    for directory, rel, _ in found_dirs:
        if rel in removed_dirs:
            continue
        try:
            planned = plan_directory(directory, rel, errors, cache)
        except OSError as exc:
            errors.append(f"{directory}: {exc}")
            continue
        if planned is not None:
            dirs.append(planned)
    groups = [g for d in dirs for g in d["groups"]]
    removes = [r for g in groups for r in g["remove"]]
    cases = build_cases(dir_review, dirs, find_composed(dir_review, infos, errors, cache))
    return {
        "version": PLAN_VERSION,
        "root": str(root),
        "created": datetime.now().isoformat(timespec="seconds"),
        "scanned_dirs": len(found_dirs),
        "dir_removals": dir_removals,
        "dir_review": dir_review,
        "dirs": dirs,
        "cases": cases,
        "skipped_program_dirs": skipped,
        "errors": errors,
        "summary": {
            "dir_removals": len(dir_removals),
            "dir_remove_bytes": sum(
                f["size"] for r in dir_removals for f in r["files"] + r["others"]
            ),
            "dir_review": dict(sorted(Counter(r["reason"] for r in dir_review).items())),
            "groups": sum(1 for g in groups if g["remove"]),
            "remove_files": len(removes),
            "remove_bytes": sum(r["size"] for r in removes),
            "damaged_files": sum(1 for r in removes if r["damaged"]),
            "cross_name_files": sum(len(g["remove"]) for g in groups if g["match"] != "name"),
            "renames": sum(1 for g in groups if g["rename_to"]),
            "review_sets": sum(len(d["review"]) for d in dirs),
            "dir_cases": sum(1 for c in cases if c["kind"] == "dir"),
            "file_cases": sum(1 for c in cases if c["kind"] == "file"),
            "composed_cases": sum(1 for c in cases if "composed" in c),
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
    if summary["dir_removals"] or summary["dir_review"]:
        equal = sum(1 for r in plan["dir_removals"] if r["relation"] == "equal")
        print(
            f"目录级重复：整目录移入回收站 {summary['dir_removals']} 个"
            f"（{human_size(summary['dir_remove_bytes'])}；与保留目录内容相同 {equal} 个，"
            f"文件名原样包含在保留目录中的子集 {summary['dir_removals'] - equal} 个），"
            "移走后变空的上级目录一并删除。"
        )
        if summary["dir_review"]:
            reasons = "，".join(f"{k} {v} 个" for k, v in summary["dir_review"].items())
            print(f"  不自动处理的包含关系 {sum(summary['dir_review'].values())} 对（{reasons}）。")
    print(
        f"重复组 {summary['groups']} 个，待移入回收站 {summary['remove_files']} 个文件"
        f"（{human_size(summary['remove_bytes'])}，其中损坏副本 {summary['damaged_files']} 个），"
        f"改回原名 {summary['renames']} 个。"
    )
    if summary["cross_name_files"]:
        print(
            f"其中 {summary['cross_name_files']} 个按命名对应识别"
            "（只差补零、只差开头流水号或两套编号整套相同），与保留项文件名不同。"
        )
    per_top: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for removal in plan["dir_removals"]:
        per_top[_top(removal["dir"])][0] += 1
    for directory in plan["dirs"]:
        counts = per_top[_top(directory["dir"])]
        counts[1] += sum(len(g["remove"]) for g in directory["groups"])
        counts[2] += sum(1 for g in directory["groups"] if g["rename_to"])
    for top, (dir_count, removes, renames) in sorted(per_top.items()):
        print(f"  {top}：移走目录 {dir_count} 个，删除文件 {removes} 个，改名 {renames} 个")
    if plan["cases"]:
        print(
            f"交模型判断的案例 {len(plan['cases'])} 个（目录 {summary['dir_cases']} 个，"
            f"其中合集恰好由单章拼成 {summary['composed_cases']} 个；"
            f"同名同体积内容不同的文件 {summary['file_cases']} 个），apply 不处理，用 show 查看材料。"
        )
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


def _verify_dir(root: Path, removal: dict) -> list[str]:
    """目录内容须与计划一致（无新增文件、无子目录），保留目录里对应的文件仍在且内容未变。"""
    base, keep_base = root / removal["dir"], root / removal["keep_dir"]
    entries = removal["files"] + removal["others"]
    try:
        listing = list(os.scandir(base))
    except OSError as exc:
        return [f"{removal['dir']} 不可访问：{exc.strerror or exc}"]
    if any(e.is_dir(follow_symlinks=False) for e in listing):
        return [f"{removal['dir']} 出现了子目录"]
    if {e.name for e in listing if not e.name.startswith(".")} != {f["name"] for f in entries}:
        return [f"{removal['dir']} 文件清单已变化"]
    problems = [_verify(base / f["name"], f) for f in entries]
    problems += [_verify(keep_base / f["keep_name"], f) for f in entries]
    return [p for p in problems if p]


def _remove_empty_parents(root: Path, directory: Path) -> list[str]:
    removed: list[str] = []
    parent = directory.parent
    while parent != root and parent.is_relative_to(root):
        try:
            parent.rmdir()
        except OSError:
            break
        removed.append(str(parent))
        parent = parent.parent
    return removed


def apply_plan(plan: dict) -> dict[str, list]:
    root = Path(plan["root"])
    result: dict[str, list] = {
        "trashed_dirs": [],
        "removed_empty_dirs": [],
        "trashed": [],
        "renamed": [],
        "skipped": [],
        "failed": [],
    }
    # 先移整目录：保留目录里的对应文件此时仍在，复核才成立；文件级去重只移走保留目录内另有同内容的文件
    for removal in plan["dir_removals"]:
        base = root / removal["dir"]
        problems = _verify_dir(root, removal)
        if problems:
            result["skipped"].append({"path": str(base), "reason": "；".join(problems)})
            continue
        failures = trash_files([base])
        if failures:
            result["failed"] += [{"path": str(p), "error": e} for p, e in failures]
            continue
        size = sum(f["size"] for f in removal["files"] + removal["others"])
        result["trashed_dirs"].append({"path": str(base), "size": size})
        result["removed_empty_dirs"] += _remove_empty_parents(root, base)
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
    if result["trashed_dirs"] or result["removed_empty_dirs"]:
        dir_freed = sum(item["size"] for item in result["trashed_dirs"])
        print(
            f"整目录移入回收站 {len(result['trashed_dirs'])} 个（{human_size(dir_freed)}），"
            f"删除变空的上级目录 {len(result['removed_empty_dirs'])} 个。"
        )
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


# ---------- 清理非图片杂项 ----------

# 类别 -> 小写文件名后缀；txt 不在内（可能是作品的设定或简介）。
JUNK_SUFFIXES = {
    "未下载完的残缺文件": (".bc!", ".!qb"),
    "广告链接与网页": (".url", ".torrent", ".mht", ".mhtml", ".html", ".htm"),
    "下载站与电子书元数据": (".opf", ".nfo"),
    "文件夹图标": (".ico",),
}
JUNK_NAMES = {
    "desktop.ini": "文件夹图标",
    "comicinfo.xml": "下载站与电子书元数据",
    ".ehviewer": "看图软件与系统残留",
    ".thumb": "看图软件与系统残留",
}
APPLE_DOUBLE = b"\x00\x05\x16\x07"


def junk_kind(path: Path) -> str | None:
    name = path.name.lower()
    if name in JUNK_NAMES:
        return JUNK_NAMES[name]
    if name.endswith(".db") and "thumbs" in name:  # 含 复件 (1) Thumbs.db、Thumbs(1).db
        return "看图软件与系统残留"
    if name.startswith("._"):
        try:
            with path.open("rb") as handle:
                magic = handle.read(4)
        except OSError:
            return None
        return "看图软件与系统残留" if magic == APPLE_DOUBLE else None
    for kind, suffixes in JUNK_SUFFIXES.items():
        if name.endswith(suffixes):
            return kind
    return None


def find_junk(root: Path) -> dict[str, Any]:
    """找出非图片杂项；同时统计其余非图片文件的扩展名，供汇报。跳过隐藏目录、符号链接与软件目录。"""
    junk: list[dict[str, Any]] = []
    missing: list[str] = []
    others: Counter[str] = Counter()
    for dirpath, dirnames, filenames in os.walk(root):
        directory = Path(dirpath)
        dirnames[:] = sorted(
            d for d in dirnames if not d.startswith(".") and not (directory / d).is_symlink()
        )
        if directory != root and is_program_dir(directory.name, filenames):
            dirnames[:] = []
            continue
        for name in sorted(filenames):
            path = directory / name
            if path.is_symlink() or not path.is_file():
                continue
            kind = junk_kind(path)
            rel = str(path.relative_to(root))
            if kind:
                junk.append({"path": rel, "kind": kind, "size": path.stat().st_size})
                if (
                    kind == "未下载完的残缺文件"
                    and not (directory / name.rpartition(".")[0]).exists()
                ):
                    missing.append(rel)
            elif not name.startswith(".") and name.rpartition(".")[2].lower() not in EXTENSIONS:
                others[name.rpartition(".")[2].lower() if "." in name else "（无扩展名）"] += 1
    return {"junk": junk, "missing": missing, "others": dict(others.most_common())}


def print_junk(found: dict[str, Any]) -> None:
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for item in found["junk"]:
        by_kind[item["kind"]].append(item)
    total = sum(item["size"] for item in found["junk"])
    print(f"非图片杂项 {len(found['junk'])} 个（{human_size(total)}）：")
    for kind, items in by_kind.items():
        names = Counter(Path(i["path"]).name for i in items).most_common(3)
        print(f"  {kind} {len(items)} 个，如 {'，'.join(n for n, _ in names)}")
    if found["missing"]:
        print(
            f"其中 {len(found['missing'])} 个残缺文件没有下载完成的同名文件，移走后作品会缺这些页："
        )
        for rel in found["missing"]:
            print(f"  {rel}")
    if found["others"]:
        listed = "，".join(f"{ext} {n}" for ext, n in found["others"].items())
        print(f"不处理的其余非图片文件：{listed}")


def clean_junk(root: Path, found: dict[str, Any]) -> dict[str, list]:
    paths = [root / item["path"] for item in found["junk"]]
    failures = trash_files(paths) if paths else []
    failed = {path for path, _ in failures}
    removed: list[str] = []
    for path in paths:
        if path not in failed:
            removed += _remove_empty_parents(root, path)
    return {
        "trashed": [p for p in paths if p not in failed],
        "removed_empty_dirs": removed,
        "failed": [{"path": str(p), "error": e} for p, e in failures],
    }


# ---------- 交模型判断的案例 ----------


def build_cases(
    dir_review: list[dict], dirs: list[dict], composed: dict[str, dict] | None = None
) -> list[dict[str, Any]]:
    """把 dir_review 与文件级人工确认项整理成案例。由单章恰好拼成的合集，与它有关的包含关系合成一个
    案例；其余保留目录与被包含目录不在同一父目录时，同一对父目录之间的包含关系合成一个案例
    （两个合集之间的取舍要整体决定）。"""
    composed = composed or {}
    by_parents: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_whole: dict[str, list[dict]] = defaultdict(list)
    units: list[list[dict]] = []
    for item in dir_review:
        a, b = _parent(item["dir"]), _parent(item["keep_dir"])
        if item["keep_dir"] in composed:
            by_whole[item["keep_dir"]].append(item)
        elif a == b:
            units.append([item])
        else:
            by_parents[(min(a, b), max(a, b))].append(item)
    units += by_parents.values()
    units += by_whole.values()
    units.sort(key=lambda items: items[0]["dir"])
    cases: list[dict[str, Any]] = []
    for items in units:
        case = {"kind": "dir", "reasons": sorted({i["reason"] for i in items}), "pairs": items}
        whole = items[0]["keep_dir"]
        if whole in composed:
            case["composed"] = {"dir": whole, **composed[whole]}
        cases.append(case)
    cases += [{"kind": "file", "dir": d["dir"], **r} for d in dirs for r in d["review"]]
    for index, case in enumerate(cases, 1):
        case["id"] = f"c{index:03d}"
    return cases


NUMBER = re.compile(r"(\d+)")


def _natural(name: str) -> list[Any]:
    return [int(part) if part.isdecimal() else part for part in NUMBER.split(name.casefold())]


def _listing(path: Path) -> tuple[list[str], list[str], list[str]]:
    """按自然顺序（2 在 10 前）列出非隐藏的图片、其他文件与子目录。"""
    images, others, subdirs = [], [], []
    for entry in sorted(os.scandir(path), key=lambda e: _natural(e.name)):
        if entry.name.startswith("."):
            continue
        if entry.is_dir(follow_symlinks=False):
            subdirs.append(entry.name)
        elif parse_name(entry.name) is not None:
            images.append(entry.name)
        else:
            others.append(entry.name)
    return images, others, subdirs


def number_gaps(numbers: list[int], limit: int = 10) -> tuple[int, list[int]] | None:
    """编号缺口：(缺号个数, 前 limit 个缺号)。编号跨度远大于个数时（文件名里的作品 ID、时间戳）
    不是页码序列，返回 None；只沿相邻编号逐段计算，不展开整个区间。"""
    unique = sorted(set(numbers))
    if not unique or unique[-1] - unique[0] + 1 > 2 * len(unique) + 10:
        return None
    count = unique[-1] - unique[0] + 1 - len(unique)
    shown: list[int] = []
    for low, high in zip(unique, unique[1:], strict=False):
        shown += range(low + 1, min(high, low + 1 + limit - len(shown)))
        if len(shown) >= limit:
            break
    return count, shown


def describe_dir(root: Path, rel: str, indent: str = "  ") -> list[str]:
    """一个目录的判断材料：图片数与体积、命名模板、首尾样例、主模板缺号、其他文件与子目录。"""
    path = root / rel
    try:
        images, others, subdirs = _listing(path)
        size = sum((path / n).stat().st_size for n in images)
    except OSError as exc:
        return [f"{indent}{rel}/ 不可访问：{exc.strerror or exc}"]
    lines = [
        f"{indent}{rel}/  图片 {len(images)} 张（{human_size(size)}），子目录 {len(subdirs)} 个"
    ]
    templates = Counter(NUMBER.sub("#", n) for n in images)
    if templates:
        lines.append(
            f"{indent}  命名："
            + "；".join(f"{t} ×{c}" for t, c in templates.most_common(4))
            + ("；…" if len(templates) > 4 else "")
        )
        sample = images if len(images) <= 6 else [*images[:3], "…", *images[-3:]]
        lines.append(f"{indent}  样例：{'，'.join(sample)}")
        main = templates.most_common(1)[0][0]
        numbers = sorted(
            int(NUMBER.findall(n)[-1])
            for n in images
            if NUMBER.sub("#", n) == main and NUMBER.search(n)
        )
        gaps = number_gaps(numbers)
        if gaps is not None and gaps[0]:
            count, shown = gaps
            more = "，…" if count > len(shown) else ""
            lines.append(
                f"{indent}  主模板编号 {numbers[0]}–{numbers[-1]}，缺 {count} 个："
                + "，".join(map(str, shown))
                + more
            )
    if others:
        lines.append(
            f"{indent}  其他文件：{'，'.join(others[:8])}{'，…' if len(others) > 8 else ''}"
        )
    if subdirs:
        lines.append(
            f"{indent}  子目录：{'，'.join(subdirs[:12])}{'，…' if len(subdirs) > 12 else ''}"
        )
    return lines


def _shown(path: str) -> str:
    """首尾有空白的路径加引号显示：` 01/` 混在缩进里看不出前导空格，照抄会写错决策路径。"""
    return (
        f"「{path}」"
        if path != path.strip() or any(p != p.strip() for p in path.split("/"))
        else path
    )


def _pair_line(item: dict, left: str | None = None) -> str:
    """跨父目录的案例给出 left（左侧父目录）：只写目录名，左侧固定为该父目录下的目录，
    被包含方在右侧时符号写作 ⊃。"""
    sign = "=" if item["relation"] == "equal" else "⊂"
    a, b = item["dir"], item["keep_dir"]
    if left is not None:
        if _parent(a) != left:
            a, b = b, a
            sign = "=" if sign == "=" else "⊃"
        a, b = posixpath.basename(a), posixpath.basename(b)
    line = (
        f"  {_shown(a)}/ {sign} {_shown(b)}/（{item['reason']}；{item['images']} 张，"
        f"文件名原样相同 {item['same_name']} 张"
    )
    if item["renamed_samples"]:
        line += "；改名如 " + "，".join(f"{a} → {b}" for a, b in item["renamed_samples"])
    return line + "）"


def describe_case(root: Path, case: dict) -> list[str]:
    if case["kind"] == "file":
        lines = [
            f"== {case['id']} 同名同体积、内容不同（{case['dir']}/，{human_size(case['size'])}）"
        ]
        data: dict[str, bytes] = {}
        for f in case["files"]:
            path = root / case["dir"] / f["name"]
            try:
                data[f["name"]] = path.read_bytes()
            except OSError as exc:
                lines.append(f"  {path} 不可访问：{exc.strerror or exc}")
                continue
            ext = EXTENSIONS.get(f["name"].rpartition(".")[2].lower(), "")
            damaged = looks_damaged(path, ext) if ext in COMPRESSED else None
            lines.append(
                f"  {path}（损坏特征：{'有' if damaged else '无' if damaged is False else '不判定'}）"
            )
        if len(data) == 2:
            a, b = data.values()
            diff = [i for i in range(len(a)) if a[i] != b[i]]
            if diff:
                lines.append(
                    f"  不同字节 {len(diff)} 个，位于 {diff[0]}–{diff[-1]}（文件长 {len(a)}）"
                )
        return lines
    pairs = case["pairs"]
    lines = [f"== {case['id']} 目录：{'、'.join(case['reasons'])}（{len(pairs)} 对）"]
    if "composed" in case:
        info = case["composed"]
        chapter_parents = sorted({_parent(c) for c in info["chapters"]})
        where = (
            f"都在 {_shown(chapter_parents[0])}/ 下"
            if len(chapter_parents) == 1
            else f"分散在 {len(chapter_parents)} 个父目录"
        )
        lines.append(
            f"  合集 {_shown(info['dir'])}/ 恰好由 {len(info['chapters'])} 个单章拼成"
            f"（图片数与哈希一致），单章{where}：{'，'.join(_shown(c) for c in info['chapters'])}"
        )
        if info["duplicates"]:
            lines.append(
                f"  与某个单章内容相同的重复单章：{'，'.join(map(_shown, info['duplicates']))}"
            )
    siblings = all(_parent(i["dir"]) == _parent(i["keep_dir"]) for i in pairs)
    if not siblings:
        first = pairs[0]
        lines.append(f"  左侧父目录：{_parent(first['dir'])}/")
        lines.append(f"  右侧父目录：{_parent(first['keep_dir'])}/")
    left = None if siblings else _parent(pairs[0]["dir"])
    lines += [_pair_line(item, left) for item in pairs]
    if len(pairs) <= 3:
        for rel in dict.fromkeys(r for item in pairs for r in (item["dir"], item["keep_dir"])):
            lines += describe_dir(root, rel)
    if siblings:
        parent = _parent(pairs[0]["dir"])
        if parent != ".":
            described = describe_dir(root, parent)
            lines.append("  所在父目录：" + described[0].strip())
            # 父目录是大分类（几百个作品）时列子目录没有帮助
            if len(_listing(root / parent)[2]) <= 40:
                lines += [line for line in described if "子目录：" in line]
        return lines
    # 跨父目录：两个合集之间的取舍，列出两边父目录及各自没有对应关系的子目录
    matched = {r for item in pairs for r in (item["dir"], item["keep_dir"])}
    for parent in sorted({_parent(r) for r in matched}):
        lines.append("  合集：" + describe_dir(root, parent)[0].strip())
        try:
            subdirs = _listing(root / parent)[2]
        except OSError:
            continue
        prefix = "" if parent == "." else parent + "/"
        unmatched = [d for d in subdirs if prefix + d not in matched]
        if unmatched and len(subdirs) <= 200:
            more = "，…" if len(unmatched) > 12 else ""
            lines.append(
                f"    无对应的子目录 {len(unmatched)} 个：{'，'.join(unmatched[:12])}{more}"
            )
    return lines


def _spread(items: list, count: int) -> list:
    """均匀取样，结果确定。"""
    if len(items) <= count:
        return items
    step = len(items) / count
    return [items[int(i * step)] for i in range(count)]


def describe_sample(root: Path, plan: dict, count: int) -> list[str]:
    """自动处理部分的抽查材料：目录级每种关系、文件级每种匹配方式各均匀取样，另列移走比例过半的目录。"""
    lines: list[str] = []
    for relation in ("equal", "subset"):
        items = [r for r in plan["dir_removals"] if r["relation"] == relation]
        if items:
            lines.append(f"== 目录级 {relation}（共 {len(items)} 个）")
            for r in _spread(items, count):
                lines.append(f"  {r['dir']}/ → 保留 {r['keep_dir']}/（{len(r['files'])} 张）")
    kinds: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for d in plan["dirs"]:
        for g in d["groups"]:
            if any(r["damaged"] for r in g["remove"]):
                kinds["damaged"].append((d["dir"], g))
            elif g["remove"]:
                kinds[g["match"]].append((d["dir"], g))
            else:
                kinds["rename_only"].append((d["dir"], g))
    for kind, items in sorted(kinds.items()):
        lines.append(f"== 文件级 {kind}（共 {len(items)} 组）")
        for rel, g in _spread(items, count):
            removes = "，".join(r["name"] for r in g["remove"]) or "—"
            rename = f"，改名为 {g['rename_to']}" if g["rename_to"] else ""
            lines.append(f"  {rel}/：保留 {g['keep']['name']}，移走 {removes}{rename}")
    heavy: list[str] = []
    for d in plan["dirs"]:
        removed = sum(len(g["remove"]) for g in d["groups"])
        try:
            total = len(_listing(root / d["dir"])[0])
        except OSError:
            continue
        if removed and removed * 2 > total:
            heavy.append(f"  {d['dir']}/：移走 {removed}/{total}")
    if heavy:
        lines.append(f"== 文件级移走超过一半图片的目录（{len(heavy)} 个）")
        lines += heavy
    return lines


# ---------- 执行模型的决策 ----------


def _inside(path: str, base: str) -> bool:
    return path == base or path.startswith(base + "/")


def _clean_rel(value: Any) -> str | None:
    if not isinstance(value, str) or not value or os.path.isabs(value):
        return None
    rel = posixpath.normpath(value)
    return None if rel in (".", "..") or rel.startswith("../") else rel


def _tree_files(root: Path, rel: str) -> tuple[dict[str, int], list[str]]:
    """rel（文件或目录）下的非隐藏普通文件 -> 体积；符号链接记为问题。隐藏文件与隐藏目录不比较。"""
    path = root / rel
    if path.is_symlink():
        return {}, [f"{rel} 是符号链接"]
    if path.is_file():
        return {rel: path.stat().st_size}, []
    files: dict[str, int] = {}
    problems: list[str] = []
    for current, subdirs, names in os.walk(path):
        base = Path(current).relative_to(root).as_posix()
        for d in list(subdirs):
            if (Path(current) / d).is_symlink():
                problems.append(f"{base}/{d} 是符号链接")
        subdirs[:] = [d for d in subdirs if not d.startswith(".")]
        for name in names:
            if name.startswith("."):
                continue
            full = Path(current) / name
            if full.is_symlink():
                problems.append(f"{base}/{name} 是符号链接")
            else:
                files[f"{base}/{name}"] = full.stat().st_size
    return files, problems


def check_case(root: Path, actions: list[dict], cache: dict[str, str]) -> list[str]:
    """执行前校验一个案例的全部操作：路径合法、移动不覆盖，且每个被移走的文件在 keep 路径下
    （含移动进 keep 的目录）有 SHA-256 相同的文件，keep 不能落在被移走的路径里。"""
    problems: list[str] = []
    moves = [a for a in actions if a.get("op") == "move"]
    trashes = [a for a in actions if a.get("op") == "trash"]
    for action in actions:
        if action.get("op") not in ("move", "trash", "trash_matching", "keep"):
            problems.append(f"未知操作 {action.get('op')!r}")
    for move in moves:
        src, dest = _clean_rel(move.get("src")), _clean_rel(move.get("dest"))
        if src is None or dest is None:
            problems.append(f"移动路径不合法：{move.get('src')!r} → {move.get('dest')!r}")
            continue
        move["src"], move["dest"] = src, dest
        if not (root / src).exists() or (root / src).is_symlink():
            problems.append(f"{src} 不存在或是符号链接")
        if not (root / dest).is_dir():
            problems.append(f"目标目录 {dest} 不存在")
        if os.path.lexists(root / dest / posixpath.basename(src)):
            problems.append(f"{dest}/{posixpath.basename(src)} 已存在")
        if _inside(dest, src):
            problems.append(f"不能把 {src} 移进它自己")
        if any(_inside(dest, _clean_rel(t.get("path")) or "") for t in trashes):
            problems.append(f"不能移进将被移走的 {dest}")
    for trash in trashes:
        path = _clean_rel(trash.get("path"))
        keeps = [_clean_rel(k) for k in trash.get("keep") or []]
        if path is None or not keeps or None in keeps:
            problems.append(f"移走项路径或 keep 不合法：{trash.get('path')!r}")
            continue
        trash["path"], trash["keep"] = path, keeps
        if not os.path.lexists(root / path):
            problems.append(f"{path} 不存在")
    if problems:
        return problems
    trashed = [t["path"] for t in trashes]
    moved = [m["src"] for m in moves]
    for trash in trashes:
        for keep in trash["keep"]:
            if any(_inside(keep, t) for t in trashed) and not any(_inside(keep, m) for m in moved):
                problems.append(f"保留路径 {keep} 在被移走的路径里")
            elif not (root / keep).exists():
                problems.append(f"保留路径 {keep} 不存在")
    if problems:
        return problems
    try:
        for trash in trashes:
            files, link_problems = _tree_files(root, trash["path"])
            problems += link_problems
            files = {f: s for f, s in files.items() if not any(_inside(f, m) for m in moved)}
            pool: dict[str, int] = {}
            sources = list(trash["keep"]) + [
                m["src"] for m in moves if any(_inside(m["dest"], k) for k in trash["keep"])
            ]
            for source in sources:
                found, link_problems = _tree_files(root, source)
                problems += link_problems
                pool.update(found)
            pool = {
                f: s
                for f, s in pool.items()
                if not any(_inside(f, t) for t in trashed) or any(_inside(f, m) for m in moved)
            }
            sizes = set(files.values())
            digests = {_hash(root, f, cache) for f, s in pool.items() if s in sizes}
            missing = [f for f, s in sorted(files.items()) if _hash(root, f, cache) not in digests]
            if missing:
                more = f" 等 {len(missing)} 个" if len(missing) > 3 else ""
                problems.append(
                    f"{trash['path']} 中 {'，'.join(missing[:3])}{more} 在保留路径下没有相同内容的文件"
                )
    except OSError as exc:
        problems.append(f"读取失败：{exc}")
    return problems


def expand_matching(root: Path, actions: list[dict], cache: dict[str, str]) -> list[str]:
    """把 trash_matching 展开为逐个文件的 trash：path 目录直接包含的非隐藏普通文件中，SHA-256 在 keep
    路径下出现过的都移走，keep 不变。展开后的 trash 照常校验。"""
    problems: list[str] = []
    for action in [a for a in actions if a.get("op") == "trash_matching"]:
        actions.remove(action)
        path = _clean_rel(action.get("path"))
        raw = action.get("keep") or []
        keeps = [k for k in map(_clean_rel, raw) if k is not None]
        if path is None or not keeps or len(keeps) != len(raw) or not (root / path).is_dir():
            problems.append(f"trash_matching 路径或 keep 不合法：{action.get('path')!r}")
            continue
        try:
            wanted: set[str] = set()
            for keep in keeps:
                found, link_problems = _tree_files(root, keep)
                problems += link_problems
                wanted |= {_hash(root, f, cache) for f in found}
            names = sorted(
                e.name
                for e in os.scandir(root / path)
                if e.is_file(follow_symlinks=False) and not e.name.startswith(".")
            )
            matched = [n for n in names if _hash(root, f"{path}/{n}", cache) in wanted]
        except OSError as exc:
            problems.append(f"读取失败：{exc}")
            continue
        if not matched:
            problems.append(f"{path} 中没有与保留路径相同内容的文件")
        actions += [
            {"case": action.get("case"), "op": "trash", "path": f"{path}/{n}", "keep": keeps}
            for n in matched
        ]
    return problems


def apply_decisions(decisions: dict, check_only: bool = False) -> dict[str, list]:
    root = Path(decisions["root"])
    result: dict[str, list] = {
        "done": [],
        "moved": [],
        "trashed": [],
        "removed_empty_dirs": [],
        "skipped": [],
        "failed": [],
    }
    by_case: dict[str, list[dict]] = defaultdict(list)
    for action in decisions["actions"]:
        by_case[str(action.get("case", ""))].append(action)
    cache: dict[str, str] = {}
    for case, actions in by_case.items():
        problems = expand_matching(root, actions, cache) or check_case(root, actions, cache)
        if problems:
            result["skipped"].append({"case": case, "reason": "；".join(problems)})
            continue
        if check_only:
            result["done"].append(case)
            for move in (a for a in actions if a["op"] == "move"):
                src = root / move["src"]
                result["moved"].append(
                    {"from": str(src), "to": str(root / move["dest"] / src.name)}
                )
            result["trashed"] += [str(root / a["path"]) for a in actions if a["op"] == "trash"]
            continue
        sources: list[Path] = []
        try:
            for move in (a for a in actions if a["op"] == "move"):
                src = root / move["src"]
                target = root / move["dest"] / src.name
                os.rename(src, target)
                sources.append(src)
                result["moved"].append({"from": str(src), "to": str(target)})
        except OSError as exc:
            result["failed"].append({"case": case, "error": f"移动失败：{exc}"})
            continue
        targets = [root / a["path"] for a in actions if a["op"] == "trash"]
        failures = trash_files(targets) if targets else []
        failed = {path for path, _ in failures}
        result["failed"] += [{"case": case, "error": f"{p}：{e}"} for p, e in failures]
        for target in targets:
            if target not in failed:
                result["trashed"].append(str(target))
                result["removed_empty_dirs"] += _remove_empty_parents(root, target)
        # 移走之后再清理移动源留下的空目录，避免先把待移走的父目录删掉
        for src in sources:
            result["removed_empty_dirs"] += _remove_empty_parents(root, src)
        if not failures:
            result["done"].append(case)
    return result


def print_decision_result(result: dict[str, list], check_only: bool = False) -> None:
    print(
        f"{'校验通过（未执行）' if check_only else '执行'}案例 {len(result['done'])} 个：移动 {len(result['moved'])} 项，"
        f"移入回收站 {len(result['trashed'])} 项，删除变空的上级目录 {len(result['removed_empty_dirs'])} 个。"
    )
    for item in result["moved"]:
        print(f"  移动 {item['from']} → {item['to']}")
    for item in result["trashed"]:
        print(f"  移走 {item}")
    if result["skipped"]:
        print(f"跳过 {len(result['skipped'])} 个案例（未做任何改动）：")
        for item in result["skipped"]:
            print(f"  {item['case']}：{item['reason']}")
    if result["failed"]:
        print(f"失败 {len(result['failed'])} 项：")
        for item in result["failed"]:
            print(f"  {item['case']}：{item['error']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="递归地按目录对图片库去重。")
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan", help="扫描并生成去重计划，不改动文件")
    plan_cmd.add_argument("root", type=Path, help="总目录")
    plan_cmd.add_argument("--out", type=Path, required=True, help="计划 JSON 的输出路径")
    show_cmd = commands.add_parser("show", help="输出抽查材料或案例的判断材料，不改动文件")
    show_cmd.add_argument("plan", type=Path, help="plan 生成的计划 JSON")
    show_cmd.add_argument("cases", nargs="*", help="案例编号，不给则输出全部案例")
    show_cmd.add_argument(
        "--sample", type=int, metavar="N", help="改为输出自动处理部分每类 N 个样本"
    )
    apply_cmd = commands.add_parser("apply", help="复核并执行计划：移入回收站、改回原名")
    apply_cmd.add_argument("plan", type=Path, help="plan 生成的计划 JSON")
    decide_cmd = commands.add_parser("apply-decisions", help="校验并执行模型写出的案例决策")
    decide_cmd.add_argument("decisions", type=Path, help="决策 JSON")
    decide_cmd.add_argument(
        "--check", action="store_true", help="只校验并列出将执行的操作与不满足的原因，不改动文件"
    )
    clean_cmd = commands.add_parser("clean", help="列出非图片杂项；加 --apply 移入回收站")
    clean_cmd.add_argument("root", type=Path, help="总目录")
    clean_cmd.add_argument("--apply", action="store_true", help="移入回收站并删除因此变空的目录")
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

    if args.command == "clean":
        root = Path(os.path.abspath(args.root))
        if not root.is_dir():
            print(f"错误：总目录不存在或不是目录：{root}", file=sys.stderr)
            return 2
        found = find_junk(root)
        print_junk(found)
        if not args.apply:
            return 0
        problem = check_platform()
        if problem:
            print(f"错误：{problem}", file=sys.stderr)
            return 2
        cleaned = clean_junk(root, found)
        print(
            f"移入回收站 {len(cleaned['trashed'])} 个，"
            f"删除变空的目录 {len(cleaned['removed_empty_dirs'])} 个。"
        )
        for item in cleaned["removed_empty_dirs"]:
            print(f"  删除空目录 {item}")
        for item in cleaned["failed"]:
            print(f"  失败 {item['path']}：{item['error']}")
        return 1 if cleaned["failed"] else 0

    source = args.decisions if args.command == "apply-decisions" else args.plan
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"错误：无法读取 {source}：{exc}", file=sys.stderr)
        return 2
    if args.command == "apply-decisions":
        if not isinstance(data.get("root"), str) or not isinstance(data.get("actions"), list):
            print("错误：决策文件须有 root 与 actions。", file=sys.stderr)
            return 2
    elif data.get("version") != PLAN_VERSION:
        print("错误：计划版本不符，请重新运行 plan。", file=sys.stderr)
        return 2
    if args.command == "show":
        root = Path(data["root"])
        if args.sample is not None:
            lines = describe_sample(root, data, args.sample)
        else:
            wanted = set(args.cases)
            unknown = wanted - {c["id"] for c in data["cases"]}
            if unknown:
                print(f"错误：没有这些案例：{'，'.join(sorted(unknown))}", file=sys.stderr)
                return 2
            lines = [
                line
                for case in data["cases"]
                if not wanted or case["id"] in wanted
                for line in describe_case(root, case)
            ]
        print("\n".join(lines))
        return 0
    if args.command == "apply-decisions" and args.check:
        checked = apply_decisions(data, check_only=True)
        print_decision_result(checked, check_only=True)
        return 0
    problem = check_platform()
    if problem:
        print(f"错误：{problem}", file=sys.stderr)
        return 2
    if args.command == "apply-decisions":
        decided = apply_decisions(data)
        print_decision_result(decided)
        return 1 if decided["failed"] else 0
    result = apply_plan(data)
    print_result(result)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
