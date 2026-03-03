"""Web 管理界面 - FastAPI 后端"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from config_loader import load_config
from crawler import ZhihuCrawler
from db import Answer, DatabaseManager, SyncLog
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from image_generator import ImageGenerator
from loguru import logger
from pydantic import BaseModel
from storage import StorageManager
from timezone_utils import get_beijing_now

# 全局状态
app_state: dict[str, Any] = {
    "sync_task": None,
    "sync_status": "idle",  # idle, running, success, failed
    "sync_progress": 0,
    "sync_message": "",
    "last_sync": None,
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

# 静态文件和模板
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# 挂载数据目录以便访问备份的 HTML
app.mount(
    "/data/html",
    StaticFiles(directory=config.storage.html_path),
    name="html_files",
)

# 挂载静态资源目录以便访问生成的图片
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


class CookieUpdate(BaseModel):
    """Cookie 更新请求模型."""

    cookies: str  # JSON 格式的 cookies


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
    deleted_answers: int
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


@app.get("/donate")
async def donate_page(request: Request):
    """捐赠页面"""
    return templates.TemplateResponse("donate.html", {"request": request})


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

    return StatsResponse(
        total_answers=stats["total_answers"],
        total_comments=stats["total_comments"],
        with_comments=stats["with_comments"],
        deleted_answers=stats["deleted_answers"],
        last_sync=last_sync,
        sync_status=app_state["sync_status"],
    )


@app.get("/api/setup/status")
async def get_setup_status():
    """获取配置状态"""
    cookie_file = get_cookie_file_path()
    has_cookie = cookie_file.exists() and cookie_file.stat().st_size > 0

    return {
        "configured": bool(config.zhihu.user_id) and has_cookie,
        "has_user_id": bool(config.zhihu.user_id),
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
    """更新 Cookie - 支持多种格式（EditThisCookie 数组 或 Playwright storage_state）"""
    try:
        # 解析 cookies
        cookies_data = json.loads(cookie_update.cookies)

        # 处理 EditThisCookie 格式（数组）转换为 Playwright storage_state 格式
        if isinstance(cookies_data, list):
            # EditThisCookie 格式 - 转换为 Playwright format
            storage_state = {"cookies": cookies_data, "origins": []}
        elif isinstance(cookies_data, dict):
            # 已经是 storage_state 格式或类似格式
            if "cookies" in cookies_data:
                storage_state = cookies_data
            else:
                # 可能是其他格式，包装成 storage_state
                storage_state = {
                    "cookies": ([cookies_data] if not isinstance(cookies_data.get("name"), list) else []),
                    "origins": [],
                }
        else:
            raise ValueError("不支持的 Cookie 格式")

        # 保存到文件
        cookie_file = get_cookie_file_path()
        cookie_file.parent.mkdir(parents=True, exist_ok=True)

        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(storage_state, f, indent=2, ensure_ascii=False)

        cookie_count = len(storage_state.get("cookies", []))
        return {"status": "success", "message": f"Cookie 已保存 ({cookie_count} 条)"}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"无效的 JSON 格式: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cookies/check")
async def check_cookies():
    """检查 Cookie 是否存在"""
    cookie_file = get_cookie_file_path()
    exists = cookie_file.exists()

    if exists:
        try:
            with open(cookie_file, encoding="utf-8") as f:
                data = json.load(f)
            # 检查是否有 cookies (支持数组或对象格式)
            has_cookies = False
            if isinstance(data, list) and len(data) > 0:
                has_cookies = True
            elif isinstance(data, dict):
                has_cookies = bool(data.get("cookies")) or bool(data.get("origins"))
            return {"exists": True, "valid": has_cookies}
        except Exception:
            return {"exists": True, "valid": False}

    return {"exists": False, "valid": False}


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
                return {
                    "status": "success",
                    "is_logged_in": True,
                    "user_name": result.get("user_name"),
                    "user_id": result.get("user_id"),
                    "message": result.get("message", "登录有效"),
                }
            else:
                return {
                    "status": "error",
                    "is_logged_in": False,
                    "message": result.get("message", "Cookie 已失效"),
                    "current_url": result.get("current_url"),
                }

    except Exception as e:
        logger.exception("Cookie 测试失败")
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


async def do_sync():
    """执行同步任务"""
    app_state["sync_status"] = "running"
    app_state["sync_progress"] = 0
    app_state["sync_message"] = "正在初始化..."

    try:
        async with ZhihuCrawler(
            user_id=config.zhihu.user_id,
            db_manager=db,
            storage_manager=storage,
            headless=True,
            request_delay=config.browser.request_delay,
            max_comments=config.zhihu.max_comments,
        ) as crawler:

            def progress_callback(current, total):
                app_state["sync_progress"] = int(current / total * 100)
                app_state["sync_message"] = f"正在同步: {current}/{total}"

            app_state["sync_message"] = "正在扫描点赞内容..."
            new_items, updated_items = await crawler.scan_likes(
                max_items=config.zhihu.max_items_per_scan, progress_callback=progress_callback
            )

            if config.zhihu.save_comments:
                app_state["sync_message"] = "正在同步评论..."
                await crawler.sync_all_comments()

            app_state["sync_status"] = "success"
            app_state["sync_message"] = f"同步完成! 新增 {new_items} 条, 更新 {updated_items} 条"
            app_state["last_sync"] = get_beijing_now().isoformat()

    except Exception as e:
        app_state["sync_status"] = "failed"
        app_state["sync_message"] = f"同步失败: {str(e)}"
        raise


@app.post("/api/sync/start")
async def start_sync(background_tasks: BackgroundTasks):
    """开始同步"""
    if app_state["sync_status"] == "running":
        return {"status": "running", "message": "同步任务已在运行中"}

    if not config.zhihu.user_id:
        raise HTTPException(status_code=400, detail="未配置用户ID")

    # 创建异步任务
    app_state["sync_task"] = asyncio.create_task(do_sync())

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
    if app_state["sync_task"] and not app_state["sync_task"].done():
        app_state["sync_task"].cancel()
        app_state["sync_status"] = "idle"
        app_state["sync_message"] = "同步已取消"

    return {"status": "stopped", "message": "同步任务已停止"}


@app.post("/api/sync/init")
async def start_init_sync():
    """开始初始化同步（全量爬取历史数据）"""
    if app_state["sync_task"] and not app_state["sync_task"].done():
        return {"status": "error", "message": "已有同步任务在运行"}

    async def do_init_sync():
        """执行初始化同步"""
        try:
            app_state["sync_status"] = "running"
            app_state["sync_message"] = "初始化采集中..."
            app_state["sync_progress"] = 0

            def progress_callback(current: int, total: int):
                if total > 0:
                    app_state["sync_progress"] = int(current / total * 100)
                else:
                    # 无限制模式，显示已处理数量
                    app_state["sync_progress"] = current
                app_state["sync_message"] = f"已处理 {current} 条点赞..."

            async with ZhihuCrawler(
                user_id=config.zhihu.user_id,
                db_manager=db,
                storage_manager=storage,
                headless=True,
                request_delay=config.zhihu.request_delay,
                max_comments=config.zhihu.max_comments_per_answer,
            ) as crawler:
                # 使用 init_mode=True 进行全量采集
                await crawler.scan_likes(
                    max_items=-1,  # 无限制
                    progress_callback=progress_callback,
                    init_mode=True,
                )

            app_state["sync_status"] = "success"
            app_state["sync_message"] = "初始化采集完成"
            app_state["last_sync"] = get_beijing_now().isoformat()

        except Exception as e:
            logger.exception(f"初始化同步失败: {e}")
            app_state["sync_status"] = "failed"
            app_state["sync_message"] = f"初始化失败: {e}"

    # 创建异步任务
    app_state["sync_task"] = asyncio.create_task(do_init_sync())

    return {"status": "started", "message": "初始化采集已启动（将爬取全部历史数据）"}


from sqlalchemy import or_


@app.get("/api/answers")
async def get_answers(page: int = 1, page_size: int = 20, search: str = ""):
    """获取回答列表"""
    session = db.get_session()
    try:
        query = session.query(Answer)

        if search:
            query = query.filter(or_(Answer.question_title.contains(search), Answer.author_name.contains(search)))

        total = query.count()
        answers = query.order_by(Answer.liked_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

        items = []
        for a in answers:
            items.append(
                {
                    "id": a.id,
                    "question_title": a.question_title,
                    "author_name": a.author_name or "匿名用户",
                    "author_avatar_url": a.author_avatar_url,
                    "author_headline": a.author_headline,
                    "voteup_count": a.voteup_count,
                    "comment_count": a.comment_count,
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
    """删除回答"""
    try:
        answer = db.get_answer_by_id(answer_id)
        if not answer:
            raise HTTPException(status_code=404, detail="回答不存在")

        # 删除文件
        if answer.html_path:
            html_file = Path(answer.html_path)
            if html_file.exists():
                html_file.unlink()

        # 从数据库删除
        session = db.get_session()
        try:
            from db import Answer

            session.query(Answer).filter_by(id=answer_id).delete()
            session.commit()
        finally:
            session.close()

        return {"status": "success", "message": "已删除"}
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
        relative_path = Path(image_path).relative_to(config.storage.static_path)

        return {
            "status": "success",
            "message": "图片生成成功",
            "data": {
                "image_path": image_path,
                "relative_path": str(relative_path),
                "image_url": f"/data/static/images/{Path(image_path).name}",
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
        images_dir = Path(config.storage.static_path) / "images"
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
                    "url": f"/data/static/images/{f.name}",
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


# 启动函数
def start_web(host: str = "0.0.0.0", port: int = 6067, reload: bool = False):
    """启动 Web 服务"""
    import uvicorn

    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_web()
