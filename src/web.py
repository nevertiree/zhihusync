"""Web 管理界面 - FastAPI 后端"""

import asyncio
import json
import os
import signal
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import or_

from config_loader import load_config
from crawler import ZhihuCrawler
from db import Answer, DatabaseManager, SyncLog
from image_generator import ImageGenerator
from storage import StorageManager
from timezone_utils import get_beijing_now

# 全局状态
app_state: dict[str, Any] = {
    "sync_task": None,
    "sync_status": "idle",  # idle, running, success, failed, stopping
    "sync_progress": 0,
    "sync_message": "",
    "last_sync": None,
    "stop_requested": False,  # 停止请求标志
    "cookie_info": None,  # 缓存的 cookie 验证信息
}

# 加载配置
config = load_config()
db = DatabaseManager(config.storage.db_path)
storage = StorageManager(
    html_path=config.storage.html_path,
    static_path=config.storage.static_path,
    images_path=config.storage.images_path,
    download_images=config.storage.download_images,
)


def get_cookie_file_path() -> Path:
    """获取 Cookie 文件路径 - 基于配置的 meta 目录"""
    # 从 db_path 推导 meta 目录
    db_path = Path(config.storage.db_path)
    meta_dir = db_path.parent
    return meta_dir / "cookies.json"


def get_sync_user_id() -> str | None:
    """获取用于同步的用户ID.

    优先从数据库获取活跃用户，如果没有则使用配置文件中的user_id.

    Returns:
        str | None: 用户ID或None
    """
    from models import User

    session = db.get_session()
    try:
        # 优先从数据库获取第一个活跃用户
        user = session.query(User).filter_by(is_active=True).first()
        if user:
            return user.id
    finally:
        session.close()

    # 如果没有数据库用户，使用配置文件中的
    return config.zhihu.user_id or None


def update_config_file(user_id: str | None = None, cookie_info: dict | None = None) -> bool:
    """更新配置文件中的 user_id 和 cookie 信息.

    Args:
        user_id: 知乎用户ID，为None则不更新
        cookie_info: Cookie相关信息，为None则不更新

    Returns:
        bool: 更新成功返回True
    """
    try:
        # 确定配置文件路径
        config_path = Path("/app/config/config.yaml")
        if not config_path.exists():
            config_path = Path("config/config.yaml")

        import yaml

        # 读取现有配置
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        else:
            config_data = {}

        # 确保 zhihu 段存在
        if "zhihu" not in config_data:
            config_data["zhihu"] = {}

        # 更新 user_id
        if user_id is not None:
            config_data["zhihu"]["user_id"] = user_id

        # 更新 cookie 信息（如果有）
        if cookie_info is not None:
            config_data["cookie_info"] = {
                **cookie_info,
                "updated_at": datetime.now().isoformat(),
            }

        # 写回文件
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)

        # 更新内存中的配置
        if user_id is not None:
            config.zhihu.user_id = user_id

        logger.info(f"配置文件已更新: {config_path}")
        return True
    except Exception as e:
        logger.error(f"更新配置文件失败: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    yield
    # 清理
    if app_state["sync_task"] and not app_state["sync_task"].done():
        app_state["sync_task"].cancel()


app = FastAPI(
    title="zhihusync 管理界面",
    description="知乎点赞内容备份工具的管理界面",
    version="0.1.0",
    lifespan=lifespan,
)

# 配置 CORS - 允许浏览器扩展访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（浏览器扩展）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件和模板
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# 挂载数据目录以便访问备份的 HTML
app.mount(
    "/data/html",
    StaticFiles(directory=config.storage.html_path),
    name="html_files",
)

# 挂载图片目录
app.mount(
    "/data/images",
    StaticFiles(directory=config.storage.images_path),
    name="data_images",
)

# 挂载静态资源目录(兼容旧路径)
app.mount(
    "/data/static",
    StaticFiles(directory=config.storage.static_path),
    name="data_static",
)


# ============ 数据模型 ============


class ConfigUpdate(BaseModel):
    """配置更新请求模型."""

    # 知乎设置
    user_id: str
    scan_interval: int = 60
    max_items_per_scan: int = -1  # -1 表示无限制
    save_comments: bool = True
    max_comments: int = -1  # -1 表示无限制
    sync_likes: bool = True
    sync_created: bool = False
    skip_video: bool = True
    min_voteup: int = 0

    # 浏览器设置
    headless: bool = True
    browser_type: str = "chromium"
    timeout: int = 30
    request_delay: float = 2.0
    proxy: str = ""
    window_width: int = 1920
    window_height: int = 1080
    scroll_delay: int = 800
    max_scroll_rounds: int = 20

    # 存储设置
    download_images: bool = True
    download_avatars: bool = True
    compress_html: bool = False
    backup_enabled: bool = False
    backup_interval_days: int = 7

    # 日志设置
    log_level: str = "INFO"
    console_output: bool = True
    log_sql: bool = False


class StorageUpdate(BaseModel):
    """存储路径更新请求模型."""

    html_path: str
    db_path: str
    static_path: str
    images_path: str


class CookieUpdate(BaseModel):
    """Cookie 更新请求模型."""

    cookies: str  # Cookie 数据
    format: str = "auto"  # 格式: auto, json, netscape, header, keyvalue


class SyncResponse(BaseModel):
    """同步响应模型."""

    status: str
    message: str
    progress: int = 0


class StatsResponse(BaseModel):
    """统计响应模型."""

    total_answers: int
    total_comments: int
    with_comments: int
    comment_anomaly: int  # 评论采集异常数
    comment_errors: int  # 评论错误数
    deleted_answers: int
    extraction_errors: int
    failed_downloads: int
    pending_downloads: int
    unresolved_failures: int
    last_sync: str | None
    sync_status: str


class AnswerItem(BaseModel):
    """回答列表项模型."""

    id: str
    question_title: str
    author_name: str
    voteup_count: int
    comment_count: int
    synced_at: str
    html_path: str | None
    original_url: str


# ============ 页面路由 ============


@app.get("/")
async def index(request: Request):
    """首页 - 仪表盘"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/config")
async def config_page(request: Request):
    """配置页面"""
    return templates.TemplateResponse("config.html", {"request": request})


@app.get("/content")
async def content_page(request: Request):
    """内容浏览页面"""
    return templates.TemplateResponse("content.html", {"request": request})


@app.get("/logs")
async def logs_page(request: Request):
    """日志页面"""
    return templates.TemplateResponse("logs.html", {"request": request})


# ============ API 路由 ============


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """获取统计信息"""
    stats = db.get_stats()

    # 获取上次同步时间
    session = db.get_session()
    try:
        last_log = session.query(SyncLog).filter_by(status="success").order_by(SyncLog.ended_at.desc()).first()
        last_sync = last_log.ended_at.isoformat() if last_log and last_log.ended_at else None
    finally:
        session.close()

    # 获取提取错误数量
    error_count = db.get_extraction_error_count(resolved=False)

    return StatsResponse(
        total_answers=stats["total_answers"],
        total_comments=stats["total_comments"],
        with_comments=stats["with_comments"],
        comment_anomaly=stats.get("comment_anomaly", 0),
        comment_errors=stats.get("comment_errors", 0),
        deleted_answers=stats["deleted_answers"],
        extraction_errors=error_count,
        failed_downloads=stats.get("failed_downloads", 0),
        pending_downloads=stats.get("pending_downloads", 0),
        unresolved_failures=stats.get("unresolved_failures", 0),
        last_sync=last_sync,
        sync_status=app_state["sync_status"],
    )


@app.get("/api/setup/status")
async def get_setup_status():
    """获取配置状态 - 检查数据库中是否有用户和cookie"""
    cookie_file = get_cookie_file_path()
    has_cookie = cookie_file.exists() and cookie_file.stat().st_size > 0

    # 检查数据库中是否有活跃用户（而不是只看配置文件）
    session = db.get_session()
    try:
        from models import User

        has_user_in_db = session.query(User).filter_by(is_active=True).first() is not None
    finally:
        session.close()

    # 使用数据库中的用户或配置文件中的用户
    has_user = has_user_in_db or bool(config.zhihu.user_id)

    return {
        "configured": has_user and has_cookie,
        "has_user_id": has_user,
        "has_cookie": has_cookie,
        "user_id": config.zhihu.user_id or "",
    }


@app.get("/api/users")
async def get_users():
    """获取监控用户列表"""
    from models import User

    session = db.get_session()
    try:
        users = session.query(User).filter_by(is_active=True).all()
        return {
            "users": [
                {
                    "user_id": user.id,
                    "name": user.name or user.id,
                    "avatar_url": user.avatar_url,
                    "headline": user.headline,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_sync": user.last_sync_at.isoformat() if user.last_sync_at else None,
                    "sync_count": user.sync_count,
                    "status": "active" if user.is_active else "inactive",
                }
                for user in users
            ]
        }
    finally:
        session.close()


class UserCreate(BaseModel):
    """创建用户请求模型."""

    user_id: str
    name: str | None = None


@app.post("/api/users")
async def create_user(user_data: UserCreate):
    """添加监控用户"""
    from models import User

    if not user_data.user_id:
        raise HTTPException(status_code=400, detail="用户ID不能为空")

    session = db.get_session()
    try:
        # 检查是否已存在
        existing = session.query(User).filter_by(id=user_data.user_id).first()
        if existing:
            if existing.is_active:
                raise HTTPException(status_code=400, detail="用户已存在")
            else:
                # 重新激活
                existing.is_active = True
                session.commit()
                # 同时更新配置文件
                update_config_file(user_id=user_data.user_id)
                return {"status": "success", "message": "用户已重新激活", "user_id": user_data.user_id}

        # 创建新用户
        user = User(id=user_data.user_id, name=user_data.name or user_data.user_id, is_active=True)
        session.add(user)
        session.commit()

        # 同时更新配置文件
        update_config_file(user_id=user_data.user_id)

        logger.info(f"添加用户: {user_data.user_id}")
        return {"status": "success", "message": "用户添加成功", "user_id": user_data.user_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"添加用户失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加用户失败: {str(e)}")
    finally:
        session.close()


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str):
    """删除（停用）监控用户"""
    from models import User

    session = db.get_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 软删除，只标记为非活跃
        user.is_active = False
        session.commit()
        logger.info(f"停用用户: {user_id}")
        return {"status": "success", "message": "用户已停用", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"删除用户失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除用户失败: {str(e)}")
    finally:
        session.close()


@app.post("/api/users/{user_id}/sync")
async def sync_user(user_id: str):
    """同步指定用户的数据"""
    from models import User

    session = db.get_session()
    try:
        user = session.query(User).filter_by(id=user_id, is_active=True).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在或未激活")
    finally:
        session.close()

    # 启动异步同步任务
    async def do_user_sync():
        try:
            async with ZhihuCrawler(
                user_id=user_id,
                db_manager=db,
                storage_manager=storage,
                headless=True,
                request_delay=config.browser.request_delay,
                max_comments=config.zhihu.max_comments,
            ) as crawler:
                # 用户同步使用普通采集模式
                await crawler.scan_likes(
                    max_items=config.zhihu.max_items_per_scan,
                    scan_mode="normal",
                )
        except Exception as e:
            logger.error(f"同步用户 {user_id} 失败: {e}")

    asyncio.create_task(do_user_sync())
    return {"status": "started", "message": f"用户 {user_id} 同步任务已启动"}


@app.get("/api/config")
async def get_config():
    """获取当前配置"""
    return {
        # 知乎设置
        "user_id": config.zhihu.user_id,
        "scan_interval": config.zhihu.scan_interval,
        "max_items_per_scan": config.zhihu.max_items_per_scan,
        "save_comments": config.zhihu.save_comments,
        "max_comments": config.zhihu.max_comments,
        "sync_likes": config.zhihu.sync_likes,
        "sync_created": config.zhihu.sync_created,
        "skip_video": config.zhihu.skip_video,
        "min_voteup": config.zhihu.min_voteup,
        # 浏览器设置
        "headless": config.browser.headless,
        "browser_type": config.browser.browser_type,
        "timeout": config.browser.timeout,
        "request_delay": config.browser.request_delay,
        "proxy": config.browser.proxy,
        "window_width": config.browser.window_width,
        "window_height": config.browser.window_height,
        "scroll_delay": config.browser.scroll_delay,
        "max_scroll_rounds": config.browser.max_scroll_rounds,
        # 存储设置
        "html_path": config.storage.html_path,
        "db_path": config.storage.db_path,
        "download_images": config.storage.download_images,
        "download_avatars": config.storage.download_avatars,
        "compress_html": config.storage.compress_html,
        "backup_enabled": config.storage.backup_enabled,
        "backup_interval_days": config.storage.backup_interval_days,
        # 日志设置
        "log_level": config.logging.level,
        "console_output": config.logging.console_output,
        "log_sql": config.logging.log_sql,
    }


@app.post("/api/config")
async def update_config(config_update: ConfigUpdate):
    """更新配置"""
    try:
        # 读取现有配置
        config_path = Path("/app/config/config.yaml")
        if not config_path.exists():
            config_path = Path("config/config.yaml")

        import yaml

        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        else:
            config_data = {}

        # 更新知乎配置
        config_data["zhihu"] = {
            "user_id": config_update.user_id,
            "scan_interval": config_update.scan_interval,
            "max_items_per_scan": config_update.max_items_per_scan,
            "save_comments": config_update.save_comments,
            "max_comments": config_update.max_comments,
            "sync_likes": config_update.sync_likes,
            "sync_created": config_update.sync_created,
            "skip_video": config_update.skip_video,
            "min_voteup": config_update.min_voteup,
        }

        # 更新浏览器配置
        config_data["browser"] = {
            "headless": config_update.headless,
            "browser_type": config_update.browser_type,
            "timeout": config_update.timeout,
            "request_delay": config_update.request_delay,
            "proxy": config_update.proxy,
            "window_width": config_update.window_width,
            "window_height": config_update.window_height,
            "scroll_delay": config_update.scroll_delay,
            "max_scroll_rounds": config_update.max_scroll_rounds,
        }

        # 更新存储配置
        config_data["storage"] = config_data.get("storage", {})
        config_data["storage"].update(
            {
                "download_images": config_update.download_images,
                "download_avatars": config_update.download_avatars,
                "compress_html": config_update.compress_html,
                "backup_enabled": config_update.backup_enabled,
                "backup_interval_days": config_update.backup_interval_days,
            }
        )

        # 更新日志配置
        config_data["logging"] = config_data.get("logging", {})
        config_data["logging"].update(
            {
                "level": config_update.log_level,
                "console_output": config_update.console_output,
                "log_sql": config_update.log_sql,
            }
        )

        # 保存
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)

        # 重新加载配置
        global config
        config = load_config(str(config_path))

        return {"status": "success", "message": "配置已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cookies")
async def update_cookies(cookie_update: CookieUpdate):
    """更新 Cookie - 支持多种格式（JSON/TXT/Header/KeyValue）"""
    try:
        from cookie_parser import parse_cookies, validate_zhihu_cookies

        # 解析 cookies（支持多种格式）
        storage_state = parse_cookies(cookie_update.cookies, cookie_update.format)

        # 验证关键 cookie
        is_valid, msg, missing = validate_zhihu_cookies(storage_state)

        # 保存到文件
        cookie_file = get_cookie_file_path()
        cookie_file.parent.mkdir(parents=True, exist_ok=True)

        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(storage_state, f, indent=2, ensure_ascii=False)

        cookie_count = len(storage_state.get("cookies", []))

        # 保存 cookie 信息到配置文件（包括域名等基本信息）
        cookie_domains = set()
        for cookie in storage_state.get("cookies", []):
            domain = cookie.get("domain", "")
            if domain:
                cookie_domains.add(domain)

        update_config_file(
            cookie_info={
                "domains": list(cookie_domains),
                "cookie_count": cookie_count,
                "valid": is_valid,
            }
        )

        # 构建响应消息
        message = (
            f"Cookie 已保存 ({cookie_count} 条) - {msg}"
            if is_valid and missing
            else f"Cookie 已保存 ({cookie_count} 条)"
            if is_valid
            else f"Cookie 已保存 ({cookie_count} 条) - ⚠️ {msg}"
        )

        return {
            "status": "success",
            "message": message,
            "cookie_count": cookie_count,
            "valid": is_valid,
            "missing": missing,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"格式解析失败: {str(e)}")
    except Exception as e:
        logger.exception("保存 Cookie 失败")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cookies/check")
async def check_cookies():
    """检查 Cookie 是否存在，返回详细信息"""
    cookie_file = get_cookie_file_path()
    exists = cookie_file.exists()

    if not exists:
        return {"exists": False, "valid": False}

    try:
        with open(cookie_file, encoding="utf-8") as f:
            data = json.load(f)
        # 检查是否有 cookies (支持数组或对象格式)
        has_cookies = False
        if isinstance(data, list) and len(data) > 0:
            has_cookies = True
        elif isinstance(data, dict):
            has_cookies = bool(data.get("cookies")) or bool(data.get("origins"))

        # 获取文件修改时间作为添加时间
        stat = cookie_file.stat()
        added_time = datetime.fromtimestamp(stat.st_mtime).isoformat()

        # 获取缓存的用户信息
        cookie_info = app_state.get("cookie_info", {})

        return {
            "exists": True,
            "valid": has_cookies,
            "user_id": cookie_info.get("user_id"),
            "user_name": cookie_info.get("user_name"),
            "added_time": added_time,
            "is_logged_in": cookie_info.get("is_logged_in", False),
        }
    except Exception:
        return {
            "exists": True,
            "valid": False,
            "user_id": None,
            "user_name": None,
            "added_time": None,
            "is_logged_in": False,
        }


@app.post("/api/cookies/test")
async def test_cookies():
    """测试 Cookie 是否有效 - 实际登录测试"""
    cookie_file = get_cookie_file_path()

    if not cookie_file.exists():
        raise HTTPException(status_code=400, detail="Cookie 文件不存在，请先配置 Cookie")

    try:
        # 加载 Cookie 文件检查格式
        with open(cookie_file, encoding="utf-8") as f:
            cookie_data = json.load(f)

        if not cookie_data.get("cookies") and not cookie_data.get("origins"):
            raise HTTPException(status_code=400, detail="Cookie 格式无效或为空")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Cookie 文件格式错误")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取 Cookie 失败: {str(e)}")

    # 启动浏览器测试登录
    try:
        async with ZhihuCrawler(
            user_id="test",  # 测试时不需要真实用户ID
            db_manager=db,
            storage_manager=storage,
            headless=True,
            request_delay=1.0,
            browser_type="auto",
        ) as crawler:
            result = await crawler.test_login()

            if result.get("is_logged_in"):
                user_id = result.get("user_id")
                user_name = result.get("user_name")

                # 缓存 cookie 信息
                app_state["cookie_info"] = {
                    "user_id": user_id,
                    "user_name": user_name,
                    "is_logged_in": True,
                }

                # 同时更新配置文件
                update_config_file(
                    user_id=user_id,
                    cookie_info={
                        "user_id": user_id,
                        "user_name": user_name,
                        "is_logged_in": True,
                        "verified_at": datetime.now().isoformat(),
                    },
                )

                return {
                    "status": "success",
                    "is_logged_in": True,
                    "user_name": user_name,
                    "user_id": user_id,
                    "message": result.get("message", "登录有效"),
                }
            else:
                # 清除缓存
                app_state["cookie_info"] = None
                return {
                    "status": "error",
                    "is_logged_in": False,
                    "message": result.get("message", "Cookie 已失效"),
                    "current_url": result.get("current_url"),
                }

    except Exception as e:
        logger.exception("Cookie 测试失败")
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


@app.get("/api/storage/mounts")
async def get_storage_mounts():
    """获取 Docker 存储挂载映射信息."""
    import os

    try:
        # 尝试获取容器信息（如果在 Docker 中运行）
        hostname = os.environ.get("HOSTNAME", "")

        # 检查是否在 Docker 环境中
        in_docker = Path("/.dockerenv").exists() or os.environ.get("ZHIHUSYNC_ENV") == "docker"

        if in_docker:
            # 读取 /proc/self/mountinfo 获取挂载信息
            mount_info = []
            try:
                with open("/proc/self/mountinfo", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 10:
                            # mountinfo 格式: ID parentID major:minor root mount_point mount_options... separator fs_type source super_options
                            # 找到 docker 相关的挂载
                            mount_point = parts[4]
                            root = parts[3]
                            if mount_point.startswith("/app/data") or mount_point.startswith("/app/config"):
                                mount_info.append(
                                    {
                                        "container_path": mount_point,
                                        "host_path": root if root != "/" else mount_point,
                                    }
                                )
            except Exception:
                pass

        # 构建存储路径映射
        mounts = {
            "html": {
                "container_path": config.storage.html_path,
                "description": "HTML 文件存储",
            },
            "db": {
                "container_path": config.storage.db_path,
                "description": "数据库文件",
            },
            "static": {
                "container_path": config.storage.static_path,
                "description": "静态资源文件",
            },
            "images": {
                "container_path": config.storage.images_path,
                "description": "图片文件",
            },
            "cookie": {
                "container_path": str(get_cookie_file_path()),
                "description": "Cookie 文件",
            },
        }

        # 尝试从环境变量获取 Docker 挂载信息
        docker_mounts = {}
        for key, value in os.environ.items():
            if key.startswith("DOCKER_MOUNT_"):
                mount_name = key.replace("DOCKER_MOUNT_", "").lower()
                docker_mounts[mount_name] = value

        return {
            "in_docker": in_docker,
            "mounts": mounts,
            "docker_mounts": docker_mounts,
            "mount_info": mount_info if in_docker else [],
            "hostname": hostname,
        }
    except Exception as e:
        logger.error(f"获取存储挂载信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取挂载信息失败: {str(e)}")


@app.post("/api/storage/migrate")
async def migrate_storage(data: dict):
    """迁移数据到新的存储位置."""
    try:
        new_html_path = data.get("html_path")
        new_db_path = data.get("db_path")
        new_static_path = data.get("static_path")
        new_images_path = data.get("images_path")

        if not all([new_html_path, new_db_path, new_static_path, new_images_path]):
            raise HTTPException(status_code=400, detail="缺少必要的路径参数")

        # 类型断言（已通过上面的检查确保不为 None）
        new_html_path = str(new_html_path)
        new_db_path = str(new_db_path)
        new_static_path = str(new_static_path)
        new_images_path = str(new_images_path)

        # 创建新目录
        Path(new_html_path).mkdir(parents=True, exist_ok=True)
        Path(new_db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(new_static_path).mkdir(parents=True, exist_ok=True)
        Path(new_images_path).mkdir(parents=True, exist_ok=True)

        # 执行数据迁移（使用 shutil）
        import shutil

        # 迁移 HTML
        if Path(config.storage.html_path).exists():
            for item in Path(config.storage.html_path).iterdir():
                dest = Path(new_html_path) / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

        # 迁移数据库
        if Path(config.storage.db_path).exists():
            shutil.copy2(str(config.storage.db_path), new_db_path)

        # 迁移静态资源
        if Path(config.storage.static_path).exists():
            for item in Path(config.storage.static_path).iterdir():
                dest = Path(new_static_path) / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

        # 迁移图片
        if Path(config.storage.images_path).exists():
            for item in Path(config.storage.images_path).iterdir():
                dest = Path(new_images_path) / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

        # 更新配置
        update_config_file(
            cookie_info={
                "migrated_at": datetime.now().isoformat(),
                "old_paths": {
                    "html": config.storage.html_path,
                    "db": config.storage.db_path,
                    "static": config.storage.static_path,
                    "images": config.storage.images_path,
                },
                "new_paths": {
                    "html": new_html_path,
                    "db": new_db_path,
                    "static": new_static_path,
                    "images": new_images_path,
                },
            }
        )

        return {
            "status": "success",
            "message": "数据迁移完成，需要重启服务以应用新配置",
            "new_paths": {
                "html": new_html_path,
                "db": new_db_path,
                "static": new_static_path,
                "images": new_images_path,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("数据迁移失败")
        raise HTTPException(status_code=500, detail=f"数据迁移失败: {str(e)}")


@app.post("/api/system/restart")
async def restart_service():
    """重启服务（通过退出进程让 Docker 重新启动容器）."""

    async def do_restart():
        await asyncio.sleep(2)  # 给前端响应时间
        os.kill(os.getpid(), signal.SIGTERM)

    # 启动异步任务来重启
    asyncio.create_task(do_restart())

    return {
        "status": "restarting",
        "message": "服务正在重启，请稍候刷新页面",
    }


async def do_sync(sync_type: str = "manual"):
    """执行同步任务.

    Args:
        sync_type: 同步类型 (manual/scheduled/full).
    """
    app_state["sync_status"] = "running"
    app_state["sync_progress"] = 0
    app_state["sync_message"] = "正在初始化..."

    # 获取同步用户ID
    user_id = get_sync_user_id()
    if not user_id:
        raise RuntimeError("未配置用户ID")

    # 创建同步日志
    log_id = db.create_sync_log(user_id=user_id, sync_type=sync_type)

    try:
        # 停止检查回调
        def stop_check():
            return app_state.get("stop_requested", False)

        async with ZhihuCrawler(
            user_id=user_id,
            db_manager=db,
            storage_manager=storage,
            headless=True,
            request_delay=config.browser.request_delay,
            max_comments=config.zhihu.max_comments,
            stop_check_callback=stop_check,
        ) as crawler:

            def progress_callback(current, total):
                app_state["sync_progress"] = int(current / total * 100) if total > 0 else 0
                total_str = str(total) if total > 0 else "?"
                app_state["sync_message"] = f"正在同步: {current}/{total_str}"

            app_state["sync_message"] = "正在扫描点赞内容..."
            # 【普通采集模式】
            # - 遇到已存在的重复数据时停止
            # - 404处理：保存删除状态记录用于完整性
            new_items, updated_items = await crawler.scan_likes(
                max_items=config.zhihu.max_items_per_scan,
                progress_callback=progress_callback,
                scan_mode="normal",  # 普通采集模式
            )

            if config.zhihu.save_comments:
                app_state["sync_message"] = "正在同步评论..."
                await crawler.sync_all_comments()

            # 更新同步日志
            db.update_sync_log(
                log_id=log_id,
                status="success",
                items_scanned=new_items + updated_items,
                items_new=new_items,
                items_updated=updated_items,
            )

            app_state["sync_status"] = "success"
            app_state["sync_message"] = f"同步完成! 新增 {new_items} 条, 更新 {updated_items} 条"
            app_state["last_sync"] = get_beijing_now().isoformat()

    except RuntimeError as e:
        # 预检查失败等已知错误
        error_msg = str(e)
        db.update_sync_log(log_id=log_id, status="failed", error_message=error_msg)
        app_state["sync_status"] = "failed"
        app_state["sync_message"] = error_msg
        logger.error(f"同步任务失败: {error_msg}")
        # 不抛出异常，让前端能看到错误状态

    except Exception as e:
        db.update_sync_log(log_id=log_id, status="failed", error_message=str(e))
        app_state["sync_status"] = "failed"
        app_state["sync_message"] = f"同步失败: {str(e)}"
        raise


@app.post("/api/sync/start")
async def start_sync():
    """开始同步（手工增量同步）"""
    if app_state["sync_status"] == "running":
        return {"status": "running", "message": "同步任务已在运行中"}

    # 检查是否有用户（数据库或配置文件）
    if not get_sync_user_id():
        raise HTTPException(status_code=400, detail="未配置用户ID")

    # 创建异步任务，标记为手工同步
    app_state["sync_task"] = asyncio.create_task(do_sync(sync_type="manual"))

    return {"status": "started", "message": "同步任务已启动"}


@app.get("/api/sync/status")
async def get_sync_status():
    """获取同步状态"""
    return {
        "status": app_state["sync_status"],
        "message": app_state["sync_message"],
        "progress": app_state["sync_progress"],
        "last_sync": app_state["last_sync"],
    }


@app.post("/api/sync/stop")
async def stop_sync():
    """停止同步"""
    if app_state["sync_status"] != "running":
        return {"status": "idle", "message": "没有正在运行的同步任务"}

    # 设置停止标志，通知爬虫优雅停止
    app_state["stop_requested"] = True
    app_state["sync_status"] = "stopping"
    app_state["sync_message"] = "正在停止同步..."

    # 如果任务还在运行，等待一段时间后再取消
    if app_state["sync_task"] and not app_state["sync_task"].done():
        try:
            # 等待 5 秒让爬虫优雅停止
            await asyncio.wait_for(app_state["sync_task"], timeout=5.0)
        except asyncio.TimeoutError:
            # 超时后强制取消
            app_state["sync_task"].cancel()
        except asyncio.CancelledError:
            pass

    # 重置状态
    app_state["sync_status"] = "idle"
    app_state["stop_requested"] = False
    app_state["sync_message"] = "同步已手动停止"

    return {"status": "stopped", "message": "同步任务已停止"}


@app.post("/api/sync/init")
async def start_init_sync():
    """开始初始化同步（全量爬取历史数据）"""
    if app_state["sync_task"] and not app_state["sync_task"].done():
        return {"status": "error", "message": "已有同步任务在运行"}

    # 获取同步用户ID
    user_id = get_sync_user_id()
    if not user_id:
        raise HTTPException(status_code=400, detail="未配置用户ID")

    async def do_init_sync():
        """执行初始化同步"""
        # 创建同步日志，标记为全量同步
        log_id = db.create_sync_log(user_id=user_id, sync_type="full")

        try:
            app_state["sync_status"] = "running"
            app_state["sync_message"] = "全量同步中..."
            app_state["sync_progress"] = 0

            new_items = 0
            updated_items = 0

            def progress_callback(current: int, total: int):
                if total > 0:
                    app_state["sync_progress"] = int(current / total * 100)
                else:
                    # 无限制模式，显示已处理数量
                    app_state["sync_progress"] = current
                app_state["sync_message"] = f"已处理 {current} 条点赞..."

            # 停止检查回调
            def stop_check():
                return app_state.get("stop_requested", False)

            async with ZhihuCrawler(
                user_id=user_id,
                db_manager=db,
                storage_manager=storage,
                headless=True,
                request_delay=config.browser.request_delay,
                max_comments=config.zhihu.max_comments,
                stop_check_callback=stop_check,
            ) as crawler:
                # 【全量采集模式】
                # - 穷尽所有点赞记录（max_items=-1 无限制）
                # - 404处理：未下载过的跳过，已下载的高亮标注
                new_items, updated_items = await crawler.scan_likes(
                    max_items=-1,  # 无限制
                    progress_callback=progress_callback,
                    init_mode=True,
                    scan_mode="full",  # 全量采集模式
                )

            # 更新同步日志
            db.update_sync_log(
                log_id=log_id,
                status="success",
                items_scanned=new_items + updated_items,
                items_new=new_items,
                items_updated=updated_items,
            )

            app_state["sync_status"] = "success"
            app_state["sync_message"] = f"全量同步完成! 新增 {new_items} 条, 更新 {updated_items} 条"
            app_state["last_sync"] = get_beijing_now().isoformat()

        except RuntimeError as e:
            # 预检查失败等已知错误
            error_msg = str(e)
            logger.error(f"全量同步失败: {error_msg}")
            db.update_sync_log(log_id=log_id, status="failed", error_message=error_msg)
            app_state["sync_status"] = "failed"
            app_state["sync_message"] = error_msg

        except Exception as e:
            logger.exception(f"全量同步失败: {e}")
            db.update_sync_log(log_id=log_id, status="failed", error_message=str(e))
            app_state["sync_status"] = "failed"
            app_state["sync_message"] = f"全量同步失败: {e}"

    # 创建异步任务
    app_state["sync_task"] = asyncio.create_task(do_init_sync())

    return {"status": "started", "message": "全量同步已启动（将爬取全部历史数据）"}


@app.get("/api/answers")
async def get_answers(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    is_deleted: bool | None = None,
    download_status: str | None = None,
    comment_anomaly: bool | None = None,
    voteup_min: int | None = None,
    voteup_max: int | None = None,
    comment_min: int | None = None,
    comment_max: int | None = None,
    sort: str = "liked_time",
    order: str = "desc",
):
    """获取回答列表"""
    session = db.get_session()
    try:
        query = session.query(Answer)

        # 搜索筛选
        if search:
            query = query.filter(or_(Answer.question_title.contains(search), Answer.author_name.contains(search)))

        # 删除状态筛选
        if is_deleted is not None:
            query = query.filter(Answer.is_deleted == is_deleted)

        # 下载状态筛选
        if download_status:
            query = query.filter(Answer.download_status == download_status)

        # 评论异常筛选（预期有评论但实际未获取的）
        if comment_anomaly:
            query = query.filter(Answer.comment_count > 0, Answer.has_comments.is_(False))

        # 点赞数范围筛选
        if voteup_min is not None:
            query = query.filter(Answer.voteup_count >= voteup_min)
        if voteup_max is not None:
            query = query.filter(Answer.voteup_count <= voteup_max)

        # 评论数范围筛选
        if comment_min is not None:
            query = query.filter(Answer.comment_count >= comment_min)
        if comment_max is not None:
            query = query.filter(Answer.comment_count <= comment_max)

        total = query.count()

        # 排序
        sort_column = getattr(Answer, sort, Answer.liked_time)
        query = query.order_by(sort_column.desc() if order == "desc" else sort_column.asc())

        answers = query.offset((page - 1) * page_size).limit(page_size).all()

        items = []
        for a in answers:
            # 获取用户信息
            user = a.user
            items.append(
                {
                    "id": a.id,
                    "user_id": a.user_id,
                    "user_name": user.name if user else None,
                    "user_avatar_url": user.avatar_url if user else None,
                    "question_title": a.question_title,
                    "author_name": a.author_name or "匿名用户",
                    "author_avatar_url": a.author_avatar_url,
                    "author_headline": a.author_headline,
                    "voteup_count": a.voteup_count,
                    "comment_count": a.comment_count,
                    "created_time": a.created_time.isoformat() if a.created_time else "",
                    "updated_time": a.updated_time.isoformat() if a.updated_time else "",
                    "liked_time": a.liked_time.isoformat() if a.liked_time else "",
                    "synced_at": a.synced_at.isoformat() if a.synced_at else "",
                    "html_path": a.html_path,
                    "original_url": a.original_url,
                }
            )

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    finally:
        session.close()


@app.get("/api/logs")
async def get_logs(lines: int = 100):
    """获取日志"""
    log_file = Path(config.logging.file)

    if not log_file.exists():
        return {"logs": []}

    try:
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            return {"logs": all_lines[-lines:]}
    except Exception as e:
        return {"logs": [f"读取日志失败: {e}"]}


@app.get("/api/sync/history")
async def get_sync_history(page: int = 1, page_size: int = 10):
    """获取同步历史"""
    session = db.get_session()
    try:
        query = session.query(SyncLog).order_by(SyncLog.started_at.desc())
        total = query.count()
        logs = query.offset((page - 1) * page_size).limit(page_size).all()

        items = []
        for log in logs:
            items.append(
                {
                    "id": log.id,
                    "started_at": log.started_at.isoformat() if log.started_at else None,
                    "ended_at": log.ended_at.isoformat() if log.ended_at else None,
                    "status": log.status,
                    "sync_type": log.sync_type or "manual",  # 兼容旧数据
                    "items_scanned": log.items_scanned,
                    "items_new": log.items_new,
                    "items_updated": log.items_updated,
                    "error_message": log.error_message,
                }
            )

        return {"items": items, "total": total, "page": page, "page_size": page_size}
    finally:
        session.close()


@app.delete("/api/answers/{answer_id}")
async def delete_answer(answer_id: str):
    """删除回答及其关联的图片"""
    try:
        answer = db.get_answer_by_id(answer_id)
        if not answer:
            raise HTTPException(status_code=404, detail="回答不存在")

        # 删除文件(HTML和相关图片)
        delete_result = await storage.delete_answer_files(answer_id)
        logger.info(f"删除回答文件: {delete_result}")

        # 从数据库删除
        session = db.get_session()
        try:
            from db import Answer

            session.query(Answer).filter_by(id=answer_id).delete()
            session.commit()
        finally:
            session.close()

        return {
            "status": "success",
            "message": "已删除",
            "detail": delete_result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 图片生成 API ============


@app.post("/api/answers/{answer_id}/generate-image")
async def generate_answer_image_api(
    answer_id: str,
    card_style: str = Query("default", description="卡片样式: default/compact/minimal"),
    include_comments: bool = Query(False, description="是否包含评论区"),
):
    """为指定回答生成截图/长图.

    Args:
        answer_id: 回答ID.
        card_style: 卡片样式 (default-默认, compact-紧凑, minimal-极简).
        include_comments: 是否包含评论区.

    Returns:
        包含生成图片路径的响应.
    """
    try:
        # 获取回答信息
        answer = db.get_answer_by_id(answer_id)
        if not answer:
            raise HTTPException(status_code=404, detail="回答不存在")

        if not answer.html_path:
            raise HTTPException(status_code=400, detail="回答没有 HTML 文件")

        html_path = Path(answer.html_path)
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="HTML 文件不存在")

        # 确保图片目录存在
        images_dir = Path(config.storage.static_path) / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        # 生成图片
        async with ImageGenerator(output_dir=str(images_dir)) as generator:
            image_path = await generator.generate_answer_card(
                html_path=str(html_path),
                include_comments=include_comments,
                card_style=card_style,
            )

        # 计算相对路径用于访问
        relative_path = Path(image_path).relative_to(config.storage.images_path)

        return {
            "status": "success",
            "message": "图片生成成功",
            "data": {
                "image_path": image_path,
                "relative_path": str(relative_path),
                "image_url": f"/data/images/answers/{Path(image_path).name}",
                "answer_id": answer_id,
                "question_title": answer.question_title,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"生成图片失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成图片失败: {str(e)}")


@app.get("/api/images")
async def list_generated_images(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取已生成的图片列表.

    Args:
        page: 页码.
        page_size: 每页数量.

    Returns:
        图片列表.
    """
    try:
        images_dir = Path(config.storage.images_path) / "screenshots"
        if not images_dir.exists():
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

        # 获取所有图片文件
        image_files = sorted(
            images_dir.glob("*.png"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        total = len(image_files)
        start = (page - 1) * page_size
        end = start + page_size
        page_files = image_files[start:end]

        items = []
        for f in page_files:
            stat = f.stat()
            items.append(
                {
                    "filename": f.name,
                    "url": f"/data/images/screenshots/{f.name}",
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    except Exception as e:
        logger.exception(f"获取图片列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/images/{filename}")
async def get_image(filename: str):
    """获取生成的图片文件.

    Args:
        filename: 图片文件名.

    Returns:
        图片文件.
    """
    try:
        image_path = Path(config.storage.static_path) / "images" / filename
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="图片不存在")

        return FileResponse(
            path=image_path,
            media_type="image/png",
            filename=filename,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/images/{filename}")
async def delete_image(filename: str):
    """删除生成的图片.

    Args:
        filename: 图片文件名.

    Returns:
        删除结果.
    """
    try:
        image_path = Path(config.storage.static_path) / "images" / filename
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="图片不存在")

        image_path.unlink()
        return {"status": "success", "message": "图片已删除"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 提取错误管理 API ============


@app.get("/api/extraction-errors")
async def get_extraction_errors(page: int = 1, page_size: int = 20, resolved: bool = False):
    """获取内容提取错误列表.

    Args:
        page: 页码.
        page_size: 每页数量.
        resolved: 是否包含已解决的错误.

    Returns:
        错误列表和总数.
    """
    from models import ExtractionError

    session = db.get_session()
    try:
        query = session.query(ExtractionError)
        if not resolved:
            query = query.filter_by(resolved=False)

        total = query.count()
        errors = query.order_by(ExtractionError.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        return {
            "items": [
                {
                    "id": e.id,
                    "answer_id": e.answer_id,
                    "question_title": e.question_title,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "resolved": e.resolved,
                }
                for e in errors
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        session.close()


@app.post("/api/extraction-errors/{error_id}/resolve")
async def resolve_extraction_error(error_id: int):
    """标讹提取错误为已解决.

    Args:
        error_id: 错误记录ID.

    Returns:
        操作结果.
    """
    success = db.resolve_extraction_error(error_id)
    if not success:
        raise HTTPException(status_code=404, detail="错误记录不存在")
    return {"status": "success", "message": "已标记为已解决"}


@app.post("/api/extraction-errors/resolve-all")
async def resolve_all_extraction_errors():
    """标讹所有提取错误为已解决.

    Returns:
        操作结果.
    """
    count = db.resolve_all_extraction_errors()
    if count == 0:
        return {"status": "success", "message": "没有未解决的错误记录"}
    return {"status": "success", "message": f"已标记 {count} 条错误为已解决"}


@app.delete("/api/extraction-errors/{error_id}")
async def delete_extraction_error(error_id: int):
    """删除提取错误记录.

    Args:
        error_id: 错误记录ID.

    Returns:
        操作结果.
    """
    success = db.delete_extraction_error(error_id)
    if not success:
        raise HTTPException(status_code=404, detail="错误记录不存在")
    return {"status": "success", "message": "错误记录已删除"}


# ============ 下载失败管理 API ============


@app.get("/api/download-failures")
async def get_download_failures(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    resolved: bool = Query(False),
    user_id: str | None = None,
):
    """获取下载失败列表.

    Args:
        page: 页码.
        page_size: 每页数量.
        resolved: 是否包含已解决的.
        user_id: 过滤用户ID.

    Returns:
        下载失败列表.
    """
    from models import DownloadFailure

    session = db.get_session()
    try:
        query = session.query(DownloadFailure)
        if not resolved:
            query = query.filter_by(resolved=False)
        if user_id:
            query = query.filter_by(user_id=user_id)

        total = query.count()
        failures = (
            query.order_by(DownloadFailure.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        )

        return {
            "items": [
                {
                    "id": f.id,
                    "answer_id": f.answer_id,
                    "question_title": f.question_title,
                    "user_id": f.user_id,
                    "question_id": f.question_id,
                    "error_type": f.error_type,
                    "error_message": f.error_message,
                    "http_status": f.http_status,
                    "retry_count": f.retry_count,
                    "max_retries": f.max_retries,
                    "last_retry_at": f.last_retry_at.isoformat() if f.last_retry_at else None,
                    "resolved": f.resolved,
                    "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in failures
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    finally:
        session.close()


@app.get("/api/download-failures/stats")
async def get_download_failure_stats():
    """获取下载失败统计.

    Returns:
        下载失败统计信息.
    """
    return db.get_download_failure_stats()


@app.post("/api/download-failures/{failure_id}/retry")
async def retry_download_failure(failure_id: int):
    """重试单个下载失败.

    Args:
        failure_id: 失败记录ID.

    Returns:
        重试结果.
    """
    from models import DownloadFailure

    session = db.get_session()
    try:
        failure = session.query(DownloadFailure).filter_by(id=failure_id).first()
        if not failure:
            raise HTTPException(status_code=404, detail="失败记录不存在")

        if failure.resolved:
            return {"status": "skipped", "message": "该记录已解决"}

        answer_id = failure.answer_id
    finally:
        session.close()

    # 启动重试任务
    async def do_retry():
        try:
            async with ZhihuCrawler(
                user_id=config.zhihu.user_id,
                db_manager=db,
                storage_manager=storage,
                headless=True,
                request_delay=config.browser.request_delay,
            ) as crawler:
                result = await crawler.retry_specific_answer(answer_id)
                return result
        except Exception as e:
            logger.exception(f"重试下载失败: {e}")
            return {"success": False, "message": str(e)}

    result = await do_retry()
    return {"status": "success" if result.get("success") else "failed", "data": result}


@app.post("/api/download-failures/retry-all")
async def retry_all_download_failures(max_items: int = Query(50, ge=1, le=100)):
    """批量重试所有失败的下载.

    Args:
        max_items: 最大重试数量.

    Returns:
        重试结果.
    """
    if app_state["sync_status"] == "running":
        return {"status": "error", "message": "已有同步任务在运行"}

    async def do_batch_retry():
        try:
            app_state["sync_status"] = "running"
            app_state["sync_message"] = "正在重试失败的下载..."

            async with ZhihuCrawler(
                user_id=config.zhihu.user_id,
                db_manager=db,
                storage_manager=storage,
                headless=True,
                request_delay=config.browser.request_delay,
            ) as crawler:
                stats = await crawler.retry_failed_downloads(max_items=max_items)

            app_state["sync_status"] = "success"
            app_state["sync_message"] = f"重试完成: 成功 {stats['success']} 条"
            return stats
        except Exception as e:
            logger.exception(f"批量重试失败: {e}")
            app_state["sync_status"] = "failed"
            app_state["sync_message"] = f"重试失败: {e}"
            raise
        finally:
            if app_state["sync_status"] == "running":
                app_state["sync_status"] = "idle"

    # 创建异步任务
    asyncio.create_task(do_batch_retry())
    return {"status": "started", "message": f"开始批量重试，最多处理 {max_items} 条"}


@app.post("/api/download-failures/{failure_id}/resolve")
async def resolve_download_failure_api(failure_id: int):
    """标记下载失败为已解决.

    Args:
        failure_id: 失败记录ID.

    Returns:
        操作结果.
    """
    success = db.resolve_download_failure(failure_id)
    if not success:
        raise HTTPException(status_code=404, detail="失败记录不存在")
    return {"status": "success", "message": "已标记为已解决"}


@app.post("/api/answers/{answer_id}/retry")
async def retry_answer_download(answer_id: str):
    """重试特定回答的下载.

    Args:
        answer_id: 回答ID.

    Returns:
        重试结果.
    """
    answer = db.get_answer_by_id(answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail="回答不存在")

    async def do_retry():
        try:
            async with ZhihuCrawler(
                user_id=answer.user_id or config.zhihu.user_id,
                db_manager=db,
                storage_manager=storage,
                headless=True,
                request_delay=config.browser.request_delay,
            ) as crawler:
                result = await crawler.retry_specific_answer(answer_id)
                return result
        except Exception as e:
            logger.exception(f"重试下载失败: {e}")
            return {"success": False, "message": str(e)}

    result = await do_retry()
    if result.get("success"):
        return {"status": "success", "message": "下载成功", "data": result}
    else:
        raise HTTPException(status_code=400, detail=result.get("message", "下载失败"))


@app.post("/api/comments/retry-anomaly")
async def retry_comment_anomaly():
    """重新采集评论异常的回答.

    获取所有 comment_count > 0 但 has_comments = False 的回答，
    重新尝试采集它们的评论。

    Returns:
        重试结果.
    """
    if app_state["sync_status"] == "running":
        return {"status": "error", "message": "已有同步任务在运行"}

    async def do_retry():
        try:
            app_state["sync_status"] = "running"
            app_state["sync_message"] = "正在重新采集评论异常项..."

            # 获取评论异常的回答列表
            from models import Answer

            session = db.get_session()
            try:
                anomaly_answers = (
                    session.query(Answer).filter(Answer.comment_count > 0, Answer.has_comments.is_(False)).all()
                )
            finally:
                session.close()

            if not anomaly_answers:
                return {"status": "success", "message": "没有评论异常项需要处理"}

            total = len(anomaly_answers)
            success_count = 0
            fail_count = 0

            async with ZhihuCrawler(
                user_id=config.zhihu.user_id,
                db_manager=db,
                storage_manager=storage,
                headless=True,
                request_delay=config.browser.request_delay,
            ) as crawler:
                for i, answer in enumerate(anomaly_answers):
                    app_state["sync_message"] = f"正在采集评论 ({i + 1}/{total}): {answer.question_title[:30]}..."

                    try:
                        result = await crawler.process_comments(answer.id)
                        if result.get("success"):
                            success_count += 1
                        else:
                            fail_count += 1

                        # 间隔延迟避免请求过快
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.warning(f"采集评论失败 [{answer.id}]: {e}")
                        fail_count += 1

            app_state["sync_status"] = "success"
            app_state["sync_message"] = f"评论重采完成: 成功 {success_count}, 失败 {fail_count}"

            return {
                "status": "success",
                "message": f"处理完成: 成功 {success_count} 条, 失败 {fail_count} 条",
                "total": total,
                "success": success_count,
                "failed": fail_count,
            }
        except Exception as e:
            logger.exception(f"评论重采失败: {e}")
            app_state["sync_status"] = "failed"
            app_state["sync_message"] = f"评论重采失败: {e}"
            raise
        finally:
            if app_state["sync_status"] == "running":
                app_state["sync_status"] = "idle"

    # 创建异步任务
    asyncio.create_task(do_retry())
    return {"status": "started", "message": "开始重新采集评论异常项"}


# 启动函数
def start_web(host: str = "0.0.0.0", port: int = 6067, reload: bool = False):
    """启动 Web 服务"""
    import uvicorn

    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_web()
