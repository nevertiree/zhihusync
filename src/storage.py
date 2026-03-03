"""存储模块 - 管理 HTML 和静态资源保存.

该模块提供 HTML 文件存储、图片下载和静态资源管理功能。
支持异步下载图片，处理 HTML 内容，确保离线可访问。

Examples:
    >>> from storage import StorageManager
    >>> storage = StorageManager("./html", "./static", "./images")
    >>> await storage.save_answer_html("12345", "标题", html_content)
"""

import asyncio
import hashlib
import re
from pathlib import Path
from typing import Optional, Set
from urllib.parse import urlparse

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from loguru import logger


class StorageManager:
    """存储管理器.

    管理 HTML 文件、图片和静态资源的存储。
    支持异步下载，缓存已下载图片避免重复下载。

    Attributes:
        html_path: HTML 文件存储路径.
        static_path: 静态资源存储路径.
        images_path: 图片存储路径.
        download_images: 是否下载图片.
        _downloaded_images: 已下载图片缓存集合.

    Examples:
        >>> storage = StorageManager(
        ...     html_path="./data/html",
        ...     static_path="./data/static",
        ...     images_path="./data/static/images",
        ...     download_images=True
        ... )
        >>> filepath = await storage.save_answer_html(
        ...     answer_id="123456",
        ...     question_title="问题标题",
        ...     html_content="<html>...</html>"
        ... )
    """

    # 知乎 CSS 样式 URL 模式
    ZHIHU_CSS_PATTERNS = [
        "static.zhihu.com",
        "unpkg.zhimg.com",
        "pic1.zhimg.com",
    ]

    def __init__(
        self, html_path: str, static_path: str, images_path: str, download_images: bool = True
    ):
        """初始化存储管理器.

        Args:
            html_path: HTML 文件存储目录路径.
            static_path: 静态资源存储目录路径.
            images_path: 图片存储目录路径.
            download_images: 是否下载图片.
        """
        self.html_path = Path(html_path)
        self.static_path = Path(static_path)
        self.images_path = Path(images_path)
        self.download_images = download_images

        # 确保目录存在
        self.html_path.mkdir(parents=True, exist_ok=True)
        self.static_path.mkdir(parents=True, exist_ok=True)
        self.images_path.mkdir(parents=True, exist_ok=True)

        # 已下载的图片缓存
        self._downloaded_images: Set[str] = set()

        logger.info(f"存储管理器初始化: html={html_path}, static={static_path}")

    def _sanitize_filename(self, text: str, max_length: int = 100) -> str:
        """清理文件名.

        移除非法字符，替换空格，限制长度。

        Args:
            text: 原始文件名.
            max_length: 最大长度.

        Returns:
            str: 清理后的文件名.
        """
        # 移除非法字符
        text = re.sub(r'[<>:"/\\|?*]', "", text)
        text = re.sub(r"\s+", "_", text)
        # 限制长度
        if len(text) > max_length:
            text = text[:max_length]
        return text.strip("_")

    def _generate_file_hash(self, content: str, length: int = 8) -> str:
        """生成内容哈希用于去重.

        Args:
            content: 文件内容.
            length: 哈希长度.

        Returns:
            str: 短哈希字符串.
        """
        return hashlib.md5(content.encode()).hexdigest()[:length]

    def get_answer_filepath(
        self, answer_id: str, question_title: str, content: Optional[str] = None
    ) -> Path:
        """生成回答文件路径.

        格式: {html_path}/{question_title}_{hash}_{answer_id}.html

        Args:
            answer_id: 回答ID.
            question_title: 问题标题.
            content: 文件内容(用于生成哈希).

        Returns:
            Path: 生成的文件路径.
        """
        safe_title = self._sanitize_filename(question_title)
        if content:
            content_hash = self._generate_file_hash(content)
            filename = f"{safe_title}_{content_hash}_{answer_id}.html"
        else:
            filename = f"{safe_title}_{answer_id}.html"
        return self.html_path / filename

    async def save_answer(
        self,
        answer_id: str,
        question_id: str,
        question_title: str,
        html_content: str,
        page_metadata: dict = None,
    ) -> str:
        """保存回答 HTML 内容.

        处理 HTML 内容，添加元数据，下载图片，保存到文件。

        Args:
            answer_id: 回答ID.
            question_id: 问题ID.
            question_title: 问题标题.
            html_content: HTML 内容.
            page_metadata: 页面元数据字典.

        Returns:
            str: 保存的文件路径.
        """
        # 构建完整的 HTML 文档
        full_html = self._build_full_html(
            question_title=question_title,
            content_html=html_content,
            metadata=page_metadata,
        )

        # 处理 HTML 并下载图片
        processed_html = await self._process_html(full_html, answer_id)

        # 生成文件路径
        filepath = self.get_answer_filepath(answer_id, question_title, html_content)

        # 保存文件
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(processed_html)

        logger.info(f"保存 HTML: {filepath}")
        return str(filepath)

    def _build_full_html(
        self, question_title: str, content_html: str, metadata: dict = None
    ) -> str:
        """构建完整的 HTML 文档.

        Args:
            question_title: 问题标题.
            content_html: 内容 HTML.
            metadata: 元数据字典.

        Returns:
            str: 完整的 HTML 文档.
        """
        meta_str = ""
        if metadata:
            for key, value in metadata.items():
                meta_str += f'<meta name="{key}" content="{value}">\n'

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{question_title} - 知乎备份</title>
    {meta_str}
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
            sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;
            line-height: 1.6; }}
        h1 {{ color: #121212; font-size: 22px; margin-bottom: 16px; }}
        .author-info {{ color: #646464; font-size: 14px; margin-bottom: 16px;
            padding-bottom: 16px; border-bottom: 1px solid #e5e5e5; }}
        .content {{ font-size: 16px; color: #121212; }}
        .content img {{ max-width: 100%; height: auto; }}
        .content p {{ margin: 0.8em 0; }}
        .metadata {{ margin-top: 32px; padding-top: 16px;
            border-top: 1px solid #e5e5e5; font-size: 12px; color: #999; }}
    </style>
</head>
<body>
    <article>
        <h1>{question_title}</h1>
        <div class="content">
            {content_html}
        </div>
    </article>
</body>
</html>"""

    async def save_answer_html(self, answer_id: str, question_title: str, html_content: str) -> str:
        """保存回答 HTML 内容 (简化版).

        处理 HTML 内容，下载图片，保存到文件。

        Args:
            answer_id: 回答ID.
            question_title: 问题标题.
            html_content: HTML 内容.

        Returns:
            str: 保存的文件路径.
        """
        return await self.save_answer(
            answer_id=answer_id,
            question_id="",
            question_title=question_title,
            html_content=html_content,
            page_metadata=None,
        )

    async def _process_html(self, html_content: str, answer_id: str) -> str:
        """处理 HTML 内容.

        提取并下载图片，替换为本地路径。

        Args:
            html_content: 原始 HTML.
            answer_id: 回答ID(用于组织图片).

        Returns:
            str: 处理后的 HTML.
        """
        soup = BeautifulSoup(html_content, "lxml")

        # 查找所有图片
        img_tasks = []
        for img in soup.find_all("img"):
            src = img.get("data-original") or img.get("src")
            if src:
                task = self._download_and_replace_image(img, src, answer_id)
                img_tasks.append(task)

        # 并发下载图片
        if img_tasks:
            await asyncio.gather(*img_tasks, return_exceptions=True)

        return str(soup)

    async def _download_and_replace_image(self, img_tag, src: str, answer_id: str) -> None:
        """下载图片并替换 src.

        Args:
            img_tag: BeautifulSoup img 标签.
            src: 图片 URL.
            answer_id: 回答ID.
        """
        if src in self._downloaded_images:
            # 使用已下载的图片
            local_path = self._get_local_image_path(src)
            img_tag["src"] = local_path
            return

        try:
            local_path = await self._download_image(src, answer_id)
            if local_path:
                img_tag["src"] = local_path
                self._downloaded_images.add(src)
        except Exception as e:
            logger.warning(f"下载图片失败 {src}: {e}")

    def _get_local_image_path(self, original_url: str) -> str:
        """获取图片本地路径.

        Args:
            original_url: 原始图片 URL.

        Returns:
            str: 相对路径.
        """
        url_hash = hashlib.md5(original_url.encode()).hexdigest()[:16]
        ext = Path(urlparse(original_url).path).suffix or ".jpg"
        return f"../static/images/{url_hash}{ext}"

    async def _download_image(self, url: str, answer_id: str) -> Optional[str]:
        """下载单张图片.

        Args:
            url: 图片 URL.
            answer_id: 回答ID.

        Returns:
            Optional[str]: 本地路径，失败返回None.
        """
        if not self.download_images:
            return None

        if url in self._downloaded_images:
            return self._get_local_image_path(url)

        try:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
            ext = Path(urlparse(url).path).suffix or ".jpg"
            local_filename = f"{url_hash}{ext}"
            local_path = self.images_path / local_filename

            # 检查是否已存在
            if local_path.exists():
                self._downloaded_images.add(url)
                return self._get_local_image_path(url)

            # 下载图片
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        content = await response.read()
                        async with aiofiles.open(local_path, "wb") as f:
                            await f.write(content)
                        self._downloaded_images.add(url)
                        logger.debug(f"下载图片: {url} -> {local_path}")
                        return self._get_local_image_path(url)
        except Exception as e:
            logger.warning(f"下载图片失败 {url}: {e}")

        return None

    def check_answer_exists(self, answer_id: str, content: Optional[str] = None) -> bool:
        """检查回答是否已存在.

        Args:
            answer_id: 回答ID.
            content: 内容(用于匹配哈希).

        Returns:
            bool: 存在返回True.
        """
        pattern = f"*{answer_id}.html"
        matches = list(self.html_path.glob(pattern))

        if not matches or not content:
            return bool(matches)

        # 检查内容哈希
        content_hash = self._generate_file_hash(content)
        for match in matches:
            if content_hash in match.name:
                return True

        return False

    def get_storage_stats(self) -> dict:
        """获取存储统计.

        Returns:
            dict: 统计信息.
        """
        html_files = list(self.html_path.glob("*.html"))
        image_files = list(self.images_path.glob("*"))

        total_html_size = sum(f.stat().st_size for f in html_files)
        total_image_size = sum(f.stat().st_size for f in image_files if f.is_file())

        return {
            "html_count": len(html_files),
            "image_count": len(image_files),
            "html_size_mb": round(total_html_size / 1024 / 1024, 2),
            "image_size_mb": round(total_image_size / 1024 / 1024, 2),
        }
