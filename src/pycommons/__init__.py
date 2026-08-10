"""pycommons — the small utilities that got copied into every repo.

Five independent modules, stdlib only (`rich` is an optional extra used by
`logsetup` and nothing else):

* :mod:`pycommons.logsetup` — `setup_logging`: per-run log file + optional
  rich/plain console, on a per-package logger tree.
* :mod:`pycommons.env` — `load_env`: dependency-free ``KEY=VALUE`` .env reader.
* :mod:`pycommons.db` — `open_sqlite_db` / `sqlite_session`: the sqlite open
  idiom (Row factory, idempotent schema, mkdir).
* :mod:`pycommons.json_store` — `load_or_default` / `save_atomic` /
  `merge_keep_nonempty`: JSON file used as a database, safely.
* :mod:`pycommons.text` — `safe_filename` / `slugify`.
"""

from .db import open_sqlite_db, sqlite_session
from .env import load_env
from .json_store import load_or_default, merge_keep_nonempty, save_atomic
from .logsetup import run_log_path, setup_logging
from .text import safe_filename, slugify

__all__ = [
    "load_env",
    "load_or_default",
    "merge_keep_nonempty",
    "open_sqlite_db",
    "run_log_path",
    "safe_filename",
    "save_atomic",
    "setup_logging",
    "slugify",
    "sqlite_session",
]
