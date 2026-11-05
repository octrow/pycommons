# tinycommons

Small helpers for Python repos: logging, `.env`, sqlite, atomic JSON, slugs.

<p>
  <a href="https://github.com/octrow/pycommons/actions/workflows/ci.yml"><img src="https://github.com/octrow/pycommons/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/tinycommons/"><img src="https://img.shields.io/pypi/v/tinycommons" alt="PyPI"></a>
  <a href="https://pypi.org/project/tinycommons/"><img src="https://img.shields.io/pypi/pyversions/tinycommons" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT"></a>
</p>

These helpers were copy-pasted between seven of my repos (tiktok-lazy-follower, get_cool_event,
dialogue-lens, finance-insights, jobs, dental-parser, chat-watch) and drifted apart.
This package is the one copy, with the bugs those copies had fixed.

Python 3.12+, stdlib only. `rich` is an optional extra for the console log.

## Install

```bash
uv add tinycommons          # or: pip install tinycommons
uv add "tinycommons[rich]"  # rich console in setup_logging
```

## Usage

```python
from tinycommons import load_env, load_or_default, save_atomic, setup_logging, sqlite_session

log_path = setup_logging("myapp", "logs")      # per-run DEBUG file + console, returns its Path

env = load_env(".env", {"WORK_TZ": "Asia/Almaty"})

SCHEMA = "CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, author TEXT);"
with sqlite_session("data/cache.db", SCHEMA) as conn:          # commits on clean exit
    conn.execute("INSERT OR IGNORE INTO videos VALUES (?, ?)", ("id1", "bob"))

clinics = load_or_default("data/clinics.json", [])            # [] only if the file is missing
save_atomic("data/clinics.json", clinics)
```

## Modules

| module | what it is |
|---|---|
| `tinycommons.logsetup` | `setup_logging`: per-run log file, optional console, rotation, secret redaction |
| `tinycommons.env` | `load_env`: dependency-free `KEY=VALUE` .env reader |
| `tinycommons.db` | `open_sqlite_db` / `sqlite_session`: Row factory, idempotent schema, mkdir |
| `tinycommons.json_store` | `load_or_default` / `save_atomic` / `merge_keep_nonempty` |
| `tinycommons.text` | `safe_filename` / `slugify` |

## Docs

- [API](docs/api.md): signatures of every function.
- [Design notes](docs/design.md): what changed from the copies, how `save_atomic` writes, specs, real output, more logging setups.
- [Migration notes](docs/migration.md): for the repos this was extracted from.

## Tests

```bash
uv sync --all-extras
uv run pytest -q
```

105 tests, no network. CI runs them on Python 3.12 and 3.13.

## License

[MIT](LICENSE)
