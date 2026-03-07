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
from typing import Any
from urllib.parse import urlparse

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from loguru import logger


class StorageManager:
    """存储管理器.

    管理 HTML 文件、图片和静态资源的存储。
    支持异步下载，缓存已下载图片避免重复下载。
    图片分类存储：头像和回答图片分开存放。

    Attributes:
        html_path: HTML 文件存储路径.
        static_path: 静态资源存储路径.
        images_path: 图片根目录路径.
        avatars_path: 头像存储路径.
        answers_images_path: 回答图片存储路径.
        download_images: 是否下载图片.
        _downloaded_images: 已下载图片缓存集合.
        _downloaded_avatars: 已下载头像缓存集合.

    Examples:
        >>> storage = StorageManager(
        ...     html_path="./data/html",
        ...     static_path="./data/static",
        ...     images_path="./data/images",
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

    def __init__(self, html_path: str, static_path: str, images_path: str, download_images: bool = True):
        """初始化存储管理器.

        Args:
            html_path: HTML 文件存储目录路径.
            static_path: 静态资源存储目录路径.
            images_path: 图片根目录路径(下分 avatars 和 answers 子目录).
            download_images: 是否下载图片.
        """
        self.html_path = Path(html_path)
        self.static_path = Path(static_path)
        self.images_path = Path(images_path)
        # 图片分类目录
        self.avatars_path = self.images_path / "avatars"
        self.answers_images_path = self.images_path / "answers"
        self.download_images = download_images

        # 确保目录存在
        self.html_path.mkdir(parents=True, exist_ok=True)
        self.static_path.mkdir(parents=True, exist_ok=True)
        self.images_path.mkdir(parents=True, exist_ok=True)
        self.avatars_path.mkdir(parents=True, exist_ok=True)
        self.answers_images_path.mkdir(parents=True, exist_ok=True)

        # 已下载的图片缓存
        self._downloaded_images: set[str] = set()
        self._downloaded_avatars: set[str] = set()

        logger.info(f"存储管理器初始化: html={html_path}, static={static_path}, images={images_path}")

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

    def get_answer_filepath(self, answer_id: str, question_title: str, content: str | None = None) -> Path:
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
        page_metadata: dict | None = None,
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

    def _build_full_html(self, question_title: str, content_html: str, metadata: dict | None = None) -> str:
        """构建完整的 HTML 文档 - 使用知乎样式.

        Args:
            question_title: 问题标题.
            content_html: 内容 HTML.
            metadata: 元数据字典.

        Returns:
            str: 完整的 HTML 文档.
        """
        meta_str = ""
        author_name = ""
        author_headline = ""
        author_avatar_url = ""
        voteup_count = ""
        comment_count = ""
        backup_time = ""
        original_url = ""

        if metadata:
            for key, value in metadata.items():
                if isinstance(value, str):
                    meta_str += f'<meta name="{key}" content="{value}">\n'
            author_name = metadata.get("author_name", "")
            author_headline = metadata.get("author_headline", "")
            author_avatar_url = metadata.get("author_avatar_url", "")
            voteup_count = str(metadata.get("voteup_count", "0"))
            comment_count = str(metadata.get("comment_count", "0"))
            backup_time = metadata.get("backup_time", "")
            original_url = metadata.get("original_url", "")

        # 处理内容 HTML - 确保使用 RichContent 类
        if 'class="RichContent' not in content_html and "class='RichContent" not in content_html:
            content_html = f'<div class="RichContent-inner">{content_html}</div>'

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{question_title} - 知乎备份</title>
    {meta_str}
    <style>
/* ============================================
   知乎主题样式 - 完整模拟知乎界面
   ============================================ */
:root {{
    --zhihu-blue: #0066ff;
    --zhihu-blue-hover: #005ce6;
    --text-primary: #121212;
    --text-secondary: #444;
    --text-tertiary: #8590a6;
    --text-link: #175199;
    --bg-primary: #ffffff;
    --bg-secondary: #f6f6f6;
    --bg-tertiary: #f9f9f9;
    --border-color: #ebebeb;
    --border-light: #f0f0f0;
    --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
        "Helvetica Neue", Arial, "Noto Sans", sans-serif;
    --font-mono: "SF Mono", Monaco, "Cascadia Code",
        "Roboto Mono", Consolas, "Courier New", monospace;
    --radius-small: 4px;
    --radius-medium: 6px;
    --shadow-card: 0 1px 3px rgba(18, 18, 18, 0.1);
}}

*, *::before, *::after {{ box-sizing: border-box; }}

html {{
    font-size: 15px;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}

body {{
    font-family: var(--font-family);
    font-size: 15px;
    line-height: 1.6;
    color: var(--text-primary);
    background: var(--bg-secondary);
    margin: 0;
    padding: 0;
    min-height: 100vh;
}}

.zhihu-page {{
    max-width: 694px;
    margin: 0 auto;
    padding: 10px 16px 50px;
    background: var(--bg-secondary);
}}

.zhihu-card {{
    background: var(--bg-primary);
    border-radius: var(--radius-medium);
    box-shadow: var(--shadow-card);
    overflow: hidden;
}}

/* 问题标题 */
.question-header {{
    padding: 20px 20px 12px;
    border-bottom: 1px solid var(--border-light);
}}

.question-title {{
    font-size: 22px;
    font-weight: 600;
    line-height: 1.4;
    color: var(--text-primary);
    margin: 0 0 12px 0;
    word-break: break-word;
}}

.question-meta {{
    font-size: 14px;
    color: var(--text-tertiary);
    line-height: 1.5;
}}

/* 作者信息 */
.answer-header {{
    padding: 16px 20px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
}}

.author-avatar {{
    width: 40px;
    height: 40px;
    border-radius: var(--radius-small);
    flex-shrink: 0;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 600;
    font-size: 16px;
    overflow: hidden;
}}

.author-avatar img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
}}

.author-info {{
    flex: 1;
    min-width: 0;
}}

.author-name-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}}

.author-name {{
    font-size: 15px;
    font-weight: 600;
    color: var(--text-secondary);
    text-decoration: none;
}}

.author-headline {{
    font-size: 14px;
    color: var(--text-tertiary);
    margin-top: 4px;
    line-height: 1.4;
}}

/* 富文本内容 */
.RichContent {{
    padding: 0 20px 16px;
    font-size: 15px;
    line-height: 1.8;
    color: var(--text-primary);
}}

.RichContent-inner {{
    word-break: break-word;
}}

.RichContent p {{
    margin: 0 0 1em 0;
    line-height: 1.8;
}}

.RichContent p:last-child {{
    margin-bottom: 0;
}}

.RichContent h1, .RichContent h2, .RichContent h3, .RichContent h4 {{
    font-weight: 600;
    margin: 1.5em 0 0.8em;
    line-height: 1.4;
    color: var(--text-primary);
}}

.RichContent h1 {{ font-size: 20px; }}
.RichContent h2 {{ font-size: 18px; }}
.RichContent h3 {{ font-size: 16px; }}
.RichContent h4 {{ font-size: 15px; }}

.RichContent a {{
    color: var(--text-link);
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color 0.2s;
}}

.RichContent a:hover {{
    border-bottom-color: var(--text-link);
}}

.RichContent strong, .RichContent b {{
    font-weight: 600;
}}

.RichContent blockquote {{
    margin: 1em 0;
    padding: 0 1em;
    color: var(--text-secondary);
    border-left: 3px solid #d3d3d3;
}}

.RichContent hr {{
    margin: 1.5em 0;
    border: none;
    border-top: 1px solid var(--border-color);
}}

.RichContent ul, .RichContent ol {{
    margin: 1em 0;
    padding-left: 2em;
}}

.RichContent li {{
    margin: 0.4em 0;
    line-height: 1.8;
}}

.RichContent pre {{
    margin: 1em 0;
    padding: 16px;
    background: #f6f6f6;
    border-radius: var(--radius-small);
    overflow-x: auto;
    font-family: var(--font-mono);
    font-size: 14px;
    line-height: 1.6;
}}

.RichContent pre code {{
    background: none;
    padding: 0;
    font-size: inherit;
    color: inherit;
    border-radius: 0;
}}

.RichContent code {{
    background: rgba(0, 102, 255, 0.08);
    padding: 2px 6px;
    border-radius: 3px;
    font-family: var(--font-mono);
    font-size: 0.9em;
    color: var(--text-primary);
}}

.RichContent img {{
    max-width: 100%;
    height: auto;
    margin: 1em 0;
    border-radius: var(--radius-small);
    display: block;
}}

.RichContent table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 14px;
}}

.RichContent th, .RichContent td {{
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    text-align: left;
}}

.RichContent th {{
    background: var(--bg-secondary);
    font-weight: 600;
}}

.RichContent tr:nth-child(even) {{
    background: var(--bg-tertiary);
}}

/* 操作栏 */
.answer-actions {{
    display: flex;
    align-items: center;
    padding: 12px 20px;
    border-top: 1px solid var(--border-light);
    gap: 16px;
}}

.vote-button {{
    display: inline-flex;
    align-items: center;
    padding: 8px 16px;
    background: var(--zhihu-blue);
    color: white;
    border: none;
    border-radius: var(--radius-small);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
}}

.vote-count {{
    font-weight: 600;
    margin-left: 4px;
}}

.action-button {{
    display: inline-flex;
    align-items: center;
    padding: 8px 12px;
    background: transparent;
    color: var(--text-tertiary);
    border: none;
    font-size: 14px;
    cursor: pointer;
}}

/* 评论区 */
.comments-section {{
    margin-top: 16px;
    padding: 16px 20px;
    border-top: 1px solid var(--border-light);
    background: var(--bg-tertiary);
}}

.comments-header {{
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 16px;
}}

.comment-item {{
    display: flex;
    gap: 12px;
    padding: 12px 0;
    border-bottom: 1px solid var(--border-light);
}}

.comment-item:last-child {{
    border-bottom: none;
}}

.comment-avatar {{
    width: 32px;
    height: 32px;
    border-radius: var(--radius-small);
    flex-shrink: 0;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 12px;
    font-weight: 600;
}}

.comment-content {{
    flex: 1;
    min-width: 0;
}}

.comment-author {{
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 4px;
}}

.comment-text {{
    font-size: 14px;
    line-height: 1.6;
    color: var(--text-primary);
    word-break: break-word;
}}

.comment-meta {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 8px;
    font-size: 13px;
    color: var(--text-tertiary);
}}

/* 底部信息 */
.backup-info {{
    padding: 16px 20px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border-light);
    font-size: 13px;
    color: var(--text-tertiary);
    text-align: center;
}}

.backup-info a {{
    color: var(--zhihu-blue);
    text-decoration: none;
}}

/* 移动端适配 */
@media (max-width: 640px) {{
    .zhihu-page {{
        padding: 0;
    }}
    .zhihu-card {{
        border-radius: 0;
    }}
    .question-title {{
        font-size: 18px;
    }}
    .RichContent {{
        font-size: 14px;
    }}
}}
    </style>
</head>
<body>
    <div class="zhihu-page">
        <div class="zhihu-card">
            <!-- 问题标题 -->
            <div class="question-header">
                <h1 class="question-title">{question_title}</h1>
                <div class="question-meta">
                    知乎备份 ·
                    <span style="color: var(--zhihu-blue); font-weight: 500;">
                        {voteup_count}
                    </span> 人赞同
                </div>
            </div>

            <!-- 作者信息 -->
            <div class="answer-header">
                <div class="author-avatar">
                    {f'<img src="{author_avatar_url}" alt="{author_name}">' if author_avatar_url else (author_name[0] if author_name else "?").upper()}
                </div>
                <div class="author-info">
                    <div class="author-name-row">
                        <span class="author-name">{author_name or "匿名用户"}</span>
                    </div>
                    <div class="author-headline">{author_headline or "知乎用户"}</div>
                </div>
            </div>

            <!-- 回答内容 -->
            <div class="RichContent">
                {content_html}
            </div>

            <!-- 操作栏 -->
            <div class="answer-actions">
                <button class="vote-button">
                    ▲ 赞同 <span class="vote-count">{voteup_count}</span>
                </button>
                <button class="action-button">
                    ▼
                </button>
                <button class="action-button">
                    💬 {comment_count} 条评论
                </button>
                <button class="action-button">
                    ⭐ 收藏
                </button>
            </div>

            <!-- 底部信息 -->
            <div class="backup-info">
                备份于 {backup_time or "未知时间"} ·
                <a href="{original_url}" target="_blank">查看原文</a>
            </div>
        </div>
    </div>
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
            downloaded_path = await self._download_image(src, answer_id)
            if downloaded_path:
                img_tag["src"] = downloaded_path
                self._downloaded_images.add(src)
        except Exception as e:
            logger.warning(f"下载图片失败 {src}: {e}")

    def _get_local_image_path(self, original_url: str) -> str:
        """获取图片本地路径.

        Args:
            original_url: 原始图片 URL.

        Returns:
            str: 绝对路径.
        """
        url_hash = hashlib.md5(original_url.encode()).hexdigest()[:16]
        ext = Path(urlparse(original_url).path).suffix or ".jpg"
        return f"/data/images/answers/{url_hash}{ext}"

    async def _download_image(self, url: str, answer_id: str) -> str | None:
        """下载单张图片到 answers 目录.

        Args:
            url: 图片 URL.
            answer_id: 回答ID.

        Returns:
            Optional[str]: 本地路径，失败返回None.
        """
        if not self.download_images:
            return None

        # 跳过本地路径
        if url.startswith("/data/") or url.startswith("../") or url.startswith("./"):
            return url

        # 跳过非 HTTP URL
        if not url.startswith("http://") and not url.startswith("https://"):
            return url

        if url in self._downloaded_images:
            return self._get_local_image_path(url)

        try:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
            ext = Path(urlparse(url).path).suffix or ".jpg"
            local_filename = f"{url_hash}{ext}"
            # 保存到 answers 子目录
            local_path = self.answers_images_path / local_filename

            # 检查是否已存在
            if local_path.exists():
                self._downloaded_images.add(url)
                return self._get_local_image_path(url)

            # 下载图片
            timeout = aiohttp.ClientTimeout(total=30)
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, timeout=timeout) as response,
                aiofiles.open(local_path, "wb") as f,
            ):
                if response.status == 200:
                    content = await response.read()
                    await f.write(content)
                    self._downloaded_images.add(url)
                    logger.debug(f"下载图片: {url} -> {local_path}")
                    return self._get_local_image_path(url)
        except Exception as e:
            logger.warning(f"下载图片失败 {url}: {e}")

        return None

    async def download_avatar(self, avatar_url: str, user_id: str) -> str | None:
        """下载用户头像到 avatars 目录.

        Args:
            avatar_url: 头像URL.
            user_id: 用户ID(用于文件名).

        Returns:
            Optional[str]: 本地相对路径，失败返回None.
        """
        if not avatar_url:
            return None

        # 检查缓存
        if user_id in self._downloaded_avatars:
            safe_user_id = hashlib.md5(user_id.encode()).hexdigest()[:16]
            return f"/data/images/avatars/avatar_{safe_user_id}.jpg"

        try:
            # 将缩略图URL转为高清图URL (_l.jpg -> .jpg)
            hd_avatar_url = avatar_url.replace("_l.jpg", ".jpg")
            if hd_avatar_url != avatar_url:
                logger.debug(f"使用高清头像URL: {hd_avatar_url[:60]}...")

            # 使用用户ID作为文件名，避免重复下载同一用户
            safe_user_id = hashlib.md5(user_id.encode()).hexdigest()[:16]
            ext = ".jpg"  # 强制使用.jpg
            local_filename = f"avatar_{safe_user_id}{ext}"
            # 保存到 avatars 子目录
            local_path = self.avatars_path / local_filename

            # 检查是否已存在且文件有效(大于5KB)
            if local_path.exists() and local_path.stat().st_size > 5120:
                logger.debug(f"头像已存在: {local_path} ({local_path.stat().st_size} bytes)")
                self._downloaded_avatars.add(user_id)
                return f"/data/images/avatars/{local_filename}"

            # 下载高清头像
            timeout = aiohttp.ClientTimeout(total=30)
            async with (
                aiohttp.ClientSession() as session,
                session.get(hd_avatar_url, timeout=timeout) as response,
            ):
                if response.status == 200:
                    content = await response.read()
                    # 检查下载的内容是否有效
                    if len(content) < 1000:
                        logger.warning(f"头像下载内容太小 ({len(content)} bytes): {hd_avatar_url}")
                        return None
                    async with aiofiles.open(local_path, "wb") as f:
                        await f.write(content)
                        self._downloaded_avatars.add(user_id)
                        logger.debug(f"下载头像: {user_id} -> {local_path} ({len(content)} bytes)")
                        return f"/data/images/avatars/{local_filename}"
        except Exception as e:
            logger.warning(f"下载头像失败 {user_id}: {e}")

        return None

    async def delete_answer_files(self, answer_id: str) -> dict:
        """删除回答相关的所有文件(HTML和图片).

        Args:
            answer_id: 回答ID.

        Returns:
            dict: 删除结果统计.
        """
        result: dict[str, Any] = {
            "html_deleted": 0,
            "images_deleted": 0,
            "errors": [],
        }

        try:
            # 1. 查找并删除HTML文件
            html_pattern = f"*{answer_id}.html"
            html_files = list(self.html_path.glob(html_pattern))

            for html_file in html_files:
                try:
                    # 先提取并删除HTML中引用的本地图片
                    async with aiofiles.open(html_file, encoding="utf-8") as f:
                        content = await f.read()

                    # 查找引用的本地图片 (/data/images/answers/xxx.jpg)
                    import re

                    local_images = re.findall(r'/data/images/answers/[^"\'\s]+', content)

                    for img_path in local_images:
                        try:
                            # 转换为绝对路径
                            img_name = Path(img_path).name
                            img_file = self.answers_images_path / img_name
                            if img_file.exists():
                                img_file.unlink()
                                result["images_deleted"] += 1
                                logger.debug(f"删除图片: {img_file}")
                        except Exception as e:
                            result["errors"].append(f"删除图片失败 {img_path}: {e}")

                    # 删除HTML文件
                    html_file.unlink()
                    result["html_deleted"] += 1
                    logger.info(f"删除HTML文件: {html_file}")

                except Exception as e:
                    result["errors"].append(f"删除HTML文件失败 {html_file}: {e}")

        except Exception as e:
            result["errors"].append(f"删除操作失败: {e}")

        return result

    def check_answer_exists(self, answer_id: str, content: str | None = None) -> bool:
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
        return any(content_hash in match.name for match in matches)

    def get_storage_stats(self) -> dict:
        """获取存储统计.

        Returns:
            dict: 统计信息.
        """
        html_files = list(self.html_path.glob("*.html"))
        avatar_files = list(self.avatars_path.glob("*.jpg"))
        answer_image_files = list(self.answers_images_path.glob("*"))

        total_html_size = sum(f.stat().st_size for f in html_files)
        total_avatar_size = sum(f.stat().st_size for f in avatar_files if f.is_file())
        total_answer_image_size = sum(f.stat().st_size for f in answer_image_files if f.is_file())

        return {
            "html_count": len(html_files),
            "avatar_count": len(avatar_files),
            "answer_image_count": len(answer_image_files),
            "total_image_count": len(avatar_files) + len(answer_image_files),
            "html_size_mb": round(total_html_size / 1024 / 1024, 2),
            "avatar_size_mb": round(total_avatar_size / 1024 / 1024, 2),
            "answer_image_size_mb": round(total_answer_image_size / 1024 / 1024, 2),
            "total_image_size_mb": round((total_avatar_size + total_answer_image_size) / 1024 / 1024, 2),
        }

    async def append_comments(self, html_path: str, comments: list[dict]) -> bool:
        """将评论追加到HTML文件中.

        Args:
            html_path: HTML文件路径.
            comments: 评论数据列表.

        Returns:
            bool: 成功返回True.
        """
        if not comments:
            return True

        try:
            path = Path(html_path)
            if not path.exists():
                logger.warning(f"HTML文件不存在: {html_path}")
                return False

            # 读取现有HTML
            async with aiofiles.open(path, encoding="utf-8") as f:
                html_content = await f.read()

            # 构建评论HTML
            comments_html = self._build_comments_html(comments)

            # 在底部信息之前插入评论区
            # 查找 <!-- 底部信息 --> 标记
            footer_marker = "<!-- 底部信息 -->"
            if footer_marker in html_content:
                # 在底部信息之前插入评论
                new_html = html_content.replace(footer_marker, f"{comments_html}\n            {footer_marker}")
            else:
                # 如果没有找到标记，在 </body> 之前插入
                body_end = "</body>"
                new_html = html_content.replace(body_end, f"{comments_html}\n{body_end}")

            # 写回文件
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(new_html)

            logger.info(f"已追加 {len(comments)} 条评论到: {html_path}")
            return True

        except Exception as e:
            logger.exception(f"追加评论失败: {e}")
            return False

    def _build_comments_html(self, comments: list[dict]) -> str:
        """构建评论区的HTML.

        Args:
            comments: 评论数据列表.

        Returns:
            str: 评论区HTML.
        """
        if not comments:
            return ""

        # 构建每条评论的HTML
        comments_items = []
        for comment in comments:
            author_name = comment.get("author_name", "匿名用户")
            author_avatar = comment.get("author_avatar_url", "")
            content = comment.get("content", "")
            like_count = comment.get("like_count", 0)
            created_time = comment.get("created_time")

            # 处理时间显示
            time_str = ""
            if created_time:
                from datetime import datetime

                if isinstance(created_time, datetime):
                    time_str = created_time.strftime("%Y-%m-%d %H:%M")
                else:
                    time_str = str(created_time)

            # 截断作者名用于头像
            avatar_text = (author_name[0] if author_name else "?").upper()

            # 头像HTML
            avatar_html = f'<img src="{author_avatar}" alt="{author_name}">' if author_avatar else avatar_text

            item_html = f"""            <div class="comment-item">
                <div class="comment-avatar">{avatar_html}</div>
                <div class="comment-content">
                    <div class="comment-author">{author_name}</div>
                    <div class="comment-text">{content}</div>
                    <div class="comment-meta">
                        <span>{time_str}</span>
                        <span>👍 {like_count}</span>
                    </div>
                </div>
            </div>"""
            comments_items.append(item_html)

        # 组合完整评论区
        comments_list = "\n".join(comments_items)

        return f"""            <!-- 评论区 -->
            <div class="comments-section">
                <div class="comments-header">💬 评论 ({len(comments)}条)</div>
{comments_list}
            </div>"""
