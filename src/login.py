"""登录脚本 - 获取知乎 Cookie"""

import asyncio
import json
import os
import sys
from pathlib import Path

from loguru import logger
from playwright.async_api import async_playwright


def get_cookie_file_path() -> Path:
    """获取 Cookie 文件路径"""
    # 优先从环境变量获取
    data_dir = os.environ.get("ZHIHUSYNC_DATA_DIR", "data")
    meta_dir = Path(data_dir) / "meta"
    return meta_dir / "cookies.json"


async def login_zhihu():
    """交互式登录知乎."""
    logger.info("启动浏览器进行登录...")
    logger.info("请在浏览器中完成登录，登录成功后会自动保存 Cookie")

    async with async_playwright() as p:
        # 启动有界面的浏览器
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})

        page = await context.new_page()

        # 打开知乎登录页
        await page.goto("https://www.zhihu.com/signin")

        logger.info("等待登录完成...")

        try:
            # 等待跳转到首页或个人主页
            await page.wait_for_url(lambda url: "zhihu.com" in url and "signin" not in url, timeout=300000)  # 5分钟超时

            logger.info("登录成功!")

            # 等待页面加载完成
            await page.wait_for_load_state("networkidle")

            # 获取 storage state (包含 localStorage)
            storage_state = await context.storage_state()

            # 保存到文件
            cookie_file = get_cookie_file_path()
            cookie_file.parent.mkdir(parents=True, exist_ok=True)

            with open(cookie_file, "w", encoding="utf-8") as f:
                json.dump(storage_state, f, indent=2, ensure_ascii=False)

            logger.info(f"Cookie 已保存到: {cookie_file}")

            # 获取用户信息
            user_info = await page.evaluate(
                """
                () => {
                    // 尝试从页面获取用户信息
                    const meta = document.querySelector('meta[name="user-info"]');
                    if (meta) {
                        return JSON.parse(meta.content);
                    }
                    // 或者从全局变量获取
                    if (window.__INITIAL_STATE__) {
                        return window.__INITIAL_STATE__.entities?.users;
                    }
                    return null;
                }
            """
            )

            if user_info:
                logger.info(f"用户信息: {json.dumps(user_info, indent=2, ensure_ascii=False)}")

            # 尝试提取用户ID
            current_url = page.url
            if "/people/" in current_url:
                user_id = current_url.split("/people/")[1].split("/")[0]
                logger.info(f"检测到的用户ID: {user_id}")
                logger.info(f'请在 config.yaml 中设置: user_id: "{user_id}"')

        except Exception as e:
            logger.error(f"登录过程出错: {e}")

        finally:
            await browser.close()
            logger.info("浏览器已关闭")


def main():
    """主函数"""
    print("=" * 50)
    print("知乎登录工具")
    print("=" * 50)
    print()
    print("此工具将打开浏览器让你登录知乎")
    print("登录成功后，Cookie 将被保存供后续使用")
    print()

    try:
        asyncio.run(login_zhihu())
    except KeyboardInterrupt:
        print("\n用户取消登录")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"登录失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
