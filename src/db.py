"""数据库模块 - 管理元数据存储.

该模块提供数据库管理功能，包括用户管理、回答管理、评论管理、
同步日志和告警配置等。使用 SQLAlchemy ORM 和 SQLite 数据库。

Examples:
    >>> from db import DatabaseManager
    >>> db = DatabaseManager("/path/to/db.sqlite")
    >>> db.add_user("user_id", "User Name")
    >>> stats = db.get_stats()
"""

from pathlib import Path
from typing import Any

from loguru import logger
from models import AlertConfig, Answer, Base, Comment, DownloadFailure, ExtractionError, SyncLog, User
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from timezone_utils import get_beijing_now


class DatabaseManager:
    """数据库管理器.

    管理 SQLite 数据库的连接和所有 CRUD 操作。
    自动创建表结构，提供用户、回答、评论等数据的管理方法。

    Attributes:
        db_path: 数据库文件路径.
        engine: SQLAlchemy 数据库引擎.
        SessionLocal: 会话工厂类.

    Examples:
        >>> db = DatabaseManager("/app/data/meta/zhihusync.db")
        >>> db.add_user("your-user-id", "用户名")
        >>> answer = db.get_answer_by_id("123456")
    """

    def __init__(self, db_path: str):
        """初始化数据库管理器.

        创建数据库引擎，初始化表结构。

        Args:
            db_path: SQLite 数据库文件路径.
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 配置SQLite引擎，优化并发性能
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={
                "check_same_thread": False,
                "timeout": 30,  # 等待锁的超时时间(秒)
            },
            echo=False,
            pool_pre_ping=True,  # 连接前检查连接是否有效
            pool_recycle=3600,  # 连接回收时间
        )

        # 启用 WAL 模式提高并发写入性能
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA cache_size=10000"))
            conn.execute(text("PRAGMA temp_store=MEMORY"))

        self.SessionLocal = sessionmaker(bind=self.engine)

        # 创建表
        Base.metadata.create_all(self.engine)
        logger.info(f"数据库初始化完成: {db_path} (WAL模式)")

    def get_session(self) -> Session:
        """获取数据库会话.

        Returns:
            Session: 数据库会话对象.
        """
        return self.SessionLocal()

    # ========== 用户管理 ==========

    def add_user(self, user_id: str, name: str | None = None) -> bool:
        """添加监控用户.

        Args:
            user_id: 知乎用户ID.
            name: 用户名称(可选).

        Returns:
            bool: 添加成功返回True，用户已存在返回False.
        """
        session = self.get_session()
        try:
            existing = session.query(User).filter_by(id=user_id).first()
            if existing:
                logger.debug(f"用户已存在: {user_id}")
                return False

            user = User(id=user_id, name=name, is_active=True)
            session.add(user)
            session.commit()
            logger.info(f"添加用户: {user_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"添加用户失败: {e}")
            return False
        finally:
            session.close()

    def get_user(self, user_id: str) -> User | None:
        """获取用户信息.

        Args:
            user_id: 用户ID.

        Returns:
            Optional[User]: 用户对象，不存在返回None.
        """
        session = self.get_session()
        try:
            return session.query(User).filter_by(id=user_id).first()
        finally:
            session.close()

    def get_all_users(self, active_only: bool = True) -> list[User]:
        """获取所有用户.

        Args:
            active_only: 是否只返回激活的用户.

        Returns:
            List[User]: 用户列表.
        """
        session = self.get_session()
        try:
            query = session.query(User)
            if active_only:
                query = query.filter_by(is_active=True)
            return query.order_by(User.created_at.desc()).all()
        finally:
            session.close()

    def update_user_sync_time(self, user_id: str) -> None:
        """更新用户同步时间.

        Args:
            user_id: 用户ID.
        """
        session = self.get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.last_sync_at = get_beijing_now()
                user.sync_count += 1
                session.commit()
        finally:
            session.close()

    def update_user_info(
        self, user_id: str, name: str | None = None, avatar_url: str | None = None, headline: str | None = None
    ) -> bool:
        """更新用户信息.

        Args:
            user_id: 用户ID.
            name: 用户名称.
            avatar_url: 头像URL.
            headline: 个性签名.

        Returns:
            bool: 更新成功返回True.
        """
        session = self.get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                if name:
                    user.name = name
                if avatar_url:
                    user.avatar_url = avatar_url
                if headline:
                    user.headline = headline
                session.commit()
                logger.info(f"更新用户信息: {user_id}, name={name}")
                return True
            return False
        finally:
            session.close()

    def delete_user(self, user_id: str) -> bool:
        """删除用户.

        Args:
            user_id: 用户ID.

        Returns:
            bool: 删除成功返回True.
        """
        session = self.get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                session.delete(user)
                session.commit()
                logger.info(f"删除用户: {user_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"删除用户失败: {e}")
            return False
        finally:
            session.close()

    # ========== 回答管理 ==========

    def save_answer(self, answer_data: dict[str, Any]) -> bool:
        """保存或更新回答元数据.

        Args:
            answer_data: 回答数据字典.

        Returns:
            bool: 新记录返回True，更新返回False.
        """
        session = self.get_session()
        try:
            existing = session.query(Answer).filter_by(id=answer_data["id"]).first()

            if existing:
                # 更新现有记录
                for key, value in answer_data.items():
                    if hasattr(existing, key):
                        # 特殊处理：不要覆盖 html_path 为 None（保留已有备份）
                        if key == "html_path" and value is None and existing.html_path:
                            logger.debug(f"保留现有HTML路径: {existing.html_path}")
                            continue
                        setattr(existing, key, value)
                existing.synced_at = get_beijing_now()
                session.commit()
                logger.debug(f"更新回答: {answer_data['id']}")
                return False
            else:
                # 创建新记录
                answer = Answer(**answer_data)
                session.add(answer)
                session.commit()
                logger.info(f"新增回答: {answer_data.get('question_title', answer_data['id'])[:50]}...")
                return True
        except Exception as e:
            session.rollback()
            logger.error(f"保存回答失败: {e}")
            return False
        finally:
            session.close()

    def get_answer_by_id(self, answer_id: str) -> Answer | None:
        """根据ID获取回答.

        Args:
            answer_id: 回答ID.

        Returns:
            Optional[Answer]: 回答对象.
        """
        session = self.get_session()
        try:
            return session.query(Answer).filter_by(id=answer_id).first()
        finally:
            session.close()

    def get_user_answers(self, user_id: str, limit: int | None = None) -> list[Answer]:
        """获取用户的所有回答.

        Args:
            user_id: 用户ID.
            limit: 限制数量.

        Returns:
            List[Answer]: 回答列表.
        """
        session = self.get_session()
        try:
            query = session.query(Answer).filter_by(user_id=user_id).order_by(Answer.liked_time.desc())
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    def get_user_answer_ids(self, user_id: str) -> list[str]:
        """获取用户的所有回答ID - 用于断点续传去重.

        Args:
            user_id: 用户ID.

        Returns:
            List[str]: 回答ID列表.
        """
        session = self.get_session()
        try:
            answers = session.query(Answer.id).filter_by(user_id=user_id).all()
            return [a[0] for a in answers]
        finally:
            session.close()

    def get_all_answers(self, limit: int | None = None, offset: int = 0, user_id: str | None = None) -> list[Answer]:
        """获取所有回答.

        Args:
            limit: 限制数量.
            offset: 偏移量.
            user_id: 过滤用户ID.

        Returns:
            List[Answer]: 回答列表.
        """
        session = self.get_session()
        try:
            query = session.query(Answer)
            if user_id:
                query = query.filter_by(user_id=user_id)
            query = query.order_by(Answer.liked_time.desc())
            if limit:
                query = query.limit(limit).offset(offset)
            return query.all()
        finally:
            session.close()

    def get_answers_without_comments(self, user_id: str | None = None) -> list[Answer]:
        """获取尚未保存评论的回答.

        Args:
            user_id: 过滤用户ID.

        Returns:
            List[Answer]: 回答列表.
        """
        session = self.get_session()
        try:
            query = session.query(Answer).filter_by(has_comments=False)
            if user_id:
                query = query.filter_by(user_id=user_id)
            return query.all()
        finally:
            session.close()

    def mark_answer_has_comments(self, answer_id: str) -> None:
        """标记回答已保存评论.

        Args:
            answer_id: 回答ID.
        """
        session = self.get_session()
        try:
            answer = session.query(Answer).filter_by(id=answer_id).first()
            if answer:
                answer.has_comments = True
                session.commit()
        finally:
            session.close()

    # ========== 评论管理 ==========

    def save_comment(self, comment_data: dict[str, Any]) -> bool:
        """保存评论元数据.

        Args:
            comment_data: 评论数据字典.

        Returns:
            bool: 新记录返回True，已存在返回False.
        """
        session = self.get_session()
        try:
            existing = session.query(Comment).filter_by(id=comment_data["id"]).first()

            if existing:
                return False

            comment = Comment(**comment_data)
            session.add(comment)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"保存评论失败: {e}")
            return False
        finally:
            session.close()

    # ========== 同步日志 ==========

    def create_sync_log(self, user_id: str | None = None, sync_type: str = "manual") -> int:
        """创建同步日志.

        Args:
            user_id: 用户ID.
            sync_type: 同步类型 (manual/scheduled/full).

        Returns:
            int: 日志ID.
        """
        session = self.get_session()
        try:
            log = SyncLog(status="running", user_id=user_id, sync_type=sync_type)
            session.add(log)
            session.commit()
            return log.id
        finally:
            session.close()

    def update_sync_log(self, log_id: int, **kwargs) -> None:
        """更新同步日志.

        Args:
            log_id: 日志ID.
            **kwargs: 要更新的字段.
        """
        session = self.get_session()
        try:
            log = session.query(SyncLog).filter_by(id=log_id).first()
            if log:
                for key, value in kwargs.items():
                    if hasattr(log, key):
                        setattr(log, key, value)
                if "status" in kwargs:
                    log.ended_at = get_beijing_now()
                session.commit()
        finally:
            session.close()

    def get_sync_history(self, user_id: str | None = None, limit: int = 50) -> list[SyncLog]:
        """获取同步历史.

        Args:
            user_id: 过滤用户ID.
            limit: 限制数量.

        Returns:
            List[SyncLog]: 同步日志列表.
        """
        session = self.get_session()
        try:
            query = session.query(SyncLog)
            if user_id:
                query = query.filter_by(user_id=user_id)
            return query.order_by(SyncLog.started_at.desc()).limit(limit).all()
        finally:
            session.close()

    # ========== 统计 ==========

    def get_stats(self, user_id: str | None = None) -> dict[str, int]:
        """获取统计信息.

        Args:
            user_id: 过滤用户ID.

        Returns:
            Dict[str, int]: 统计字典.
        """
        session = self.get_session()
        try:
            query = session.query(Answer)
            if user_id:
                query = query.filter_by(user_id=user_id)

            total_answers = query.count()

            # 评论统计 - 区分有评论和无评论但应该有评论的（异常）
            with_comments = query.filter_by(has_comments=True).count()

            # 应该有评论但还没有获取的（comment_count > 0 但 has_comments = False）
            comment_anomaly = query.filter(Answer.comment_count > 0, Answer.has_comments.is_(False)).count()

            # 下载状态统计
            failed_downloads = query.filter_by(download_status="failed").count()
            pending_downloads = query.filter_by(download_status="pending").count()

            # 未解决的下载失败
            unresolved_failures = session.query(DownloadFailure).filter_by(resolved=False).count()

            # 评论采集异常统计（extraction_errors 表中 error_type 包含 comment 的）
            comment_errors = (
                session.query(ExtractionError)
                .filter(ExtractionError.error_type.like("%comment%"), ExtractionError.resolved.is_(False))
                .count()
            )

            return {
                "total_answers": total_answers,
                "total_comments": session.query(Comment).count(),
                "with_comments": with_comments,
                "comment_anomaly": comment_anomaly,  # 应该有评论但未获取的
                "comment_errors": comment_errors,  # 评论采集错误数
                "deleted_answers": query.filter_by(is_deleted=True).count(),
                "total_users": session.query(User).filter_by(is_active=True).count(),
                "failed_downloads": failed_downloads,
                "pending_downloads": pending_downloads,
                "unresolved_failures": unresolved_failures,
            }
        finally:
            session.close()

    # ========== 提取错误记录 ==========

    def add_extraction_error(
        self,
        answer_id: str | None = None,
        question_title: str | None = None,
        error_type: str = "other",
        error_message: str = "",
        stack_trace: str | None = None,
        html_snapshot: str | None = None,
    ) -> int:
        """添加内容提取错误记录.

        Args:
            answer_id: 回答ID.
            question_title: 问题标题.
            error_type: 错误类型(parse_error/network_error/timeout/other).
            error_message: 错误详情.
            stack_trace: 错误堆栈.
            html_snapshot: HTML快照.

        Returns:
            int: 错误记录ID.
        """
        session = self.get_session()
        try:
            error = ExtractionError(
                answer_id=answer_id,
                question_title=question_title,
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                html_snapshot=html_snapshot,
            )
            session.add(error)
            session.commit()
            logger.warning(f"记录提取错误: answer_id={answer_id}, type={error_type}")
            return error.id
        except Exception as e:
            session.rollback()
            logger.error(f"保存提取错误记录失败: {e}")
            return -1
        finally:
            session.close()

    def get_extraction_errors(
        self, resolved: bool | None = None, limit: int = 50, offset: int = 0
    ) -> list[ExtractionError]:
        """获取提取错误列表.

        Args:
            resolved: 是否已解决(None表示全部).
            limit: 限制数量.
            offset: 偏移量.

        Returns:
            List[ExtractionError]: 错误记录列表.
        """
        session = self.get_session()
        try:
            query = session.query(ExtractionError)
            if resolved is not None:
                query = query.filter_by(resolved=resolved)
            return query.order_by(ExtractionError.created_at.desc()).limit(limit).offset(offset).all()
        finally:
            session.close()

    def get_extraction_error_count(self, resolved: bool = False) -> int:
        """获取提取错误数量.

        Args:
            resolved: 是否已解决.

        Returns:
            int: 错误数量.
        """
        session = self.get_session()
        try:
            return session.query(ExtractionError).filter_by(resolved=resolved).count()
        finally:
            session.close()

    def resolve_extraction_error(self, error_id: int) -> bool:
        """标记提取错误为已解决.

        Args:
            error_id: 错误记录ID.

        Returns:
            bool: 操作成功返回True.
        """
        session = self.get_session()
        try:
            error = session.query(ExtractionError).filter_by(id=error_id).first()
            if error:
                error.resolved = True
                error.resolved_at = get_beijing_now()
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"标记错误为已解决失败: {e}")
            return False
        finally:
            session.close()

    def resolve_all_extraction_errors(self) -> int:
        """标记所有未解决的提取错误为已解决.

        Returns:
            int: 更新的记录数量.
        """
        session = self.get_session()
        try:
            count = (
                session.query(ExtractionError)
                .filter_by(resolved=False)
                .update({"resolved": True, "resolved_at": get_beijing_now()})
            )
            session.commit()
            logger.info(f"批量标记 {count} 条错误记录为已解决")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"批量标记错误失败: {e}")
            return 0
        finally:
            session.close()

    def delete_extraction_error(self, error_id: int) -> bool:
        """删除提取错误记录.

        Args:
            error_id: 错误记录ID.

        Returns:
            bool: 删除成功返回True.
        """
        session = self.get_session()
        try:
            error = session.query(ExtractionError).filter_by(id=error_id).first()
            if error:
                session.delete(error)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"删除错误记录失败: {e}")
            return False
        finally:
            session.close()

    # ========== 下载失败记录管理 ==========

    def add_download_failure(
        self,
        answer_id: str,
        user_id: str,
        question_title: str | None = None,
        question_id: str | None = None,
        error_type: str = "other",
        error_message: str = "",
        http_status: int | None = None,
    ) -> int:
        """添加下载失败记录.

        Args:
            answer_id: 回答ID.
            user_id: 用户ID.
            question_title: 问题标题.
            question_id: 问题ID.
            error_type: 错误类型.
            error_message: 错误详情.
            http_status: HTTP状态码.

        Returns:
            int: 记录ID.
        """
        session = self.get_session()
        try:
            # 检查是否已存在未解决的记录
            existing = session.query(DownloadFailure).filter_by(answer_id=answer_id, resolved=False).first()
            if existing:
                existing.retry_count += 1
                existing.last_retry_at = get_beijing_now()
                existing.error_message = error_message
                existing.http_status = http_status
                session.commit()
                return existing.id

            failure = DownloadFailure(
                answer_id=answer_id,
                user_id=user_id,
                question_title=question_title,
                question_id=question_id,
                error_type=error_type,
                error_message=error_message,
                http_status=http_status,
            )
            session.add(failure)
            session.commit()
            return failure.id
        except Exception as e:
            session.rollback()
            logger.error(f"添加下载失败记录失败: {e}")
            return -1
        finally:
            session.close()

    def get_download_failures(
        self,
        resolved: bool = False,
        user_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DownloadFailure]:
        """获取下载失败列表.

        Args:
            resolved: 是否已解决.
            user_id: 过滤用户ID.
            limit: 限制数量.
            offset: 偏移量.

        Returns:
            List[DownloadFailure]: 失败记录列表.
        """
        session = self.get_session()
        try:
            query = session.query(DownloadFailure).filter_by(resolved=resolved)
            if user_id:
                query = query.filter_by(user_id=user_id)
            return query.order_by(DownloadFailure.created_at.desc()).offset(offset).limit(limit).all()
        finally:
            session.close()

    def get_download_failure_count(self, resolved: bool = False, user_id: str | None = None) -> int:
        """获取下载失败数量.

        Args:
            resolved: 是否已解决.
            user_id: 过滤用户ID.

        Returns:
            int: 失败数量.
        """
        session = self.get_session()
        try:
            query = session.query(DownloadFailure).filter_by(resolved=resolved)
            if user_id:
                query = query.filter_by(user_id=user_id)
            return query.count()
        finally:
            session.close()

    def resolve_download_failure(self, failure_id: int) -> bool:
        """标记下载失败为已解决.

        Args:
            failure_id: 记录ID.

        Returns:
            bool: 操作成功返回True.
        """
        session = self.get_session()
        try:
            failure = session.query(DownloadFailure).filter_by(id=failure_id).first()
            if failure:
                failure.resolved = True
                failure.resolved_at = get_beijing_now()
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"标记下载失败为已解决失败: {e}")
            return False
        finally:
            session.close()

    def resolve_download_failure_by_answer(self, answer_id: str) -> bool:
        """根据回答ID标记下载失败为已解决.

        Args:
            answer_id: 回答ID.

        Returns:
            bool: 操作成功返回True.
        """
        session = self.get_session()
        try:
            count = (
                session.query(DownloadFailure)
                .filter_by(answer_id=answer_id, resolved=False)
                .update({"resolved": True, "resolved_at": get_beijing_now()})
            )
            session.commit()
            return count > 0
        except Exception as e:
            session.rollback()
            logger.error(f"标记下载失败为已解决失败: {e}")
            return False
        finally:
            session.close()

    def get_pending_retry_failures(self, max_retries: int = 3) -> list[DownloadFailure]:
        """获取待重试的下载失败记录.

        Args:
            max_retries: 最大重试次数.

        Returns:
            List[DownloadFailure]: 待重试记录列表.
        """
        session = self.get_session()
        try:
            return (
                session.query(DownloadFailure)
                .filter_by(resolved=False)
                .filter(DownloadFailure.retry_count < max_retries)
                .order_by(DownloadFailure.last_retry_at.asc().nullsfirst())
                .all()
            )
        finally:
            session.close()

    def update_answer_download_status(
        self,
        answer_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        """更新回答下载状态.

        Args:
            answer_id: 回答ID.
            status: 下载状态(success/failed/pending/skipped).
            error: 错误信息.
        """
        session = self.get_session()
        try:
            answer = session.query(Answer).filter_by(id=answer_id).first()
            if answer:
                answer.download_status = status
                if error:
                    answer.last_error = error
                if status == "failed":
                    answer.retry_count = (answer.retry_count or 0) + 1
                session.commit()
        finally:
            session.close()

    def get_answers_by_download_status(
        self,
        status: str,
        user_id: str | None = None,
        limit: int | None = None,
    ) -> list[Answer]:
        """根据下载状态获取回答.

        Args:
            status: 下载状态.
            user_id: 过滤用户ID.
            limit: 限制数量.

        Returns:
            List[Answer]: 回答列表.
        """
        session = self.get_session()
        try:
            query = session.query(Answer).filter_by(download_status=status)
            if user_id:
                query = query.filter_by(user_id=user_id)
            query = query.order_by(Answer.liked_time.desc())
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    def get_download_failure_stats(self) -> dict[str, Any]:
        """获取下载失败统计.

        Returns:
            Dict[str, int]: 统计字典.
        """
        session = self.get_session()
        try:
            total = session.query(DownloadFailure).count()
            unresolved = session.query(DownloadFailure).filter_by(resolved=False).count()
            by_type = {}
            for error_type in ["403", "404", "timeout", "network_error", "other"]:
                count = session.query(DownloadFailure).filter_by(error_type=error_type, resolved=False).count()
                by_type[error_type] = count
            return {
                "total": total,
                "unresolved": unresolved,
                "by_type": by_type,
            }
        finally:
            session.close()

    # ========== 告警配置 ==========

    def get_alert_config(self) -> AlertConfig | None:
        """获取告警配置.

        Returns:
            Optional[AlertConfig]: 告警配置对象.
        """
        session = self.get_session()
        try:
            config = session.query(AlertConfig).first()
            if not config:
                config = AlertConfig()
                session.add(config)
                session.commit()
            return config
        finally:
            session.close()

    def update_alert_config(self, **kwargs) -> bool:
        """更新告警配置.

        Args:
            **kwargs: 要更新的字段.

        Returns:
            bool: 更新成功返回True.
        """
        session = self.get_session()
        try:
            config = session.query(AlertConfig).first()
            if not config:
                config = AlertConfig()
                session.add(config)

            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            config.updated_at = get_beijing_now()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新告警配置失败: {e}")
            return False
        finally:
            session.close()
