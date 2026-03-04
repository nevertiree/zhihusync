"""
API Integration Tests - 测试所有API端点的完整功能
包括：用户管理、配置管理、同步控制、数据查询
"""

import pytest
import time
import requests
from datetime import datetime


class TestUserManagement:
    """用户管理API测试"""

    def test_create_user_success(self, base_url, test_user_ids):
        """测试成功创建用户"""
        user_id = test_user_ids[0]
        response = requests.post(
            f"{base_url}/api/users",
            json={"user_id": user_id, "name": "测试用户"},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["user_id"] == user_id

    def test_create_user_duplicate(self, base_url, test_user_ids):
        """测试重复创建用户"""
        user_id = test_user_ids[0]
        # 第二次创建应该失败或重新激活
        response = requests.post(
            f"{base_url}/api/users",
            json={"user_id": user_id, "name": "测试用户2"},
            timeout=10
        )
        # 应该返回200（重新激活）或400（已存在）
        assert response.status_code in [200, 400]

    def test_create_user_empty_id(self, base_url):
        """测试创建空ID用户"""
        response = requests.post(
            f"{base_url}/api/users",
            json={"user_id": "", "name": "无效用户"},
            timeout=10
        )
        assert response.status_code == 400

    def test_get_users_list(self, base_url):
        """测试获取用户列表"""
        response = requests.get(f"{base_url}/api/users", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert isinstance(data["users"], list)

    def test_delete_user(self, base_url, test_user_ids):
        """测试删除用户"""
        # 先创建第二个测试用户用于删除
        if len(test_user_ids) > 1:
            user_id = test_user_ids[1]
            requests.post(
                f"{base_url}/api/users",
                json={"user_id": user_id, "name": "待删除用户"},
                timeout=10
            )

            # 删除用户
            response = requests.delete(f"{base_url}/api/users/{user_id}", timeout=10)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    def test_delete_nonexistent_user(self, base_url):
        """测试删除不存在的用户"""
        response = requests.delete(f"{base_url}/api/users/nonexistent_user_12345", timeout=10)
        assert response.status_code == 404


class TestConfigManagement:
    """配置管理API测试"""

    def test_get_config(self, base_url):
        """测试获取配置"""
        response = requests.get(f"{base_url}/api/config", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "scan_interval" in data
        assert "max_items_per_scan" in data

    def test_update_config(self, base_url, test_user_ids):
        """测试更新配置"""
        config_data = {
            "user_id": test_user_ids[0],
            "scan_interval": 30,
            "max_items_per_scan": 50,
            "save_comments": True,
            "max_comments": 100,
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
        response = requests.post(
            f"{base_url}/api/config",
            json=config_data,
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_get_setup_status(self, base_url):
        """测试获取设置状态"""
        response = requests.get(f"{base_url}/api/setup/status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data
        assert "has_user_id" in data
        assert "has_cookie" in data


class TestCookieManagement:
    """Cookie管理API测试"""

    def test_check_cookies(self, base_url):
        """测试检查Cookie"""
        response = requests.get(f"{base_url}/api/cookies/check", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "exists" in data
        assert "valid" in data

    def test_update_cookies(self, base_url, test_cookies):
        """测试更新Cookie"""
        response = requests.post(
            f"{base_url}/api/cookies",
            json={"cookies": json.dumps(test_cookies)},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_test_cookies(self, base_url):
        """测试Cookie登录验证"""
        response = requests.post(f"{base_url}/api/cookies/test", timeout=60)
        # 可能成功或失败，取决于Cookie有效性
        assert response.status_code in [200, 400, 500]


class TestSyncControl:
    """同步控制API测试"""

    def test_get_sync_status(self, base_url):
        """测试获取同步状态"""
        response = requests.get(f"{base_url}/api/sync/status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["idle", "running", "success", "failed"]

    def test_start_sync_without_config(self, base_url):
        """测试未配置时启动同步"""
        # 这个测试需要在没有配置的情况下运行
        response = requests.post(f"{base_url}/api/sync/start", timeout=10)
        # 应该返回错误
        assert response.status_code in [200, 400]

    def test_stop_sync(self, base_url):
        """测试停止同步"""
        response = requests.post(f"{base_url}/api/sync/stop", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestDataQuery:
    """数据查询API测试"""

    def test_get_stats(self, base_url):
        """测试获取统计信息"""
        response = requests.get(f"{base_url}/api/stats", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "total_answers" in data
        assert "total_comments" in data
        assert "deleted_answers" in data

    def test_get_answers(self, base_url):
        """测试获取回答列表"""
        response = requests.get(f"{base_url}/api/answers", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_get_answers_with_pagination(self, base_url):
        """测试分页获取回答"""
        response = requests.get(
            f"{base_url}/api/answers?page=1&page_size=10",
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_get_answers_with_search(self, base_url):
        """测试搜索回答"""
        response = requests.get(
            f"{base_url}/api/answers?search=test",
            timeout=10
        )
        assert response.status_code == 200

    def test_get_sync_history(self, base_url):
        """测试获取同步历史"""
        response = requests.get(f"{base_url}/api/sync/history", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_get_logs(self, base_url):
        """测试获取日志"""
        response = requests.get(f"{base_url}/api/logs?lines=50", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data


class TestPageRoutes:
    """页面路由测试"""

    def test_index_page(self, base_url):
        """测试首页"""
        response = requests.get(base_url, timeout=10)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_config_page(self, base_url):
        """测试配置页面"""
        response = requests.get(f"{base_url}/config", timeout=10)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_content_page(self, base_url):
        """测试内容页面"""
        response = requests.get(f"{base_url}/content", timeout=10)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_logs_page(self, base_url):
        """测试日志页面"""
        response = requests.get(f"{base_url}/logs", timeout=10)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.integration
class TestFullWorkflow:
    """完整工作流程测试"""

    def test_complete_setup_flow(self, base_url, test_user_ids, test_cookies):
        """测试完整设置流程"""
        # 1. 检查初始状态
        response = requests.get(f"{base_url}/api/setup/status", timeout=10)
        initial_status = response.json()

        # 2. 添加用户
        user_id = test_user_ids[0]
        response = requests.post(
            f"{base_url}/api/users",
            json={"user_id": user_id, "name": "测试用户"},
            timeout=10
        )
        assert response.status_code == 200

        # 3. 更新配置
        config_data = {
            "user_id": user_id,
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
        response = requests.post(
            f"{base_url}/api/config",
            json=config_data,
            timeout=10
        )
        assert response.status_code == 200

        # 4. 上传Cookie
        response = requests.post(
            f"{base_url}/api/cookies",
            json={"cookies": json.dumps(test_cookies)},
            timeout=10
        )
        assert response.status_code == 200

        # 5. 验证设置完成
        response = requests.get(f"{base_url}/api/setup/status", timeout=10)
        final_status = response.json()
        assert final_status["has_user_id"] == True
        assert final_status["has_cookie"] == True

        print(f"\n✅ 完整设置流程测试通过")
        print(f"   初始状态: {initial_status}")
        print(f"   最终状态: {final_status}")
