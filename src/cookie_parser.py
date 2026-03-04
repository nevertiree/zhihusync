"""Cookie 解析器 - 支持多种格式导入.

支持的格式:
1. Playwright storage_state JSON
2. EditThisCookie JSON 数组
3. Netscape Cookie Format (TXT)
4. HTTP Header Cookie 格式
5. JSON 对象格式 {name: value}
6. 简单 key=value 格式
"""

import json
import re
from typing import Any

from loguru import logger


def parse_cookies(data: str, format_hint: str | None = None) -> dict[str, Any]:
    """解析多种格式的 Cookie 数据.

    Args:
        data: 原始 cookie 字符串
        format_hint: 格式提示 (json, txt, header, netscape, auto)

    Returns:
        Playwright storage_state 格式: {"cookies": [...], "origins": []}

    Raises:
        ValueError: 格式无法解析
    """
    data = data.strip()

    if not data:
        raise ValueError("Cookie 数据为空")

    # 根据格式提示或自动检测解析
    if format_hint == "json" or (format_hint is None and data.startswith(("{", "["))):
        return _parse_json_format(data)
    elif format_hint == "netscape" or (format_hint is None and _is_netscape_format(data)):
        return _parse_netscape_format(data)
    elif format_hint == "header" or (format_hint is None and data.lower().startswith("cookie:")):
        return _parse_header_format(data)
    elif format_hint == "keyvalue":
        return _parse_keyvalue_format(data)
    else:
        # 自动检测
        return _auto_detect_and_parse(data)


def _auto_detect_and_parse(data: str) -> dict[str, Any]:
    """自动检测格式并解析."""
    # 尝试 JSON
    if data.startswith(("{", "[")):
        try:
            return _parse_json_format(data)
        except ValueError:
            pass

    # 尝试 Netscape 格式
    if _is_netscape_format(data):
        try:
            return _parse_netscape_format(data)
        except ValueError:
            pass

    # 尝试 Header 格式
    if "=" in data and (";" in data or data.lower().startswith("cookie:")):
        try:
            return _parse_header_format(data)
        except ValueError:
            pass

    # 尝试 key=value 格式
    if "=" in data:
        try:
            return _parse_keyvalue_format(data)
        except ValueError:
            pass

    raise ValueError("无法自动识别 Cookie 格式，请手动选择格式")


def _is_netscape_format(data: str) -> bool:
    """检查是否为 Netscape cookie 格式."""
    lines = data.strip().split("\n")
    for line in lines[:5]:  # 检查前5行
        if line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:  # Netscape 格式至少有7个字段
            return True
    return False


def _parse_json_format(data: str) -> dict[str, Any]:
    """解析 JSON 格式 (Playwright / EditThisCookie)."""
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}")

    # EditThisCookie 格式: 数组
    if isinstance(parsed, list):
        cookies = [_normalize_cookie(c) for c in parsed if isinstance(c, dict)]
        return {"cookies": cookies, "origins": []}

    # Playwright storage_state 格式
    if isinstance(parsed, dict):
        if "cookies" in parsed:
            # 已经是 storage_state 格式
            cookies = [_normalize_cookie(c) for c in parsed.get("cookies", [])]
            return {"cookies": cookies, "origins": parsed.get("origins", [])}
        else:
            # 可能是单条 cookie 对象
            if "name" in parsed and "value" in parsed:
                return {"cookies": [_normalize_cookie(parsed)], "origins": []}
            # 可能是 {name: value} 简单格式
            cookies = [{"name": k, "value": str(v), "domain": ".zhihu.com", "path": "/"} for k, v in parsed.items()]
            return {"cookies": cookies, "origins": []}

    raise ValueError("不支持的 JSON 结构")


def _parse_netscape_format(data: str) -> dict[str, Any]:
    """解析 Netscape Cookie 格式 (TXT).

    格式: domain\tflag\tpath\tsecure\texpiration\tname\tvalue
    """
    cookies = []
    lines = data.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 7:
            # 尝试用空格分隔
            parts = line.split()

        if len(parts) >= 7:
            try:
                # Netscape 格式: domain flag path secure expiration name value
                domain = parts[0]
                # flag 通常是 TRUE/FALSE，表示是否允许子域名
                path = parts[2]
                secure = parts[3].upper() == "TRUE"
                expires = int(parts[4]) if parts[4].isdigit() else None
                name = parts[5]
                value = parts[6] if len(parts) > 6 else ""

                cookie = {
                    "name": name,
                    "value": value,
                    "domain": domain if domain.startswith(".") else f".{domain}",
                    "path": path,
                    "secure": secure,
                }
                if expires:
                    cookie["expires"] = expires

                cookies.append(cookie)
            except (ValueError, IndexError) as e:
                logger.warning(f"跳过无效的 Netscape cookie 行: {line[:50]}... ({e})")
                continue

    if not cookies:
        raise ValueError("Netscape 格式解析失败，未找到有效 cookie")

    return {"cookies": cookies, "origins": []}


def _parse_header_format(data: str) -> dict[str, Any]:
    """解析 HTTP Header Cookie 格式.

    格式: Cookie: name=value; name2=value2
    """
    # 移除 "Cookie:" 前缀
    if data.lower().startswith("cookie:"):
        data = data[7:].strip()

    cookies = []
    # 分割 cookie 对
    pairs = re.split(r";\s*", data)

    for pair in pairs:
        if not pair or "=" not in pair:
            continue

        # 处理 name=value 格式
        if "=" in pair:
            name, value = pair.split("=", 1)
            name = name.strip()
            value = value.strip()

            # 解码 URL 编码
            try:
                from urllib.parse import unquote

                value = unquote(value)
            except Exception:
                pass

            if name:
                cookies.append(
                    {
                        "name": name,
                        "value": value,
                        "domain": ".zhihu.com",
                        "path": "/",
                        "secure": True,
                    }
                )

    if not cookies:
        raise ValueError("Header 格式解析失败")

    return {"cookies": cookies, "origins": []}


def _parse_keyvalue_format(data: str) -> dict[str, Any]:
    """解析简单的 key=value 格式."""
    cookies = []

    # 尝试换行分隔
    if "\n" in data:
        pairs = data.strip().split("\n")
    else:
        # 尝试分号分隔
        pairs = data.strip().split(";")

    for pair in pairs:
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue

        name, value = pair.split("=", 1)
        name = name.strip()
        value = value.strip()

        if name:
            cookies.append(
                {
                    "name": name,
                    "value": value,
                    "domain": ".zhihu.com",
                    "path": "/",
                }
            )

    if not cookies:
        raise ValueError("key=value 格式解析失败")

    return {"cookies": cookies, "origins": []}


def _normalize_cookie(cookie: dict) -> dict:
    """标准化 cookie 对象，确保必要字段."""
    normalized = {
        "name": str(cookie.get("name", "")),
        "value": str(cookie.get("value", "")),
        "domain": str(cookie.get("domain", ".zhihu.com")),
        "path": str(cookie.get("path", "/")),
    }

    # 处理过期时间（支持 expires 或 expirationDate）
    expires = cookie.get("expires") or cookie.get("expirationDate")
    if expires:
        try:
            # EditThisCookie 可能使用浮点数
            expires_int = int(float(expires))
            normalized["expires"] = expires_int
        except (ValueError, TypeError):
            pass

    # httpOnly 和 secure
    if cookie.get("httpOnly"):
        normalized["httpOnly"] = True
    if cookie.get("secure"):
        normalized["secure"] = True

    # 处理 sameSite 值（转换 Firefox/EditThisCookie 格式到 Playwright 格式）
    same_site = cookie.get("sameSite")
    if same_site:
        same_site_map = {
            "strict": "Strict",
            "lax": "Lax",
            "none": "None",
            "no_restriction": "None",
        }
        normalized_val = same_site_map.get(str(same_site).lower(), same_site)
        # 只接受有效的值
        if normalized_val in ("Strict", "Lax", "None"):
            normalized["sameSite"] = normalized_val

    return normalized


def validate_zhihu_cookies(storage_state: dict) -> tuple[bool, str, list[str]]:
    """验证是否包含必要的知乎 Cookie.

    Returns:
        (是否有效, 提示消息, 缺失的关键cookie列表)
    """
    cookies = storage_state.get("cookies", [])
    cookie_names = {c.get("name", "").lower() for c in cookies}

    # 知乎关键 cookie
    essential = ["z_c0"]  # 必须
    recommended = ["_xsrf", "_zap", "d_c0", "__zse_ck"]  # 推荐

    missing_essential = [c for c in essential if c.lower() not in cookie_names]
    missing_recommended = [c for c in recommended if c.lower() not in cookie_names]

    if missing_essential:
        return False, f"缺少关键 Cookie: {', '.join(missing_essential)}", missing_essential

    if missing_recommended:
        return True, f"Cookie 已保存，但缺少推荐字段: {', '.join(missing_recommended)}", missing_recommended

    return True, "Cookie 验证通过", []


def convert_to_playwright_format(data: Any) -> dict[str, Any]:
    """将各种格式的 cookie 数据转换为 Playwright storage_state 格式."""
    if isinstance(data, str):
        return parse_cookies(data)
    elif isinstance(data, dict):
        if "cookies" in data:
            return data
        return {"cookies": [_normalize_cookie(data)], "origins": []}
    elif isinstance(data, list):
        return {"cookies": [_normalize_cookie(c) for c in data], "origins": []}
    else:
        raise ValueError(f"不支持的 cookie 数据类型: {type(data)}")
