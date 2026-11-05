# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.3] - 2026-11-05

### Changed

- README refreshed: shorter, plain language; example section renamed to Usage.
- `setup_logging` split up to cut its complexity (lint C901).
- Lint cleanups: import sorting (I001), `collections.abc` imports (UP035), single `with` statement (SIM117).
- CI: GitHub Actions dependencies bumped.

## [0.2.2] - 2026-10-15

### Changed

- README images get phone-width variants, so text stays readable on a 390px screen.
- Python version classifiers in package metadata (the PyPI "python" badge showed "missing").

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
