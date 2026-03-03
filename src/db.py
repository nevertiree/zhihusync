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
from models import AlertConfig, Answer, Base, Comment, SyncLog, User
from sqlalchemy import create_engine
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
        >>> db.add_user("mo-ri-jing-tan-zhu-jie-chong", "用户名")
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

        self.engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, echo=False
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

        # 创建表
        Base.metadata.create_all(self.engine)
        logger.info(f"数据库初始化完成: {db_path}")

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
        self, user_id: str, name: str = None, avatar_url: str = None, headline: str = None
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
            query = (
                session.query(Answer).filter_by(user_id=user_id).order_by(Answer.liked_time.desc())
            )
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

    def get_all_answers(
        self, limit: int | None = None, offset: int = 0, user_id: str | None = None
    ) -> list[Answer]:
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

    def create_sync_log(self, user_id: str | None = None) -> int:
        """创建同步日志.

        Args:
            user_id: 用户ID.

        Returns:
            int: 日志ID.
        """
        session = self.get_session()
        try:
            log = SyncLog(status="running", user_id=user_id)
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

            return {
                "total_answers": query.count(),
                "total_comments": session.query(Comment).count(),
                "with_comments": query.filter_by(has_comments=True).count(),
                "deleted_answers": query.filter_by(is_deleted=True).count(),
                "total_users": session.query(User).filter_by(is_active=True).count(),
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
