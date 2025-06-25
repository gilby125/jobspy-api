# Changelog

All notable changes to the JobSpy Docker API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Placeholder for upcoming changes

## [1.0.1] - 2023-11-30

### Fixed
- Fixed CSV export functionality when using `format=csv` parameter
- Fixed `DEFAULT_COUNTRY_INDEED` environment variable not being used as fallback when parameter is not provided
- Fixed `site_name=all` being rejected as an invalid option
- Fixed `ENABLE_API_KEY_AUTH` defaulting to disabled instead of enabled when not specified.



## [1.0.0] - 2025-04-28

### Added
- Initial release of JobSpy Docker API
- Comprehensive job search across multiple platforms
- API Key Authentication system
- Rate limiting capabilities
- Response caching
- Proxy support
- Customizable default search parameters
- CORS support
- Health check endpoints
- Comprehensive logging

### Changed
- N/A (initial release)

### Fixed
- N/A (initial release)

[Unreleased]: https://github.com/username/job-spy-fastapi/compare/v1.0.0...HEAD
[1.0.1]: https://github.com/username/job-spy-fastapi/releases/tag/v1.0.1
[1.0.0]: https://github.com/username/job-spy-fastapi/releases/tag/v1.0.0
