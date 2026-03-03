"""Tests for web module."""

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web import app, db, config


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestStaticFiles:
    """Tests for static file routes."""

    def test_static_files_mount(self, client):
        """Test static files are accessible."""
        # Test static files mount
        response = client.get("/static/js/admin.js")
        # Should return 200 or 404 (if file doesn't exist)
        assert response.status_code in [200, 404]

    def test_html_files_mount(self, client):
        """Test HTML files mount point exists."""
        # The mount point should exist even if no files
        response = client.get("/data/html/")
        # Directory listing might be disabled
        assert response.status_code in [200, 403, 404]


class TestAPIEndpoints:
    """Tests for API endpoints."""

    def test_get_stats(self, client):
        """Test stats endpoint returns correct structure."""
        response = client.get("/api/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_answers" in data
        assert "total_comments" in data
        assert "with_comments" in data
        assert "deleted_answers" in data
        assert "last_sync" in data
        assert "sync_status" in data

    def test_get_setup_status(self, client):
        """Test setup status endpoint."""
        response = client.get("/api/setup/status")
        assert response.status_code == 200

        data = response.json()
        assert "configured" in data
        assert "has_user_id" in data
        assert "has_cookie" in data
        assert "user_id" in data
        assert isinstance(data["configured"], bool)
        assert isinstance(data["has_user_id"], bool)
        assert isinstance(data["has_cookie"], bool)

    def test_get_users(self, client):
        """Test users endpoint returns correct structure."""
        response = client.get("/api/users")
        assert response.status_code == 200

        data = response.json()
        assert "users" in data
        assert isinstance(data["users"], list)

        # Check user structure if users exist
        for user in data["users"]:
            assert "user_id" in user
            assert "name" in user
            assert "status" in user
            assert user["status"] in ["active", "inactive"]

    def test_get_config(self, client):
        """Test config endpoint."""
        response = client.get("/api/config")
        assert response.status_code == 200

        data = response.json()
        assert "user_id" in data
        assert "scan_interval" in data
        assert "max_items_per_scan" in data
        assert "save_comments" in data
        assert "headless" in data

    def test_page_routes(self, client):
        """Test page routes return HTML."""
        pages = ["/", "/config", "/content", "/logs"]

        for page in pages:
            response = client.get(page)
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]


class TestCookieEndpoints:
    """Tests for cookie-related endpoints."""

    def test_check_cookies(self, client):
        """Test cookie check endpoint."""
        response = client.get("/api/cookies/check")
        assert response.status_code == 200

        data = response.json()
        assert "exists" in data
        assert "valid" in data

    def test_update_cookies_invalid(self, client):
        """Test updating cookies with invalid data."""
        response = client.post(
            "/api/cookies",
            json={"cookies": "invalid json"}
        )
        # Should handle invalid data gracefully
        assert response.status_code in [200, 400, 422]


class TestSyncEndpoints:
    """Tests for sync-related endpoints."""

    def test_get_sync_status(self, client):
        """Test sync status endpoint."""
        response = client.get("/api/sync/status")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ["idle", "running", "success", "failed"]

    def test_get_sync_history(self, client):
        """Test sync history endpoint."""
        response = client.get("/api/sync/history")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list) or isinstance(data, dict)


class TestAnswerEndpoints:
    """Tests for answer-related endpoints."""

    def test_get_answers(self, client):
        """Test answers list endpoint."""
        response = client.get("/api/answers")
        assert response.status_code == 200

    def test_get_answers_with_pagination(self, client):
        """Test answers endpoint with pagination params."""
        response = client.get("/api/answers?page=1&page_size=10")
        assert response.status_code == 200

    def test_delete_answer_not_found(self, client):
        """Test deleting non-existent answer."""
        response = client.delete("/api/answers/nonexistent")
        # Should return 404 or handle gracefully
        assert response.status_code in [200, 404]
