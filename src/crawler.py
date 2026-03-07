"""爬虫模块 - 知乎内容抓取"""

import asyncio
import contextlib
import json
import random
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag
from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from db import DatabaseManager
from storage import StorageManager
from timezone_utils import get_beijing_now

# 随机 User-Agent 列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
]


class ZhihuCrawler:
    """知乎爬虫 - 支持多种浏览器"""

    # API 端点
    ZHIHU_BASE = "https://www.zhihu.com"
    API_BASE = "https://www.zhihu.com/api/v4"

    def __init__(
        self,
        user_id: str,
        db_manager: DatabaseManager,
        storage_manager: StorageManager,
        headless: bool = True,
        request_delay: float = 2.0,
        browser_type: str = "auto",
        max_comments: int = -1,
        stop_check_callback: Callable | None = None,
    ):
        """初始化爬虫.

        Args:
            user_id: 知乎用户ID.
            db_manager: 数据库管理器实例.
            storage_manager: 存储管理器实例.
            headless: 是否使用无头模式.
            request_delay: 请求间隔(秒).
            browser_type: 浏览器类型(auto/chromium/firefox/webkit/edge).
            max_comments: 每篇回答最大评论数，-1表示无限制.
            stop_check_callback: 停止检查回调函数，返回True表示需要停止.
        """
        self.user_id = user_id
        self.db = db_manager
        self.storage = storage_manager
        self.headless = headless
        self.request_delay = request_delay
        self.browser_type = browser_type  # auto, chromium, firefox, webkit, edge
        self.max_comments = max_comments
        self.stop_check_callback = stop_check_callback

        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

        # 统计
        self.new_items = 0
        self.updated_items = 0

        # 停止标志
        self._stopped = False

    def check_should_stop(self) -> bool:
        """检查是否应该停止处理.

        Returns:
            True 如果需要停止，False 继续处理
        """
        # 检查内部停止标志
        if self._stopped:
            return True

        # 检查外部回调（如果设置了）
        return bool(self.stop_check_callback and self.stop_check_callback())

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    def _get_available_browser(self, playwright):
        """获取可用的浏览器类型"""
        import os

        # 如果指定了浏览器类型，优先使用
        if self.browser_type != "auto":
            return self.browser_type

        # 检查环境变量
        env_browser = os.environ.get("PLAYWRIGHT_BROWSER", "")
        if env_browser in ["chromium", "firefox", "webkit", "edge"]:
            return env_browser

        # 尝试检测已安装的浏览器
        browsers = ["chromium", "firefox", "webkit"]
        for browser_name in browsers:
            try:
                getattr(playwright, browser_name)  # 验证浏览器可用
                logger.debug(f"检测到浏览器: {browser_name}")
                return browser_name
            except Exception:
                continue

        # 默认返回 chromium
        return "chromium"

    def _get_cookie_file_path(self) -> Path:
        """获取 Cookie 文件路径 - 基于 db_path 所在目录"""
        db_path = Path(self.db.db_path if hasattr(self.db, "db_path") else "/app/data/meta/zhihusync.db")
        meta_dir = db_path.parent
        return meta_dir / "cookies.json"

    async def init_browser(self):
        """初始化浏览器 - 支持多种浏览器"""
        logger.info(f"正在初始化浏览器 (类型: {self.browser_type})...")

        playwright = await async_playwright().start()
        self._playwright = playwright

        # 获取可用的浏览器
        browser_name = self._get_available_browser(playwright)
        logger.info(f"使用浏览器: {browser_name}")

        # 获取浏览器类型
        if browser_name == "edge":
            # Edge 使用 chromium 启动，但指定 executable_path
            browser_type = playwright.chromium
            edge_path = self._get_edge_path()
            launch_options = {
                "headless": self.headless,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                ],
            }
            if edge_path:
                launch_options["executable_path"] = edge_path
                logger.info(f"使用 Edge 浏览器: {edge_path}")
        else:
            browser_type = getattr(playwright, browser_name)
            launch_options = {
                "headless": self.headless,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                ],
            }

        try:
            self.browser = await browser_type.launch(**launch_options)  # type: ignore[arg-type]
        except Exception as e:
            logger.warning(f"启动 {browser_name} 失败: {e}，尝试其他浏览器...")
            # 尝试其他浏览器
            for fallback in ["chromium", "firefox", "webkit"]:
                if fallback != browser_name:
                    try:
                        browser_type = getattr(playwright, fallback)
                        self.browser = await browser_type.launch(**launch_options)
                        logger.info(f"使用备用浏览器: {fallback}")
                        break
                    except Exception as e2:
                        logger.warning(f"启动 {fallback} 也失败: {e2}")
                        continue
            else:
                raise Exception("没有可用的浏览器，请运行: playwright install")

        # 尝试加载已保存的 Cookie
        storage_state = None
        cookie_file = self._get_cookie_file_path()
        if cookie_file.exists():
            try:
                with open(cookie_file, encoding="utf-8") as f:
                    storage_state = json.load(f)
                logger.info("已加载保存的 Cookie")
            except Exception as e:
                logger.warning(f"加载 Cookie 失败: {e}")

        # 随机选择 User-Agent
        user_agent = random.choice(USER_AGENTS)

        context_options = {
            "user_agent": user_agent,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
            # 添加更多浏览器参数以绕过检测
            "permissions": ["geolocation"],
            "color_scheme": "light",
        }

        # 尝试使用 storage_state，如果失败则手动添加 cookie
        if storage_state:
            try:
                context_options["storage_state"] = storage_state
                self.context = await self.browser.new_context(**context_options)  # type: ignore[arg-type]
                logger.info("已使用 storage_state 创建 context")
            except Exception as e:
                logger.warning(f"使用 storage_state 失败: {e}，尝试手动添加 cookie")
                context_options.pop("storage_state", None)
                self.context = await self.browser.new_context(**context_options)  # type: ignore[arg-type]
                # 手动添加 cookie
                await self._add_cookies_manually(storage_state)
        else:
            self.context = await self.browser.new_context(**context_options)  # type: ignore[arg-type]

        self.page = await self.context.new_page()

        # 注入反检测脚本 - 绕过知乎的风控检测
        await self._inject_anti_detection()

        # 验证登录状态
        await self._verify_login_status()

        logger.info("浏览器初始化完成")

    async def _inject_anti_detection(self):
        """注入反检测脚本 - 隐藏自动化痕迹.

        知乎会检测以下特征来判断是否为爬虫：
        1. navigator.webdriver - 浏览器自动化标志
        2. navigator.plugins - 插件列表为空
        3. navigator.languages - 语言列表
        4. window.chrome - Chrome 对象
        5. Canvas/WebGL 指纹
        """
        try:
            if self.page is None:
                logger.warning("页面未初始化，无法注入反检测脚本")
                return
            # 注入脚本隐藏 webdriver 标志
            await self.page.add_init_script(
                """
                // 删除 webdriver 标志
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });

                // 添加 Chrome 对象（如果是 Chromium 浏览器）
                if (!window.chrome) {
                    window.chrome = {
                        runtime: {
                            OnInstalledReason: {CHROME_UPDATE: "chrome_update"},
                            OnRestartRequiredReason: {APP_UPDATE: "app_update"},
                            PlatformArch: {X86_64: "x86-64"},
                            PlatformNaclArch: {X86_64: "x86-64"},
                            PlatformOs: {WIN: "win"},
                            RequestUpdateCheckStatus: {NO_UPDATE: "no_update"},
                        }
                    };
                }

                // 添加插件列表
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        },
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer2",
                            length: 1,
                            name: "Chrome PDF Viewer"
                        }
                    ],
                });

                // 添加语言列表
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en'],
                });

                // 覆盖 permissions 查询
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications'
                        ? Promise.resolve({state: Notification.permission})
                        : originalQuery(parameters)
                );

                // 隐藏 Playwright 特定属性
                delete navigator.__proto__.webdriver;
            """
            )
            logger.debug("已注入反检测脚本")
        except Exception as e:
            logger.warning(f"注入反检测脚本失败: {e}")

    async def pre_check(self) -> dict:
        """采集前预检查 - 验证 Cookie 和存储有效性.

        Returns:
            检查结果: {
                "success": bool,
                "message": str,
                "checks": {
                    "cookie_exists": bool,
                    "cookie_valid": bool,
                    "storage_writable": bool,
                }
            }
        """
        logger.info("=" * 60)
        logger.info("🔍 开始采集前预检查...")
        logger.info("=" * 60)

        result: dict[str, Any] = {
            "success": False,
            "message": "",
            "checks": {
                "cookie_exists": False,
                "cookie_valid": False,
                "storage_writable": False,
            },
        }

        # 1. 检查 Cookie 文件是否存在
        cookie_file = self._get_cookie_file_path()
        if not cookie_file.exists():
            result["message"] = "❌ Cookie 文件不存在，请先配置 Cookie"
            logger.error(result["message"])
            return result

        try:
            with open(cookie_file, encoding="utf-8") as f:
                storage_state = json.load(f)
            cookies = storage_state.get("cookies", [])
            if not cookies:
                result["message"] = "❌ Cookie 文件为空，请重新配置"
                logger.error(result["message"])
                return result

            result["checks"]["cookie_exists"] = True
            logger.info(f"✅ Cookie 文件存在: {len(cookies)} 条 cookie")
        except Exception as e:
            result["message"] = f"❌ Cookie 文件读取失败: {e}"
            logger.error(result["message"])
            return result

        # 2. 检查 Cookie 有效性（调用知乎 API 验证）
        try:
            logger.info("🔍 正在验证 Cookie 有效性...")

            if self.page is None:
                result["message"] = "❌ 页面未初始化，无法验证 Cookie"
                logger.error(result["message"])
                return result

            # 直接访问知乎 API 验证登录状态（最可靠的方式）
            api_response = await self.page.evaluate(
                """
                async () => {
                    try {
                        const response = await fetch('https://www.zhihu.com/api/v4/me', {
                            method: 'GET',
                            credentials: 'include',
                            headers: {
                                'Accept': 'application/json'
                            }
                        });
                        const data = await response.json();
                        return {
                            success: response.ok && data.id && !data.error,
                            data: data,
                            status: response.status
                        };
                    } catch (e) {
                        return { success: false, error: e.toString() };
                    }
                }
            """
            )

            if api_response and api_response.get("success"):
                result["checks"]["cookie_valid"] = True
                user_data = api_response.get("data", {})
                user_name = user_data.get("name", "未知用户")
                logger.info(f"✅ Cookie 验证通过: {user_name}")
            else:
                error_info = api_response.get("data", {}) if api_response else {}
                error_msg = (
                    error_info.get("error", {}).get("message", "未知错误")
                    if isinstance(error_info, dict)
                    else "Cookie 无效"
                )
                result["message"] = "❌ Cookie 已失效，请更新 Cookie 后重试"
                if error_msg:
                    result["message"] += f" (错误: {error_msg})"
                logger.error(result["message"])
                return result

        except Exception as e:
            result["message"] = f"❌ Cookie 验证失败: {e}"
            logger.error(result["message"])
            return result

        # 3. 检查存储目录是否可写
        try:
            html_path = Path(self.storage.html_path)
            html_path.mkdir(parents=True, exist_ok=True)

            # 尝试写入测试文件
            test_file = html_path / ".write_test"
            test_file.write_text("test")
            test_file.unlink()

            result["checks"]["storage_writable"] = True
            logger.info(f"✅ 存储目录可写: {html_path}")
        except Exception as e:
            result["message"] = f"❌ 存储目录不可写: {e}"
            logger.error(result["message"])
            return result

        # 所有检查通过
        result["success"] = True
        result["message"] = "✅ 预检查全部通过，开始采集"
        logger.info("=" * 60)
        logger.info(result["message"])
        logger.info("=" * 60)

        return result

    async def _verify_login_status(self):
        """验证登录状态，如果失效则尝试刷新.

        知乎 Cookie 过期后会导致大量 403，需要及时检测。
        """
        try:
            if self.page is None:
                logger.warning("页面未初始化，无法验证登录状态")
                return

            # 访问知乎首页检查登录状态
            await self.page.goto("https://www.zhihu.com", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)

            # 检查是否有用户菜单（登录标志）
            has_user_menu = await self.page.query_selector(".AppHeader-profile") is not None

            if not has_user_menu:
                # 尝试检查 localStorage 中的用户信息
                user_info = await self.page.evaluate(
                    """
                    () => {
                        try {
                            const user = localStorage.getItem('$$user');
                            return user ? JSON.parse(user) : null;
                        } catch (e) {
                            return null;
                        }
                    }
                """
                )

                if not user_info:
                    logger.warning("⚠️ Cookie 可能已过期，建议更新 Cookie 以减少 403 错误")
                else:
                    logger.info(f"✅ 登录状态有效: {user_info.get('name', '未知用户')}")
            else:
                logger.info("✅ 登录状态验证通过")

        except Exception as e:
            logger.warning(f"验证登录状态失败: {e}")

    async def _add_cookies_manually(self, storage_state):
        """手动添加 cookie 到 context - 使用 Playwright API"""
        try:
            cookies = storage_state.get("cookies", [])
            if not cookies:
                return

            # 使用 Playwright 的 add_cookies API，支持 httpOnly
            assert self.context is not None  # noqa: S101

            # 转换 cookie 格式
            formatted_cookies = []
            for cookie in cookies:
                cookie_dict = {
                    "name": cookie.get("name", ""),
                    "value": cookie.get("value", ""),
                    "domain": cookie.get("domain", ".zhihu.com"),
                    "path": cookie.get("path", "/"),
                }
                # 添加可选属性
                if cookie.get("httpOnly"):
                    cookie_dict["httpOnly"] = True
                if cookie.get("secure"):
                    cookie_dict["secure"] = True
                # 修复 sameSite 值：Playwright 只接受 Strict/Lax/None
                same_site = cookie.get("sameSite")
                if same_site:
                    same_site_map = {
                        "strict": "Strict",
                        "lax": "Lax",
                        "none": "None",
                        "no_restriction": "None",
                    }
                    normalized = same_site_map.get(same_site.lower(), same_site)
                    if normalized in ("Strict", "Lax", "None"):
                        cookie_dict["sameSite"] = normalized
                # 处理过期时间（支持 expires 或 expirationDate）
                expires = cookie.get("expires") or cookie.get("expirationDate")
                if expires:
                    with contextlib.suppress(ValueError, TypeError):
                        cookie_dict["expires"] = int(float(expires))
                formatted_cookies.append(cookie_dict)

            await self.context.add_cookies(formatted_cookies)  # type: ignore[arg-type]
            logger.info(f"通过 Playwright API 设置了 {len(formatted_cookies)} 条 cookie")

            # 创建页面并访问知乎以验证 cookie
            self.page = await self.context.new_page()
            assert self.page is not None  # noqa: S101
            await self.page.goto("https://www.zhihu.com", wait_until="domcontentloaded", timeout=10000)

        except Exception as e:
            logger.warning(f"手动添加 cookie 失败: {e}")

    def _get_edge_path(self):
        """获取 Edge 浏览器路径"""
        import os
        import platform

        system = platform.system()
        possible_paths = []

        if system == "Windows":
            possible_paths = [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            ]
        elif system == "Darwin":  # macOS
            possible_paths = [
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "~/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            ]
        elif system == "Linux":
            possible_paths = [
                "/usr/bin/microsoft-edge",
                "/usr/bin/microsoft-edge-stable",
                "/opt/microsoft-edge/msedge",
                "/snap/bin/edge",
            ]

        # 检查环境变量
        edge_env = os.environ.get("EDGE_PATH", os.environ.get("PLAYWRIGHT_EDGE_PATH", ""))
        if edge_env:
            possible_paths.insert(0, edge_env)

        for path in possible_paths:
            path = os.path.expanduser(path)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        return None

    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, "_playwright"):
            await self._playwright.stop()
        logger.info("浏览器已关闭")

    async def test_login(self) -> dict:
        """测试 Cookie 是否有效 - 返回登录状态"""
        logger.info("测试登录状态...")

        try:
            assert self.page is not None  # noqa: S101
            # 访问知乎首页
            await self.page.goto(f"{self.ZHIHU_BASE}", timeout=30000)

            # 检查是否有登录态
            assert self.page is not None  # noqa: S101
            # 方法1: 检查 localStorage 中的用户信息
            user_info = await self.page.evaluate(
                """
                () => {
                    try {
                        const user = localStorage.getItem('$$user');
                        return user ? JSON.parse(user) : null;
                    } catch (e) {
                        return null;
                    }
                }
            """
            )

            # 方法2: 检查页面上的用户头像或昵称元素
            assert self.page is not None  # noqa: S101
            has_user_menu = (
                await self.page.locator("[data-za-detail-view-path-module='TopNavBar'] .AppHeader-profile").count() > 0
            )

            # 方法3: 尝试访问 API 获取当前用户信息
            assert self.page is not None  # noqa: S101
            me_response = None
            try:
                await self.page.goto(f"{self.API_BASE}/me", timeout=10000)
                content = await self.page.content()
                soup = BeautifulSoup(content, "lxml")
                text = soup.find("pre")
                if text:
                    me_response = json.loads(text.get_text())
            except Exception:
                pass

            # 判断登录状态
            is_logged_in = False
            user_name = None
            user_id = None

            if user_info and user_info.get("name"):
                is_logged_in = True
                user_name = user_info.get("name")
                user_id = user_info.get("url_token") or user_info.get("id")
            elif has_user_menu:
                is_logged_in = True
            elif me_response and not me_response.get("error"):
                is_logged_in = True
                user_name = me_response.get("name")
                user_id = me_response.get("url_token") or me_response.get("id")

            # 获取当前页面 URL 判断是否被重定向到登录页
            assert self.page is not None  # noqa: S101
            current_url = self.page.url
            if "signin" in current_url or "login" in current_url:
                is_logged_in = False

            result = {
                "success": is_logged_in,
                "is_logged_in": is_logged_in,
                "user_name": user_name,
                "user_id": user_id,
                "current_url": current_url,
                "message": "登录有效" if is_logged_in else "Cookie 已失效或过期，请重新登录",
            }

            if is_logged_in:
                logger.info(f"✅ 登录有效，用户: {user_name or '未知'}")
            else:
                logger.warning("❌ Cookie 已失效")

            return result

        except Exception as e:
            logger.exception(f"测试登录失败: {e}")
            return {
                "success": False,
                "is_logged_in": False,
                "message": f"测试失败: {str(e)}",
            }

    async def wait_for_login(self, timeout: int = 300):
        """等待用户登录"""
        logger.info("请登录知乎...")

        assert self.page is not None  # noqa: S101
        await self.page.goto(f"{self.ZHIHU_BASE}/signin")

        # 等待跳转到首页或个人主页
        try:
            assert self.page is not None  # noqa: S101
            await self.page.wait_for_url(lambda url: "zhihu.com" in url and "signin" not in url, timeout=timeout * 1000)
            logger.info("登录成功")
            return True
        except Exception:
            logger.error("登录超时")
            return False

    def _extract_json_from_page(self, text: str, pattern: str) -> dict | None:
        """从页面内容中提取 JSON 数据"""
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _parse_timestamp(self, ts: int | str) -> datetime:
        """解析时间戳"""
        ts_float = float(ts)
        if ts_float > 1e12:  # 毫秒时间戳
            ts_float = ts_float / 1000
        return datetime.fromtimestamp(ts_float)

    async def _delay(self, extra_delay: float = 0):
        """请求延迟 - 添加随机扰动模拟人类行为.

        Args:
            extra_delay: 额外延迟时间（应对403时增加）
        """
        # 基础延迟 + 随机扰动 (±30%)
        base_delay = self.request_delay + extra_delay
        random_delay = base_delay * (0.7 + random.random() * 0.6)

        # 偶尔增加更长的延迟（模拟用户阅读）
        if random.random() < 0.1:  # 10% 概率
            random_delay += random.uniform(1.0, 3.0)

        await asyncio.sleep(random_delay)

    async def _random_mouse_move(self):
        """随机鼠标移动 - 模拟人类行为.

        知乎会检测鼠标移动轨迹，完全静止或规律移动会被识别为机器人。
        """
        try:
            if not self.page:
                return

            # 随机移动鼠标到页面某个位置
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await self.page.mouse.move(x, y)

            # 偶尔滚动页面
            if random.random() < 0.3:  # 30% 概率
                scroll_y = random.randint(-200, 200)
                await self.page.evaluate(f"window.scrollBy(0, {scroll_y})")

        except Exception:
            pass  # 鼠标移动失败不影响主要功能

    async def _fetch_user_profile(self):
        """获取用户详细信息（名称、头像、签名）"""
        try:
            url = f"{self.ZHIHU_BASE}/people/{self.user_id}"
            logger.info(f"获取用户资料: {url}")

            await self._delay()
            assert self.page is not None  # noqa: S101
            await self.page.goto(url, wait_until="networkidle")
            await asyncio.sleep(1)

            # 提取用户信息
            assert self.page is not None  # noqa: S101
            user_info = await self.page.evaluate(
                """
                () => {
                    const result = {
                        name: null,
                        avatar_url: null,
                        headline: null
                    };

                    // 尝试多种选择器获取用户名
                    const nameSelectors = [
                        '.ProfileHeader-name',
                        '.UserNameCard-name',
                        '[data-za-detail-view-path-module="UserNameCard"]',
                        '.ProfileHeader-content .ProfileHeader-name',
                        '.Card .UserNameCard .UserNameCard-name'
                    ];

                    for (const selector of nameSelectors) {
                        const el = document.querySelector(selector);
                        if (el && el.textContent.trim()) {
                            result.name = el.textContent.trim();
                            break;
                        }
                    }

                    // 获取头像
                    const avatarSelectors = [
                        '.ProfileHeader-avatar img',
                        '.UserAvatar img',
                        '.Avatar img',
                        'img[alt="头像"]'
                    ];

                    for (const selector of avatarSelectors) {
                        const el = document.querySelector(selector);
                        if (el && el.src) {
                            result.avatar_url = el.src;
                            break;
                        }
                    }

                    // 获取个性签名
                    const headlineSelectors = [
                        '.ProfileHeader-headline',
                        '.UserNameCard-headline',
                        '.ProfileHeader-contentHeadline'
                    ];

                    for (const selector of headlineSelectors) {
                        const el = document.querySelector(selector);
                        if (el && el.textContent.trim()) {
                            result.headline = el.textContent.trim();
                            break;
                        }
                    }

                    return result;
                }
            """
            )

            if user_info.get("name") or user_info.get("avatar_url"):
                # 下载用户头像
                local_avatar = None
                if user_info.get("avatar_url"):
                    local_avatar = await self.storage.download_avatar(user_info.get("avatar_url"), self.user_id)

                self.db.update_user_info(
                    self.user_id,
                    name=user_info.get("name"),
                    avatar_url=local_avatar or user_info.get("avatar_url"),
                    headline=user_info.get("headline"),
                )
                logger.info(
                    f"获取到用户信息: name={user_info.get('name')}, "
                    f"headline={user_info.get('headline', '')[:30]}..."
                )
            else:
                logger.warning("未能获取到用户详细信息")

        except Exception as e:
            logger.warning(f"获取用户资料失败: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def fetch_likes(  # noqa: C901
        self,
        limit: int = 20,
        offset: int = 0,
        item_callback: Callable[[dict, int], Awaitable[None]] | None = None,
    ) -> list[dict]:
        """获取用户点赞列表 - 增量滚动模式，边滚动边解析边保存"""
        # 访问用户主页
        url = f"{self.ZHIHU_BASE}/people/{self.user_id}"
        logger.info(f"访问用户主页: {url}")

        await self._delay()
        assert self.page is not None  # noqa: S101
        await self.page.goto(url)

        # 等待页面加载
        try:
            assert self.page is not None  # noqa: S101
            await self.page.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(2)
        except Exception:
            pass

        # 增量滚动：分批滚动并解析，避免长时间等待
        # 处理无限制情况（limit < 0）
        no_limit = limit < 0
        target_count = "无限制" if no_limit else limit
        logger.info(f"开始增量滚动，目标数量: {target_count}...")
        all_activities: list[dict] = []
        processed_ids: set[str] = set()  # 跟踪已处理的activity ID
        last_count = 0
        no_new_content_count = 0
        max_no_new_content = 8 if no_limit else 5  # 全量模式下更多容错
        max_scroll_rounds = 1000 if no_limit else 50  # 全量模式下大幅增加滚动轮数
        scroll_round = 0
        total_processed = 0  # 实际处理计数

        # 全量模式下，先滚动到底部多次以加载更多历史内容
        if no_limit:
            logger.info("全量模式：先进行深度滚动加载历史内容...")
            for deep_scroll in range(10):
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                current_height = await self.page.evaluate("document.body.scrollHeight")
                logger.debug(f"深度滚动 {deep_scroll + 1}/10，页面高度: {current_height}px")

        # 循环条件：无限制时只检查滚动次数，有限制时检查目标数量
        last_height = 0
        while (no_limit or total_processed < limit) and scroll_round < max_scroll_rounds:
            scroll_round += 1
            logger.info(f"第 {scroll_round} 轮滚动...")

            # 每次滚动更多次，更激进的滚动策略
            assert self.page is not None  # noqa: S101
            for _ in range(5):  # 增加滚动次数到5次
                await self.page.evaluate(
                    """() => {
                        window.scrollBy(0, 1500);
                    }"""
                )
                # 随机延迟 1-3 秒，给页面足够时间加载
                sleep_time = random.uniform(1.0, 3.0)
                await asyncio.sleep(sleep_time)

            # 额外等待，确保内容加载完成
            await asyncio.sleep(2)

            # 获取当前页面高度，检查是否有新内容加载
            current_height = await self.page.evaluate("document.body.scrollHeight")
            logger.info(f"页面高度: {current_height}px (上次: {last_height}px)")

            # 获取当前页面内容并解析
            assert self.page is not None  # noqa: S101
            content = await self.page.content()
            activities = self._parse_activities_from_html(content)

            if not activities:
                no_new_content_count += 1
                if no_new_content_count >= max_no_new_content:
                    logger.info("没有解析到活动数据，停止滚动")
                    break
                continue

            # 检查是否有新内容
            has_new_activity = len(activities) > last_count
            has_new_height = current_height > last_height

            if has_new_activity:
                new_activities = activities[last_count:]  # 只获取新增的部分
                new_count = len(new_activities)
                logger.info(f"第 {scroll_round} 轮滚动后: 共 {len(activities)} 条 (+{new_count})")

                # 立即处理新增的activities（边滚动边保存）
                if item_callback:
                    for activity in new_activities:
                        activity_id = activity.get("id", "")
                        if activity_id and activity_id not in processed_ids:
                            try:
                                await item_callback(activity, total_processed)
                                processed_ids.add(activity_id)
                                total_processed += 1

                                # 检查是否已达到限制
                                if not no_limit and total_processed >= limit:
                                    logger.info(f"已达到目标数量 {limit}，停止滚动")
                                    break
                            except Exception as e:
                                logger.warning(f"处理activity失败: {e}")

                all_activities = activities
                last_count = len(activities)
                no_new_content_count = 0

                # 检查是否已达到限制
                if not no_limit and total_processed >= limit:
                    break
            elif has_new_height:
                # 页面高度增加了但没有新activity，可能是其他内容（如广告）
                logger.info(f"页面高度增加 ({last_height} -> {current_height}) 但没有新activity")
                no_new_content_count = 0  # 重置计数器，继续尝试
            else:
                no_new_content_count += 1
                logger.info(f"没有新内容，连续 {no_new_content_count} 次")

                # 尝试点击"查看更多"或"加载更多"按钮
                try:
                    assert self.page is not None  # noqa: S101
                    has_more = await self.page.evaluate(
                        """() => {
                            const selectors = [
                                '.ActivityItem-more',
                                '.ContentItem-more',
                                '.FeedItem-more',
                                '[data-za-detail-view-element_name="ViewMore"]',
                                '.Button:contains("查看更多")',
                                '.Button:contains("加载更多")',
                                'button:contains("查看更多")',
                                'button:contains("加载更多")'
                            ];
                            for (const sel of selectors) {
                                const btn = document.querySelector(sel);
                                if (btn && btn.offsetParent !== null) {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        }"""
                    )
                    if has_more:
                        logger.info("点击了'查看更多'按钮")
                        await asyncio.sleep(random.uniform(2.0, 4.0))
                        continue
                except Exception as e:
                    logger.debug(f"点击'查看更多'失败: {e}")

            # 更新页面高度记录
            last_height = current_height

            # 如果已经获取足够内容，提前退出
            if not no_limit and total_processed >= limit:
                logger.info(f"已获取足够内容 ({total_processed} 条)，停止滚动")
                break

            # 连续多次没有新内容，停止滚动
            if no_new_content_count >= max_no_new_content:
                logger.info(f"连续 {max_no_new_content} 次没有新内容，停止滚动")
                # 全量模式下尝试点击更多按钮后继续
                if no_limit and scroll_round < max_scroll_rounds:
                    logger.info("全量模式下继续尝试...")
                    try:
                        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(3)
                        # 检查是否有新内容
                        content = await self.page.content()
                        activities = self._parse_activities_from_html(content)
                        if len(activities) > last_count:
                            no_new_content_count = 0
                            continue
                    except Exception:
                        pass
                break

        if all_activities:
            logger.info(f"共解析到 {len(all_activities)} 条，实际处理 {total_processed} 条")
            # 返回所有activities（已通过回调处理过）
            return all_activities

        # 如果页面解析失败，尝试直接访问 API
        logger.info("页面解析失败，尝试直接访问 API...")
        api_url = f"{self.API_BASE}/members/{self.user_id}/activities?limit={limit}&offset={offset}"

        await self._delay()
        assert self.page is not None  # noqa: S101
        await self.page.goto(api_url)

        assert self.page is not None  # noqa: S101
        content = await self.page.content()
        soup = BeautifulSoup(content, "lxml")
        text_elem = soup.find("pre")

        if isinstance(text_elem, Tag):
            try:
                raw_text = text_elem.get_text()
                data = json.loads(raw_text)
                activities = data.get("data", [])
                paging = data.get("paging", {})
                logger.info(f"API 返回: {len(activities)} 条记录, total={paging.get('totals', 'unknown')}")
                return activities
            except json.JSONDecodeError as e:
                logger.warning(f"解析 API 响应失败: {e}")
        else:
            logger.warning("API 响应中没有找到 JSON 数据")

        return []

    def _extract_question_info_from_link(self, href: str) -> tuple[str, str]:
        """从链接提取问题ID和问题标题。

        Args:
            href: 回答链接，格式: //www.zhihu.com/question/{question_id}/answer/{answer_id}

        Returns:
            tuple: (question_id, question_title) 或 ("", "") 如果提取失败
        """
        question_id = ""
        if "/question/" in href:
            parts = href.split("/")
            for i, part in enumerate(parts):
                if part == "question" and i + 1 < len(parts):
                    question_id = parts[i + 1]
                    break
        return question_id, ""

    def _extract_author_info_from_html(self, author_info: Tag) -> dict:
        """从 AuthorInfo HTML 元素提取作者信息。

        Args:
            author_info: BeautifulSoup Tag 对象，包含作者信息

        Returns:
            dict: 包含 author_name, author_id, author_headline 的字典
        """
        author_name = ""
        author_id = ""
        author_headline = ""

        # 尝试多种选择器获取用户名
        name_selectors = [
            "a.UserLink-link",
            ".AuthorInfo-name",
            "[data-za-detail-view-element_name='UserName']",
        ]
        for selector in name_selectors:
            name_elem = author_info.select_one(selector)
            if name_elem and name_elem.get_text(strip=True):
                author_name = name_elem.get_text(strip=True)
                break

        # 获取用户ID
        name_elem = author_info.select_one("a.UserLink-link")
        if name_elem:
            href_val = name_elem.get("href", "")
            # 确保 href 是字符串类型
            if isinstance(href_val, str):
                # 提取用户ID，处理多种格式
                if "/people/" in href_val:
                    author_id = href_val.split("/people/")[-1].split("?")[0].strip("/")
                elif href_val.startswith("//"):
                    # 格式: //www.zhihu.com/people/xxx
                    author_id = href_val.split("/")[-1].split("?")[0]
                else:
                    author_id = href_val.strip("/")

        # 获取作者签名
        badge = author_info.find("div", class_="AuthorInfo-badgeText")
        if badge:
            author_headline = badge.get_text(strip=True)

        return {
            "name": author_name,
            "id": author_id,
            "headline": author_headline,
        }

    def _extract_voteup_count(self, actions: Tag) -> int:
        """从 ContentItem-actions 提取赞同数。

        Args:
            actions: BeautifulSoup Tag 对象，包含操作按钮

        Returns:
            int: 赞同数，默认为 0
        """
        vote_btn = actions.find("button", class_="VoteButton")
        if vote_btn:
            text = vote_btn.get_text(strip=True)
            numbers = re.findall(r"\d+", text)
            if numbers:
                return int(numbers[0])
        return 0

    def _extract_comment_count(self, actions: Tag) -> int:
        """从 ContentItem-actions 提取评论数。

        Args:
            actions: BeautifulSoup Tag 对象，包含操作按钮

        Returns:
            int: 评论数，默认为 0
        """
        comment_btn = actions.find("a", class_="ContentItem-action") or actions.find(
            "button", class_="ContentItem-action"
        )
        if comment_btn:
            text = comment_btn.get_text(strip=True)
            numbers = re.findall(r"\d+", text)
            if numbers:
                return int(numbers[0])
        return 0

    def _parse_time_to_timestamp(self, time_str: str) -> int:
        """解析时间字符串为毫秒时间戳。

        Args:
            time_str: 时间字符串，格式: %Y-%m-%d %H:%M

        Returns:
            int: 毫秒时间戳，解析失败返回 0
        """
        if not time_str:
            return 0
        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            return int(dt.timestamp() * 1000)
        except ValueError:
            return 0

    def _parse_single_activity(self, item: Tag) -> dict | None:
        """解析单个活动项。

        Args:
            item: BeautifulSoup Tag 对象，包含单个活动

        Returns:
            dict | None: 解析成功返回活动字典，失败返回 None
        """
        try:
            # 获取活动类型和时间
            meta_div = item.find("div", class_="ActivityItem-meta")
            if not isinstance(meta_div, Tag):
                return None

            meta_title = meta_div.find("span", class_="ActivityItem-metaTitle")
            if not isinstance(meta_title, Tag):
                return None
            time_span = meta_div.find_all("span")
            time_elem = time_span[-1] if len(time_span) > 1 else None
            created_time_str = time_elem.text if isinstance(time_elem, Tag) else ""

            # 只处理点赞活动
            if "赞同" not in meta_title.text:
                return None

            # 确定类型
            is_article = "文章" in meta_title.text
            verb = "MEMBER_VOTEUP_ARTICLE" if is_article else "MEMBER_VOTEUP_ANSWER"

            # 获取内容项
            content_item = item.find("div", class_="ContentItem")
            if not isinstance(content_item, Tag):
                return None

            # 提取 data-zop 属性
            data_zop_val = content_item.get("data-zop", "{}")
            data_zop = data_zop_val if isinstance(data_zop_val, str) else "{}"
            try:
                zop_data = json.loads(data_zop)
            except json.JSONDecodeError:
                zop_data = {}

            answer_id = str(zop_data.get("itemId", ""))

            # 从 title 中提取问题信息和链接
            title_elem = content_item.find("h2", class_="ContentItem-title")
            question_title = ""
            question_id = ""

            if isinstance(title_elem, Tag):
                link = title_elem.find("a")
                if isinstance(link, Tag):
                    question_title = link.get_text(strip=True)
                    href_val = link.get("href", "")
                    answer_href = href_val if isinstance(href_val, str) else ""
                    question_id, _ = self._extract_question_info_from_link(answer_href)

            # 获取作者信息
            author_info_elem = content_item.find("div", class_="AuthorInfo")
            author_data = {"name": "", "id": "", "headline": ""}
            if isinstance(author_info_elem, Tag):
                author_data = self._extract_author_info_from_html(author_info_elem)

            # 获取赞同数和评论数
            voteup_count = 0
            comment_count = 0
            actions = content_item.find("div", class_="ContentItem-actions")
            if isinstance(actions, Tag):
                voteup_count = self._extract_voteup_count(actions)
                comment_count = self._extract_comment_count(actions)

            # 解析时间字符串为时间戳
            created_time = self._parse_time_to_timestamp(created_time_str)

            # 构建完整的活动数据
            return {
                "id": answer_id,
                "verb": verb,
                "created_time": created_time,
                "target": {
                    "id": answer_id,
                    "type": "article" if is_article else "answer",
                    "question": {
                        "id": question_id,
                        "title": question_title,
                    },
                    "author": author_data,
                    "voteup_count": voteup_count,
                    "comment_count": comment_count,
                    "created_time": created_time,
                    "updated_time": created_time,
                },
            }

        except Exception as e:
            logger.debug(f"Failed to parse activity item: {e}")
            return None

    def _parse_activities_from_html(self, html: str) -> list[dict]:
        """从 HTML 页面中解析活动数据"""
        activities = []
        soup = BeautifulSoup(html, "lxml")

        # 查找所有活动项
        activity_items = soup.find_all("div", class_="List-item")
        logger.debug(f"Found {len(activity_items)} activity items in HTML")

        for item in activity_items:
            activity = self._parse_single_activity(item)
            if activity:
                activities.append(activity)
                question_title = activity["target"]["question"]["title"]
                logger.debug(f"Parsed activity: {activity['id']} - {question_title[:50]}")

        return activities

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def fetch_answer_detail(self, answer_id: str) -> dict | None:
        """获取回答详情"""
        url = f"{self.API_BASE}/answers/{answer_id}"
        params = {"include": "content,voteup_count,comment_count,created_time,updated_time,author"}

        full_url = f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        await self._delay()
        assert self.page is not None  # noqa: S101
        await self.page.goto(full_url)

        content = await self.page.content()
        soup = BeautifulSoup(content, "lxml")
        text_elem = soup.find("pre")

        if isinstance(text_elem, Tag):
            try:
                return json.loads(text_elem.get_text())
            except json.JSONDecodeError:
                pass

        return None

    async def fetch_answer_page(  # noqa: C901
        self, question_id: str, answer_id: str, max_retries: int = 3
    ) -> tuple[str | None, dict | None]:
        """获取回答页面 HTML，包含完整内容和样式，支持403重试.

        Args:
            question_id: 问题ID.
            answer_id: 回答ID.
            max_retries: 最大重试次数.

        Returns:
            Tuple[页面HTML内容, 错误信息字典]:
            - 成功: (html_content, None)
            - 404删除: ("__DELETED__", None)
            - 失败: (None, error_info)
            error_info 格式: {
                "error_type": str,  # "403"/"404"/"timeout"/"network_error"/"other"
                "error_message": str,
                "http_status": int | None,
                "retry_count": int,
            }
        """
        url = f"{self.ZHIHU_BASE}/question/{question_id}/answer/{answer_id}"
        last_error = None

        for attempt in range(max_retries):
            try:
                # 403重试时增加额外延迟
                extra_delay = attempt * 2  # 每次重试多等2秒
                await self._delay(extra_delay)

                # 随机鼠标移动模拟人类行为
                await self._random_mouse_move()

                assert self.page is not None  # noqa: S101
                response = await self.page.goto(url, wait_until="networkidle", timeout=30000)

                # 检测HTTP状态
                if response:
                    status = response.status
                    if status == 404:
                        logger.warning(f"页面404(可能已被删除): {url}")
                        return "__DELETED__", None
                    elif status == 403:
                        logger.warning(f"页面403(访问被拒绝): {url}, 尝试 {attempt + 1}/{max_retries}")
                        last_error = {
                            "error_type": "403",
                            "error_message": "HTTP 403 Forbidden - 访问被拒绝，可能是Cookie过期或触发风控",
                            "http_status": 403,
                            "retry_count": attempt + 1,
                        }
                        # 403时增加额外延迟后重试
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 5 + random.randint(1, 5)  # 随机6-20秒递增
                            logger.info(f"403错误，等待 {wait_time} 秒后重试...")
                            await asyncio.sleep(wait_time)

                            # 尝试重新验证登录状态并刷新
                            try:
                                # 访问首页重新建立会话
                                await self.page.goto(
                                    "https://www.zhihu.com", wait_until="domcontentloaded", timeout=15000
                                )
                                await asyncio.sleep(2)

                                # 检查是否需要重新登录
                                signin_link = await self.page.query_selector("a[href*='signin']")
                                if signin_link:
                                    logger.error("⚠️ 检测到未登录状态，Cookie 已过期，请更新 Cookie")
                                    # 不再继续重试，直接返回错误
                                    return None, {
                                        "error_type": "403_cookie_expired",
                                        "error_message": "Cookie 已过期，请更新 Cookie 后重试",
                                        "http_status": 403,
                                        "retry_count": attempt + 1,
                                    }

                                # 重新注入反检测脚本
                                await self._inject_anti_detection()

                            except Exception as e:
                                logger.debug(f"刷新会话失败: {e}")
                        continue
                    elif status >= 500:
                        logger.warning(f"服务器错误 {status}: {url}, 尝试 {attempt + 1}/{max_retries}")
                        last_error = {
                            "error_type": "server_error",
                            "error_message": f"HTTP {status} Server Error",
                            "http_status": status,
                            "retry_count": attempt + 1,
                        }
                        if attempt < max_retries - 1:
                            await asyncio.sleep((attempt + 1) * 3)
                        continue
                    elif status >= 400:
                        logger.warning(f"客户端错误 {status}: {url}")
                        # 4xx错误不重试（除403外）
                        return None, {
                            "error_type": str(status),
                            "error_message": f"HTTP {status} Client Error",
                            "http_status": status,
                            "retry_count": attempt + 1,
                        }

                # 检查页面内容是否包含404提示
                page_title = await self.page.title()
                if "404" in page_title or "不存在" in page_title:
                    logger.warning(f"页面标题表明404: {page_title}")
                    return "__DELETED__", None

                # 检查是否有内容区域
                content_exists = await self.page.query_selector(".RichContent, .QuestionAnswer-content")
                if not content_exists:
                    # 检查是否显示"内容不存在"等提示
                    error_selectors = [
                        "text=/内容不存在/",
                        "text=/页面不存在/",
                        "text=/404/",
                        ".ErrorPage",
                        ".NotFoundPage",
                    ]
                    not_found = False
                    for selector in error_selectors:
                        try:
                            error_el = await self.page.query_selector(selector)
                            if error_el:
                                logger.warning(f"页面显示不存在提示: {url}")
                                not_found = True
                                break
                        except Exception:
                            continue
                    if not_found:
                        return "__DELETED__", None

                # 等待内容加载
                try:
                    assert self.page is not None  # noqa: S101
                    await self.page.wait_for_selector(".RichContent", timeout=10000)
                except Exception:
                    logger.warning(f"等待内容超时: {answer_id}")

                # 点击所有"展开全文"按钮
                await self._expand_all_content()

                # 滚动页面以加载所有内容
                await self._scroll_page()

                # 获取页面内容和样式
                content = await self._get_page_with_styles()
                return content, None

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"获取页面失败: {url}, 错误: {error_msg}, 尝试 {attempt + 1}/{max_retries}")

                # 判断错误类型
                error_type = "other"
                http_status = None
                if "timeout" in error_msg.lower():
                    error_type = "timeout"
                elif "net" in error_msg.lower() or "connection" in error_msg.lower():
                    error_type = "network_error"

                last_error = {
                    "error_type": error_type,
                    "error_message": error_msg,
                    "http_status": http_status,
                    "retry_count": attempt + 1,
                }

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)

        # 所有重试失败
        logger.error(f"获取页面失败，已重试 {max_retries} 次: {url}")
        return None, last_error

    async def _expand_all_content(self):
        """点击所有'展开全文'按钮以获取完整内容"""
        try:
            # 查找所有展开按钮
            assert self.page is not None  # noqa: S101
            expand_buttons = await self.page.query_selector_all(
                'button.ContentItem-more, button.Button:has-text("阅读全文"), ' 'button.Button:has-text("展开全文")'
            )

            for button in expand_buttons[:5]:  # 限制最多点击5个
                try:
                    await button.click()
                    await asyncio.sleep(0.5)  # 等待内容展开
                except Exception:
                    continue

            # 也尝试通过 JavaScript 点击
            assert self.page is not None  # noqa: S101
            await self.page.evaluate(
                """
                () => {
                    const buttons = document.querySelectorAll(
                        'button.ContentItem-more, .ContentItem-more'
                    );
                    buttons.forEach(btn => btn.click());
                }
            """
            )
            await asyncio.sleep(1)

        except Exception as e:
            logger.debug(f"展开内容时出错: {e}")

    async def _get_page_with_styles(self) -> str:
        """获取页面内容并提取关键样式"""
        assert self.page is not None  # noqa: S101
        # 获取原始 HTML
        html_content = await self.page.content()

        # 获取所有样式表内容
        assert self.page is not None  # noqa: S101
        styles = await self.page.evaluate(
            """
            () => {
                const styles = [];
                // 获取内联样式
                document.querySelectorAll('style').forEach(el => {
                    styles.push(el.textContent);
                });
                // 获取链接的 CSS 文件（部分）
                document.querySelectorAll('link[rel="stylesheet"]').forEach(el => {
                    // 只保留知乎域名的样式
                    if (el.href && el.href.includes('zhihu.com')) {
                        styles.push(`/* Original: ${el.href} */`);
                    }
                });
                return styles.join('\\n');
            }
        """
        )

        # 构建包含样式的完整 HTML
        soup = BeautifulSoup(html_content, "lxml")

        # 添加提取的样式到 head
        head = soup.find("head")
        if head:
            style_tag = soup.new_tag("style")
            style_tag.string = styles
            head.append(style_tag)

        return str(soup)

    async def fetch_comments(self, answer_id: str, limit: int = 20) -> tuple[list[dict], dict]:  # noqa: C901
        """获取评论 - 包括根评论和子评论.

        Returns:
            Tuple[评论列表, 统计信息]:
                - 评论列表: 所有评论数据
                - 统计信息: {
                    "root_comments": int,  # 根评论数
                    "child_comments": int,  # 子评论数
                    "total_expected": int,  # 预期总数
                    "api_error": str | None,  # API错误信息
                }
        """
        stats: dict[str, Any] = {
            "root_comments": 0,
            "child_comments": 0,
            "total_expected": 0,
            "api_error": None,
        }
        all_comments: list[dict[str, Any]] = []

        # 知乎 API limit 最大支持 20，超过会返回 400 错误
        api_limit = min(limit, 20)

        # 1. 获取根评论（支持分页）
        root_url = f"{self.API_BASE}/answers/{answer_id}/root_comments"
        offset = 0
        has_more = True

        while has_more and len(all_comments) < limit:
            params = {"limit": api_limit, "offset": offset, "order": "normal", "status": "open"}
            full_url = f"{root_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

            await self._delay()
            logger.info(f"请求根评论 API: {full_url}")

            try:
                assert self.page is not None  # noqa: S101
                response = await self.page.goto(full_url, wait_until="networkidle", timeout=15000)

                # 检查响应状态
                if response:
                    logger.info(f"评论 API 响应状态: {response.status} {response.status_text}")

                if response and response.status == 403:
                    logger.warning(f"获取评论被403拒绝: {answer_id}")
                    stats["api_error"] = "403 Forbidden"
                    return [], stats

                if response and response.status != 200:
                    logger.warning(f"评论 API 返回非200状态: {response.status}")
                    stats["api_error"] = f"HTTP {response.status}"

                content = await self.page.content()

                # 记录原始响应用于调试
                content_preview = content[:500] if len(content) < 1000 else content[:500] + "..."
                logger.debug(f"评论 API 原始响应: {content_preview}")

                soup = BeautifulSoup(content, "lxml")
                text_elem = soup.find("pre")

                if isinstance(text_elem, Tag):
                    raw_text = text_elem.get_text()
                    logger.debug(f"评论 API JSON 文本: {raw_text[:500]}")

                    try:
                        data = json.loads(raw_text)
                    except json.JSONDecodeError as e:
                        logger.error(f"解析评论 JSON 失败: {e}, 文本: {raw_text[:200]}")
                        stats["api_error"] = f"JSON parse error: {e}"
                        return [], stats

                    # 检查 error 字段
                    if data.get("error"):
                        error_msg = data.get("error", {}).get("message", "Unknown error")
                        logger.error(f"评论 API 返回错误: {error_msg}")
                        stats["api_error"] = f"API error: {error_msg}"
                        return [], stats

                    root_comments = data.get("data", [])
                    paging = data.get("paging", {})
                    stats["root_comments"] = len(root_comments)
                    stats["total_expected"] = paging.get("totals", 0)

                    logger.info(f"根评论 API 返回: {len(root_comments)} 条，预期共 {stats['total_expected']} 条")

                    # 处理根评论并获取子评论
                    for item in root_comments:
                        comment = item.get("comment", item)
                        all_comments.append(comment)

                        # 获取子评论
                        child_comments = comment.get("child_comments", [])
                        if child_comments:
                            stats["child_comments"] = stats.get("child_comments", 0) + len(child_comments)
                            all_comments.extend(child_comments)
                            logger.debug(f"评论 {comment.get('id')} 有 {len(child_comments)} 条子评论")

                        # 如果子评论过多，需要单独API获取剩余部分
                        child_comment_count = comment.get("child_comment_count", 0)
                        if child_comment_count > len(child_comments):
                            logger.info(
                                f"评论 {comment.get('id')} 有更多子评论: {child_comment_count} > {len(child_comments)}, "
                                f"开始获取剩余子评论..."
                            )
                            remaining_child_comments = await self.fetch_child_comments(
                                comment.get("id"), offset=len(child_comments)
                            )
                            if remaining_child_comments:
                                stats["child_comments"] = stats.get("child_comments", 0) + len(remaining_child_comments)
                                all_comments.extend(remaining_child_comments)
                                logger.info(f"额外获取了 {len(remaining_child_comments)} 条子评论")

                    # 检查是否还有更多评论
                    is_end = paging.get("is_end", True)
                    totals = paging.get("totals", 0)
                    stats["total_expected"] = totals

                    if is_end or len(root_comments) == 0:
                        has_more = False
                        logger.debug(f"评论分页结束: is_end={is_end}, 本页获取={len(root_comments)}")
                    else:
                        offset += len(root_comments)
                        logger.debug(f"继续获取评论: offset={offset}, has_more={has_more}")

                    # 更新统计
                    stats["root_comments"] = len([c for c in all_comments if c.get("type") != "child"])

                else:
                    logger.warning(f"评论 API 返回无内容: {answer_id}")
                    stats["api_error"] = "Empty response"
                    break  # 退出分页循环

            except json.JSONDecodeError as e:
                logger.warning(f"解析评论 JSON 失败: {e}")
                stats["api_error"] = f"JSON decode error: {e}"
                break
            except Exception as e:
                logger.warning(f"获取评论失败: {e}")
                stats["api_error"] = f"Exception: {e}"
                break

            # 如果已经获取足够，提前退出
            if len(all_comments) >= limit:
                logger.debug(f"已达到评论获取上限: {len(all_comments)} >= {limit}")
                break

        # 循环结束，返回结果
        logger.info(
            f"评论采集完成: 根评论 {stats['root_comments']}, 子评论 {stats['child_comments']}, 总计 {len(all_comments)}"
        )
        return all_comments, stats

    async def fetch_child_comments(self, comment_id: str, offset: int = 0) -> list[dict]:
        """获取子评论（分页获取）.

        Args:
            comment_id: 父评论ID
            offset: 起始偏移量

        Returns:
            子评论列表
        """
        all_child_comments = []
        child_url = f"{self.API_BASE}/comments/{comment_id}/child_comments"
        has_more = True
        current_offset = offset

        while has_more:
            params = {"limit": 20, "offset": current_offset}
            full_url = f"{child_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

            await self._delay()
            logger.debug(f"请求子评论 API: {full_url}")

            try:
                assert self.page is not None  # noqa: S101
                response = await self.page.goto(full_url, wait_until="networkidle", timeout=15000)

                if response and response.status != 200:
                    logger.warning(f"子评论 API 返回非200状态: {response.status}")
                    break

                content = await self.page.content()
                soup = BeautifulSoup(content, "lxml")
                text_elem = soup.find("pre")

                if isinstance(text_elem, Tag):
                    raw_text = text_elem.get_text()
                    data = json.loads(raw_text)

                    if data.get("error"):
                        error_msg = data.get("error", {}).get("message", "Unknown error")
                        logger.error(f"子评论 API 错误: {error_msg}")
                        break

                    child_comments = data.get("data", [])
                    paging = data.get("paging", {})

                    for item in child_comments:
                        comment = item.get("comment", item)
                        comment["type"] = "child"  # 标记为子评论
                        all_child_comments.append(comment)

                    # 检查是否还有更多
                    is_end = paging.get("is_end", True)
                    if is_end or len(child_comments) == 0:
                        has_more = False
                    else:
                        current_offset += len(child_comments)
                        logger.debug(f"继续获取子评论: offset={current_offset}")
                else:
                    logger.warning("子评论 API 返回无内容")
                    break

            except Exception as e:
                logger.warning(f"获取子评论失败: {e}")
                break

        return all_child_comments

    async def _scroll_page(self):
        """滚动页面加载内容"""
        assert self.page is not None  # noqa: S101
        await self.page.evaluate(
            """
            async () => {
                await new Promise((resolve) => {
                    let totalHeight = 0;
                    const distance = 500;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;

                        if (totalHeight >= scrollHeight) {
                            clearInterval(timer);
                            resolve();
                        }
                    }, 200);

                    setTimeout(() => {
                        clearInterval(timer);
                        resolve();
                    }, 5000);
                });
            }
        """
        )

    async def _scroll_page_for_activities(self):
        """滚动页面加载更多动态内容"""
        logger.info("滚动页面加载更多动态...")

        # 先点击"查看更多"或"展开"按钮（如果有）
        try:
            assert self.page is not None  # noqa: S101
            await self.page.evaluate(
                """
                () => {
                    // 点击所有"查看更多"按钮
                    const buttons = document.querySelectorAll(
                        'button[data-za-detail-view-element_name="ViewMore"], '
                        + '.ActivityItem-more, .ContentItem-more, .Button:contains("查看更多")'
                    );
                    buttons.forEach(btn => btn.click());

                    // 点击所有"展开阅读全文"按钮
                    const expandButtons = document.querySelectorAll(
                        '.ContentItem-expandButton, .RichContent-expandButton'
                    );
                    expandButtons.forEach(btn => btn.click());
                }
            """
            )
            await asyncio.sleep(1)
        except Exception:
            pass

        # 多次滚动页面加载更多内容
        last_height = 0
        scroll_attempts = 0
        max_scroll_attempts = 10

        while scroll_attempts < max_scroll_attempts:
            # 滚动到页面底部
            assert self.page is not None  # noqa: S101
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)  # 等待内容加载

            # 获取新的页面高度
            assert self.page is not None  # noqa: S101
            new_height = await self.page.evaluate("document.body.scrollHeight")

            if new_height == last_height:
                # 高度没有变化，尝试再滚动一次确认
                scroll_attempts += 1
                if scroll_attempts >= 3:  # 连续3次没有新内容则停止
                    logger.info(f"滚动结束，共滚动 {scroll_attempts} 次")
                    break
            else:
                # 有新内容加载，重置计数
                scroll_attempts = 0
                last_height = new_height
                logger.debug(f"页面高度变化: {last_height} -> {new_height}")

        logger.info(f"页面滚动完成，最终高度: {last_height}")

    def _extract_content_from_page(self, soup: BeautifulSoup, target: dict) -> tuple[str, str]:
        """从页面提取回答内容。

        Args:
            soup: BeautifulSoup 对象，解析后的页面
            target: 目标数据字典，包含 content 字段作为备选

        Returns:
            tuple: (content_html, content_text)
        """
        content_elem = soup.select_one(".RichContent-inner")
        if content_elem:
            content_html = str(content_elem)
            content_text = content_elem.get_text(separator="\n", strip=True)
        else:
            content_html = target.get("content", "")
            content_text = BeautifulSoup(content_html, "lxml").get_text(separator="\n", strip=True)
        return content_html, content_text

    def _extract_author_info_from_page(
        self, soup: BeautifulSoup, author: dict
    ) -> tuple[str | None, str | None, str | None]:
        """从页面提取作者详细信息（头像、名称、签名）。

        Args:
            soup: BeautifulSoup 对象，解析后的页面
            author: 作者数据字典，包含 headline 字段作为备选

        Returns:
            tuple: (author_avatar_url, author_name, author_headline)
        """
        author_avatar_url = None
        author_headline = None
        author_name_from_page = None

        # 从页面提取作者信息
        author_info_elem = soup.select_one(".AuthorInfo")
        if author_info_elem:
            # 提取头像 - 尝试多种选择器
            avatar_selectors = [
                ".Avatar img",
                ".UserAvatar img",
                "img.Avatar",
                ".author-avatar img",
                'img[alt*="头像"]',
                "img",
            ]
            for selector in avatar_selectors:
                avatar_img = author_info_elem.select_one(selector)
                if avatar_img:
                    src = avatar_img.get("src")
                    if isinstance(src, str):
                        author_avatar_url = src
                        logger.debug(f"提取到作者头像: {author_avatar_url[:60]}...")
                        break

            # 提取作者名（如果API中没有）
            name_elem = author_info_elem.select_one("a.UserLink-link, .AuthorInfo-name")
            if name_elem:
                author_name_from_page = name_elem.get_text(strip=True)
                logger.debug(f"从页面提取到作者名: {author_name_from_page}")

            # 提取签名
            headline_elem = author_info_elem.select_one(".AuthorInfo-badgeText, .AuthorInfo-headline")
            if headline_elem:
                author_headline = headline_elem.get_text(strip=True)

        return author_avatar_url, author_name_from_page, author_headline

    async def _mark_html_as_deleted(self, html_path: str, question_title: str) -> None:
        """在HTML文件中标注原回答已被删除.

        Args:
            html_path: HTML文件路径
            question_title: 问题标题
        """
        try:

            import aiofiles

            path = Path(html_path)
            if not path.exists():
                return

            # 读取现有HTML
            async with aiofiles.open(path, encoding="utf-8") as f:
                content = await f.read()

            # 检查是否已添加删除标注
            if 'class="deleted-notice"' in content:
                return

            # 构建删除标注HTML
            beijing_time = get_beijing_now()
            deleted_notice = f"""
    <div class="deleted-notice" style="
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
        color: white;
        padding: 16px 20px;
        margin: 0;
        font-weight: 600;
        font-size: 15px;
        display: flex;
        align-items: center;
        gap: 10px;
    ">
        <span style="font-size: 20px;">⚠️</span>
        <div>
            <div style="font-size: 16px; margin-bottom: 4px;">原回答已被删除</div>
            <div style="font-size: 13px; opacity: 0.9;">
                该回答在知乎上已被作者删除或不存在 ·
                检测时间: {beijing_time.strftime("%Y-%m-%d %H:%M:%S")}
            </div>
        </div>
    </div>
    """

            # 在 zhihu-card div 开头插入删除标注
            if '<div class="zhihu-card">' in content:
                content = content.replace('<div class="zhihu-card">', f'<div class="zhihu-card">\n{deleted_notice}')
            else:
                # 在 body 标签后插入
                content = content.replace("<body>", f"<body>\n{deleted_notice}")

            # 写回文件
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(content)

            logger.info(f"已在HTML中添加删除标注: {question_title[:50]}...")
        except Exception as e:
            logger.warning(f"添加删除标注失败: {e}")

    async def process_answer(  # noqa: C901
        self, activity: dict, liked_time: datetime, scan_mode: str = "normal"
    ) -> bool:
        """处理单个回答

        Args:
            activity: 活动数据
            liked_time: 点赞时间
            scan_mode: 扫描模式
                - "normal": 普通采集（定时/手工触发），遇到重复停止
                - "full": 全量采集（手工触发），穷尽所有点赞

        404处理策略:
            - 全量采集时，如果404且本地未下载过 → 跳过不采集（节省空间）
            - 全量采集时，如果404但本地已下载 → 标记为删除并高亮标注，保留原内容
            - 普通采集时，404处理同上（保持数据完整性）

        403处理策略:
            - 自动重试3次，每次增加延迟
            - 如果仍失败，记录到下载失败表，稍后统一重试
        """
        try:
            target = activity.get("target", {})

            # 提取回答信息
            answer_id = str(target.get("id", ""))
            question = target.get("question", {})
            question_id = str(question.get("id", ""))
            question_title = question.get("title", "无标题")

            author = target.get("author", {})
            author_id = author.get("id", "")
            author_name = author.get("name", "匿名用户")
            author_url = author.get("url", "")
            author_headline = author.get("headline", "")

            voteup_count = target.get("voteup_count", 0)
            comment_count = target.get("comment_count", 0)
            created_time = target.get("created_time", 0)
            updated_time = target.get("updated_time", 0)

            # 检查是否已存在
            existing = self.db.get_answer_by_id(answer_id)

            # 获取完整页面内容（带重试）
            logger.info(f"获取回答: {question_title[:60]}...")
            page_html, error_info = await self.fetch_answer_page(question_id, answer_id)

            # 处理404被删除的内容
            if page_html == "__DELETED__":
                logger.warning(f"回答已被删除: {question_title[:60]}...")

                if existing:
                    # 【核心逻辑】本地已下载过，需要标记为删除但保留原内容
                    if not existing.is_deleted:
                        update_data = {
                            "id": answer_id,
                            "is_deleted": True,
                            "download_status": "success",
                            "content_text": existing.content_text,  # 保留原内容预览
                            "extra_meta": {
                                "deleted": True,
                                "deleted_at": get_beijing_now().isoformat(),
                                "author_headline": author_headline,
                                "note": "该回答已被原作者删除或知乎删除，此处保留备份",
                            },
                        }
                        # 【核心逻辑】如果已有HTML备份，保留路径并在文件中添加删除标注
                        if existing.html_path:
                            update_data["html_path"] = existing.html_path
                            # 在HTML文件中添加删除标注（高亮提示）
                            await self._mark_html_as_deleted(existing.html_path, question_title)
                            logger.info(f"已高亮标注删除状态（保留原内容）: {question_title[:60]}...")

                        self.db.save_answer(update_data)
                        self.updated_items += 1
                        logger.info(f"已标记为删除状态（保留备份）: {question_title[:60]}...")
                    return True

                # 【核心逻辑】本地未下载过且是404
                if scan_mode == "full":
                    # 全量采集模式：跳过不采集，节省存储空间
                    logger.info(f"全量采集：跳过404且未备份的回答: {question_title[:60]}...")
                    return True  # 返回True表示已处理（跳过），不计入新条目
                else:
                    # 普通采集模式：保存删除状态记录（用于完整性）
                    answer_data = {
                        "id": answer_id,
                        "user_id": self.user_id,
                        "question_id": question_id,
                        "question_title": question_title,
                        "author_id": author_id,
                        "author_name": author_name,
                        "author_avatar_url": None,
                        "author_headline": author_headline,
                        "author_url": author_url,
                        "content_text": "[此回答已被删除或不存在]",
                        "content_length": 0,
                        "voteup_count": voteup_count,
                        "comment_count": comment_count,
                        "created_time": (self._parse_timestamp(created_time) if created_time else None),
                        "updated_time": (self._parse_timestamp(updated_time) if updated_time else None),
                        "liked_time": liked_time,
                        "html_path": None,
                        "original_url": f"{self.ZHIHU_BASE}/question/{question_id}/answer/{answer_id}",
                        "has_comments": False,
                        "is_deleted": True,
                        "download_status": "skipped",
                        "extra_meta": {
                            "deleted": True,
                            "deleted_at": get_beijing_now().isoformat(),
                            "author_headline": author_headline,
                            "note": "首次发现时已被删除",
                        },
                    }
                    is_new = self.db.save_answer(answer_data)
                    if is_new:
                        self.new_items += 1
                        logger.info(f"普通采集：保存删除状态记录: {question_title[:60]}...")
                    return True

            # 处理下载失败（403等错误）- 不保存任何数据，直接暴露问题
            if error_info:
                error_type = error_info.get("error_type", "unknown")
                http_status = error_info.get("http_status")
                error_msg = error_info.get("error_message", "未知错误")

                # 403错误特殊处理：明确提示Cookie过期问题
                if http_status == 403 or error_type == "403_cookie_expired":
                    logger.error(
                        f"🚫 采集被阻止(403): {question_title[:60]}... | "
                        f"原因: {error_msg} | "
                        f"建议: 请更新知乎Cookie后重试"
                    )
                else:
                    logger.error(f"下载失败: {question_title[:60]}..., 错误: {error_msg}")

                # 【重要】不保存任何回答数据到数据库，直接记录失败
                # 这样用户能看到问题而不是错误数据

                # 记录到下载失败表（用于后续重试和统计）
                failure_id = self.db.add_download_failure(
                    answer_id=answer_id,
                    user_id=self.user_id,
                    question_title=question_title,
                    question_id=question_id,
                    error_type=error_type,
                    error_message=error_msg,
                    http_status=http_status,
                )

                # 记录提取错误（用于前端展示）
                self.db.add_extraction_error(
                    answer_id=answer_id,
                    question_title=question_title,
                    error_type=error_type if error_type != "403_cookie_expired" else "cookie_expired",
                    error_message=f"【{error_type}】{error_msg}",
                )

                logger.warning(
                    f"已记录下载失败 #{failure_id}: {question_title[:60]}... | " f"可在'明细'页面查看失败项并重新采集"
                )
                return False

            # 如果是已存在的记录且没有更新，跳过
            if existing:
                logger.debug(f"回答已存在，跳过: {question_title[:50]}...")
                return False

            # 解析页面获取内容
            if page_html is None:
                logger.error("页面内容为空，无法解析")
                return False
            soup = BeautifulSoup(page_html, "lxml")

            # 提取回答内容
            content_html, content_text = self._extract_content_from_page(soup, target)

            # 提取作者详细信息（头像、名称、签名）
            author_avatar_url: str | None
            author_name_from_page: str | None
            author_headline_from_page: str | None
            (
                author_avatar_url,
                author_name_from_page,
                author_headline_from_page,
            ) = self._extract_author_info_from_page(soup, author)

            # 使用页面提取的作者名
            if author_name_from_page and not author_name:
                author_name = author_name_from_page

            # 如果从页面没提取到签名，使用 API 数据中的
            if author_headline_from_page:
                author_headline = author_headline_from_page
            elif not author_headline:
                author_headline = author.get("headline", "")

            # 下载作者头像
            local_author_avatar = None
            if author_avatar_url and author_id:
                local_author_avatar = await self.storage.download_avatar(author_avatar_url, author_id)
                if local_author_avatar:
                    author_avatar_url = local_author_avatar

            # 保存 HTML 文件
            metadata = {
                "question_id": question_id,
                "author_name": author_name,
                "author_headline": author_headline,
                "author_avatar_url": author_avatar_url or "",
                "voteup_count": voteup_count,
                "comment_count": comment_count,
                "updated_time": (self._parse_timestamp(updated_time).isoformat() if updated_time else ""),
                "backup_time": get_beijing_now().isoformat(),
            }

            html_path = await self.storage.save_answer(
                answer_id=answer_id,
                question_id=question_id,
                question_title=question_title,
                html_content=content_html,
                page_metadata=metadata,
            )

            # 保存元数据到数据库
            answer_data = {
                "id": answer_id,
                "user_id": self.user_id,  # 添加用户ID
                "question_id": question_id,
                "question_title": question_title,
                "author_id": author_id,
                "author_name": author_name,
                "author_avatar_url": author_avatar_url,
                "author_headline": author_headline,
                "author_url": author_url,
                "content_text": content_text[:2000] if content_text else "",
                "content_length": len(content_text) if content_text else 0,
                "voteup_count": voteup_count,
                "comment_count": comment_count,
                "created_time": (self._parse_timestamp(created_time) if created_time else None),
                "updated_time": (self._parse_timestamp(updated_time) if updated_time else None),
                "liked_time": liked_time,
                "html_path": html_path,
                "original_url": f"{self.ZHIHU_BASE}/question/{question_id}/answer/{answer_id}",
                "has_comments": False,
                "download_status": "success",  # 标记下载成功
                "retry_count": 0,
                "last_error": None,
                "extra_meta": {
                    "author_headline": author_headline,
                },
            }

            is_new = self.db.save_answer(answer_data)

            # 如果之前有下载失败记录，标记为已解决
            self.db.resolve_download_failure_by_answer(answer_id)

            if is_new:
                self.new_items += 1
            else:
                self.updated_items += 1

            # 如果有评论，立即获取
            if comment_count > 0:
                logger.debug(f"回答有 {comment_count} 条评论，开始获取...")
                comment_result = await self.process_comments(answer_id)

                # 检查评论采集是否异常
                if comment_result and comment_result.get("anomaly"):
                    logger.warning(
                        f"📊 评论采集异常记录 [{answer_id}]: "
                        f"预期 {comment_result.get('expected_count')} 条, "
                        f"实际 {comment_result.get('saved_count')} 条"
                    )

            return True

        except Exception as e:
            logger.exception(f"处理回答失败: {e}")
            # 记录提取错误
            import traceback

            question_title = activity.get("target", {}).get("question", {}).get("title", "未知")
            answer_id = str(activity.get("target", {}).get("id", ""))
            self.db.add_extraction_error(
                answer_id=answer_id,
                question_title=question_title,
                error_type="parse_error",
                error_message=str(e),
                stack_trace=traceback.format_exc(),
            )
            return False

    async def process_comments(self, answer_id: str) -> dict:
        """处理评论 - 包含异常检测.

        Returns:
            处理结果: {
                "success": bool,
                "saved_count": int,
                "expected_count": int,
                "anomaly": bool,
                "anomaly_reason": str | None,
            }
        """
        result: dict[str, Any] = {
            "success": False,
            "saved_count": 0,
            "expected_count": 0,
            "anomaly": False,
            "anomaly_reason": None,
        }

        try:
            answer = self.db.get_answer_by_id(answer_id)
            if not answer or answer.has_comments:
                logger.debug(
                    f"跳过评论处理: answer_id={answer_id}, exists={bool(answer)}, has_comments={answer.has_comments if answer else 'N/A'}"
                )
                result["success"] = True
                return result

            expected_count = answer.comment_count or 0
            result["expected_count"] = expected_count

            # 计算评论获取上限
            comment_limit = 1000 if self.max_comments < 0 else self.max_comments
            logger.info(f"获取评论: {answer_id} (预期 {expected_count} 条, 上限 {comment_limit} 条)")

            comments_data, stats = await self.fetch_comments(answer_id, limit=comment_limit)
            actual_count = len(comments_data)

            logger.info(f"评论 API 返回 {actual_count} 条数据 (预期 {expected_count} 条)")

            # 异常检测
            if stats.get("api_error"):
                # API 调用失败
                result["anomaly"] = True
                result["anomaly_reason"] = f"API错误: {stats['api_error']}"
                logger.error(f"🚨 评论采集异常 [{answer_id}]: {result['anomaly_reason']}")

                # 记录异常但不标记为已处理，允许重试
                self.db.add_extraction_error(
                    answer_id=answer_id,
                    question_title=answer.question_title,
                    error_type="comment_api_error",
                    error_message=f"预期 {expected_count} 条评论，API错误: {stats['api_error']}",
                )
                return result

            if expected_count > 0 and actual_count == 0:
                # 严重异常：预期有评论但实际获取0条
                result["anomaly"] = True
                result["anomaly_reason"] = f"预期 {expected_count} 条但获取 0 条"
                logger.error(f"🚨 评论采集严重异常 [{answer_id}]: {result['anomaly_reason']}")

                # 记录异常
                self.db.add_extraction_error(
                    answer_id=answer_id,
                    question_title=answer.question_title,
                    error_type="comment_anomaly",
                    error_message=f"预期 {expected_count} 条评论，实际获取 0 条，可能存在403限制",
                )
                # 不标记为已处理，允许后续重试
                return result

            if expected_count > 10 and actual_count < expected_count * 0.5:
                # 轻度异常：获取数量远低于预期（少于50%）
                result["anomaly"] = True
                result["anomaly_reason"] = f"预期 {expected_count} 条但仅获取 {actual_count} 条"
                logger.warning(f"⚠️ 评论数量异常 [{answer_id}]: {result['anomaly_reason']}")

                # 记录异常但仍保存已获取的评论
                self.db.add_extraction_error(
                    answer_id=answer_id,
                    question_title=answer.question_title,
                    error_type="comment_partial",
                    error_message=f"预期 {expected_count} 条，实际获取 {actual_count} 条",
                )

            if not comments_data:
                # 确实没有评论
                self.db.mark_answer_has_comments(answer_id)
                logger.info(f"回答确实无评论: {answer_id}")
                result["success"] = True
                return result

            # 保存评论
            comments_to_save = []
            for comment in comments_data:
                author_info = comment.get("author", {}) if isinstance(comment, dict) else {}
                comment_info = {
                    "id": str(comment.get("id", "")) if isinstance(comment, dict) else str(comment),
                    "answer_id": answer_id,
                    "author_id": author_info.get("id", "") if isinstance(author_info, dict) else "",
                    "author_name": author_info.get("name", "匿名用户") if isinstance(author_info, dict) else "匿名用户",
                    "author_avatar_url": author_info.get("avatar_url", "") if isinstance(author_info, dict) else "",
                    "content": comment.get("content", "") if isinstance(comment, dict) else str(comment),
                    "like_count": comment.get("like_count", 0) if isinstance(comment, dict) else 0,
                    "created_time": (
                        self._parse_timestamp(comment.get("created_time", 0))
                        if isinstance(comment, dict) and comment.get("created_time")
                        else None
                    ),
                }
                self.db.save_comment(comment_info)
                comments_to_save.append(comment_info)

            # 追加评论到 HTML 文件
            if comments_to_save and answer.html_path:
                await self.storage.append_comments(answer.html_path, comments_to_save)

            self.db.mark_answer_has_comments(answer_id)
            logger.info(f"保存 {len(comments_to_save)} 条评论: {answer_id}")

            result["success"] = True
            result["saved_count"] = len(comments_to_save)
            return result

        except Exception as e:
            logger.exception(f"处理评论失败: {e}")
            result["anomaly_reason"] = f"Exception: {e}"
            return result

    async def scan_likes(  # noqa: C901
        self,
        max_items: int = 50,
        progress_callback: Callable | None = None,
        init_mode: bool = False,
        scan_mode: str = "normal",
    ):
        """扫描用户点赞内容 - 支持断点续传和初始化模式，边滚动边保存.

        采集模式说明:
            normal (普通采集):
                - 触发方式: 定时触发或手工触发
                - 停止条件: 遇到已存在的重复数据时停止
                - 适用场景: 日常增量同步
                - 404处理: 本地未下载过的404回答会保存为删除状态记录

            full (全量采集):
                - 触发方式: 仅手工触发（点击"全量同步"按钮）
                - 停止条件: 穷尽用户的所有点赞记录
                - 适用场景: 初次使用或需要完整备份时
                - 404处理: 本地未下载过的404回答直接跳过（节省空间）

        特殊情况说明:
            初次使用时:
                - 数据库为空，普通采集等同于全量采集
                - 建议直接使用"全量同步"以获得最佳效果

            404回答处理:
                - 本地已下载过: 高亮标注删除状态，保留原内容，不会被404页面覆盖
                - 本地未下载过（全量）: 跳过不采集，节省存储空间
                - 本地未下载过（普通）: 保存删除状态记录（用于完整性）

        Args:
            max_items: 最大扫描数量，-1 表示无限制
            progress_callback: 进度回调函数
            init_mode: 初始化模式，True 时会重新爬取所有历史数据（无视已存在）
            scan_mode: 扫描模式，"normal" 或 "full"
        """
        mode_str = "全量采集模式" if scan_mode == "full" else "普通采集模式"
        init_str = "（初始化）" if init_mode else ""
        logger.info(f"开始扫描用户 {self.user_id} 的点赞内容 ({mode_str}{init_str}, max={max_items})...")

        # 🆕 采集前预检查
        pre_check_result = await self.pre_check()
        if not pre_check_result["success"]:
            error_msg = pre_check_result["message"]
            logger.error(f"❌ 预检查失败，终止采集: {error_msg}")
            raise RuntimeError(f"预检查失败: {error_msg}")

        # 确保用户记录在数据库中存在
        user_created = self.db.add_user(self.user_id, self.user_id)
        logger.info(f"用户记录检查: user_id={self.user_id}, created={user_created}")

        # 获取用户详细信息（名称、头像、签名）
        await self._fetch_user_profile()

        self.new_items = 0
        self.updated_items = 0
        self._stopped = False  # 重置停止标志
        scanned = 0
        processed_ids: set[str] = set()  # 防止重复处理

        # 获取已处理的回答ID
        existing_answers = self.db.get_user_answer_ids(self.user_id)

        if init_mode:
            logger.info(f"初始化模式：将重新爬取所有 {len(existing_answers)} 条历史数据")
        else:
            # 增量模式：跳过已存在的
            processed_ids.update(existing_answers)
            logger.info(f"已有 {len(processed_ids)} 条回答，将跳过重复内容")

        # -1 表示无限制
        no_limit = max_items < 0

        async def process_single_activity(activity: dict, index: int) -> None:
            """处理单个activity的回调函数"""
            nonlocal scanned

            # 🛑 检查是否需要停止
            if self.check_should_stop():
                logger.info(f"🛑 停止处理，已处理 {scanned} 条")
                return

            # 只处理点赞回答
            if activity.get("verb") != "MEMBER_VOTEUP_ARTICLE" and activity.get("verb") != "MEMBER_VOTEUP_ANSWER":
                return

            # 获取回答ID用于去重
            target = activity.get("target", {})
            answer_id = str(target.get("id", ""))

            # 如果已经处理过，跳过（初始化模式除外）
            if answer_id and answer_id in processed_ids and not init_mode:
                logger.debug(f"跳过已处理的回答: {answer_id}")
                scanned += 1
                if progress_callback:
                    progress_callback(scanned, max_items if not no_limit else -1)
                return

            # 初始化模式下，已存在的回答强制更新
            if init_mode and answer_id and answer_id in existing_answers:
                logger.debug(f"初始化模式：强制更新已存在的回答: {answer_id}")

            # 解析点赞时间
            created_time = activity.get("created_time", 0)
            liked_time = self._parse_timestamp(created_time) if created_time else get_beijing_now()

            # 处理回答（会立即保存到数据库和文件）
            # 传递 scan_mode 以支持不同的404处理策略
            success = await self.process_answer(activity, liked_time, scan_mode=scan_mode)
            if success and answer_id:
                processed_ids.add(answer_id)

            scanned += 1

            if progress_callback:
                progress_callback(scanned, max_items if not no_limit else -1)

            # 每处理5条更新一次同步时间（断点续传）
            if scanned % 5 == 0:
                self.db.update_user_sync_time(self.user_id)

        # 调用fetch_likes，使用回调函数实现边滚动边处理
        activities = await self.fetch_likes(
            limit=max_items,
            offset=0,
            item_callback=process_single_activity,
        )

        # 如果没有通过回调处理（兼容旧逻辑），则批量处理
        if scanned == 0 and activities:
            logger.info(f"通过批量模式处理 {len(activities)} 条记录")
            for activity in activities:
                # 🛑 检查是否需要停止
                if self.check_should_stop():
                    logger.info(f"🛑 批量处理被停止，已处理 {scanned} 条")
                    break
                await process_single_activity(activity, scanned)
                if not no_limit and scanned >= max_items:
                    break

        logger.info(f"扫描完成: 处理 {scanned} 条，新增 {self.new_items} 条，更新 {self.updated_items} 条")

        # 最终更新用户同步时间和次数
        if self.new_items > 0 or self.updated_items > 0:
            self.db.update_user_sync_time(self.user_id)
            logger.info(f"已更新用户同步时间: {self.user_id}")
        else:
            logger.info("没有新内容，跳过更新用户同步时间")

        return self.new_items, self.updated_items

    async def sync_all_comments(self):
        """同步所有未获取评论的回答"""
        answers = self.db.get_answers_without_comments()
        logger.info(f"需要同步评论的回答: {len(answers)} 条")

        for answer in answers:
            await self.process_comments(answer.id)
            await asyncio.sleep(1)  # 避免请求过快

    async def retry_failed_downloads(self, max_items: int = 50) -> dict:
        """重试失败的下载.

        Args:
            max_items: 最大重试数量.

        Returns:
            Dict: 重试结果统计.
        """
        # 获取待重试的失败记录
        failures = self.db.get_pending_retry_failures(max_retries=3)
        if not failures:
            logger.info("没有待重试的下载失败记录")
            return {"success": 0, "failed": 0, "skipped": 0, "total": 0}

        # 限制数量
        failures = failures[:max_items]
        logger.info(f"开始重试 {len(failures)} 个失败的下载...")

        stats = {"success": 0, "failed": 0, "skipped": 0, "total": len(failures)}

        for failure in failures:
            try:
                # 更新最后重试时间
                failure.last_retry_at = get_beijing_now()
                failure.retry_count += 1

                logger.info(f"重试下载: {failure.question_title[:60]}... (第 {failure.retry_count} 次)")

                # 尝试重新下载
                page_html, error_info = await self.fetch_answer_page(
                    failure.question_id or "", failure.answer_id, max_retries=3
                )

                if page_html and page_html != "__DELETED__":
                    # 下载成功，解析并保存
                    soup = BeautifulSoup(page_html, "lxml")
                    content_html, content_text = self._extract_content_from_page(soup, {})

                    # 保存HTML文件
                    metadata = {
                        "question_id": failure.question_id or "",
                        "author_name": "",
                        "backup_time": get_beijing_now().isoformat(),
                    }

                    await self.storage.save_answer(
                        answer_id=failure.answer_id,
                        question_id=failure.question_id or "",
                        question_title=failure.question_title or "",
                        html_content=content_html,
                        page_metadata=metadata,
                    )

                    # 更新数据库状态
                    self.db.update_answer_download_status(answer_id=failure.answer_id, status="success")

                    # 标记失败记录为已解决
                    self.db.resolve_download_failure(failure.id)

                    logger.info(f"重试成功: {failure.question_title[:60]}...")
                    stats["success"] += 1

                elif page_html == "__DELETED__":
                    # 内容已被删除
                    logger.warning(f"内容已被删除: {failure.question_title[:60]}...")
                    self.db.update_answer_download_status(answer_id=failure.answer_id, status="skipped")
                    self.db.resolve_download_failure(failure.id)
                    stats["skipped"] += 1

                else:
                    # 仍然失败
                    error_msg = error_info["error_message"] if error_info else "未知错误"
                    logger.warning(f"重试仍然失败: {failure.question_title[:60]}... - {error_msg}")

                    # 更新错误信息
                    if error_info:
                        failure.error_message = error_info["error_message"]
                        failure.http_status = error_info.get("http_status")

                    stats["failed"] += 1

                await asyncio.sleep(self.request_delay)

            except Exception as e:
                logger.exception(f"重试下载时出错: {e}")
                stats["failed"] += 1

        logger.info(f"重试完成: 成功 {stats['success']}, 失败 {stats['failed']}, 跳过 {stats['skipped']}")
        return stats

    async def retry_specific_answer(self, answer_id: str) -> dict:
        """重试特定回答的下载.

        Args:
            answer_id: 回答ID.

        Returns:
            Dict: 重试结果.
        """
        # 获取回答信息
        answer = self.db.get_answer_by_id(answer_id)
        if not answer:
            return {"success": False, "message": "回答不存在"}

        if answer.download_status == "success":
            return {"success": True, "message": "回答已下载成功"}

        logger.info(f"重试特定回答: {answer.question_title[:60]}...")

        # 尝试重新下载
        page_html, error_info = await self.fetch_answer_page(answer.question_id, answer_id, max_retries=3)

        if page_html and page_html != "__DELETED__":
            # 下载成功
            soup = BeautifulSoup(page_html, "lxml")
            content_html, content_text = self._extract_content_from_page(soup, {})

            # 保存HTML文件
            metadata = {
                "question_id": answer.question_id,
                "backup_time": get_beijing_now().isoformat(),
            }

            html_path = await self.storage.save_answer(
                answer_id=answer_id,
                question_id=answer.question_id,
                question_title=answer.question_title,
                html_content=content_html,
                page_metadata=metadata,
            )

            # 更新数据库
            self.db.update_answer_download_status(answer_id=answer_id, status="success")
            self.db.resolve_download_failure_by_answer(answer_id)

            return {"success": True, "message": "下载成功", "html_path": html_path}

        elif page_html == "__DELETED__":
            self.db.update_answer_download_status(answer_id=answer_id, status="skipped")
            self.db.resolve_download_failure_by_answer(answer_id)
            return {"success": False, "message": "内容已被删除"}

        else:
            error_msg = error_info["error_message"] if error_info else "未知错误"
            self.db.update_answer_download_status(answer_id=answer_id, status="failed", error=error_msg)
            return {"success": False, "message": error_msg}
