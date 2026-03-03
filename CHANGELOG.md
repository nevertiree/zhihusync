# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial support for parsing liked articles (previously only answers were supported)
- Comprehensive unit tests (43 tests) covering web API, crawler, and storage modules

### Fixed
- Fixed `fetch_likes` method to parse activity data from user profile HTML
- Added `_parse_activities_from_html` method to extract like records
- Fixed missing `user_id` field in `answer_data` causing database errors
- Added `save_answer` method in `StorageManager` for saving complete HTML documents
- Added `_build_full_html` method to generate styled HTML documents
- **Fixed 404 error** when clicking "View" button in backup content page by adding `/data/html` static file route
- **Fixed empty user list** in dashboard by adding `/api/users` endpoint with proper field mapping
- **Fixed truncated content** by adding `_expand_all_content` method to click "阅读全文" (Read full) buttons
- **Fixed missing CSS styles** by enhancing HTML template with Zhihu-like styling including:
  - Proper typography and colors matching Zhihu's design
  - Mobile responsive styles
  - Author information section
  - Vote count display
  - Metadata footer

## [0.3.0] - 2026-03-03

### Added
- **Long image generation**: Convert HTML backups to screenshot-style long images
  - New `image_generator.py` module using Playwright for rendering
  - API endpoint `POST /api/answers/{id}/generate-image`
  - Support for 3 card styles: default, compact, minimal
  - 2x high-resolution screenshots (694px width, Zhihu standard)
  - Frontend UI with preview and download options
- **Ruff linter**: Introduced Ruff as the primary Python linter
  - Added `pyproject.toml` with Ruff, Black, and isort configurations
  - Updated `.pre-commit-config.yaml` with Ruff hooks
  - Replaced flake8, pydocstyle, and isort with Ruff

### Changed
- **Major UI style overhaul**: Completely redesigned HTML template to match Zhihu's appearance
  - Card-based layout with gray background and white content cards
  - Added question header section with vote count display
  - Enhanced author information section with avatar gradient
  - RichContent styling for better typography and readability
  - Added action bar (vote, comment, favorite buttons)
  - Improved responsive design for mobile devices

### Fixed
- **Fixed image access 404**: Added missing `/data/static` static file mount in `web.py`
  - Generated images can now be accessed at `/data/static/images/xxx.png`
- **Fixed viewport_height error**: Corrected undefined variable in `image_generator.py`
- **Fixed font-family line too long**: Split long CSS font declarations in HTML template

## [0.2.0] - 2026-03-03

### Added
- Web management interface with FastAPI backend
- Visual configuration for Cookie settings
- Real-time sync progress display
- Content browser with search and pagination
- Configuration guide banner for first-time users
- Docker Compose support for easy deployment
- Cookie testing functionality to verify login status
- API endpoints for all operations
- SQLite database for metadata storage
- Automatic image downloading

### Changed
- Migrated from command-line only to web-based management
- Improved HTML styling to preserve Zhihu's native appearance
- Enhanced error handling and logging

### Fixed
- Cookie format conversion issues
- Browser initialization in Docker environment
- Storage path handling for cross-platform compatibility

## [0.1.0] - 2026-02-28

### Added
- Initial release
- Automatic backup of Zhihu liked answers
- Comment backup support
- Docker containerization
- Playwright-based crawler
- Incremental sync (only new content)
- Metadata recording (author, votes, timestamps)
- Basic HTML output with styling

[Unreleased]: https://github.com/yourusername/zhihusync/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/yourusername/zhihusync/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yourusername/zhihusync/releases/tag/v0.1.0
