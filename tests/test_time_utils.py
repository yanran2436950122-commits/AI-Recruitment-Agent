"""展示层时间格式化测试。"""

from datetime import datetime, timezone

from utils.time_utils import format_display_time


def test_utc_iso_string_to_asia_shanghai() -> None:
    """UTC ISO 字符串应转换为 Asia/Shanghai 展示时间。"""

    assert format_display_time("2026-06-06T12:03:56+00:00", "Asia/Shanghai") == "2026-06-06 20:03:56"


def test_z_suffix_to_asia_shanghai() -> None:
    """Z 后缀 UTC 字符串应转换为配置时区展示。"""

    assert format_display_time("2026-06-06T12:03:56Z", "Asia/Shanghai") == "2026-06-06 20:03:56"


def test_datetime_to_asia_shanghai() -> None:
    """datetime 对象应按展示时区格式化。"""

    value = datetime(2026, 6, 6, 12, 3, 56, tzinfo=timezone.utc)

    assert format_display_time(value, "Asia/Shanghai") == "2026-06-06 20:03:56"
