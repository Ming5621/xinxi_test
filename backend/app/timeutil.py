"""UTC 时间存储与对外展示约定。

库内 DateTime 一律按「无时区的 UTC」写入；对外 JSON 序列化时附加 Z，
避免前端把 UTC 当成本地时间（中国教室会慢约 8 小时）。

Excel 等本地展示优先用 IANA 的 Asia/Shanghai。精简版 Windows 和没把
tzdata 打进包的程序没有这套时区数据，模块导入时 ZoneInfo 会抛
ZoneInfoNotFoundError，服务进程直接退出。找不到时改用固定 UTC+8
（1991 年以后的中国标准时间，没有夏令时）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Annotated, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import PlainSerializer

logger = logging.getLogger(__name__)

SHANGHAI_KEY = "Asia/Shanghai"
# 1991 年起 Asia/Shanghai 固定为 UTC+8，教室里的成绩和心跳都落在这段时间里。
SHANGHAI_OFFSET = timedelta(hours=8)


def load_display_tz() -> tzinfo:
    """中国标准时间。有时区库时用 ZoneInfo，否则用固定 UTC+8。"""
    try:
        return ZoneInfo(SHANGHAI_KEY)
    except ZoneInfoNotFoundError:
        logger.warning("未找到时区 %s，本地展示时间改用固定 UTC+8", SHANGHAI_KEY)
        return timezone(SHANGHAI_OFFSET, name=SHANGHAI_KEY)


DISPLAY_TZ = load_display_tz()


def utc_now() -> datetime:
    """返回 naive UTC，写入 SQLite DateTime 列。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def serialize_utc_datetime(value: datetime) -> str:
    """JSON 输出带 Z 的 ISO8601，供浏览器按本地时区展示。"""
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def format_local(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Excel / 日志等本地可读时间（Asia/Shanghai）。"""
    if not dt:
        return ""
    return ensure_utc(dt).astimezone(DISPLAY_TZ).strftime(fmt)


UtcDateTime = Annotated[
    datetime,
    PlainSerializer(serialize_utc_datetime, return_type=str, when_used="json"),
]
