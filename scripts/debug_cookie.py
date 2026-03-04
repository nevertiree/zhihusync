"""Selenium Cookie 调试脚本 - 自动获取知乎 Cookie.

使用方法:
1. 确保已安装依赖: pip install selenium webdriver-manager
2. 运行脚本: python scripts/debug_cookie.py
3. 脚本会打开 Chrome，请手动登录知乎
4. 登录后按回车，脚本会自动获取 Cookie 并发送到服务器
"""

import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


def get_zhihu_cookies_manual():
    """手动方式获取知乎 Cookie - 打开浏览器让用户登录."""
    print("=" * 60)
    print("知乎 Cookie 获取工具")
    print("=" * 60)

    # 配置 Chrome
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # 启动浏览器
    print("\n正在启动 Chrome...")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    # 隐藏 webdriver 标志
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    try:
        # 打开知乎
        print("打开知乎网站...")
        driver.get("https://www.zhihu.com")

        print("\n" + "=" * 60)
        print("请在浏览器中登录知乎")
        print("登录完成后，回到这里按回车键继续...")
        print("=" * 60)

        input("\n登录完成后按回车键继续...")

        # 等待一下确保 cookie 已设置
        time.sleep(2)

        # 获取所有 cookie
        cookies = driver.get_cookies()

        print(f"\n获取到 {len(cookies)} 个 Cookie")

        # 检查关键 cookie
        cookie_names = [c['name'] for c in cookies]
        print(f"Cookie 列表: {cookie_names}")

        if 'z_c0' not in cookie_names:
            print("\n❌ 警告: 未找到关键 Cookie (z_c0)")
            print("请确保已成功登录知乎")
            return None

        # 转换为 storage_state 格式
        storage_state = {
            "cookies": [
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c["domain"],
                    "path": c["path"],
                    "httpOnly": c.get("httpOnly", False),
                    "secure": c.get("secure", False),
                    **({"expires": int(c["expiry"])} if "expiry" in c else {}),
                    **({"sameSite": c["sameSite"]} if "sameSite" in c else {}),
                }
                for c in cookies
            ],
            "origins": []
        }

        print("\n✅ 成功获取 Cookie!")
        return storage_state

    except Exception as e:
        print(f"\n❌ 获取 Cookie 失败: {e}")
        return None
    finally:
        driver.quit()


def save_cookie_locally(storage_state: dict, filepath: str = "data/meta/cookies.json"):
    """保存 Cookie 到本地文件."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, indent=2, ensure_ascii=False)

    cookie_count = len(storage_state.get("cookies", []))
    print(f"\n✅ Cookie 已保存到: {path}")
    print(f"   共 {cookie_count} 条 Cookie")

    # 显示关键 cookie
    key_cookies = ["z_c0", "_xsrf", "_zap", "d_c0"]
    found = [c["name"] for c in storage_state.get("cookies", []) if c["name"] in key_cookies]
    print(f"   关键 Cookie: {found}")


def send_cookie_to_server(storage_state: dict, server_url: str = "http://localhost:6067"):
    """发送 Cookie 到 zhihusync 服务器."""
    try:
        import requests

        response = requests.post(
            f"{server_url}/api/cookies",
            json={
                "cookies": json.dumps(storage_state),
                "format": "json"
            },
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 服务器响应: {result.get('message', '保存成功')}")
            return True
        else:
            error = response.json()
            print(f"\n❌ 服务器返回错误: {error.get('detail', '未知错误')}")
            return False

    except Exception as e:
        print(f"\n❌ 发送到服务器失败: {e}")
        return False


def main():
    """主函数."""
    import sys

    # 获取 Cookie
    storage_state = get_zhihu_cookies_manual()

    if not storage_state:
        print("\n❌ 获取 Cookie 失败")
        sys.exit(1)

    # 保存到本地
    save_cookie_locally(storage_state)

    # 发送到服务器
    print("\n" + "=" * 60)
    print("正在发送到 zhihusync 服务器...")
    print("=" * 60)

    success = send_cookie_to_server(storage_state)

    if success:
        print("\n🎉 全部完成! Cookie 已保存到服务器")
    else:
        print("\n⚠️ Cookie 已保存到本地，但发送到服务器失败")
        print("   你可以手动复制 data/meta/cookies.json 的内容到配置页面")


if __name__ == "__main__":
    main()
