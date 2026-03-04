"""从现有 Chrome 配置提取知乎 Cookie.

使用方法:
    python scripts/extract_cookie_from_chrome.py

Windows 会自动查找 Chrome Cookie 数据库。
需要安装 pypiwin32: pip install pypiwin32
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


def get_chrome_cookie_path():
    """获取 Chrome Cookie 文件路径."""
    system = sys.platform

    if system == "win32":
        # Windows
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        path = Path(local_app_data) / "Google/Chrome/User Data/Default/Network/Cookies"
        if path.exists():
            return path
        # 旧版路径
        path = Path(local_app_data) / "Google/Chrome/User Data/Default/Cookies"
        if path.exists():
            return path
    elif system == "darwin":
        # macOS
        path = Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"
        if path.exists():
            return path
    else:
        # Linux
        path = Path.home() / ".config/google-chrome/Default/Cookies"
        if path.exists():
            return path

    return None


def get_edge_cookie_path():
    """获取 Edge Cookie 文件路径."""
    system = sys.platform

    if system == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        path = Path(local_app_data) / "Microsoft/Edge/User Data/Default/Network/Cookies"
        if path.exists():
            return path
        path = Path(local_app_data) / "Microsoft/Edge/User Data/Default/Cookies"
        if path.exists():
            return path

    return None


def decrypt_cookie_value(encrypted_value: bytes) -> str:
    """解密 Chrome Cookie 值 (Windows)."""
    try:
        import win32crypt
        decrypted = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)
        return decrypted[1].decode('utf-8')
    except Exception:
        # 如果解密失败，返回空字符串
        return ""


def extract_zhihu_cookies(cookie_db_path: Path) -> list:
    """从 Chrome Cookie 数据库提取知乎 Cookie."""

    # 复制到临时文件（避免锁定）
    temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(temp_fd)

    try:
        try:
            shutil.copy2(cookie_db_path, temp_path)
        except PermissionError:
            raise PermissionError(
                "Chrome 正在运行，无法读取 Cookie 数据库。\n"
                "请尝试以下方法之一:\n"
                "1. 关闭 Chrome 后重试\n"
                "2. 使用 scripts/debug_cookie.py (Selenium 方式)\n"
                "3. 手动从浏览器复制 Cookie"
            )

        conn = sqlite3.connect(temp_path)
        cursor = conn.cursor()

        # 查询知乎域名下的 cookies
        cursor.execute(
            "SELECT name, value, encrypted_value, host_key, path, is_httponly, is_secure, expires_utc "
            "FROM cookies WHERE host_key LIKE '%zhihu.com%'"
        )

        cookies = []
        for row in cursor.fetchall():
            name, value, encrypted_value, host_key, path, is_httponly, is_secure, expires_utc = row

            # 如果有加密值且值为空，尝试解密
            if not value and encrypted_value:
                value = decrypt_cookie_value(encrypted_value)

            cookie = {
                "name": name,
                "value": value or "",
                "domain": host_key,
                "path": path,
                "httpOnly": bool(is_httponly),
                "secure": bool(is_secure),
            }

            # 转换过期时间
            if expires_utc and expires_utc > 0:
                # Chrome 使用的是从 1601-01-01 开始的微秒数
                import datetime
                epoch = datetime.datetime(1601, 1, 1)
                expires = epoch + datetime.timedelta(microseconds=expires_utc)
                cookie["expires"] = int(expires.timestamp())

            cookies.append(cookie)

        conn.close()
        return cookies

    finally:
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except:
            pass


def main():
    """主函数."""
    print("=" * 60)
    print("知乎 Cookie 提取工具")
    print("=" * 60)

    # 尝试 Chrome
    cookie_path = get_chrome_cookie_path()
    browser_name = "Chrome"

    if not cookie_path:
        cookie_path = get_edge_cookie_path()
        browser_name = "Edge"

    if not cookie_path:
        print("\n❌ 未找到 Chrome 或 Edge 的 Cookie 数据库")
        print("   请确保浏览器已安装并登录过知乎")
        sys.exit(1)

    print(f"\n找到 {browser_name} Cookie 数据库:")
    print(f"   {cookie_path}")

    print("\n正在提取知乎 Cookie...")
    cookies = extract_zhihu_cookies(cookie_path)

    if not cookies:
        print("\n❌ 未找到知乎 Cookie")
        print("   请确保已在浏览器中登录知乎")
        sys.exit(1)

    print(f"\n✅ 找到 {len(cookies)} 个知乎 Cookie")
    print(f"   Cookie 名称: {[c['name'] for c in cookies]}")

    # 检查关键 cookie
    key_cookies = ["z_c0", "_xsrf", "_zap", "d_c0"]
    found_keys = [c["name"] for c in cookies if c["name"] in key_cookies]
    missing_keys = [k for k in key_cookies if k not in found_keys]

    print(f"\n关键 Cookie:")
    print(f"   ✅ 已找到: {found_keys}")
    if missing_keys:
        print(f"   ⚠️ 缺失: {missing_keys}")

    if "z_c0" not in found_keys:
        print("\n❌ 错误: 未找到关键 Cookie (z_c0)")
        print("   请确保已在浏览器中登录知乎")
        sys.exit(1)

    # 构建 storage_state
    storage_state = {
        "cookies": cookies,
        "origins": []
    }

    # 保存到文件
    output_path = Path("data/meta/cookies.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Cookie 已保存到: {output_path.absolute()}")

    # 发送到服务器
    print("\n正在发送到 zhihusync 服务器...")
    try:
        import requests

        response = requests.post(
            "http://localhost:6067/api/cookies",
            json={
                "cookies": json.dumps(storage_state),
                "format": "json"
            },
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 服务器响应: {result.get('message', '保存成功')}")
        else:
            error = response.json()
            print(f"❌ 服务器错误: {error.get('detail', '未知错误')}")
    except Exception as e:
        print(f"⚠️ 发送到服务器失败: {e}")
        print("   Cookie 已保存到本地，请手动导入到配置页面")


if __name__ == "__main__":
    main()
