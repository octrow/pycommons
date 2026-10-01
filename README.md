# pycommons

The small utilities that got copy-pasted into every repo — `setup_logging`,
`load_env`, the ten-line sqlite open, JSON-file-as-database, and slugs.
Extracted once, from seven repos (tiktok-lazy-follower, get_cool_event,
dialogue-lens, finance-insights, jobs, dental-parser, chat-watch).

Python ≥3.12. **Stdlib only.** `rich` is an optional extra used by `logsetup`'s
console sink and nothing else — and even then it is imported inside the function
and falls back to a plain `StreamHandler`, so a stdlib-only consumer can install
`pycommons` bare.

| module | what it is |
|---|---|
| `pycommons.logsetup` | `setup_logging` — per-run log file + optional console, on a per-package logger tree |
| `pycommons.env` | `load_env` — dependency-free `KEY=VALUE` .env reader |
| `pycommons.db` | `open_sqlite_db` / `sqlite_session` — Row factory, idempotent schema, mkdir |
| `pycommons.json_store` | `load_or_default` / `save_atomic` / `merge_keep_nonempty` |
| `pycommons.text` | `safe_filename` / `slugify` |

## Behaviour

The normative behaviour of every module lives in `openspec/specs/` — 22
requirements over 68 scenarios, each one carrying the reason it exists and, where
there was one, the bug in the original copy that put it there. Those specs are
the baseline; changes are proposed against them.

| capability | spec |
|---|---|
| `pycommons.logsetup` | [openspec/specs/logsetup/spec.md](openspec/specs/logsetup/spec.md) |
| `pycommons.env` | [openspec/specs/env/spec.md](openspec/specs/env/spec.md) |
| `pycommons.db` | [openspec/specs/db/spec.md](openspec/specs/db/spec.md) |
| `pycommons.json_store` | [openspec/specs/json-store/spec.md](openspec/specs/json-store/spec.md) |
| `pycommons.text` | [openspec/specs/text/spec.md](openspec/specs/text/spec.md) |

```bash
openspec list --specs                  # requirement counts
openspec show logsetup                 # read one
openspec validate --specs --strict     # check them
```

The short version, if you only read one thing: nothing is configured at import
time, a corrupt file raises instead of reading as empty, a save is atomic, a
re-scrape never overwrites a non-empty field, and `rich` is optional at runtime
rather than only at install time.

## Usage

```python
from pycommons import setup_logging

# tiktok-lazy-follower / get_cool_event, verbatim behaviour:
log_path = setup_logging("tlf", cfg.logs_dir)                  # rich console + DEBUG file

# dialogue-lens: files only, persistent + per-run
setup_logging("dialogue_lens", "logs", console_level=None,
              persistent_file="dialogue-lens.log", run_prefix="run-")

# jobs: root logger, plain console, plus jobspy's non-propagating loggers
setup_logging("", "logs", rich=False, run_prefix="run_", attach=["JobSpy:*"])
```

Production defaults (all stdlib, each with an opt-out kwarg): the persistent file
is a `RotatingFileHandler` (`persistent_max_bytes=10 MiB`, `persistent_backups=5`);
uncaught exceptions in the main thread (CRITICAL) and worker threads (ERROR) are
logged with their traceback and then handed to the previous hook
(`catch_uncaught=True`); `warnings.warn` lands in the file
(`capture_warnings=True`); and values of `*TOKEN*` / `*SECRET*` / `*KEY*` /
`*PASSWORD*` / `*HASH*` env vars (8+ chars) and `Bearer <token>` are masked as
`***` in every handler (`redact=True`; the env is read once per setup call).

```python
from pycommons import load_env, open_sqlite_db, sqlite_session

env = load_env(".env", {"WORK_TZ": "Asia/Almaty"})

SCHEMA = "CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, author TEXT);"
with sqlite_session("data/cache.db", SCHEMA) as conn:          # commits on clean exit
    conn.execute("INSERT OR IGNORE INTO videos VALUES (?, ?)", ("id1", "bob"))

conn = open_sqlite_db("cache.db", SCHEMA)                      # caller closes
```

```python
from pycommons import load_or_default, merge_keep_nonempty, safe_filename, save_atomic

clinics = {c["link_2gis"]: c for c in load_or_default("data/clinics.json", [])}
fresh = merge_keep_nonempty(clinics.get(link, {}), scraped,
                            always=("rating", "review_count"))
save_atomic("data/clinics.json", [*clinics.values()])
images_dir = IMAGES / safe_filename(fresh["name"])             # max_len=50, sep="_"
```

## API

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

## Migration notes

* **Per-run filenames are unified** on `<run_prefix><YYYY-MM-DD-HH-MM-SS>.log`
  (tlf/gce's format). dialogue-lens (`run-%Y%m%d-%H%M%S.log`) and jobs
  (`run_%Y-%m-%d_%H%M%S.log`) get `run-` / `run_` via `run_prefix` but their
  stamp punctuation changes. Nothing parses these names.
* **`setup_logging` takes a logger name and a directory**, not a config object.
  tlf passed its whole `Config`; call `setup_logging("tlf", cfg.logs_dir)`.
* **dialogue-lens' `setup_logging` returned a `Logger` and logged a session
  banner**; this returns the per-run `Path`. Use `logging.getLogger(name)` and
  log your own `argv` line — the banner is app policy, not logging setup.
* **finance-insights keeps its own `logsetup`** and is not a consumer: it is
  deliberately rich-free with `RotatingFileHandler` plus a second
  `llm_audit` logger tree, i.e. a different design, not a parameterisation.
* **`load_env` no longer carries dialogue-lens' `DEFAULTS` dict.** Those values
  (`WORK_TZ`, `WORK_START`, …) are that app's domain config; pass them in.
* **`merge_keep_nonempty` returns a new dict**; dental-parser mutated the
  `existing` dict and reassigned. Assign the result.
* **`load_or_default` raises on corrupt JSON** where dental-parser's
  `except: pass` returned empty. A consumer that truly wants the old behaviour
  must catch `json.JSONDecodeError` explicitly.
* **`sanitize_name` → `safe_filename`, `find_clinic_directory`'s inlined copy
  should call the same function.** Output is unchanged for existing directory
  names.

## Tests

```bash
cd /home/octrow/dev/pylibs && uv run --package pycommons --extra dev pytest pycommons/tests -q
```

94 tests, no network, no real `logs/` directory (everything goes to `tmp_path`).
The rich-absent branch is covered by monkeypatching `builtins.__import__`, so the
stdlib fallback is tested with rich installed.
