"""时区工具模块 - 统一处理北京时间.

该模块提供获取北京时间的方法，确保所有日志和数据库记录使用统一的时区。

Examples:
    >>> from timezone_utils import get_beijing_time, get_beijing_now
    >>> now = get_beijing_now()
    >>> print(now.strftime("%Y-%m-%d %H:%M:%S"))
"""

from datetime import datetime, timedelta, timezone

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


def get_beijing_now() -> datetime:
    """获取当前北京时间.

    Returns:
        datetime: 带北京时区信息的当前时间.

    Examples:
        >>> now = get_beijing_now()
        >>> print(now.strftime("%Y-%m-%d %H:%M:%S"))
    """
    return datetime.now(BEIJING_TZ)


def get_beijing_time(dt: datetime = None) -> datetime:
    """将时间转换为北京时间.

    Args:
        dt: 要转换的时间，默认为当前时间.

    Returns:
        datetime: 带北京时区的时间.

    Examples:
        >>> utc_time = datetime.now(timezone.utc)
        >>> bj_time = get_beijing_time(utc_time)
    """
    if dt is None:
        return get_beijing_now()

    # 如果已经有 timezone 信息，转换为北京时区
    if dt.tzinfo is not None:
        return dt.astimezone(BEIJING_TZ)

    # 如果没有 timezone 信息，假设是本地时间，添加北京时区
    return dt.replace(tzinfo=BEIJING_TZ)


def format_beijing_time(dt: datetime = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化北京时间为字符串.

    Args:
        dt: 要格式化的时间，默认为当前时间.
        fmt: 格式字符串.

    Returns:
        str: 格式化后的时间字符串.

    Examples:
        >>> print(format_beijing_time())
        2024-01-15 10:30:00
    """
    bj_time = get_beijing_time(dt)
    return bj_time.strftime(fmt)


def beijing_timestamp() -> float:
    """获取当前北京时间的时间戳.

    Returns:
        float: 时间戳（秒）.
    """
    return get_beijing_now().timestamp()
