"""Tests for storage module."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import os
import tempfile

import pytest
from storage import StorageManager


@pytest.fixture
def temp_storage():
    """Create temporary storage manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "html")
        static_path = os.path.join(tmpdir, "static")
        images_path = os.path.join(tmpdir, "images")

        storage = StorageManager(
            html_path=html_path,
            static_path=static_path,
            images_path=images_path,
            download_images=False,  # Disable actual downloads in tests
        )
        yield storage


class TestFilePathGeneration:
    """Tests for file path generation."""

    def test_get_answer_filepath_with_content(self, temp_storage):
        """Test filepath generation with content."""
        result = temp_storage.get_answer_filepath(
            answer_id="12345",
            question_title="Test Question",
            content="Some content here",
        )

        assert result.name.startswith("Test_Question_")
        assert result.name.endswith("_12345.html")
        assert "_" in result.name  # should have hash

    def test_get_answer_filepath_without_content(self, temp_storage):
        """Test filepath generation without content."""
        result = temp_storage.get_answer_filepath(
            answer_id="12345",
            question_title="Test Question",
            content=None,
        )

        assert result.name == "Test_Question_12345.html"

    def test_sanitize_filename(self, temp_storage):
        """Test filename sanitization removes illegal chars."""
        result = temp_storage._sanitize_filename('Test<>"/\\|?*Question')
        # All illegal characters removed
        assert "<" not in result
        assert ">" not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result
        assert '"' not in result
        assert ":" not in result

    def test_sanitize_filename_with_spaces(self, temp_storage):
        """Test spaces are replaced with underscores."""
        result = temp_storage._sanitize_filename("Test Question Title")
        assert result == "Test_Question_Title"

    def test_generate_file_hash(self, temp_storage):
        """Test file hash generation."""
        result = temp_storage._generate_file_hash("test content")
        assert len(result) == 8
        assert result.isalnum()


class TestHtmlBuilding:
    """Tests for HTML document building."""

    def test_build_full_html_structure(self, temp_storage):
        """Test full HTML document structure."""
        result = temp_storage._build_full_html(
            question_title="Test Question",
            content_html="<p>Test content</p>",
            metadata={
                "author_name": "Test Author",
                "author_headline": "Test Headline",
                "voteup_count": 100,
                "backup_time": "2026-03-01T12:00:00",
            },
        )

        assert "<!DOCTYPE html>" in result
        assert '<html lang="zh-CN">' in result
        assert "Test Question" in result
        assert "Test content" in result
        assert "Test Author" in result
        assert "100" in result

    def test_build_full_html_contains_styles(self, temp_storage):
        """Test HTML contains CSS styles."""
        result = temp_storage._build_full_html(
            question_title="Test",
            content_html="<p>Content</p>",
        )

        assert "<style>" in result
        assert "</style>" in result
        assert "font-family" in result
        assert "max-width" in result

    def test_build_full_html_metadata(self, temp_storage):
        """Test HTML contains metadata."""
        result = temp_storage._build_full_html(
            question_title="Test",
            content_html="<p>Content</p>",
            metadata={"question_id": "12345", "custom_key": "custom_value"},
        )

        assert '<meta name="question_id" content="12345">' in result
        assert '<meta name="custom_key" content="custom_value">' in result

    def test_build_full_html_mobile_responsive(self, temp_storage):
        """Test HTML includes mobile responsive styles."""
        result = temp_storage._build_full_html(
            question_title="Test",
            content_html="<p>Content</p>",
        )

        assert "@media (max-width: 640px)" in result
        assert "viewport" in result

    def test_build_full_html_zhihu_like_styling(self, temp_storage):
        """Test HTML has Zhihu-like styling."""
        result = temp_storage._build_full_html(
            question_title="Test",
            content_html="<p>Content</p>",
        )

        # Check for Zhihu-like color scheme
        assert "#121212" in result  # Zhihu text color
        assert "#f6f6f6" in result  # Zhihu background
        assert "#0066ff" in result  # Zhihu blue


class TestStorageStats:
    """Tests for storage statistics."""

    def test_get_storage_stats_empty(self, temp_storage):
        """Test stats for empty storage."""
        result = temp_storage.get_storage_stats()

        assert result["html_count"] == 0
        assert result["image_count"] == 0
        assert result["html_size_mb"] == 0
        assert result["image_size_mb"] == 0

    def test_check_answer_exists(self, temp_storage):
        """Test checking if answer exists."""
        # Initially should not exist
        exists = temp_storage.check_answer_exists("12345")
        assert exists is False


class TestImagePathGeneration:
    """Tests for image path generation."""

    def test_get_local_image_path(self, temp_storage):
        """Test local image path generation."""
        result = temp_storage._get_local_image_path("https://pic1.zhimg.com/test.jpg")
        assert result.startswith("../static/images/")
        assert result.endswith(".jpg")

    def test_get_local_image_path_with_hash(self, temp_storage):
        """Test image path contains hash."""
        result1 = temp_storage._get_local_image_path("https://pic1.zhimg.com/test1.jpg")
        result2 = temp_storage._get_local_image_path("https://pic1.zhimg.com/test2.jpg")
        # Different URLs should produce different hashes
        assert result1 != result2


class TestHtmlProcessing:
    """Tests for HTML processing."""

    @pytest.mark.asyncio
    async def test_process_html_preserves_structure(self, temp_storage):
        """Test HTML processing preserves document structure."""
        html = """
        <html>
            <body>
                <p>Test content</p>
                <img src="https://pic1.zhimg.com/test.jpg">
            </body>
        </html>
        """

        result = await temp_storage._process_html(html, "answer123")

        # Check that document structure is preserved
        assert "<html>" in result
        assert "<body>" in result
        assert "Test content" in result
        # Image processing is async and may not complete in test
        assert "<img" in result

    @pytest.mark.asyncio
    async def test_process_html_handles_multiple_images(self, temp_storage):
        """Test HTML processing handles multiple images."""
        html = """
        <html>
            <body>
                <img src="https://pic1.zhimg.com/img1.jpg">
                <img src="https://pic1.zhimg.com/img2.jpg">
            </body>
        </html>
        """

        result = await temp_storage._process_html(html, "answer123")

        # Document should contain both images
        assert result.count("<img") == 2
