# type: ignore
"""数据模型定义.

该模块定义了知乎同步工具使用的所有数据库模型，使用 SQLAlchemy ORM。
包含用户、回答、评论、同步日志和告警相关的数据模型。

Attributes:
    Base: SQLAlchemy 声明式基类，所有模型的基类.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()
"""SQLAlchemy 声明式基类."""

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))


def get_beijing_now_naive() -> datetime:
    """获取当前北京时间（无时区，用于 SQLite）.

    Returns:
        datetime: 无时区的北京时间.
    """
    dt = datetime.now(BEIJING_TZ)
    return dt.replace(tzinfo=None)


class User(Base):
    """监控用户表.

    存储需要监控的知乎用户信息，包括用户ID、名称、状态等。
    与 Answer 和 SyncLog 建立一对多关系。

    Attributes:
        id: 用户ID，主键.
        name: 用户名称.
        avatar_url: 头像URL.
        headline: 个性签名.
        is_active: 是否激活.
        created_at: 添加时间.
        updated_at: 更新时间.
        last_sync_at: 上次同步时间.
        sync_count: 同步次数.
        answers: 关联的回答列表.
        sync_logs: 关联的同步日志列表.
    """

    __tablename__ = "users"

    id = Column(String(50), primary_key=True, comment="用户ID")
    name = Column(String(255), nullable=True, comment="用户名称")
    avatar_url = Column(String(500), nullable=True, comment="头像URL")
    headline = Column(String(500), nullable=True, comment="个性签名")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(DateTime, default=get_beijing_now_naive, comment="添加时间")
    updated_at = Column(DateTime, default=get_beijing_now_naive, onupdate=get_beijing_now_naive, comment="更新时间")
    last_sync_at = Column(DateTime, nullable=True, comment="上次同步时间")
    sync_count = Column(Integer, default=0, comment="同步次数")

    # 关系
    answers = relationship("Answer", back_populates="user", cascade="all, delete-orphan")
    sync_logs = relationship("SyncLog", back_populates="user", cascade="all, delete-orphan")


class Answer(Base):
    """知乎回答元数据表.

    存储备份的知乎回答元数据，包括问题信息、作者信息、
    点赞数、评论数等。实际内容存储在 HTML 文件中。

    Attributes:
        id: 回答ID，主键.
        user_id: 所属用户ID，外键.
        question_id: 问题ID.
        question_title: 问题标题.
        author_id: 作者ID.
        author_name: 作者名称.
        author_url: 作者主页URL.
        content_text: 纯文本内容预览.
        content_length: 内容长度.
        voteup_count: 点赞数.
        comment_count: 评论数.
        created_time: 回答创建时间.
        updated_time: 回答更新时间.
        liked_time: 用户点赞时间.
        synced_at: 同步时间.
        html_path: 本地HTML文件路径.
        original_url: 原始URL.
        has_comments: 是否已保存评论.
        is_deleted: 是否已被知乎删除.
        download_status: 下载状态(success/failed/pending).
        retry_count: 重试次数.
        last_error: 最后一次错误信息.
        extra_meta: 额外元数据.
        user: 关联的用户对象.
        comments: 关联的评论列表.
    """

    __tablename__ = "answers"

    id = Column(String(50), primary_key=True, comment="回答ID")
    user_id = Column(String(50), ForeignKey("users.id"), nullable=False, comment="所属用户ID")
    question_id = Column(String(50), nullable=False, comment="问题ID")
    question_title = Column(Text, nullable=False, comment="问题标题")
    author_id = Column(String(50), nullable=True, comment="作者ID")
    author_name = Column(String(255), nullable=True, comment="作者名称")
    author_avatar_url = Column(String(500), nullable=True, comment="作者头像URL")
    author_headline = Column(String(500), nullable=True, comment="作者个性签名")
    author_url = Column(String(500), nullable=True, comment="作者主页URL")

    # 内容元数据
    content_text = Column(Text, comment="纯文本内容预览")
    content_length = Column(Integer, default=0, comment="内容长度")
    voteup_count = Column(Integer, default=0, comment="点赞数")
    comment_count = Column(Integer, default=0, comment="评论数")

    # 时间相关
    created_time = Column(DateTime, comment="回答创建时间")
    updated_time = Column(DateTime, comment="回答更新时间")
    liked_time = Column(DateTime, comment="用户点赞时间")
    synced_at = Column(DateTime, default=get_beijing_now_naive, comment="同步时间")

    # 存储路径
    html_path = Column(String(500), comment="本地HTML文件路径")
    original_url = Column(String(500), nullable=False, comment="原始URL")

    # 状态标记
    has_comments = Column(Boolean, default=False, comment="是否已保存评论")
    is_deleted = Column(Boolean, default=False, comment="是否已被知乎删除")
    download_status = Column(String(20), default="pending", comment="下载状态: success/failed/pending/skipped")
    retry_count = Column(Integer, default=0, comment="重试次数")
    last_error = Column(Text, nullable=True, comment="最后一次错误信息")

    # 额外元数据
    extra_meta = Column(JSON, default=dict, comment="额外元数据")

    # 关系
    user = relationship("User", back_populates="answers")
    comments = relationship("Comment", back_populates="answer", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_question_id", "question_id"),
        Index("idx_author_id", "author_id"),
        Index("idx_liked_time", "liked_time"),
        Index("idx_synced_at", "synced_at"),
        Index("idx_download_status", "download_status"),
    )


class Comment(Base):
    """评论元数据表.

    存储回答的评论信息，包括评论内容、作者、点赞数等。

    Attributes:
        id: 评论ID，主键.
        answer_id: 所属回答ID，外键.
        author_id: 评论者ID.
        author_name: 评论者名称.
        content: 评论内容.
        like_count: 点赞数.
        created_time: 评论创建时间.
        synced_at: 同步时间.
        answer: 关联的回答对象.
    """

    __tablename__ = "comments"

    id = Column(String(50), primary_key=True, comment="评论ID")
    answer_id = Column(String(50), ForeignKey("answers.id"), nullable=False, comment="所属回答ID")

    # 评论作者
    author_id = Column(String(50), nullable=True, comment="评论者ID")
    author_name = Column(String(255), nullable=True, comment="评论者名称")
    author_avatar_url = Column(String(500), nullable=True, comment="评论者头像URL")

    # 内容
    content = Column(Text, nullable=False, comment="评论内容")
    like_count = Column(Integer, default=0, comment="点赞数")

    # 时间
    created_time = Column(DateTime, comment="评论创建时间")
    synced_at = Column(DateTime, default=get_beijing_now_naive, comment="同步时间")

    # 关系
    answer = relationship("Answer", back_populates="comments")

    __table_args__ = (
        Index("idx_comment_answer_id", "answer_id"),
        Index("idx_comment_author_id", "author_id"),
    )


class SyncLog(Base):
    """同步日志表.

    记录每次同步操作的日志，包括开始时间、结束时间、
    状态、扫描条目数等信息。

    Attributes:
        id: 日志ID，主键，自增.
        user_id: 用户ID，外键.
        started_at: 开始时间.
        ended_at: 结束时间.
        status: 状态(running/success/failed).
        items_scanned: 扫描条目数.
        items_new: 新增条目数.
        items_updated: 更新条目数.
        error_message: 错误信息.
        user: 关联的用户对象.
    """

    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=True, comment="用户ID")
    started_at = Column(DateTime, default=get_beijing_now_naive, comment="开始时间")
    ended_at = Column(DateTime, comment="结束时间")
    status = Column(String(20), comment="状态: running/success/failed")
    sync_type = Column(String(20), default="manual", comment="同步类型: manual/scheduled/full")
    items_scanned = Column(Integer, default=0, comment="扫描条目数")
    items_new = Column(Integer, default=0, comment="新增条目数")
    items_updated = Column(Integer, default=0, comment="更新条目数")
    error_message = Column(Text, comment="错误信息")

    # 关系
    user = relationship("User", back_populates="sync_logs")


class AlertConfig(Base):
    """告警配置表.

    存储告警通知的配置信息，支持 Webhook 和邮件两种方式。

    Attributes:
        id: 配置ID，主键，自增.
        enabled: 是否启用告警.
        webhook_url: Webhook URL.
        webhook_method: 请求方法(默认POST).
        webhook_headers: 请求头(JSON格式).
        smtp_host: SMTP服务器地址.
        smtp_port: SMTP端口(默认587).
        smtp_user: 邮箱账号.
        smtp_password: 邮箱密码.
        email_from: 发件人.
        email_to: 收件人列表，逗号分隔.
        alert_on_cookie_expire: Cookie过期时告警.
        alert_on_sync_error: 同步失败时告警.
        alert_on_rate_limit: 频率限制时告警.
        created_at: 创建时间.
        updated_at: 更新时间.
    """

    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    enabled = Column(Boolean, default=False, comment="是否启用")

    # Webhook 配置
    webhook_url = Column(String(500), nullable=True, comment="Webhook URL")
    webhook_method = Column(String(10), default="POST", comment="请求方法")
    webhook_headers = Column(JSON, default=dict, comment="请求头")

    # 邮件配置
    smtp_host = Column(String(255), nullable=True, comment="SMTP服务器")
    smtp_port = Column(Integer, default=587, comment="SMTP端口")
    smtp_user = Column(String(255), nullable=True, comment="邮箱账号")
    smtp_password = Column(String(255), nullable=True, comment="邮箱密码")
    email_from = Column(String(255), nullable=True, comment="发件人")
    email_to = Column(String(500), nullable=True, comment="收件人列表，逗号分隔")

    # 告警规则
    alert_on_cookie_expire = Column(Boolean, default=True, comment="Cookie过期告警")
    alert_on_sync_error = Column(Boolean, default=True, comment="同步失败告警")
    alert_on_rate_limit = Column(Boolean, default=True, comment="频率限制告警")

    created_at = Column(DateTime, default=get_beijing_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=get_beijing_now_naive, onupdate=get_beijing_now_naive, comment="更新时间")


class AlertHistory(Base):
    """告警历史表.

    记录已发送的告警通知历史。

    Attributes:
        id: 历史记录ID，主键，自增.
        alert_type: 告警类型(cookie_expire/sync_error/rate_limit).
        title: 告警标题.
        message: 告警内容.
        channel: 发送渠道(webhook/email).
        status: 发送状态(success/failed).
        error_info: 错误信息.
        created_at: 创建时间.
    """

    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(50), comment="告警类型: cookie_expire/sync_error/rate_limit")
    title = Column(String(255), comment="告警标题")
    message = Column(Text, comment="告警内容")
    channel = Column(String(50), comment="发送渠道: webhook/email")
    status = Column(String(20), comment="状态: success/failed")
    error_info = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=get_beijing_now_naive, comment="创建时间")


class ExtractionError(Base):
    """内容提取错误记录表.

    记录采集过程中内容提取失败的错误信息，便于用户发现和调试问题。

    Attributes:
        id: 错误记录ID，主键，自增.
        answer_id: 回答ID.
        question_title: 问题标题.
        error_type: 错误类型(parse_error/network_error/timeout/other).
        error_message: 错误详情.
        stack_trace: 错误堆栈.
        html_snapshot: HTML快照(可选).
        created_at: 创建时间.
        resolved: 是否已解决.
        resolved_at: 解决时间.
    """

    __tablename__ = "extraction_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    answer_id = Column(String(50), nullable=True, comment="回答ID")
    question_title = Column(String(500), nullable=True, comment="问题标题")
    error_type = Column(String(50), comment="错误类型: parse_error/network_error/timeout/other")
    error_message = Column(Text, comment="错误详情")
    stack_trace = Column(Text, nullable=True, comment="错误堆栈")
    html_snapshot = Column(Text, nullable=True, comment="HTML快照")
    created_at = Column(DateTime, default=get_beijing_now_naive, comment="创建时间")
    resolved = Column(Boolean, default=False, comment="是否已解决")
    resolved_at = Column(DateTime, nullable=True, comment="解决时间")

    __table_args__ = (
        Index("idx_error_created_at", "created_at"),
        Index("idx_error_resolved", "resolved"),
        Index("idx_error_type", "error_type"),
    )


class DownloadFailure(Base):
    """下载失败记录表.

    记录因403等网络错误导致的下载失败，支持重试机制。

    Attributes:
        id: 记录ID，主键，自增.
        answer_id: 回答ID.
        question_title: 问题标题.
        user_id: 所属用户ID.
        question_id: 问题ID.
        error_type: 错误类型(403/404/timeout/network_error/other).
        error_message: 错误详情.
        http_status: HTTP状态码.
        retry_count: 已重试次数.
        max_retries: 最大重试次数.
        last_retry_at: 最后重试时间.
        resolved: 是否已解决.
        resolved_at: 解决时间.
        created_at: 创建时间.
    """

    __tablename__ = "download_failures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    answer_id = Column(String(50), nullable=False, comment="回答ID")
    question_title = Column(String(500), nullable=True, comment="问题标题")
    user_id = Column(String(50), ForeignKey("users.id"), nullable=False, comment="所属用户ID")
    question_id = Column(String(50), nullable=True, comment="问题ID")

    # 错误信息
    error_type = Column(String(50), comment="错误类型: 403/404/timeout/network_error/other")
    error_message = Column(Text, comment="错误详情")
    http_status = Column(Integer, nullable=True, comment="HTTP状态码")

    # 重试相关
    retry_count = Column(Integer, default=0, comment="已重试次数")
    max_retries = Column(Integer, default=3, comment="最大重试次数")
    last_retry_at = Column(DateTime, nullable=True, comment="最后重试时间")

    # 状态
    resolved = Column(Boolean, default=False, comment="是否已解决")
    resolved_at = Column(DateTime, nullable=True, comment="解决时间")
    created_at = Column(DateTime, default=get_beijing_now_naive, comment="创建时间")

    __table_args__ = (
        Index("idx_download_failure_answer_id", "answer_id"),
        Index("idx_download_failure_user_id", "user_id"),
        Index("idx_download_failure_resolved", "resolved"),
        Index("idx_download_failure_error_type", "error_type"),
        Index("idx_download_failure_created_at", "created_at"),
    )
