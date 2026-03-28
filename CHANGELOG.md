# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.3] - 2026-03-28

### Added
- Multi-select questions in question list
- Practice set management (create, view, delete)
- Batch generate similar questions
- Print practice set as PDF (original or similar questions)
- Review count tracking for questions
- Practice sets page

### Changed
- Similar question now works in batch mode (removed single-question interaction)
- Questions table now has selection column

## [1.0.2] - 2026-03-28

### Fixed
- LLM similar question returns empty content (MiniMax thinking block issue)
- Added `thinking={"type": "disabled"}` to disable MiniMax thinking blocks
- Similar question generation now works correctly for math problems

## [1.0.1] - 2026-03-28

### Added
- Grade and semester support for questions (一年级至高三年级, 上学期/下学期)
- Tag management and selection for questions
- Statistics by grade and semester
- Management center for error books, subjects, tags, error types, knowledge points
- Upload preview after question creation
- Original image display in question detail view
- Edit functionality for questions with tag support

### Changed
- Grade dropdown now shows Chinese labels (一年级, 二年级, etc.)
- Search box width adjusted to be narrower
- Question text areas have increased height

### Fixed
- Subject dropdown not loading data
- Missing database columns for grade/semester
- Image upload directory path issue

## [1.0.0] - 2026-03-28

### Added
- Initial release
- Image upload with OCR recognition (multiple providers)
- Question management (CRUD)
- Error book organization
- Subject categorization
- Similar question generation via LLM
- Statistics dashboard
