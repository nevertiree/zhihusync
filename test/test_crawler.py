"""Tests for crawler module."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crawler import ZhihuCrawler


@pytest.fixture
def mock_db():
    """Create mock database manager."""
    db = Mock()
    db.db_path = "/tmp/test.db"
    return db


@pytest.fixture
def mock_storage():
    """Create mock storage manager."""
    storage = Mock()
    storage.html_path = "/tmp/html"
    storage.static_path = "/tmp/static"
    storage.images_path = "/tmp/images"
    return storage


@pytest.fixture
def crawler(mock_db, mock_storage):
    """Create crawler instance with mocks."""
    return ZhihuCrawler(
        user_id="test-user",
        db_manager=mock_db,
        storage_manager=mock_storage,
        headless=True,
        request_delay=0.1,
    )


class TestParseActivitiesFromHtml:
    """Tests for _parse_activities_from_html method."""

    def test_parse_empty_html(self, crawler):
        """Test parsing empty HTML returns empty list."""
        html = "<html><body></body></html>"
        result = crawler._parse_activities_from_html(html)
        assert result == []

    def test_parse_html_with_voteup(self, crawler):
        """Test parsing HTML with voteup activity."""
        html = """
        <div class="List-item">
            <div class="ActivityItem-meta">
                <span class="ActivityItem-metaTitle">赞同了回答</span>
                <span>2026-03-01 12:00</span>
            </div>
            <div class="ContentItem" data-zop='{"itemId": "12345"}'>
                <h2 class="ContentItem-title">
                    <a href="//www.zhihu.com/question/111/answer/12345">Test Question</a>
                </h2>
                <div class="AuthorInfo">
                    <a class="UserLink-link" href="/people/test-author">Test Author</a>
                </div>
            </div>
        </div>
        """
        result = crawler._parse_activities_from_html(html)

        assert len(result) == 1
        assert result[0]["id"] == "12345"
        assert result[0]["verb"] == "MEMBER_VOTEUP_ANSWER"
        assert result[0]["target"]["question"]["title"] == "Test Question"
        assert result[0]["target"]["author"]["name"] == "Test Author"

    def test_parse_html_with_article(self, crawler):
        """Test parsing HTML with article voteup."""
        html = """
        <div class="List-item">
            <div class="ActivityItem-meta">
                <span class="ActivityItem-metaTitle">赞同了文章</span>
                <span>2026-03-01 12:00</span>
            </div>
            <div class="ContentItem" data-zop='{"itemId": "67890"}'>
                <h2 class="ContentItem-title">
                    <a href="//zhuanlan.zhihu.com/p/67890">Test Article</a>
                </h2>
            </div>
        </div>
        """
        result = crawler._parse_activities_from_html(html)

        assert len(result) == 1
        assert result[0]["id"] == "67890"
        assert result[0]["verb"] == "MEMBER_VOTEUP_ARTICLE"

    def test_parse_html_skips_non_voteup(self, crawler):
        """Test parsing skips non-voteup activities."""
        html = """
        <div class="List-item">
            <div class="ActivityItem-meta">
                <span class="ActivityItem-metaTitle">发布了想法</span>
                <span>2026-03-01 12:00</span>
            </div>
        </div>
        """
        result = crawler._parse_activities_from_html(html)
        assert len(result) == 0

    def test_parse_html_extracts_question_id(self, crawler):
        """Test parsing extracts question ID from URL."""
        html = """
        <div class="List-item">
            <div class="ActivityItem-meta">
                <span class="ActivityItem-metaTitle">赞同了回答</span>
                <span>2026-03-01 12:00</span>
            </div>
            <div class="ContentItem" data-zop='{"itemId": "12345"}'>
                <h2 class="ContentItem-title">
                    <a href="//www.zhihu.com/question/98765/answer/12345">Test</a>
                </h2>
            </div>
        </div>
        """
        result = crawler._parse_activities_from_html(html)

        assert len(result) == 1
        assert result[0]["target"]["question"]["id"] == "98765"


class TestTimestampParsing:
    """Tests for timestamp parsing."""

    def test_parse_timestamp_milliseconds(self, crawler):
        """Test parsing millisecond timestamp."""
        ts = 1700000000000  # milliseconds
        result = crawler._parse_timestamp(ts)
        assert isinstance(result, datetime)

    def test_parse_timestamp_seconds(self, crawler):
        """Test parsing second timestamp."""
        ts = 1700000000  # seconds
        result = crawler._parse_timestamp(ts)
        assert isinstance(result, datetime)

    def test_parse_timestamp_string(self, crawler):
        """Test parsing string timestamp."""
        ts = "1700000000000"
        result = crawler._parse_timestamp(ts)
        assert isinstance(result, datetime)


class TestProcessAnswer:
    """Tests for process_answer method."""

    @pytest.mark.asyncio
    async def test_process_answer_existing(self, crawler, mock_db):
        """Test process_answer skips existing answers."""
        mock_db.get_answer_by_id.return_value = Mock()

        activity = {
            "target": {
                "id": "12345",
                "question": {"id": "111", "title": "Test"},
                "author": {"id": "a1", "name": "Author"},
            }
        }

        result = await crawler.process_answer(activity, datetime.now())

        assert result is False
        mock_db.get_answer_by_id.assert_called_once_with("12345")


class TestExpandContent:
    """Tests for content expansion functionality."""

    @pytest.mark.asyncio
    async def test_expand_all_content_clicks_buttons(self, crawler):
        """Test _expand_all_content clicks expand buttons."""
        mock_page = AsyncMock()
        mock_page.query_selector_all.return_value = [
            AsyncMock(),
            AsyncMock(),
        ]
        crawler.page = mock_page

        await crawler._expand_all_content()

        # Should attempt to click buttons
        assert mock_page.query_selector_all.called
        assert mock_page.evaluate.called

    @pytest.mark.asyncio
    async def test_get_page_with_styles(self, crawler):
        """Test _get_page_with_styles extracts styles."""
        mock_page = AsyncMock()
        mock_page.content.return_value = """
        <html>
            <head><style>body{{color: red;}}</style></head>
            <body>Content</body>
        </html>
        """
        mock_page.evaluate.return_value = "/* styles */"
        crawler.page = mock_page

        result = await crawler._get_page_with_styles()

        assert "Content" in result
        assert mock_page.content.called
        assert mock_page.evaluate.called


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_sanitize_filename_removes_illegal_chars(self, crawler):
        """Test illegal characters are removed from filename."""
        # Access storage's sanitize method through crawler
        from src.storage import StorageManager

        storage = StorageManager("/tmp/html", "/tmp/static", "/tmp/images")
        result = storage._sanitize_filename('file<>:"/\\|?*name')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_sanitize_filename_limits_length(self, crawler):
        """Test filename length is limited."""
        from src.storage import StorageManager

        storage = StorageManager("/tmp/html", "/tmp/static", "/tmp/images")
        long_name = "a" * 200
        result = storage._sanitize_filename(long_name)
        assert len(result) <= 100
