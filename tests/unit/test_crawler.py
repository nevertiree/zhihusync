"""
爬虫模块单元测试
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestCrawlerUtils:
    """爬虫工具函数测试"""

    def test_parse_timestamp_milliseconds(self):
        """测试毫秒时间戳解析"""
        from crawler import ZhihuCrawler

        # 创建mock对象
        crawler = ZhihuCrawler.__new__(ZhihuCrawler)

        # 测试毫秒时间戳
        ts = 1609459200000  # 2021-01-01 00:00:00 UTC
        result = crawler._parse_timestamp(ts)

        assert isinstance(result, datetime)
        assert result.year == 2021

    def test_parse_timestamp_seconds(self):
        """测试秒时间戳解析"""
        from crawler import ZhihuCrawler

        crawler = ZhihuCrawler.__new__(ZhihuCrawler)

        # 测试秒时间戳
        ts = 1609459200
        result = crawler._parse_timestamp(ts)

        assert isinstance(result, datetime)
        assert result.year == 2021

    def test_extract_question_info_from_link(self):
        """测试从链接提取问题信息"""
        from crawler import ZhihuCrawler

        crawler = ZhihuCrawler.__new__(ZhihuCrawler)

        # 测试标准格式
        href = "//www.zhihu.com/question/123456/answer/789012"
        question_id, _ = crawler._extract_question_info_from_link(href)
        assert question_id == "123456"

        # 测试无效格式
        href = "//www.zhihu.com/other/path"
        question_id, _ = crawler._extract_question_info_from_link(href)
        assert question_id == ""


class TestStorageUtils:
    """存储模块工具函数测试"""

    def test_sanitize_filename(self):
        """测试文件名清理"""
        from storage import StorageManager

        storage = StorageManager.__new__(StorageManager)

        # 测试清理非法字符
        filename = 'test<>:"/\\|?*file.txt'
        result = storage._sanitize_filename(filename)
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result

        # 测试截断长文件名
        long_name = "a" * 200
        result = storage._sanitize_filename(long_name)
        assert len(result) <= 100

    def test_generate_file_hash(self):
        """测试文件哈希生成"""
        from storage import StorageManager

        storage = StorageManager.__new__(StorageManager)

        content = "test content"
        hash1 = storage._generate_file_hash(content)
        hash2 = storage._generate_file_hash(content)

        # 相同内容应该生成相同哈希
        assert hash1 == hash2
        assert len(hash1) == 8

        # 不同内容应该生成不同哈希
        different_content = "different content"
        hash3 = storage._generate_file_hash(different_content)
        assert hash1 != hash3


class TestDatabaseOperations:
    """数据库操作测试"""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """创建临时数据库"""
        from db import DatabaseManager

        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        yield db

    def test_add_user(self, temp_db):
        """测试添加用户"""
        result = temp_db.add_user("test_user_123", "Test User")
        assert result == True

        # 重复添加应该返回False
        result = temp_db.add_user("test_user_123", "Test User")
        assert result == False

    def test_get_user(self, temp_db):
        """测试获取用户"""
        temp_db.add_user("test_user_456", "Test User 456")

        user = temp_db.get_user("test_user_456")
        assert user is not None
        assert user.id == "test_user_456"
        assert user.name == "Test User 456"

        # 获取不存在的用户
        user = temp_db.get_user("nonexistent")
        assert user is None

    def test_save_answer(self, temp_db):
        """测试保存回答"""
        # 先添加用户
        temp_db.add_user("test_user", "Test")

        answer_data = {
            "id": "answer_123",
            "user_id": "test_user",
            "question_id": "q_456",
            "question_title": "Test Question",
            "author_id": "author_789",
            "author_name": "Test Author",
            "content_text": "Test content",
            "content_length": 100,
            "voteup_count": 10,
            "comment_count": 5,
            "original_url": "https://zhihu.com/question/456/answer/123",
        }

        # 新记录应该返回True
        result = temp_db.save_answer(answer_data)
        assert result == True

        # 更新应该返回False
        answer_data["content_text"] = "Updated content"
        result = temp_db.save_answer(answer_data)
        assert result == False

    def test_get_answer_by_id(self, temp_db):
        """测试根据ID获取回答"""
        temp_db.add_user("test_user", "Test")

        answer_data = {
            "id": "answer_789",
            "user_id": "test_user",
            "question_id": "q_123",
            "question_title": "Test Question",
            "original_url": "https://zhihu.com/question/123/answer/789",
        }
        temp_db.save_answer(answer_data)

        answer = temp_db.get_answer_by_id("answer_789")
        assert answer is not None
        assert answer.id == "answer_789"

        # 获取不存在的回答
        answer = temp_db.get_answer_by_id("nonexistent")
        assert answer is None

    def test_get_stats(self, temp_db):
        """测试获取统计信息"""
        stats = temp_db.get_stats()

        assert "total_answers" in stats
        assert "total_comments" in stats
        assert "with_comments" in stats
        assert "deleted_answers" in stats
        assert "total_users" in stats


class TestConfigLoader:
    """配置加载测试"""

    def test_default_config(self):
        """测试默认配置"""
        from config_loader import ZhihuConfig, StorageConfig, BrowserConfig

        zhihu = ZhihuConfig()
        assert zhihu.user_id == ""
        assert zhihu.scan_interval == 60
        assert zhihu.max_items_per_scan == -1

        storage = StorageConfig()
        assert storage.download_images == True
        assert storage.compress_html == False

        browser = BrowserConfig()
        assert browser.headless == True
        assert browser.browser_type == "chromium"

    def test_config_from_dict(self):
        """测试从字典加载配置"""
        from config_loader import ZhihuConfig

        data = {
            "user_id": "test_user",
            "scan_interval": 30,
            "max_items_per_scan": 100,
        }
        config = ZhihuConfig(**data)

        assert config.user_id == "test_user"
        assert config.scan_interval == 30
        assert config.max_items_per_scan == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
