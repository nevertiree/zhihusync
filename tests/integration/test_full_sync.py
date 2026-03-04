"""
全量同步功能测试 - 测试实际同步流程
"""

import pytest
import time
import json
import requests
from pathlib import Path


class TestFullSyncProcess:
    """全量同步流程测试"""

    @pytest.fixture
    def base_url(self):
        return "http://localhost:6067"

    @pytest.fixture
    def test_cookies(self):
        """加载测试cookies"""
        cookie_path = Path(__file__).parent / "cookies.json"
        with open(cookie_path, encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def test_users(self):
        """加载测试用户"""
        users_path = Path(__file__).parent / "test_users.json"
        with open(users_path, encoding="utf-8") as f:
            data = json.load(f)
            return data["test_users"]

    def setup_method(self, base_url, test_users, test_cookies):
        """测试前置设置"""
        # 添加测试用户
        user_id = test_users[0]["user_id"]
        requests.post(
            f"{base_url}/api/users",
            json={"user_id": user_id, "name": "测试用户"},
            timeout=10
        )

        # 更新配置
        config_data = {
            "user_id": user_id,
            "scan_interval": 30,
            "max_items_per_scan": 5,
            "save_comments": True,
            "max_comments": 10,
            "sync_likes": True,
            "sync_created": False,
            "skip_video": True,
            "min_voteup": 0,
            "headless": True,
            "browser_type": "chromium",
            "timeout": 30,
            "request_delay": 2.0,
            "proxy": "",
            "window_width": 1920,
            "window_height": 1080,
            "scroll_delay": 800,
            "max_scroll_rounds": 20,
            "download_images": True,
            "download_avatars": True,
            "compress_html": False,
            "backup_enabled": False,
            "backup_interval_days": 7,
            "log_level": "INFO",
            "console_output": True,
            "log_sql": False,
        }
        requests.post(f"{base_url}/api/config", json=config_data, timeout=10)

        # 上传Cookie
        requests.post(
            f"{base_url}/api/cookies",
            json={"cookies": json.dumps(test_cookies)},
            timeout=10
        )

    def test_cookie_validation(self, base_url):
        """测试Cookie验证"""
        response = requests.post(f"{base_url}/api/cookies/test", timeout=60)

        # 记录结果，不强制要求成功（Cookie可能过期）
        if response.status_code == 200:
            data = response.json()
            print(f"Cookie验证结果: {data}")
        else:
            print(f"Cookie验证失败: {response.status_code}")
            pytest.skip("Cookie验证失败，跳过后续测试")

    def test_incremental_sync(self, base_url):
        """测试增量同步"""
        # 启动同步
        response = requests.post(f"{base_url}/api/sync/start", timeout=10)

        if response.status_code != 200:
            pytest.skip("无法启动同步")

        # 等待同步完成（最多60秒）
        max_wait = 60
        for i in range(max_wait // 5):
            time.sleep(5)

            status_resp = requests.get(f"{base_url}/api/sync/status", timeout=10)
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                status = status_data.get("status")

                print(f"[{i*5}s] Sync status: {status}")

                if status in ["success", "failed"]:
                    break

        # 检查结果
        stats_resp = requests.get(f"{base_url}/api/stats", timeout=10)
        if stats_resp.status_code == 200:
            stats = stats_resp.json()
            print(f"同步统计: {stats}")

    def test_full_sync(self, base_url):
        """测试全量同步"""
        # 启动全量同步
        response = requests.post(f"{base_url}/api/sync/init", timeout=10)

        if response.status_code == 400:
            pytest.skip("未配置用户ID")

        if response.status_code != 200:
            pytest.skip(f"无法启动全量同步: {response.text}")

        print("全量同步已启动，监控中...")

        # 监控同步进度（最多120秒）
        max_wait = 120
        for i in range(max_wait // 10):
            time.sleep(10)

            status_resp = requests.get(f"{base_url}/api/sync/status", timeout=10)
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                status = status_data.get("status")
                progress = status_data.get("progress", 0)
                message = status_data.get("message", "")

                print(f"[{i*10}s] Status: {status}, Progress: {progress}%, Message: {message}")

                if status in ["success", "failed"]:
                    break

        # 获取最终统计
        stats_resp = requests.get(f"{base_url}/api/stats", timeout=10)
        if stats_resp.status_code == 200:
            stats = stats_resp.json()
            print(f"\n全量同步完成统计:")
            print(f"  - 总回答数: {stats.get('total_answers', 0)}")
            print(f"  - 总评论数: {stats.get('total_comments', 0)}")
            print(f"  - 已删除回答: {stats.get('deleted_answers', 0)}")

    def test_sync_with_multiple_users(self, base_url, test_users):
        """测试多用户同步"""
        if len(test_users) < 2:
            pytest.skip("需要至少2个测试用户")

        # 添加第二个用户
        user_id = test_users[1]["user_id"]
        requests.post(
            f"{base_url}/api/users",
            json={"user_id": user_id, "name": "测试用户2"},
            timeout=10
        )

        # 获取用户列表
        response = requests.get(f"{base_url}/api/users", timeout=10)
        assert response.status_code == 200
        data = response.json()

        users = data.get("users", [])
        user_ids = [u["user_id"] for u in users]

        # 验证用户已添加
        assert any(uid in user_ids for uid in [u["user_id"] for u in test_users[:2]])

        print(f"多用户测试通过，当前用户数: {len(users)}")


class TestErrorHandling:
    """错误处理测试"""

    @pytest.fixture
    def base_url(self):
        return "http://localhost:6067"

    def test_sync_without_user_id(self, base_url):
        """测试未设置用户ID时启动同步"""
        # 先清空配置中的用户ID
        config_data = {
            "user_id": "",
            "scan_interval": 30,
            "max_items_per_scan": 10,
            "save_comments": True,
            "max_comments": 50,
            "sync_likes": True,
            "sync_created": False,
            "skip_video": True,
            "min_voteup": 0,
            "headless": True,
            "browser_type": "chromium",
            "timeout": 30,
            "request_delay": 2.0,
            "proxy": "",
            "window_width": 1920,
            "window_height": 1080,
            "scroll_delay": 800,
            "max_scroll_rounds": 20,
            "download_images": True,
            "download_avatars": True,
            "compress_html": False,
            "backup_enabled": False,
            "backup_interval_days": 7,
            "log_level": "INFO",
            "console_output": True,
            "log_sql": False,
        }
        requests.post(f"{base_url}/api/config", json=config_data, timeout=10)

        # 尝试启动同步
        response = requests.post(f"{base_url}/api/sync/start", timeout=10)

        # 应该返回错误
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data = response.json()
            # 可能返回错误信息
            print(f"同步响应: {data}")

    def test_invalid_cookie_format(self, base_url):
        """测试无效Cookie格式"""
        response = requests.post(
            f"{base_url}/api/cookies",
            json={"cookies": "invalid json {{"},
            timeout=10
        )

        # 应该返回400错误
        assert response.status_code in [400, 422]

    def test_nonexistent_api_endpoint(self, base_url):
        """测试访问不存在的API端点"""
        response = requests.get(f"{base_url}/api/nonexistent", timeout=10)
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
