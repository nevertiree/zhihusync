"""
Docker 环境功能测试 - 使用新的 Cookie
"""

import json
import sys
from pathlib import Path

import requests
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")

BASE_URL = "http://localhost:6067"


class DockerTester:
    def __init__(self):
        self.results = []

    def log_test(self, name: str, status: str, message: str = ""):
        result = {"name": name, "status": status, "message": message}
        self.results.append(result)
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        logger.info(f"{icon} {name}: {status} - {message}")
        return result

    def test_api_stats(self):
        """测试统计接口"""
        try:
            resp = requests.get(f"{BASE_URL}/api/stats", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                msg = f"回答: {data.get('total_answers', 0)}, 评论: {data.get('total_comments', 0)}"
                self.log_test("API - 统计信息", "PASS", msg)
                return True
            else:
                self.log_test("API - 统计信息", "FAIL", f"状态码: {resp.status_code}")
                return False
        except Exception as e:
            self.log_test("API - 统计信息", "FAIL", str(e))
            return False

    def test_api_setup_status(self):
        """测试配置状态"""
        try:
            resp = requests.get(f"{BASE_URL}/api/setup/status", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                msg = f"已配置: {data.get('configured')}, 有Cookie: {data.get('has_cookie')}"
                self.log_test("API - 配置状态", "PASS", msg)
                return True
            else:
                self.log_test("API - 配置状态", "FAIL", f"状态码: {resp.status_code}")
                return False
        except Exception as e:
            self.log_test("API - 配置状态", "FAIL", str(e))
            return False

    def test_api_config(self):
        """测试配置获取"""
        try:
            resp = requests.get(f"{BASE_URL}/api/config", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                msg = f"用户ID: {data.get('user_id', '未设置')}"
                self.log_test("API - 配置获取", "PASS", msg)
                return True
            else:
                self.log_test("API - 配置获取", "FAIL", f"状态码: {resp.status_code}")
                return False
        except Exception as e:
            self.log_test("API - 配置获取", "FAIL", str(e))
            return False

    def test_api_cookie_check(self):
        """测试 Cookie 检查"""
        try:
            resp = requests.get(f"{BASE_URL}/api/cookies/check", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                msg = f"存在: {data.get('exists')}, 有效: {data.get('valid')}"
                self.log_test("API - Cookie检查", "PASS", msg)
                return True
            else:
                self.log_test("API - Cookie检查", "FAIL", f"状态码: {resp.status_code}")
                return False
        except Exception as e:
            self.log_test("API - Cookie检查", "FAIL", str(e))
            return False

    def test_api_sync_status(self):
        """测试同步状态"""
        try:
            resp = requests.get(f"{BASE_URL}/api/sync/status", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                msg = f"状态: {data.get('status')}"
                self.log_test("API - 同步状态", "PASS", msg)
                return True
            else:
                self.log_test("API - 同步状态", "FAIL", f"状态码: {resp.status_code}")
                return False
        except Exception as e:
            self.log_test("API - 同步状态", "FAIL", str(e))
            return False

    def test_cookie_in_container(self):
        """检查容器内的 Cookie 文件"""
        try:
            import subprocess

            result = subprocess.run(
                ["docker", "exec", "zhihusync", "cat", "/app/data/meta/cookies.json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                cookies = data.get("cookies", [])
                names = [c.get("name") for c in cookies]
                msg = f"Cookie数量: {len(cookies)}, 包含: {', '.join(names[:4])}..."
                self.log_test("容器 - Cookie文件", "PASS", msg)
                return True
            else:
                self.log_test("容器 - Cookie文件", "FAIL", result.stderr)
                return False
        except Exception as e:
            self.log_test("容器 - Cookie文件", "FAIL", str(e))
            return False

    def run_all_tests(self):
        logger.info("=" * 60)
        logger.info("开始 Docker 第二轮测试（使用新 Cookie）")
        logger.info("=" * 60)

        self.test_api_stats()
        self.test_api_setup_status()
        self.test_api_config()
        self.test_api_cookie_check()
        self.test_api_sync_status()
        self.test_cookie_in_container()

        self.print_report()

    def print_report(self):
        logger.info("\n" + "=" * 60)
        logger.info("第二轮测试报告")
        logger.info("=" * 60)

        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")

        for r in self.results:
            icon = "✅" if r["status"] == "PASS" else "❌"
            logger.info(f"{icon} {r['name']}: {r['message']}")

        logger.info("-" * 60)
        logger.info(f"总计: {len(self.results)} 项, 通过: {passed}, 失败: {failed}")
        logger.info("=" * 60)


if __name__ == "__main__":
    tester = DockerTester()
    tester.run_all_tests()
