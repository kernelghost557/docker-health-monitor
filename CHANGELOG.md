# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions CI pipeline (lint, type-check, test, coverage)
- Pre-commit hooks (ruff, mypy, pytest)
- Type checking with mypy (strict mode)
- Multi-threaded HTTP server (ThreadingMixIn)
- Graceful shutdown on SIGTERM/SIGINT
- Coverage reporting via Codecov
- Badges for CI and coverage in README
- Additional tests for exporter and CLI
- CHANGELOG.md

### Changed
- `docker_compose_restart_count` metric type changed from Counter to Gauge to correctly represent absolute restart count (prevents double-counting on scrapes)
- Updated README with development instructions, project structure, and badges

### Fixed
- Corrected metric update logic for restart count (set instead of inc)
