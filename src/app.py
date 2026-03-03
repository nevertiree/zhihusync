"""集成的应用启动器 - 同时启动爬虫服务和 Web 界面.

该模块提供统一的入口点，支持三种运行模式：
- web: 仅运行 Web 管理界面
- scheduler: 仅运行定时同步服务
- both: 同时运行 Web 和定时任务(默认)

Examples:
    >>> # 运行完整服务
    >>> python app.py
    >>> # 仅运行 Web 界面
    >>> python app.py --mode web
    >>> # 仅运行定时任务
    >>> python app.py --mode scheduler
"""

import asyncio
import sys
from pathlib import Path

from loguru import logger

# 确保能导入其他模块
sys.path.insert(0, str(Path(__file__).parent))


async def run_scheduler():
    """运行定时同步服务.

    加载配置并启动同步服务，不包含 Web 界面。
    """
    from config_loader import ensure_directories, load_config
    from main import ZhihuSyncService

    config = load_config()
    ensure_directories(config)

    service = ZhihuSyncService(config)

    # 启动服务(在后台运行)
    await service.start()


def run_web():
    """运行 Web 界面.

    启动 FastAPI Web 服务器，提供管理界面和 API。
    此函数会阻塞直到服务器停止。
    """
    import uvicorn

    from web import app

    uvicorn.run(app, host="0.0.0.0", port=6067, log_level="info")


async def run_both():
    """同时运行 Web 和定时任务.

    在异步环境中同时启动调度器和 Web 服务器。
    这是最常用的运行模式。
    """
    from config_loader import ensure_directories, load_config
    from main import ZhihuSyncService

    config = load_config()
    ensure_directories(config)

    # 创建服务
    service = ZhihuSyncService(config)

    # 启动定时任务(不阻塞)
    service.scheduler.start()
    service.schedule_jobs()

    logger.info("=" * 50)
    logger.info("zhihusync 已启动")
    logger.info("Web 界面: http://localhost:6067")
    logger.info("=" * 50)

    # 启动 Web 服务(阻塞)
    import uvicorn

    from web import app

    config_uvicorn = uvicorn.Config(app, host="0.0.0.0", port=6067, log_level="info")
    server = uvicorn.Server(config_uvicorn)
    await server.serve()


def main():
    """主入口.

    解析命令行参数并启动对应的服务模式。
    支持 --mode 参数指定运行模式。
    """
    import argparse

    parser = argparse.ArgumentParser(description="zhihusync 启动器")
    parser.add_argument(
        "--mode",
        choices=["web", "scheduler", "both"],
        default="both",
        help="运行模式: web=仅Web界面, scheduler=仅定时任务, both=同时运行(默认)",
    )

    args = parser.parse_args()

    try:
        if args.mode == "web":
            logger.info("启动 Web 管理界面...")
            run_web()
        elif args.mode == "scheduler":
            logger.info("启动定时同步服务...")
            asyncio.run(run_scheduler())
        else:  # both
            logger.info("启动完整服务 (Web + 定时任务)...")
            asyncio.run(run_both())
    except KeyboardInterrupt:
        logger.info("用户中断，正在关闭...")
    except Exception as e:
        logger.exception(f"启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
