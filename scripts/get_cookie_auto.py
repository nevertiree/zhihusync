"""自动获取知乎 Cookie - 使用 Playwright (无需手动复制粘贴).

使用方法:
    uv run python scripts/get_cookie_auto.py

脚本会:
1. 打开 Chrome 浏览器
2. 访问知乎
3. 如果未登录，提示你登录
4. 自动获取所有 Cookie（包括 httpOnly）
5. 直接发送到 zhihusync 服务器
"""

import json
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("❌ 需要安装 playwright")
    print("   运行: uv add playwright")
    sys.exit(1)


def get_zhihu_cookies():
    """使用 Playwright 获取知乎 Cookie."""
    print("=" * 60)
    print("知乎 Cookie 自动获取工具")
    print("=" * 60)

    with sync_playwright() as p:
        # 启动浏览器（使用用户数据目录，保持登录状态）
        print("\n启动浏览器...")
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],  # 显示浏览器窗口
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )

        page = context.new_page()

        # 隐藏 webdriver 标志
        page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """
        )

        try:
            # 访问知乎
            print("打开知乎...")
            page.goto("https://www.zhihu.com", wait_until="networkidle")

            # 检查是否已登录
            print("\n检查登录状态...")
            page.wait_for_timeout(2000)

            # 查找登录按钮或用户头像
            login_button = page.locator("text=登录").first
            user_menu = page.locator(".AppHeader-profile").first

            if login_button.is_visible() and not user_menu.is_visible():
                print("\n⚠️ 检测到未登录")
                print("=" * 60)
                print("请在浏览器中登录知乎")
                print("登录完成后，按回车键继续...")
                print("=" * 60)
                input()

                # 等待页面刷新
                page.wait_for_timeout(3000)

            # 获取所有 cookie
            print("\n获取 Cookie...")
            cookies = context.cookies("https://www.zhihu.com")

            if not cookies:
                print("❌ 未获取到任何 Cookie")
                return None

            print(f"✅ 获取到 {len(cookies)} 个 Cookie")

            # 检查关键 cookie
            cookie_names = [c["name"] for c in cookies]
            print(f"   Cookie 列表: {cookie_names}")

            if "z_c0" not in cookie_names:
                print("\n❌ 未找到关键 Cookie (z_c0)")
                print("   请确保已成功登录知乎")
                return None

            # 转换为 storage_state 格式
            storage_state = {"cookies": cookies, "origins": []}

            return storage_state

        finally:
            browser.close()


def save_and_send(storage_state):
    """保存到本地并发送到服务器."""
    # 保存到本地
    cookie_path = Path("data/meta/cookies.json")
    cookie_path.parent.mkdir(parents=True, exist_ok=True)

    with open(cookie_path, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, indent=2, ensure_ascii=False)

    cookie_count = len(storage_state["cookies"])
    print(f"\n✅ Cookie 已保存到: {cookie_path.absolute()}")
    print(f"   共 {cookie_count} 条 Cookie")

    # 发送到服务器
    print("\n发送到 zhihusync 服务器...")
    try:
        import requests

        response = requests.post(
            "http://localhost:6067/api/cookies",
            json={"cookies": json.dumps(storage_state), "format": "json"},
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 服务器响应: {result.get('message', '保存成功')}")
            return True
        else:
            error = response.json()
            print(f"❌ 服务器错误: {error.get('detail', '未知错误')}")
            return False

    except Exception as e:
        print(f"⚠️ 发送到服务器失败: {e}")
        print("   Cookie 已保存到本地，请手动粘贴到配置页面")
        return False


def main():
    """主函数."""
    storage_state = get_zhihu_cookies()

    if not storage_state:
        print("\n❌ 获取 Cookie 失败")
        sys.exit(1)

    success = save_and_send(storage_state)

    if success:
        print("\n" + "=" * 60)
        print("🎉 全部完成! Cookie 已自动保存到服务器")
        print("   现在可以直接使用 zhihusync 了！")
        print("=" * 60)
    else:
        print("\n⚠️ Cookie 已保存到本地，但服务器同步失败")


if __name__ == "__main__":
    main()
