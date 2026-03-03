"""
测试同步功能 - 触发实际的知乎同步
"""

import json
import sys
import time
from pathlib import Path

import requests
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")

BASE_URL = "http://localhost:6067"


def test_cookie_login():
    """测试 Cookie 登录"""
    logger.info("=" * 60)
    logger.info("测试 Cookie 登录验证")
    logger.info("=" * 60)

    try:
        resp = requests.post(f"{BASE_URL}/api/cookies/test", timeout=60)
        logger.info(f"响应状态: {resp.status_code}")
        logger.info(f"响应内容: {resp.text}")

        if resp.status_code == 200:
            data = resp.json()
            if data.get("is_logged_in"):
                logger.info(f"✅ Cookie 登录成功! 用户: {data.get('user_name')}")
                return True
            else:
                logger.warning(f"⚠️ Cookie 登录失败: {data.get('message')}")
                return False
        else:
            logger.error(f"❌ 请求失败: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        logger.error(f"❌ 测试异常: {e}")
        return False


def test_start_sync():
    """测试开始同步"""
    logger.info("\n" + "=" * 60)
    logger.info("测试开始同步")
    logger.info("=" * 60)

    try:
        resp = requests.post(f"{BASE_URL}/api/sync/start", timeout=10)
        logger.info(f"响应状态: {resp.status_code}")
        logger.info(f"响应内容: {resp.text}")

        if resp.status_code in (200, 202):
            logger.info("✅ 同步任务已启动")
            return True
        else:
            logger.error(f"❌ 启动同步失败: {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ 测试异常: {e}")
        return False


def monitor_sync():
    """监控同步进度"""
    logger.info("\n" + "=" * 60)
    logger.info("监控同步进度（最多60秒）")
    logger.info("=" * 60)

    for i in range(12):  # 12 * 5 = 60秒
        try:
            resp = requests.get(f"{BASE_URL}/api/sync/status", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                message = data.get("message", "")
                progress = data.get("progress", 0)

                logger.info(f"[{i*5}s] 状态: {status}, 进度: {progress}%, 消息: {message}")

                if status in ("success", "failed"):
                    logger.info(f"同步结束: {status}")
                    return status == "success"
        except Exception as e:
            logger.error(f"查询状态失败: {e}")

        time.sleep(5)

    logger.warning("同步监控超时")
    return False


def check_results():
    """检查同步结果"""
    logger.info("\n" + "=" * 60)
    logger.info("检查同步结果")
    logger.info("=" * 60)

    try:
        resp = requests.get(f"{BASE_URL}/api/stats", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"总回答数: {data.get('total_answers', 0)}")
            logger.info(f"总评论数: {data.get('total_comments', 0)}")
            logger.info(f"有评论的回答: {data.get('with_comments', 0)}")
            return data.get("total_answers", 0) > 0
    except Exception as e:
        logger.error(f"查询结果失败: {e}")

    return False


if __name__ == "__main__":
    # 测试 Cookie 登录
    login_ok = test_cookie_login()

    if not login_ok:
        logger.warning("\n⚠️ Cookie 登录测试未通过，跳过后续测试")
        sys.exit(1)

    # 启动同步
    sync_started = test_start_sync()

    if sync_started:
        # 监控同步
        sync_ok = monitor_sync()

        # 检查结果
        has_data = check_results()

        if has_data:
            logger.info("\n✅ 同步测试成功！已获取到数据")
        else:
            logger.warning("\n⚠️ 同步完成但未获取到数据（可能是空账号或已同步过）")
    else:
        logger.error("\n❌ 无法启动同步")
