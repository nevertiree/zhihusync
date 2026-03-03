"""图片生成模块 - 将 HTML 渲染为长图.

该模块提供 HTML 转长图功能，模拟知乎截图效果。
使用 Playwright 进行渲染，支持多种截图模式。

Examples:
    >>> from image_generator import ImageGenerator
    >>> generator = ImageGenerator()
    >>> image_path = await generator.generate_from_html_file("answer.html")
    >>> # 或者从 URL 生成
    >>> image_path = await generator.generate_from_url("http://localhost:6067/data/html/xxx.html")
"""

import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from loguru import logger
from playwright.async_api import Browser, BrowserContext, async_playwright


class ImageGenerator:
    """图片生成器 - 将 HTML 渲染为长图.

    使用 Playwright 渲染 HTML 并截取完整页面截图，
    生成类似知乎原生界面的长图效果。

    Attributes:
        output_dir: 图片输出目录.
        browser_type: 浏览器类型.
        viewport_width: 视口宽度.
        _browser: Playwright 浏览器实例.
        _context: 浏览器上下文.

    Examples:
        >>> generator = ImageGenerator("./data/images", viewport_width=694)
        >>> async with generator:
        ...     path = await generator.generate_from_html_file("./data/html/xxx.html")
    """

    # 默认配置
    DEFAULT_VIEWPORT_WIDTH = 694  # 知乎内容区宽度
    DEFAULT_VIEWPORT_HEIGHT = 1080
    DEFAULT_DEVICE_SCALE_FACTOR = 2  # 2x 分辨率，更清晰

    def __init__(
        self,
        output_dir: str = "/app/data/static/images",
        browser_type: str = "chromium",
        viewport_width: int = 694,
        device_scale_factor: int = 2,
    ):
        """初始化图片生成器.

        Args:
            output_dir: 图片输出目录.
            browser_type: 浏览器类型 (chromium/firefox/webkit).
            viewport_width: 视口宽度，默认 694 (知乎内容区宽度).
            device_scale_factor: 设备缩放比例，默认 2 倍图.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.browser_type = browser_type
        self.viewport_width = viewport_width
        self.viewport_height = self.DEFAULT_VIEWPORT_HEIGHT
        self.device_scale_factor = device_scale_factor

        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._playwright = None

        logger.info(f"图片生成器初始化: {output_dir}, {self.viewport_width}x{self.viewport_height}")

    async def __aenter__(self):
        """异步上下文管理器入口."""
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口."""
        await self._close_browser()

    async def _init_browser(self):
        """初始化浏览器."""
        if self._browser:
            return

        self._playwright = await async_playwright().start()

        browser_type = getattr(self._playwright, self.browser_type, self._playwright.chromium)

        self._browser = await browser_type.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
            ],
        )

        # 创建上下文，设置视口和设备缩放
        self._context = await self._browser.new_context(
            viewport={
                "width": self.viewport_width,
                "height": self.viewport_height,
            },
            device_scale_factor=self.device_scale_factor,
        )

        logger.debug("浏览器初始化完成")

    async def _close_browser(self):
        """关闭浏览器."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.debug("浏览器已关闭")

    def _get_output_path(self, identifier: str, suffix: str = "") -> Path:
        """生成输出文件路径.

        Args:
            identifier: 标识符（如回答ID或哈希值）.
            suffix: 可选的后缀.

        Returns:
            Path: 输出文件路径.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if suffix:
            filename = f"zhihu_{identifier}_{suffix}_{timestamp}.png"
        else:
            filename = f"zhihu_{identifier}_{timestamp}.png"
        return self.output_dir / filename

    def _generate_id_from_html(self, html_content: str) -> str:
        """从 HTML 内容生成唯一标识.

        Args:
            html_content: HTML 内容.

        Returns:
            str: 短哈希值.
        """
        return hashlib.md5(html_content.encode()).hexdigest()[:12]

    async def generate_from_html_file(
        self,
        html_path: str,
        output_path: Optional[str] = None,
        full_page: bool = True,
        add_watermark: bool = True,
        clip_to_content: bool = True,
    ) -> str:
        """从 HTML 文件生成长图.

        Args:
            html_path: HTML 文件路径.
            output_path: 可选的自定义输出路径.
            full_page: 是否截取完整页面.
            add_watermark: 是否添加水印.
            clip_to_content: 是否裁剪到内容区域.

        Returns:
            str: 生成的图片路径.
        """
        html_file = Path(html_path)
        if not html_file.exists():
            raise FileNotFoundError(f"HTML 文件不存在: {html_path}")

        # 读取 HTML 内容
        html_content = html_file.read_text(encoding="utf-8")

        # 生成输出路径
        if not output_path:
            answer_id = html_file.stem.split("_")[-1] if "_" in html_file.stem else "unknown"
            output_path = self._get_output_path(answer_id)
        else:
            output_path = Path(output_path)

        # 生成图片
        return await self.generate_from_html(
            html_content=html_content,
            output_path=str(output_path),
            full_page=full_page,
            add_watermark=add_watermark,
            clip_to_content=clip_to_content,
        )

    async def generate_from_html(
        self,
        html_content: str,
        output_path: str,
        full_page: bool = True,
        add_watermark: bool = True,
        clip_to_content: bool = True,
    ) -> str:
        """从 HTML 内容生成长图.

        Args:
            html_content: HTML 内容.
            output_path: 输出图片路径.
            full_page: 是否截取完整页面.
            add_watermark: 是否添加水印.
            clip_to_content: 是否裁剪到内容区域.

        Returns:
            str: 生成的图片路径.
        """
        if not self._browser:
            await self._init_browser()

        page = await self._context.new_page()

        try:
            # 添加截图专用样式
            screenshot_styles = """
            <style>
                .screenshot-mode {
                    background: #ffffff !important;
                }
                .screenshot-mode .zhihu-page {
                    padding: 0 !important;
                    max-width: 694px !important;
                }
                .screenshot-mode .zhihu-card {
                    box-shadow: none !important;
                    border-radius: 0 !important;
                }
                .screenshot-watermark {
                    position: fixed !important;
                    bottom: 10px !important;
                    right: 10px !important;
                    padding: 6px 12px !important;
                    background: rgba(0, 0, 0, 0.5) !important;
                    color: white !important;
                    font-size: 11px !important;
                    border-radius: 4px !important;
                    z-index: 99999 !important;
                    pointer-events: none !important;
                }
                /* 隐藏操作栏和备份信息，更像原生截图 */
                .screenshot-mode .answer-actions,
                .screenshot-mode .backup-info {
                    display: none !important;
                }
            </style>
            """

            # 插入截图样式和水印
            if "</head>" in html_content:
                html_content = html_content.replace("</head>", f"{screenshot_styles}</head>")

            # 添加截图模式类和水印
            if "<body" in html_content:
                html_content = html_content.replace("<body", '<body class="screenshot-mode"')

            if add_watermark and '<div class="screenshot-watermark"' not in html_content:
                watermark = '<div class="screenshot-watermark">zhihusync backup</div>'
                if "</body>" in html_content:
                    html_content = html_content.replace("</body>", f"{watermark}</body>")

            # 加载 HTML 内容
            await page.set_content(html_content, wait_until="networkidle")

            # 等待字体和样式加载完成
            await asyncio.sleep(0.5)

            # 获取页面尺寸
            dimensions = await page.evaluate(
                """
                () => {
                    const card = document.querySelector('.zhihu-card');
                    const content = document.querySelector('.RichContent');
                    const body = document.body;
                    return {
                        scrollWidth: Math.max(body.scrollWidth, card?.scrollWidth || 0),
                        scrollHeight: Math.max(body.scrollHeight, card?.scrollHeight || 0),
                        cardHeight: card?.offsetHeight || 0,
                        cardTop: card?.offsetTop || 0,
                    };
                }
            """
            )

            logger.debug(f"页面尺寸: {dimensions}")

            # 设置截图选项
            screenshot_options = {
                "path": output_path,
                "type": "png",
            }

            if full_page:
                screenshot_options["full_page"] = True

            # 如果指定了裁剪区域，计算裁剪参数
            if clip_to_content and dimensions["cardHeight"] > 0:
                # 获取 .zhihu-card 的位置和尺寸
                clip_box = await page.locator(".zhihu-card").bounding_box()
                if clip_box:
                    # 添加一些边距
                    padding = 20
                    screenshot_options["clip"] = {
                        "x": max(0, clip_box["x"] - padding),
                        "y": max(0, clip_box["y"] - padding),
                        "width": min(clip_box["width"] + padding * 2, self.viewport_width),
                        "height": clip_box["height"] + padding * 2,
                    }
                    # 不裁剪时禁用 full_page
                    screenshot_options["full_page"] = False

            # 截取图片
            await page.screenshot(**screenshot_options)

            logger.info(f"图片生成完成: {output_path}")
            return output_path

        finally:
            await page.close()

    async def generate_from_url(
        self,
        url: str,
        output_path: Optional[str] = None,
        wait_for_selector: Optional[str] = ".zhihu-card",
        full_page: bool = True,
    ) -> str:
        """从 URL 生成长图.

        Args:
            url: 页面 URL.
            output_path: 可选的输出路径.
            wait_for_selector: 等待加载的选择器.
            full_page: 是否截取完整页面.

        Returns:
            str: 生成的图片路径.
        """
        if not self._browser:
            await self._init_browser()

        page = await self._context.new_page()

        try:
            # 访问页面
            await page.goto(url, wait_until="networkidle")

            # 等待特定元素加载
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=5000)
                except Exception:
                    logger.warning(f"等待元素超时: {wait_for_selector}")

            # 额外等待确保字体加载
            await asyncio.sleep(1)

            # 生成输出路径
            if not output_path:
                url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                output_path = self._get_output_path(url_hash)

            # 截图
            await page.screenshot(
                path=output_path,
                full_page=full_page,
                type="png",
            )

            logger.info(f"图片生成完成: {output_path}")
            return output_path

        finally:
            await page.close()

    async def generate_answer_card(
        self,
        html_path: str,
        include_comments: bool = False,
        card_style: str = "default",
    ) -> str:
        """生成回答卡片图片（针对知乎回答优化的截图）.

        这是专门优化的方法，生成的图片更像从知乎 App/网页截图的效果。

        Args:
            html_path: HTML 文件路径.
            include_comments: 是否包含评论区.
            card_style: 卡片样式 (default/compact/minimal).

        Returns:
            str: 生成的图片路径.
        """
        html_file = Path(html_path)
        if not html_file.exists():
            raise FileNotFoundError(f"HTML 文件不存在: {html_path}")

        # 读取并修改 HTML
        html_content = html_file.read_text(encoding="utf-8")

        # 根据样式添加额外 CSS
        style_modifiers = {
            "compact": """
                .zhihu-page { max-width: 375px !important; }
                .RichContent { font-size: 14px !important; }
                .question-title { font-size: 18px !important; }
            """,
            "minimal": """
                .answer-header { display: none !important; }
                .answer-actions { display: none !important; }
                .backup-info { display: none !important; }
            """,
            "default": "",
        }

        extra_style = style_modifiers.get(card_style, "")
        if extra_style and "</style>" in html_content:
            html_content = html_content.replace("</style>", f"{extra_style}</style>")

        # 如果不包含评论，移除评论区
        if not include_comments and '<div class="comments-section">' in html_content:
            # 使用正则或简单替换移除评论区
            import re

            html_content = re.sub(
                r'<div class="comments-section">.*?</div>\s*</div>\s*<!-- end comments -->',
                "",
                html_content,
                flags=re.DOTALL,
            )

        # 生成输出路径
        answer_id = html_file.stem.split("_")[-1] if "_" in html_file.stem else "unknown"
        output_path = self._get_output_path(answer_id, suffix=card_style)

        # 生成图片
        return await self.generate_from_html(
            html_content=html_content,
            output_path=str(output_path),
            full_page=True,
            add_watermark=True,
            clip_to_content=False,
        )


# 同步包装函数（方便非异步代码调用）
def generate_image_sync(
    html_path: str, output_dir: str = "/app/data/static/images", **kwargs
) -> str:
    """同步方式生成图片（方便调用）.

    Args:
        html_path: HTML 文件路径.
        output_dir: 输出目录.
        **kwargs: 其他参数传递给 generate_from_html_file.

    Returns:
        str: 生成的图片路径.
    """

    async def _generate():
        async with ImageGenerator(output_dir=output_dir) as generator:
            return await generator.generate_from_html_file(html_path, **kwargs)

    return asyncio.run(_generate())


async def generate_answer_image(
    html_path: str,
    answer_id: str = "",
    output_dir: str = "/app/data/static/images",
) -> Tuple[bool, str]:
    """生成回答图片的便捷函数.

    Args:
        html_path: HTML 文件路径.
        answer_id: 回答ID（用于日志）.
        output_dir: 输出目录.

    Returns:
        Tuple[bool, str]: (是否成功, 结果消息/路径).
    """
    try:
        async with ImageGenerator(output_dir=output_dir) as generator:
            image_path = await generator.generate_from_html_file(
                html_path=html_path,
                full_page=True,
                add_watermark=True,
            )
            return True, image_path
    except Exception as e:
        logger.exception(f"生成图片失败: {e}")
        return False, str(e)
