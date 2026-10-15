# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.1] - 2026-10-15

### Changed

- README redesign: light/dark SVG hero and diagram, badges; images use absolute URLs so they render on PyPI.

## [0.2.0] - 2026-10-14

### Added

- `logsetup`: production logging with a rotating persistent file.
- PyPI distribution published as `tinycommons`.

### Fixed

- `save_atomic` uses a unique temp file, so concurrent writers no longer collide.

## [0.1.0] - 2026-10-14

### Added

- Initial release: `setup_logging`, `load_env`, SQLite helper, atomic JSON store, `slugify`. MIT license.
