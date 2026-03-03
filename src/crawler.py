"""爬虫模块 - 知乎内容抓取"""

import asyncio
import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from db import DatabaseManager
from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from storage import StorageManager
from tenacity import retry, stop_after_attempt, wait_exponential
from timezone_utils import get_beijing_now


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
        """
        self.user_id = user_id
        self.db = db_manager
        self.storage = storage_manager
        self.headless = headless
        self.request_delay = request_delay
        self.browser_type = browser_type  # auto, chromium, firefox, webkit, edge
        self.max_comments = max_comments

        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

        # 统计
        self.new_items = 0
        self.updated_items = 0

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
        db_path = Path(
            self.db.db_path if hasattr(self.db, "db_path") else "/app/data/meta/zhihusync.db"
        )
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
            self.browser = await browser_type.launch(**launch_options)
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

        context_options = {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0"
            ),
            "viewport": {"width": 1920, "height": 1080},
            "locale": "zh-CN",
        }

        # 尝试使用 storage_state，如果失败则手动添加 cookie
        if storage_state:
            try:
                context_options["storage_state"] = storage_state
                self.context = await self.browser.new_context(**context_options)
                logger.info("已使用 storage_state 创建 context")
            except Exception as e:
                logger.warning(f"使用 storage_state 失败: {e}，尝试手动添加 cookie")
                context_options.pop("storage_state", None)
                self.context = await self.browser.new_context(**context_options)
                # 手动添加 cookie
                await self._add_cookies_manually(storage_state)
        else:
            self.context = await self.browser.new_context(**context_options)

        self.page = await self.context.new_page()

        logger.info("浏览器初始化完成")

    async def _add_cookies_manually(self, storage_state):
        """手动添加 cookie 到 context - 使用 JavaScript 方式"""
        try:
            cookies = storage_state.get("cookies", [])
            if not cookies:
                return

            # 创建页面访问知乎以便添加 cookie
            self.page = await self.context.new_page()
            await self.page.goto(
                "https://www.zhihu.com", wait_until="domcontentloaded", timeout=10000
            )

            # 使用 JavaScript 批量设置 cookie
            success_count = 0
            for cookie in cookies:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                domain = cookie.get("domain", ".zhihu.com")
                path = cookie.get("path", "/")

                try:
                    # 使用 encodeURIComponent 处理特殊字符
                    js_code = f"""() => {{
                        document.cookie = "{name}=" + encodeURIComponent("{value}") +
                        "; domain={domain}; path={path}";
                    }}"""
                    await self.page.evaluate(js_code)
                    success_count += 1
                except Exception as e:
                    logger.debug(f"设置 cookie {name} 失败: {e}")

            logger.info(f"通过 JavaScript 设置了 {success_count}/{len(cookies)} 条 cookie")
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
            # 访问知乎首页
            await self.page.goto(f"{self.ZHIHU_BASE}", timeout=30000)

            # 检查是否有登录态
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
            has_user_menu = (
                await self.page.locator(
                    "[data-za-detail-view-path-module='TopNavBar'] .AppHeader-profile"
                ).count()
                > 0
            )

            # 方法3: 尝试访问 API 获取当前用户信息
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

        await self.page.goto(f"{self.ZHIHU_BASE}/signin")

        # 等待跳转到首页或个人主页
        try:
            await self.page.wait_for_url(
                lambda url: "zhihu.com" in url and "signin" not in url, timeout=timeout * 1000
            )
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

    def _parse_timestamp(self, ts: int or str) -> datetime:
        """解析时间戳"""
        if isinstance(ts, str):
            ts = int(ts)
        if ts > 1e12:  # 毫秒时间戳
            ts = ts / 1000
        return datetime.fromtimestamp(ts)

    async def _delay(self):
        """请求延迟"""
        await asyncio.sleep(self.request_delay)

    async def _fetch_user_profile(self):
        """获取用户详细信息（名称、头像、签名）"""
        try:
            url = f"{self.ZHIHU_BASE}/people/{self.user_id}"
            logger.info(f"获取用户资料: {url}")

            await self._delay()
            await self.page.goto(url, wait_until="networkidle")
            await asyncio.sleep(1)

            # 提取用户信息
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
                    local_avatar = await self.storage.download_avatar(
                        user_info.get("avatar_url"), self.user_id
                    )

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
    async def fetch_likes(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """获取用户点赞列表 - 增量滚动模式，边滚动边解析避免长时间等待"""
        # 访问用户主页
        url = f"{self.ZHIHU_BASE}/people/{self.user_id}"
        logger.info(f"访问用户主页: {url}")

        await self._delay()
        await self.page.goto(url)

        # 等待页面加载
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(2)
        except Exception:
            pass

        # 增量滚动：分批滚动并解析，避免长时间等待
        logger.info(f"开始增量滚动，目标数量: {limit}...")
        all_activities = []
        last_count = 0
        no_new_content_count = 0
        max_no_new_content = 3
        max_scroll_rounds = 20  # 最多滚动20轮，防止无限滚动
        scroll_round = 0

        while len(all_activities) < limit + offset and scroll_round < max_scroll_rounds:
            scroll_round += 1
            logger.debug(f"第 {scroll_round} 轮滚动...")

            # 每次滚动3次
            for _ in range(3):
                await self.page.evaluate(
                    """() => {
                        window.scrollBy(0, 800);
                    }"""
                )
                await asyncio.sleep(0.8)

            # 获取当前页面内容并解析
            content = await self.page.content()
            activities = self._parse_activities_from_html(content)

            if not activities:
                no_new_content_count += 1
                if no_new_content_count >= max_no_new_content:
                    logger.info("没有解析到活动数据，停止滚动")
                    break
                continue

            # 检查是否有新内容
            if len(activities) > last_count:
                new_count = len(activities) - last_count
                logger.info(f"第 {scroll_round} 轮滚动后: 共 {len(activities)} 条 (+{new_count})")
                all_activities = activities
                last_count = len(activities)
                no_new_content_count = 0
            else:
                no_new_content_count += 1
                logger.debug(f"没有新内容，连续 {no_new_content_count} 次")

                # 尝试点击"查看更多"按钮
                try:
                    has_more = await self.page.evaluate(
                        """() => {
                            const btn = document.querySelector(
                                '.ActivityItem-more, .ContentItem-more, '
                                + '.FeedItem-more, [data-za-detail-view-element_name="ViewMore"]'
                            );
                            if (btn) { btn.click(); return true; }
                            return false;
                        }"""
                    )
                    if has_more:
                        logger.debug("点击了'查看更多'按钮")
                        await asyncio.sleep(1)
                        continue
                except Exception:
                    pass

            # 如果已经获取足够内容，提前退出
            if len(all_activities) >= limit + offset:
                logger.info(f"已获取足够内容 ({len(all_activities)} 条)，停止滚动")
                break

            # 连续多次没有新内容，停止滚动
            if no_new_content_count >= max_no_new_content:
                logger.info(f"连续 {max_no_new_content} 次没有新内容，停止滚动")
                break

        if all_activities:
            logger.info(f"共解析到 {len(all_activities)} 条，返回 [{offset}:{offset + limit}]")
            return all_activities[offset : offset + limit]

        # 如果页面解析失败，尝试访问 API
        logger.info("页面解析失败，尝试直接访问 API...")
        api_url = f"{self.API_BASE}/members/{self.user_id}/activities?limit={limit}&offset={offset}"

        await self._delay()
        await self.page.goto(api_url)

        content = await self.page.content()
        soup = BeautifulSoup(content, "lxml")
        text = soup.find("pre")

        if text:
            try:
                raw_text = text.get_text()
                data = json.loads(raw_text)
                activities = data.get("data", [])
                paging = data.get("paging", {})
                logger.info(
                    f"API 返回: {len(activities)} 条记录, total={paging.get('totals', 'unknown')}"
                )
                return activities
            except json.JSONDecodeError as e:
                logger.warning(f"解析 API 响应失败: {e}")
        else:
            logger.warning("API 响应中没有找到 JSON 数据")

        return []

    def _parse_activities_from_html(self, html: str) -> list[dict]:
        """从 HTML 页面中解析活动数据"""
        activities = []
        soup = BeautifulSoup(html, "lxml")

        # 查找所有活动项
        activity_items = soup.find_all("div", class_="List-item")
        logger.debug(f"Found {len(activity_items)} activity items in HTML")

        for item in activity_items:
            try:
                # 获取活动类型和时间
                meta_div = item.find("div", class_="ActivityItem-meta")
                if not meta_div:
                    continue

                meta_title = meta_div.find("span", class_="ActivityItem-metaTitle")
                time_span = meta_div.find_all("span")
                created_time_str = time_span[-1].text if len(time_span) > 1 else ""

                # 只处理点赞活动
                if not meta_title or "赞同" not in meta_title.text:
                    continue

                # 确定类型
                is_article = "文章" in meta_title.text
                verb = "MEMBER_VOTEUP_ARTICLE" if is_article else "MEMBER_VOTEUP_ANSWER"

                # 获取内容项
                content_item = item.find("div", class_="ContentItem")
                if not content_item:
                    continue

                # 提取 data-zop 属性
                data_zop = content_item.get("data-zop", "{}")
                try:
                    zop_data = json.loads(data_zop)
                except json.JSONDecodeError:
                    zop_data = {}

                answer_id = str(zop_data.get("itemId", ""))

                # 从 title 中提取问题信息和链接
                title_elem = content_item.find("h2", class_="ContentItem-title")
                question_title = ""
                question_id = ""
                answer_href = ""

                if title_elem:
                    link = title_elem.find("a")
                    if link:
                        question_title = link.get_text(strip=True)
                        answer_href = link.get("href", "")
                        # 从 href 中提取 question_id
                        # 格式: //www.zhihu.com/question/{question_id}/answer/{answer_id}
                        if "/question/" in answer_href:
                            parts = answer_href.split("/")
                            for i, part in enumerate(parts):
                                if part == "question" and i + 1 < len(parts):
                                    question_id = parts[i + 1]
                                    break

                # 获取作者信息
                author_info = content_item.find("div", class_="AuthorInfo")
                author_name = ""
                author_id = ""
                author_headline = ""

                if author_info:
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
                        href = name_elem.get("href", "")
                        # 提取用户ID，处理多种格式
                        if "/people/" in href:
                            author_id = href.split("/people/")[-1].split("?")[0].strip("/")
                        elif href.startswith("//"):
                            # 格式: //www.zhihu.com/people/xxx
                            author_id = href.split("/")[-1].split("?")[0]
                        else:
                            author_id = href.strip("/")

                    # 获取作者签名
                    badge = author_info.find("div", class_="AuthorInfo-badgeText")
                    if badge:
                        author_headline = badge.get_text(strip=True)

                # 获取赞同数和评论数
                voteup_count = 0
                comment_count = 0
                actions = content_item.find("div", class_="ContentItem-actions")
                if actions:
                    # 查找赞同按钮
                    vote_btn = actions.find("button", class_="VoteButton")
                    if vote_btn:
                        text = vote_btn.get_text(strip=True)
                        # 提取数字
                        import re

                        numbers = re.findall(r"\d+", text)
                        if numbers:
                            voteup_count = int(numbers[0])

                    # 查找评论按钮/链接
                    comment_btn = actions.find("a", class_="ContentItem-action") or actions.find(
                        "button", class_="ContentItem-action"
                    )
                    if comment_btn:
                        text = comment_btn.get_text(strip=True)
                        # 提取数字，如 "10 条评论" 或 "评论"
                        numbers = re.findall(r"\d+", text)
                        if numbers:
                            comment_count = int(numbers[0])
                        elif "评论" in text:
                            # 有评论按钮但没有数字，可能是0或有评论但数字未显示
                            comment_count = 0

                # 解析时间字符串为时间戳
                created_time = 0
                if created_time_str:
                    try:
                        from datetime import datetime

                        dt = datetime.strptime(created_time_str, "%Y-%m-%d %H:%M")
                        created_time = int(dt.timestamp() * 1000)  # 毫秒时间戳
                    except ValueError:
                        pass

                # 构建完整的活动数据，符合 process_answer 期望的格式
                activity = {
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
                        "author": {
                            "id": author_id,
                            "name": author_name,
                            "headline": author_headline,
                        },
                        "voteup_count": voteup_count,
                        "comment_count": comment_count,
                        "created_time": created_time,
                        "updated_time": created_time,
                    },
                }

                activities.append(activity)
                logger.debug(f"Parsed activity: {answer_id} - {question_title[:50]}")

            except Exception as e:
                logger.debug(f"Failed to parse activity item: {e}")
                continue

        return activities

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def fetch_answer_detail(self, answer_id: str) -> dict | None:
        """获取回答详情"""
        url = f"{self.API_BASE}/answers/{answer_id}"
        params = {"include": "content,voteup_count,comment_count,created_time,updated_time,author"}

        full_url = f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        await self._delay()
        await self.page.goto(full_url)

        content = await self.page.content()
        soup = BeautifulSoup(content, "lxml")
        text = soup.find("pre")

        if text:
            try:
                return json.loads(text.get_text())
            except json.JSONDecodeError:
                pass

        return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def fetch_answer_page(self, question_id: str, answer_id: str) -> str | None:
        """获取回答页面 HTML，包含完整内容和样式"""
        url = f"{self.ZHIHU_BASE}/question/{question_id}/answer/{answer_id}"

        await self._delay()
        await self.page.goto(url, wait_until="networkidle")

        # 等待内容加载
        try:
            await self.page.wait_for_selector(".RichContent", timeout=10000)
        except Exception:
            logger.warning(f"等待内容超时: {answer_id}")

        # 点击所有"展开全文"按钮
        await self._expand_all_content()

        # 滚动页面以加载所有内容
        await self._scroll_page()

        # 获取页面内容和样式
        content = await self._get_page_with_styles()
        return content

    async def _expand_all_content(self):
        """点击所有'展开全文'按钮以获取完整内容"""
        try:
            # 查找所有展开按钮
            expand_buttons = await self.page.query_selector_all(
                'button.ContentItem-more, button.Button:has-text("阅读全文"), '
                'button.Button:has-text("展开全文")'
            )

            for button in expand_buttons[:5]:  # 限制最多点击5个
                try:
                    await button.click()
                    await asyncio.sleep(0.5)  # 等待内容展开
                except Exception:
                    continue

            # 也尝试通过 JavaScript 点击
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
        # 获取原始 HTML
        html_content = await self.page.content()

        # 获取所有样式表内容
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def fetch_comments(self, answer_id: str, limit: int = 20) -> list[dict]:
        """获取评论"""
        url = f"{self.API_BASE}/answers/{answer_id}/root_comments"
        params = {"limit": limit, "offset": 0, "order": "normal", "status": "open"}

        full_url = f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        await self._delay()
        logger.debug(f"请求评论 API: {full_url}")
        await self.page.goto(full_url)

        content = await self.page.content()
        soup = BeautifulSoup(content, "lxml")
        text = soup.find("pre")

        if text:
            try:
                raw_text = text.get_text()
                logger.debug(f"评论 API 原始响应: {raw_text[:500]}...")
                data = json.loads(raw_text)
                comments = data.get("data", [])
                logger.debug(f"评论 API 返回: {len(comments)} 条评论")
                # 打印数据结构用于调试
                if comments:
                    logger.debug(
                        f"第一条评论结构: {list(comments[0].keys()) if isinstance(comments[0], dict) else type(comments[0])}"
                    )
                return comments
            except json.JSONDecodeError as e:
                logger.warning(f"解析评论 JSON 失败: {e}")
            except Exception as e:
                logger.warning(f"获取评论失败: {e}")
        else:
            logger.warning(f"评论 API 返回无内容: {answer_id}")

        return []

    async def _scroll_page(self):
        """滚动页面加载内容"""
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
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)  # 等待内容加载

            # 获取新的页面高度
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

    async def process_answer(self, activity: dict, liked_time: datetime) -> bool:
        """处理单个回答"""
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

            # 如果是已存在的记录且没有更新，跳过
            if existing:
                logger.debug(f"回答已存在，跳过: {question_title[:50]}...")
                return False

            # 获取完整页面内容
            logger.info(f"获取回答: {question_title[:60]}...")
            page_html = await self.fetch_answer_page(question_id, answer_id)

            if not page_html:
                logger.warning(f"无法获取页面内容: {answer_id}")
                return False

            # 解析页面获取内容
            soup = BeautifulSoup(page_html, "lxml")

            # 提取回答内容
            content_elem = soup.select_one(".RichContent-inner")
            if content_elem:
                content_html = str(content_elem)
                content_text = content_elem.get_text(separator="\n", strip=True)
            else:
                content_html = target.get("content", "")
                content_text = BeautifulSoup(content_html, "lxml").get_text(
                    separator="\n", strip=True
                )

            # 提取作者详细信息（头像、名称、签名）
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
                    if avatar_img and avatar_img.get("src"):
                        author_avatar_url = avatar_img.get("src")
                        logger.debug(f"提取到作者头像: {author_avatar_url[:60]}...")
                        break

                # 提取作者名（如果API中没有）
                if not author_name:
                    name_elem = author_info_elem.select_one("a.UserLink-link, .AuthorInfo-name")
                    if name_elem:
                        author_name_from_page = name_elem.get_text(strip=True)
                        logger.debug(f"从页面提取到作者名: {author_name_from_page}")

                # 提取签名
                headline_elem = author_info_elem.select_one(
                    ".AuthorInfo-badgeText, .AuthorInfo-headline"
                )
                if headline_elem:
                    author_headline = headline_elem.get_text(strip=True)

            # 使用页面提取的作者名
            if author_name_from_page and not author_name:
                author_name = author_name_from_page

            # 如果从页面没提取到签名，使用 API 数据中的
            if not author_headline:
                author_headline = author.get("headline", "")

            # 下载作者头像
            local_author_avatar = None
            if author_avatar_url and author_id:
                local_author_avatar = await self.storage.download_avatar(
                    author_avatar_url, author_id
                )
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
                "updated_time": (
                    self._parse_timestamp(updated_time).isoformat() if updated_time else ""
                ),
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
                "created_time": self._parse_timestamp(created_time) if created_time else None,
                "updated_time": self._parse_timestamp(updated_time) if updated_time else None,
                "liked_time": liked_time,
                "html_path": html_path,
                "original_url": f"{self.ZHIHU_BASE}/question/{question_id}/answer/{answer_id}",
                "has_comments": False,
                "extra_meta": {
                    "author_headline": author_headline,
                },
            }

            is_new = self.db.save_answer(answer_data)

            if is_new:
                self.new_items += 1
            else:
                self.updated_items += 1

            # 如果有评论，立即获取
            if comment_count > 0:
                logger.debug(f"回答有 {comment_count} 条评论，开始获取...")
                await self.process_comments(answer_id)

            return True

        except Exception as e:
            logger.exception(f"处理回答失败: {e}")
            return False

    async def process_comments(self, answer_id: str):
        """处理评论"""
        try:
            answer = self.db.get_answer_by_id(answer_id)
            if not answer or answer.has_comments:
                logger.debug(
                    f"跳过评论处理: answer_id={answer_id}, exists={bool(answer)}, has_comments={answer.has_comments if answer else 'N/A'}"
                )
                return

            # 计算评论获取上限，-1 表示使用较大默认值
            comment_limit = 1000 if self.max_comments < 0 else self.max_comments
            logger.info(f"获取评论: {answer_id} (预期 {answer.comment_count} 条, 上限 {comment_limit} 条)")
            comments_data = await self.fetch_comments(answer_id, limit=comment_limit)
            logger.info(f"评论 API 返回 {len(comments_data)} 条数据")

            if not comments_data:
                # 标记为已处理（即使没有评论）避免重复请求
                self.db.mark_answer_has_comments(answer_id)
                logger.info(f"回答无评论: {answer_id}")
                return

            comments_to_save = []
            for item in comments_data:
                comment = item.get("comment", item)  # 处理不同格式
                author_info = comment.get("author", {})
                comment_info = {
                    "id": str(comment.get("id", "")),
                    "answer_id": answer_id,
                    "author_id": author_info.get("id", ""),
                    "author_name": author_info.get("name", "匿名用户"),
                    "author_avatar_url": author_info.get("avatar_url", ""),
                    "content": comment.get("content", ""),
                    "like_count": comment.get("like_count", 0),
                    "created_time": (
                        self._parse_timestamp(comment.get("created_time", 0))
                        if comment.get("created_time")
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

        except Exception as e:
            logger.exception(f"处理评论失败: {e}")

    async def scan_likes(self, max_items: int = 50, progress_callback: Callable | None = None):
        """扫描用户点赞内容 - 支持断点续传"""
        logger.info(f"开始扫描用户 {self.user_id} 的点赞内容 (max={max_items})...")

        # 确保用户记录在数据库中存在
        user_created = self.db.add_user(self.user_id, self.user_id)
        logger.info(f"用户记录检查: user_id={self.user_id}, created={user_created}")

        # 获取用户详细信息（名称、头像、签名）
        await self._fetch_user_profile()

        self.new_items = 0
        self.updated_items = 0
        scanned = 0
        offset = 0
        limit = 10  # 减少每批数量，更频繁保存
        processed_ids = set()  # 防止重复处理

        # 获取已处理的回答ID，支持断点续传
        existing_answers = self.db.get_user_answer_ids(self.user_id)
        processed_ids.update(existing_answers)
        logger.info(f"已有 {len(processed_ids)} 条回答，将跳过重复内容")

        # -1 表示无限制
        no_limit = max_items < 0

        while no_limit or scanned < max_items:
            batch_size = limit if no_limit else min(limit, max_items - scanned)
            activities = await self.fetch_likes(limit=batch_size, offset=offset)

            if not activities:
                logger.info("没有更多活动数据")
                break

            batch_new = 0
            for activity in activities:
                # 只处理点赞回答
                if (
                    activity.get("verb") != "MEMBER_VOTEUP_ARTICLE"
                    and activity.get("verb") != "MEMBER_VOTEUP_ANSWER"
                ):
                    continue

                # 获取回答ID用于去重
                target = activity.get("target", {})
                answer_id = str(target.get("id", ""))

                # 如果已经处理过，跳过
                if answer_id and answer_id in processed_ids:
                    logger.debug(f"跳过已处理的回答: {answer_id}")
                    scanned += 1
                    if not no_limit and scanned >= max_items:
                        break
                    continue

                # 解析点赞时间
                created_time = activity.get("created_time", 0)
                liked_time = (
                    self._parse_timestamp(created_time) if created_time else get_beijing_now()
                )

                # 处理回答（会立即保存到数据库和文件）
                success = await self.process_answer(activity, liked_time)
                if success and answer_id:
                    processed_ids.add(answer_id)
                    batch_new += 1

                scanned += 1

                if progress_callback:
                    progress_callback(scanned, max_items if not no_limit else -1)

                if not no_limit and scanned >= max_items:
                    break

            logger.info(f"本批处理: {len(activities)} 条，新增: {batch_new} 条，累计: {scanned}")

            # 每批处理完后立即更新同步时间（断点续传）
            if batch_new > 0:
                self.db.update_user_sync_time(self.user_id)

            offset += len(activities)

            # 如果没有更多数据，退出
            if len(activities) < batch_size:
                logger.info("活动数据不足，结束扫描")
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
