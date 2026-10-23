"""UTC 时间存储与对外展示约定。

库内 DateTime 一律按「无时区的 UTC」写入；对外 JSON 序列化时附加 Z，
避免前端把 UTC 当成本地时间（中国教室会慢约 8 小时）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional
from zoneinfo import ZoneInfo

from pydantic import PlainSerializer

DISPLAY_TZ = ZoneInfo("Asia/Shanghai")


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
