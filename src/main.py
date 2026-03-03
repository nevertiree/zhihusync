"""主服务入口.

该模块提供 zhihusync 服务的核心功能，包括定时任务调度、
同步任务管理和日志配置。

Examples:
    >>> from main import ZhihuSyncService
    >>> from config_loader import load_config
    >>> config = load_config()
    >>> service = ZhihuSyncService(config)
    >>> await service.start()
"""

import asyncio
import signal
import sys
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import AppConfig, ensure_directories, load_config
from crawler import ZhihuCrawler
from db import DatabaseManager
from storage import StorageManager


class ZhihuSyncService:
    """zhihusync 服务主类.

    提供完整的同步服务，包括调度器管理、同步任务执行和日志配置。

    Attributes:
        config: 应用配置对象.
        scheduler: APScheduler 调度器.
        running: 服务运行状态.
        db: 数据库管理器.
        storage: 存储管理器.

    Examples:
        >>> config = load_config()
        >>> service = ZhihuSyncService(config)
        >>> # 运行一次同步
        >>> await service.run_once()
        >>> # 启动定时服务
        >>> await service.start()
    """

    def __init__(self, config: AppConfig):
        """初始化服务.

        Args:
            config: 应用配置对象.
        """
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self.running = False

        # 初始化组件
        self.db = DatabaseManager(config.storage.db_path)
        self.storage = StorageManager(
            html_path=config.storage.html_path,
            static_path=config.storage.static_path,
            images_path=config.storage.images_path,
            download_images=config.storage.download_images,
        )

        # 初始化日志
        self._setup_logging()

        logger.info("=" * 50)
        logger.info("zhihusync 服务初始化")
        logger.info(f"用户ID: {config.zhihu.user_id or '未设置'}")
        logger.info(f"扫描间隔: {config.zhihu.scan_interval} 分钟")
        logger.info("=" * 50)

    def _setup_logging(self):
        """配置日志.

        设置控制台和文件日志输出，根据配置文件调整级别和格式。
        使用北京时间 (UTC+8)。
        """
        # 移除默认处理器
        logger.remove()

        # 自定义时间格式化函数 - 返回北京时间
        def beijing_time_formatter(record):
            from datetime import datetime, timedelta, timezone

            beijing_tz = timezone(timedelta(hours=8))
            beijing_time = datetime.now(beijing_tz)
            record["extra"]["beijing_time"] = beijing_time.strftime("%Y-%m-%d %H:%M:%S")
            return "{extra[beijing_time]} | {level} | {name} | {message}\n"

        # 添加控制台输出
        logger.add(
            sys.stdout,
            level=self.config.logging.level,
            format=beijing_time_formatter,
            colorize=True,
        )

        # 添加文件输出
        logger.add(
            self.config.logging.file,
            level=self.config.logging.level,
            format=beijing_time_formatter,
            rotation=self.config.logging.rotation,
            retention=self.config.logging.retention,
            encoding="utf-8",
        )

    async def run_sync(self):
        """执行同步任务.

        扫描用户点赞内容，保存回答和评论元数据及 HTML。
        任务结果会记录到同步日志中。
        """
        if not self.config.zhihu.user_id:
            logger.error("未配置用户ID，请在 config.yaml 中设置 zhihu.user_id")
            return

        log_id = self.db.create_sync_log()

        try:
            logger.info("开始同步任务...")

            async with ZhihuCrawler(
                user_id=self.config.zhihu.user_id,
                db_manager=self.db,
                storage_manager=self.storage,
                headless=self.config.browser.headless,
                request_delay=self.config.browser.request_delay,
            ) as crawler:
                # 扫描点赞内容
                new_items, updated_items = await crawler.scan_likes(
                    max_items=self.config.zhihu.max_items_per_scan
                )

                # 同步评论
                if self.config.zhihu.save_comments:
                    await crawler.sync_all_comments()

                # 更新日志
                self.db.update_sync_log(
                    log_id=log_id,
                    status="success",
                    items_scanned=new_items + updated_items,
                    items_new=new_items,
                    items_updated=updated_items,
                )

                logger.info(f"同步完成: 新增 {new_items}, 更新 {updated_items}")

                # 输出统计
                stats = self.db.get_stats()
                logger.info(f"当前总计: {stats['total_answers']} 回答, " f"{stats['total_comments']} 评论")

        except Exception as e:
            logger.exception(f"同步任务失败: {e}")
            self.db.update_sync_log(log_id=log_id, status="failed", error_message=str(e))

    async def run_once(self):
        """运行一次同步.

        用于手动触发单次同步，不启动调度器。
        """
        await self.run_sync()

    def schedule_jobs(self):
        """设置定时任务.

        根据配置文件的扫描间隔，设置定期同步任务。
        """
        # 定期同步点赞内容
        self.scheduler.add_job(
            self.run_sync,
            trigger=IntervalTrigger(minutes=self.config.zhihu.scan_interval),
            id="sync_likes",
            name="同步点赞内容",
            replace_existing=True,
        )

        logger.info(f"定时任务已设置，每 {self.config.zhihu.scan_interval} 分钟执行一次")

    async def start(self):
        """启动服务.

        启动调度器，设置定时任务，并立即执行一次同步。
        服务会持续运行直到收到停止信号。
        """
        self.running = True

        # 启动调度器
        self.scheduler.start()
        self.schedule_jobs()

        # 立即执行一次
        await self.run_sync()

        logger.info("服务已启动，按 Ctrl+C 停止")

        # 保持运行
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    def stop(self):
        """停止服务.

        停止调度器并关闭服务。
        """
        logger.info("正在停止服务...")
        self.running = False
        self.scheduler.shutdown()
        logger.info("服务已停止")

    def handle_signal(self, signum, frame):
        """处理信号.

        处理 SIGINT 和 SIGTERM 信号，优雅关闭服务。

        Args:
            signum: 信号编号.
            frame: 当前栈帧.
        """
        logger.info(f"收到信号 {signum}")
        self.stop()
        sys.exit(0)


async def main():
    """主函数.

    加载配置、初始化服务并启动。
    """
    # 加载配置
    config = load_config()

    # 确保目录存在
    ensure_directories(config)

    # 创建服务
    service = ZhihuSyncService(config)

    # 注册信号处理
    signal.signal(signal.SIGINT, service.handle_signal)
    signal.signal(signal.SIGTERM, service.handle_signal)

    # 启动服务
    await service.start()


def cli_main():
    """CLI 入口.

    命令行入口函数，处理异常和用户中断。
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.exception(f"程序异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
