"""扫描文件、生成重命名方案、执行与撤销。"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from .timeparse import TimeInfo, has_date_only, is_chinese_date, parse

TARGET_FMT = "%Y%m%d_%H%M%S"
TARGET_EXAMPLE = "20170118_102952"

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".gif", ".bmp", ".webp",
    ".tif", ".tiff", ".heic", ".heif", ".avif", ".ico", ".svg",
    ".dng", ".cr2", ".cr3", ".nef", ".arw", ".rw2", ".orf", ".raf",
}
VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v", ".mpg", ".mpeg",
    ".3gp", ".ts", ".mts", ".m2ts", ".webm", ".rmvb", ".rm", ".vob", ".asf", ".f4v",
}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

# 已经是目标格式（允许末尾带 _1 / -2 这类去重序号）
STD_NAME_RE = re.compile(r"^\d{8}_\d{6}(?:[_-]\d{1,3})?$")
STD_NAME_EXACT_RE = re.compile(r"^\d{8}_\d{6}$")

STATUS_READY = "ready"
STATUS_STD = "std"
STATUS_NO_TIME = "notime"
STATUS_CN = "cn"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


@dataclass
class Item:
    path: Path
    status: str = STATUS_READY
    dt: datetime | None = None
    source: str = ""
    new_name: str = ""
    old_name: str = ""
    note: str = ""
    error: str = ""

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def display_old(self) -> str:
        return self.old_name or self.path.name

    @property
    def display_new(self) -> str:
        return self.new_name or "—"

    @property
    def ext(self) -> str:
        return self.path.suffix.lower()

    @property
    def is_image(self) -> bool:
        return self.ext in IMAGE_EXTS


def is_media(path: Path) -> bool:
    return path.suffix.lower() in MEDIA_EXTS


def collect(paths: Sequence[str], recursive: bool = True) -> list[Path]:
    """把文件/目录展开成媒体文件列表（去重、排除隐藏与临时文件）。"""
    found: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        if p.name.startswith((".", "~$")):
            return
        if not is_media(p):
            return
        try:
            key = str(p.resolve()).lower()
        except OSError:
            key = str(p).lower()
        if key in seen:
            return
        seen.add(key)
        found.append(p)

    for raw in paths:
        p = Path(raw)
        try:
            if p.is_dir():
                it: Iterator[Path] = p.rglob("*") if recursive else p.glob("*")
                for f in it:
                    try:
                        if f.is_file():
                            add(f)
                    except OSError:
                        continue
            elif p.is_file():
                add(p)
        except OSError:
            continue

    return found


def build_plan(files: Iterable[Path]) -> list[Item]:
    """为每个文件算出目标名与状态。"""
    items: list[Item] = []

    for f in files:
        item = Item(path=f)
        stem = f.stem

        if STD_NAME_RE.match(stem):
            item.status = STATUS_STD
            item.note = "已是标准格式"
            items.append(item)
            continue

        if is_chinese_date(stem):
            item.status = STATUS_CN
            item.note = "中文日期命名，保持原样"
            items.append(item)
            continue

        info: TimeInfo | None = parse(stem)
        if info is None:
            item.status = STATUS_NO_TIME
            item.note = "只有日期缺少时分秒" if has_date_only(stem) else "文件名中未发现时间信息"
            items.append(item)
            continue

        item.dt = info.dt
        item.source = info.label
        item.new_name = info.dt.strftime(TARGET_FMT) + f.suffix
        if item.new_name == f.name:
            item.status = STATUS_STD
            item.note = "已是标准格式"
        else:
            item.note = info.label
        items.append(item)

    _resolve_collisions(items)
    return items


def _resolve_collisions(items: list[Item]) -> None:
    """同目录同名时追加 _1 / _2 序号，并避开磁盘上已存在的文件。"""
    groups: dict[Path, list[Item]] = defaultdict(list)
    for it in items:
        groups[it.path.parent].append(it)

    for parent, group in groups.items():
        movers = {it.path.name.lower() for it in group if it.status == STATUS_READY}
        try:
            existing = {p.name.lower() for p in parent.iterdir()}
        except OSError:
            existing = set()
        taken = existing - movers

        ready = [i for i in group if i.status == STATUS_READY]
        ready.sort(key=lambda i: (i.dt, i.path.name.lower()))

        for it in ready:
            suffix = it.path.suffix
            base = it.dt.strftime(TARGET_FMT)
            candidate = base + suffix
            n = 1
            while candidate.lower() in taken:
                candidate = f"{base}_{n}{suffix}"
                n += 1
                if n > 999:
                    break
            it.new_name = candidate
            if n > 1:
                it.note = "同秒重名，已加序号"
            taken.add(candidate.lower())


def execute(items: Sequence[Item]) -> tuple[list[tuple[Path, Path]], list[str]]:
    """执行重命名，返回 (撤销记录, 错误信息列表)。"""
    records: list[tuple[Path, Path]] = []
    errors: list[str] = []

    for it in items:
        if it.status != STATUS_READY or not it.new_name:
            continue
        target = it.path.with_name(it.new_name)
        try:
            it.path.rename(target)
        except OSError as exc:
            it.status = STATUS_FAILED
            it.error = str(exc)
            errors.append(f"{it.path.name} → {it.new_name}：{exc}")
            continue
        it.old_name = it.path.name
        it.path = target
        it.status = STATUS_DONE
        records.append((target, target.with_name(it.old_name)))

    return records, errors


def undo(records: Sequence[tuple[Path, Path]]) -> tuple[int, list[str]]:
    """按相反顺序把文件改回原名。"""
    ok = 0
    problems: list[str] = []
    for current, original in reversed(list(records)):
        try:
            if not current.exists():
                problems.append(f"{current.name} 已不存在，跳过")
                continue
            if original.exists():
                problems.append(f"{original.name} 已存在，跳过")
                continue
            current.rename(original)
            ok += 1
        except OSError as exc:
            problems.append(f"{current.name}：{exc}")
    return ok, problems


def summarize(items: Sequence[Item]) -> dict[str, int]:
    counts = {
        STATUS_READY: 0, STATUS_STD: 0, STATUS_NO_TIME: 0, STATUS_CN: 0,
        STATUS_DONE: 0, STATUS_FAILED: 0,
    }
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1
    return counts
