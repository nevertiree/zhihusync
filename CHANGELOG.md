# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial support for parsing liked articles (previously only answers were supported)

### Fixed
- Fixed `fetch_likes` method to parse activity data from user profile HTML
- Added `_parse_activities_from_html` method to extract like records
- Fixed missing `user_id` field in `answer_data` causing database errors
- Added `save_answer` method in `StorageManager` for saving complete HTML documents
- Added `_build_full_html` method to generate styled HTML documents

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
