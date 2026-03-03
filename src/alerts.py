"""告警通知模块.

该模块提供告警管理功能，支持 Webhook 和邮件两种通知渠道。
可配置不同类型告警的开关，并记录告警历史。

Examples:
    >>> from alerts import AlertManager, init_alert_manager
    >>> alert_mgr = init_alert_manager(db)
    >>> await alert_mgr.send_alert(
    ...     alert_type="sync_error",
    ...     title="同步失败",
    ...     message="详细错误信息..."
    ... )
"""

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiohttp
from db import DatabaseManager
from loguru import logger
from models import AlertConfig, AlertHistory


class AlertManager:
    """告警管理器.

    管理告警配置和发送，支持 Webhook 和邮件通知。
    可配置不同类型告警的开关，自动记录发送历史。

    Attributes:
        db: 数据库管理器.
        _config: 告警配置对象.

    Examples:
        >>> alert_mgr = AlertManager(db)
        >>> config = alert_mgr.get_config()
        >>> await alert_mgr.send_alert("cookie_expire", "Cookie过期", "请重新登录")
    """

    def __init__(self, db: DatabaseManager):
        """初始化告警管理器.

        Args:
            db: 数据库管理器实例.
        """
        self.db = db
        self._config: AlertConfig | None = None
        self._load_config()

    def _load_config(self):
        """加载告警配置.

        从数据库加载配置，不存在则创建默认配置。
        """
        session = self.db.get_session()
        try:
            config = session.query(AlertConfig).first()
            if not config:
                # 创建默认配置
                config = AlertConfig()
                session.add(config)
                session.commit()
            self._config = config
        finally:
            session.close()

    def get_config(self) -> AlertConfig | None:
        """获取告警配置.

        Returns:
            Optional[AlertConfig]: 当前告警配置.
        """
        return self._config

    def update_config(self, **kwargs):
        """更新告警配置.

        Args:
            **kwargs: 要更新的配置字段.

        Returns:
            bool: 更新成功返回 True.
        """
        session = self.db.get_session()
        try:
            config = session.query(AlertConfig).first()
            if not config:
                config = AlertConfig()
                session.add(config)

            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            config.updated_at = datetime.now()
            session.commit()
            self._config = config
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新告警配置失败: {e}")
            return False
        finally:
            session.close()

    async def send_alert(self, alert_type: str, title: str, message: str):
        """发送告警.

        根据配置发送 Webhook 和/或邮件告警。
        检查告警类型开关，记录发送历史。

        Args:
            alert_type: 告警类型(cookie_expire/sync_error/rate_limit).
            title: 告警标题.
            message: 告警消息内容.
        """
        if not self._config or not self._config.enabled:
            logger.debug("告警未启用，跳过发送")
            return

        # 检查是否需要发送此类告警
        if alert_type == "cookie_expire" and not self._config.alert_on_cookie_expire:
            return
        if alert_type == "sync_error" and not self._config.alert_on_sync_error:
            return
        if alert_type == "rate_limit" and not self._config.alert_on_rate_limit:
            return

        # 发送 Webhook
        if self._config.webhook_url:
            await self._send_webhook(alert_type, title, message)

        # 发送邮件
        if self._config.smtp_host and self._config.email_to:
            await self._send_email(alert_type, title, message)

    async def _send_webhook(self, alert_type: str, title: str, message: str):
        """发送 Webhook.

        发送 JSON 格式的 POST 请求到配置的 Webhook URL。

        Args:
            alert_type: 告警类型.
            title: 告警标题.
            message: 告警消息.
        """
        try:
            payload = {
                "type": alert_type,
                "title": title,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "source": "zhihusync",
            }

            headers = {"Content-Type": "application/json", **(self._config.webhook_headers or {})}

            timeout = aiohttp.ClientTimeout(total=30)
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self._config.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                ) as resp,
            ):
                success = resp.status < 400

                # 记录历史
                self._record_history(
                    alert_type=alert_type,
                    title=title,
                    message=message,
                    channel="webhook",
                    status="success" if success else "failed",
                    error_info=None if success else f"HTTP {resp.status}",
                )

                if success:
                    logger.info(f"Webhook 告警发送成功: {title}")
                else:
                    logger.warning(f"Webhook 告警发送失败: HTTP {resp.status}")

        except Exception as e:
            logger.error(f"Webhook 告警发送异常: {e}")
            self._record_history(
                alert_type=alert_type,
                title=title,
                message=message,
                channel="webhook",
                status="failed",
                error_info=str(e),
            )

    async def _send_email(self, alert_type: str, title: str, message: str):
        """发送邮件.

        使用 SMTP 发送 HTML 格式的告警邮件。

        Args:
            alert_type: 告警类型.
            title: 告警标题.
            message: 告警消息.
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[zhihusync] {title}"
            msg["From"] = self._config.email_from or self._config.smtp_user
            msg["To"] = self._config.email_to

            # HTML 内容
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #0066ff;">{title}</h2>
                <p>{message}</p>
                <hr>
                <p style="font-size: 12px; color: #666;">
                    发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                    告警类型: {alert_type}<br>
                    来源: zhihusync
                </p>
            </body>
            </html>
            """

            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # 连接 SMTP 服务器
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                server.starttls()
                server.login(self._config.smtp_user, self._config.smtp_password)
                server.send_message(msg)

            # 记录历史
            self._record_history(
                alert_type=alert_type,
                title=title,
                message=message,
                channel="email",
                status="success",
            )

            logger.info(f"邮件告警发送成功: {title}")

        except Exception as e:
            logger.error(f"邮件告警发送异常: {e}")
            self._record_history(
                alert_type=alert_type,
                title=title,
                message=message,
                channel="email",
                status="failed",
                error_info=str(e),
            )

    def _record_history(
        self,
        alert_type: str,
        title: str,
        message: str,
        channel: str,
        status: str,
        error_info: str | None = None,
    ):
        """记录告警历史.

        Args:
            alert_type: 告警类型.
            title: 告警标题.
            message: 告警消息.
            channel: 通知渠道(webhook/email).
            status: 发送状态(success/failed).
            error_info: 错误信息(可选).
        """
        session = self.db.get_session()
        try:
            history = AlertHistory(
                alert_type=alert_type,
                title=title,
                message=message,
                channel=channel,
                status=status,
                error_info=error_info,
            )
            session.add(history)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"记录告警历史失败: {e}")
        finally:
            session.close()

    def get_history(self, limit: int = 50) -> list[AlertHistory]:
        """获取告警历史.

        Args:
            limit: 返回记录数量限制.

        Returns:
            List[AlertHistory]: 告警历史列表.
        """
        session = self.db.get_session()
        try:
            return session.query(AlertHistory).order_by(AlertHistory.created_at.desc()).limit(limit).all()
        finally:
            session.close()


# 全局告警管理器实例
_alert_manager: AlertManager | None = None


def init_alert_manager(db: DatabaseManager):
    """初始化告警管理器.

    创建全局告警管理器实例。

    Args:
        db: 数据库管理器.

    Returns:
        AlertManager: 告警管理器实例.
    """
    global _alert_manager
    _alert_manager = AlertManager(db)
    return _alert_manager


def get_alert_manager() -> AlertManager | None:
    """获取告警管理器实例.

    Returns:
        Optional[AlertManager]: 告警管理器实例，未初始化返回 None.
    """
    return _alert_manager


async def send_cookie_expire_alert(user_name: str):
    """发送 Cookie 过期告警.

    Args:
        user_name: 用户名.
    """
    if _alert_manager:
        await _alert_manager.send_alert(
            alert_type="cookie_expire",
            title=f"Cookie 已过期 - {user_name}",
            message=f"用户 {user_name} 的知乎 Cookie 已过期或失效，请重新配置 Cookie 以恢复同步。",
        )


async def send_sync_error_alert(user_name: str, error: str):
    """发送同步失败告警.

    Args:
        user_name: 用户名.
        error: 错误信息.
    """
    if _alert_manager:
        await _alert_manager.send_alert(
            alert_type="sync_error",
            title=f"同步失败 - {user_name}",
            message=f"用户 {user_name} 的同步任务失败：{error}",
        )


async def send_rate_limit_alert():
    """发送频率限制告警."""
    if _alert_manager:
        await _alert_manager.send_alert(
            alert_type="rate_limit",
            title="触发频率限制",
            message="知乎 API 请求过于频繁，已触发频率限制，请稍后重试或增加扫描间隔。",
        )
