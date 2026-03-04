"""Pytest configuration and shared fixtures."""

import json
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient


# Get fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def test_config():
    """Load test configuration."""
    config_path = FIXTURES_DIR / "test_users.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def test_cookies():
    """Load test cookies."""
    cookie_path = FIXTURES_DIR / "cookies.json"
    with open(cookie_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def base_url():
    """Base URL for API tests."""
    return "http://localhost:6067"


@pytest.fixture
def client():
    """Create FastAPI test client."""
    from web import app
    return TestClient(app)


@pytest.fixture(scope="session")
def test_user_ids(test_config):
    """Get list of test user IDs."""
    return [user["user_id"] for user in test_config["test_users"]]


@pytest.fixture(scope="session")
def project_root():
    """Return project root directory."""
    return Path(__file__).parent.parent
