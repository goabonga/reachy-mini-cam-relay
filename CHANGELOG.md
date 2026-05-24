# Changelog

All notable changes to this project are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/) and this project
adheres to [Semantic Versioning](https://semver.org/). New entries are
generated from [Conventional Commits](https://www.conventionalcommits.org/)
by [multicz](https://github.com/goabonga/multicz).

## [0.1.0] - 2026-05-24

### Added

- relay Reachy Mini camera, mic and speakers as Linux virtual devices with automatic reconnection (`c3f42b7`)

### Fixed

- **cli**: drop unused typing.Tuple import flagged by ruff F401 (`943bb38`)
- **cli**: assert proc.stdin/stdout non-None for mypy strict union-attr (`f1a7d09`)
