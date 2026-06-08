"""时间展示工具，保持存储 UTC，仅在展示层转换时区。"""

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo


def format_display_time(value: Any, timezone_name: str = "Asia/Shanghai") -> str:
    """把 UTC ISO 字符串或 datetime 转换为指定展示时区的时间字符串。"""

    parsed = parse_utc_datetime(value)
    if not parsed:
        return str(value or "")
    try:
        display_tz = ZoneInfo(timezone_name or "Asia/Shanghai")
    except Exception:
        display_tz = ZoneInfo("Asia/Shanghai")
    return parsed.astimezone(display_tz).strftime("%Y-%m-%d %H:%M:%S")


def parse_utc_datetime(value: Any) -> datetime:
    """解析 UTC ISO 字符串、Z 后缀字符串或 datetime，并返回带 UTC 时区的 datetime。"""

    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
