# API

```
logsetup: setup_logging(logger_name, logs_dir="logs", *, console_level=INFO,
                        file_level=DEBUG, rich=True, console=None,
                        persistent_file=False, attach=(), run_prefix="",
                        reconfigure=False) -> Path
          run_log_path(logger_name) -> Path | None
          FILE_FORMAT, RUN_STAMP

env:      load_env(path, defaults=None, *, override_os_environ=False) -> dict[str, str]

db:       open_sqlite_db(path="cache.db", schema_sql="") -> sqlite3.Connection
          sqlite_session(path="cache.db", schema_sql="")   # contextmanager

json_store: load_or_default(path, default=None) -> Any
            save_atomic(path, data, *, indent=2) -> Path
            merge_keep_nonempty(old, new, *, always=()) -> dict

text:     safe_filename(name, *, max_len=50, sep="_") -> str     # keeps Unicode + case
          slugify(text, *, max_len=0, sep="-", fallback="x") -> str   # ascii lowercase
```
