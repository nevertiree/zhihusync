"""
Integration tests for Extraction Errors API - 测试内容提取错误 API

运行测试: pytest tests/integration/test_extraction_errors_api.py -v
"""

import pytest
from fastapi.testclient import TestClient

# Mark all tests as integration tests
pytestmark = [pytest.mark.integration, pytest.mark.api]


class TestExtractionErrorsAPI:
    """测试内容提取错误相关的 API 接口"""

    def test_get_extraction_errors_empty(self, client):
        """测试获取空的错误列表"""
        response = client.get("/api/extraction-errors?resolved=false")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_resolve_all_errors_empty(self, client):
        """测试当没有错误时标记全部为已解决"""
        response = client.post("/api/extraction-errors/resolve-all")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "没有未解决的错误" in data["message"]

    def test_resolve_nonexistent_error(self, client):
        """测试标记不存在的错误为已解决"""
        response = client.post("/api/extraction-errors/99999/resolve")
        assert response.status_code == 404
        data = response.json()
        assert "不存在" in data["detail"]

    def test_delete_nonexistent_error(self, client):
        """测试删除不存在的错误"""
        response = client.delete("/api/extraction-errors/99999")
        assert response.status_code == 404
        data = response.json()
        assert "不存在" in data["detail"]

    def test_get_extraction_errors_with_resolved_filter(self, client):
        """测试使用 resolved 参数筛选错误"""
        # 获取未解决的
        response = client.get("/api/extraction-errors?resolved=false")
        assert response.status_code == 200

        # 获取全部的（包括已解决）
        response = client.get("/api/extraction-errors?resolved=true")
        assert response.status_code == 200

    def test_get_extraction_errors_pagination(self, client):
        """测试错误列表分页"""
        response = client.get("/api/extraction-errors?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert "page" in data
        assert "page_size" in data


class TestStatsAPI:
    """测试统计 API"""

    def test_get_stats_includes_error_count(self, client):
        """测试统计信息包含提取错误数量"""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "extraction_errors" in data
        assert isinstance(data["extraction_errors"], int)


class TestErrorWorkflow:
    """测试完整的错误处理工作流"""

    def test_full_error_lifecycle(self, client):
        """测试错误的完整生命周期：创建（模拟）-> 标记已解决 -> 验证"""
        # 注意：这里只是测试 API，实际错误创建是通过爬虫产生的
        # 所以我们只测试 API 的响应格式

        # 1. 获取初始错误数
        response = client.get("/api/stats")
        initial_count = response.json()["extraction_errors"]

        # 2. 标记所有为已解决
        response = client.post("/api/extraction-errors/resolve-all")
        assert response.status_code == 200

        # 3. 再次获取错误数（应该为 0）
        response = client.get("/api/stats")
        final_count = response.json()["extraction_errors"]

        # 最终应该没有未解决的错误
        assert final_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
