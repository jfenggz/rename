"""从文件名中提取时间信息。

支持的写法（示例均可解析）：
    2017-01-18 10:29:52 / 2017.01.18 10.29.52 / 20170118_102952
    20170118102952（紧凑 14 位）
    mmexport1794065790035（13 位毫秒时间戳）
    wx_camera_1698765432（10 位秒时间戳）
    PXL_20210118_102952123（带毫秒尾巴）

注意：中文日期写法（2017年1月18日 10时29分52秒）不做处理，由调用方跳过。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

MIN_YEAR = 1990
MAX_YEAR = 2100

_LOCAL_TZ = datetime.now().astimezone().tzinfo

# 显式分隔的「日期 + 时间」：2017-01-18 10:29:52 / 2017.01.18 10.29.52
# 只认半角分隔符，中文日期写法由 is_chinese_date 单独识别并跳过
_RE_SEPARATED = re.compile(
    r"(?<!\d)"
    r"((?:19|20)\d{2})[-_./](\d{1,2})[-_./](\d{1,2})"
    r"[ _T\-]{0,3}"
    r"(\d{1,2})[-_.:：](\d{1,2})[-_.:：](\d{1,2})"
)

# 中文日期写法：2017年1月18日 / 1月18日 10时29分
_RE_CN_DATE = re.compile(
    r"(?:19|20)\d{2}\s*年"
    r"|\d{1,2}\s*月\s*\d{1,2}\s*[日号]"
    r"|\d{1,2}\s*时\s*\d{1,2}\s*分"
)

# 紧凑写法：20170118_102952 / 20170118102952 / 2024-01-01-12-00-00
_RE_COMPACT = re.compile(
    r"(?<!\d)((?:19|20)\d{2})([01]\d)([0-3]\d)[\-_. _]?"
    r"([0-2]\d)([0-5]\d)([0-5]\d)"
)

# 只有日期没有时间，用于给出更准确的提示
_RE_DATE_ONLY = re.compile(
    r"(?<!\d)((?:19|20)\d{2})[-_.年/]?([01]\d)[-_.月/]?([0-3]\d)(?!\d)"
)

# 时间戳：微秒 / 毫秒 / 秒
_RE_EPOCH_US = re.compile(r"(?<!\d)(\d{16})(?!\d)")
_RE_EPOCH_MS = re.compile(r"(?<!\d)(\d{13})(?!\d)")
_RE_EPOCH_S = re.compile(r"(?<!\d)(\d{10})(?!\d)")


@dataclass(frozen=True)
class TimeInfo:
    dt: datetime
    label: str  # 用于界面展示的来源说明


def _build(y, mo, d, h, mi, s) -> Optional[datetime]:
    try:
        y, mo, d, h, mi, s = int(y), int(mo), int(d), int(h), int(mi), int(s)
    except (TypeError, ValueError):
        return None
    if not (MIN_YEAR <= y <= MAX_YEAR):
        return None
    try:
        return datetime(y, mo, d, h, mi, s)
    except ValueError:
        return None


def _from_epoch(value: str, unit: str) -> Optional[datetime]:
    try:
        ts = float(value)
    except ValueError:
        return None
    if unit == "us":
        ts /= 1_000_000
    elif unit == "ms":
        ts /= 1_000
    try:
        dt = datetime.fromtimestamp(ts, tz=_LOCAL_TZ).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return None
    return dt if MIN_YEAR <= dt.year <= MAX_YEAR else None


def parse(stem: str) -> Optional[TimeInfo]:
    """从文件名（不含扩展名）中解析时间，找不到返回 None。"""
    if not stem:
        return None

    for m in _RE_SEPARATED.finditer(stem):
        dt = _build(*m.groups()[:6])
        if dt:
            return TimeInfo(dt, "文件名日期时间")

    for m in _RE_COMPACT.finditer(stem):
        dt = _build(*m.groups()[:6])
        if dt:
            return TimeInfo(dt, "紧凑日期时间")

    for m in _RE_EPOCH_US.finditer(stem):
        dt = _from_epoch(m.group(1), "us")
        if dt:
            return TimeInfo(dt, "微秒时间戳")

    for m in _RE_EPOCH_MS.finditer(stem):
        dt = _from_epoch(m.group(1), "ms")
        if dt:
            return TimeInfo(dt, "毫秒时间戳")

    for m in _RE_EPOCH_S.finditer(stem):
        dt = _from_epoch(m.group(1), "s")
        if dt:
            return TimeInfo(dt, "秒时间戳")

    return None


def is_chinese_date(stem: str) -> bool:
    """文件名里用的是中文日期写法（2017年1月18日、10时29分…），这类不动。"""
    return bool(stem) and _RE_CN_DATE.search(stem) is not None


def has_date_only(stem: str) -> bool:
    """文件名里只有日期、没有时分秒。"""
    for m in _RE_DATE_ONLY.finditer(stem):
        if _build(m.group(1), m.group(2), m.group(3), 0, 0, 0):
            return True
    return False
