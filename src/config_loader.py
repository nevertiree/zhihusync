"""配置加载模块.

该模块负责加载和管理应用程序的配置，支持从 YAML 文件和环境变量加载配置。
使用 Pydantic 进行配置验证和类型检查。

Examples:
    >>> from config_loader import load_config, ensure_directories
    >>> config = load_config()
    >>> ensure_directories(config)
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ZhihuConfig(BaseModel):
    """知乎配置类.

    Attributes:
        user_id: 知乎用户ID.
        scan_interval: 扫描间隔(分钟).
        max_items_per_scan: 每次扫描最大条目数.
        save_comments: 是否保存评论.
        max_comments: 每篇文章最大评论数.
    """

    user_id: str = ""
    scan_interval: int = 60
    max_items_per_scan: int = 50
    save_comments: bool = True
    max_comments: int = 100


class StorageConfig(BaseModel):
    """存储配置类.

    Attributes:
        html_path: HTML文件保存路径.
        db_path: SQLite数据库路径.
        static_path: 静态文件路径.
        download_images: 是否下载图片.
        images_path: 图片保存路径.
    """

    html_path: str = "/app/data/html"
    db_path: str = "/app/data/meta/zhihusync.db"
    static_path: str = "/app/data/static"
    download_images: bool = True
    images_path: str = "/app/data/static/images"


class BrowserConfig(BaseModel):
    """浏览器配置类.

    Attributes:
        headless: 是否使用无头模式.
        browser_type: 浏览器类型(chromium/firefox/webkit).
        timeout: 页面加载超时时间(秒).
        request_delay: 请求间隔时间(秒).
        user_agent: User-Agent字符串.
    """

    headless: bool = True
    browser_type: str = "chromium"
    timeout: int = 30
    request_delay: float = 2.0
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"


class LoggingConfig(BaseModel):
    """日志配置类.

    Attributes:
        level: 日志级别(DEBUG/INFO/WARNING/ERROR).
        format: 日志格式字符串.
        file: 日志文件路径.
        rotation: 日志轮转大小.
        retention: 日志保留时间.
    """

    level: str = "INFO"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"
    file: str = "/app/data/meta/zhihusync.log"
    rotation: str = "10 MB"
    retention: str = "30 days"


class AppConfig(BaseSettings):
    """应用程序主配置类.

    集成所有子配置类，支持从环境变量加载配置。
    环境变量前缀为 ZHIHUSYNC_。

    Attributes:
        zhihu: 知乎相关配置.
        storage: 存储相关配置.
        browser: 浏览器相关配置.
        logging: 日志相关配置.

    Examples:
        >>> config = AppConfig()
        >>> print(config.zhihu.user_id)
        >>> print(config.storage.html_path)
    """

    zhihu: ZhihuConfig = Field(default_factory=ZhihuConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    class Config:
        """Pydantic配置类."""

        env_prefix = "ZHIHUSYNC_"


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """加载配置文件.

    按优先级从以下位置加载配置:
    1. 指定的配置文件路径
    2. /app/config/config.yaml (Docker环境)
    3. config/config.yaml (本地开发)
    4. ~/.zhihusync/config.yaml (用户目录)
    5. 环境变量

    Args:
        config_path: 配置文件路径，为None时自动查找.

    Returns:
        AppConfig: 应用配置对象.

    Examples:
        >>> config = load_config()  # 自动查找
        >>> config = load_config("/path/to/config.yaml")  # 指定路径
    """
    # 默认配置文件路径
    if config_path is None:
        # 按优先级查找配置文件
        possible_paths = [
            Path("/app/config/config.yaml"),  # Docker 环境
            Path("config/config.yaml"),  # 本地开发
            Path.home() / ".zhihusync" / "config.yaml",  # 用户目录
        ]
        for path in possible_paths:
            if path.exists():
                config_path = str(path)
                break

    # 如果存在配置文件，从文件加载
    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        return AppConfig(**config_data)

    # 从环境变量加载
    return AppConfig()


def ensure_directories(config: AppConfig) -> None:
    """确保必要的目录存在.

    根据配置创建所有必要的目录，包括HTML存储目录、
    数据库目录、静态文件目录和日志目录。

    Args:
        config: 应用配置对象.

    Returns:
        None

    Examples:
        >>> config = load_config()
        >>> ensure_directories(config)
    """
    paths = [
        config.storage.html_path,
        config.storage.static_path,
        config.storage.images_path,
        Path(config.storage.db_path).parent,
        Path(config.logging.file).parent,
    ]
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)
