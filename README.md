<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/octrow/pycommons/main/assets/readme/hero-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="https://raw.githubusercontent.com/octrow/pycommons/main/assets/readme/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/octrow/pycommons/main/assets/readme/hero-dark.svg">
  <img src="https://raw.githubusercontent.com/octrow/pycommons/main/assets/readme/hero-light.svg" width="100%" alt="tinycommons: the helpers every repo ends up copying, extracted once. Five stdlib-only modules: logsetup, env, db, json_store, text. Beside the title, a real Python session: safe_filename keeps Cyrillic, slugify gives an ASCII slug, merge_keep_nonempty keeps a filled phone and refreshes the rating, and load_or_default raises on a corrupt file instead of returning the default.">
</picture>

<p align="center">
  <a href="https://github.com/octrow/pycommons/actions/workflows/ci.yml"><img src="https://github.com/octrow/pycommons/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/tinycommons/"><img src="https://img.shields.io/pypi/v/tinycommons" alt="PyPI"></a>
  <a href="https://pypi.org/project/tinycommons/"><img src="https://img.shields.io/pypi/pyversions/tinycommons" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT"></a>
</p>

`setup_logging`, `load_env`, the ten-line sqlite open, a JSON file used as a database, and slugs.
These got copy-pasted between seven of my repos (tiktok-lazy-follower, get_cool_event,
dialogue-lens, finance-insights, jobs, dental-parser, chat-watch) and drifted apart. This package
is the one copy, with the bugs those copies had fixed.

Python 3.12+, stdlib only. `rich` is an optional extra for the `logsetup` console sink. It is
imported inside the function, and without it you get a plain `StreamHandler`, so installing bare
is fine.

## Install

```bash
uv add tinycommons          # or: pip install tinycommons
uv add "tinycommons[rich]"  # rich console in setup_logging
```

## Usage

```python
from tinycommons import load_env, load_or_default, merge_keep_nonempty, safe_filename, \
    save_atomic, setup_logging, slugify, sqlite_session

log_path = setup_logging("myapp", "logs")      # per-run DEBUG file + console, returns its Path

env = load_env(".env", {"WORK_TZ": "Asia/Almaty"})

SCHEMA = "CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, author TEXT);"
with sqlite_session("data/cache.db", SCHEMA) as conn:          # commits on clean exit
    conn.execute("INSERT OR IGNORE INTO videos VALUES (?, ?)", ("id1", "bob"))

clinics = load_or_default("data/clinics.json", [])            # [] only if the file is missing
save_atomic("data/clinics.json", clinics)
```

Output from a real session:

```python
>>> safe_filename("Клиника «Улыбка»")      # keeps Unicode and case
'Клиника_Улыбка'
>>> slugify("Ivan P. Sidorov")             # ASCII, lowercase
'ivan-p-sidorov'
>>> slugify("Иван Сидоров")                # non-ASCII is dropped, not transliterated
'x'
>>> merge_keep_nonempty({"phone": "+7 701", "rating": 4.1},
...                     {"phone": "", "rating": 4.6}, always=("rating",))
{'phone': '+7 701', 'rating': 4.6}
>>> load_or_default("corrupt.json", [])
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
```

## What changed from the copies

If you read one thing: nothing is configured at import time, a corrupt file raises instead of
reading as empty, a save is atomic, a re-scrape never overwrites a non-empty field, and `rich` is
optional at runtime, not only at install time.

The JSON store is where the originals lost data. dental-parser wrote the file with a plain
`json.dump`, so a crash mid-write truncated the only copy of an hour-long scrape. Its reader had
`except: pass`, so a corrupt file read as "no data" and the next save replaced it with an emptier
one. `save_atomic` now writes like this:

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/octrow/pycommons/main/assets/readme/save-atomic-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="https://raw.githubusercontent.com/octrow/pycommons/main/assets/readme/save-atomic-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/octrow/pycommons/main/assets/readme/save-atomic-dark.svg">
  <img src="https://raw.githubusercontent.com/octrow/pycommons/main/assets/readme/save-atomic-light.svg" width="100%" alt="save_atomic: mkstemp creates a unique temp file in the target directory, json.dump writes it with ensure_ascii=False, fsync flushes it to disk, os.replace renames it over the target. If anything raises before the rename, the temp file is deleted, the original file is untouched and the error is re-raised.">
</picture>

The temp name is unique per call, so two concurrent writers can't rename each other's half-written
file into place.

`setup_logging` has production defaults, each with an opt-out kwarg:

- the persistent file is a `RotatingFileHandler` (`persistent_max_bytes=10 MiB`, `persistent_backups=5`);
- uncaught exceptions in the main thread (CRITICAL) and worker threads (ERROR) are logged with
  their traceback, then passed to the previous hook (`catch_uncaught=True`);
- `warnings.warn` goes to the file (`capture_warnings=True`);
- values of `*TOKEN*` / `*SECRET*` / `*KEY*` / `*PASSWORD*` / `*HASH*` env vars (8+ chars) and
  `Bearer <token>` show up as `***` in every handler (`redact=True`; the env is read once per call).

## Modules

| module | what it is | spec |
|---|---|---|
| `tinycommons.logsetup` | `setup_logging`: per-run log file + optional console, on a per-package logger tree | [logsetup](openspec/specs/logsetup/spec.md) |
| `tinycommons.env` | `load_env`: dependency-free `KEY=VALUE` .env reader | [env](openspec/specs/env/spec.md) |
| `tinycommons.db` | `open_sqlite_db` / `sqlite_session`: Row factory, idempotent schema, mkdir | [db](openspec/specs/db/spec.md) |
| `tinycommons.json_store` | `load_or_default` / `save_atomic` / `merge_keep_nonempty` | [json-store](openspec/specs/json-store/spec.md) |
| `tinycommons.text` | `safe_filename` / `slugify` | [text](openspec/specs/text/spec.md) |

The specs in `openspec/specs/` define the behaviour: 22 requirements, 67 scenarios. Each
requirement says why it exists and, where there was one, which bug in the original copy put it
there. Changes are proposed against them.

```bash
openspec list --specs                  # requirement counts
openspec show logsetup                 # read one
openspec validate --specs --strict     # check them
```

More `setup_logging` setups, taken from the consumer repos:

```python
# tiktok-lazy-follower / get_cool_event: rich console + DEBUG file
log_path = setup_logging("tlf", cfg.logs_dir)

# dialogue-lens: files only, persistent + per-run
setup_logging("dialogue_lens", "logs", console_level=None,
              persistent_file="dialogue-lens.log", run_prefix="run-")

# jobs: root logger, plain console, plus jobspy's non-propagating loggers
setup_logging("", "logs", rich=False, run_prefix="run_", attach=["JobSpy:*"])
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

<details>
<summary><b>Migration notes</b> for the repos this was extracted from</summary>

* **Per-run filenames are unified** on `<run_prefix><YYYY-MM-DD-HH-MM-SS>.log`
  (tlf/gce's format). dialogue-lens (`run-%Y%m%d-%H%M%S.log`) and jobs
  (`run_%Y-%m-%d_%H%M%S.log`) get `run-` / `run_` via `run_prefix`, but their
  stamp punctuation changes. Nothing parses these names.
* **`setup_logging` takes a logger name and a directory**, not a config object.
  tlf passed its whole `Config`; call `setup_logging("tlf", cfg.logs_dir)`.
* **dialogue-lens' `setup_logging` returned a `Logger` and logged a session
  banner**; this one returns the per-run `Path`. Use `logging.getLogger(name)` and
  log your own `argv` line. The banner is app policy, not logging setup.
* **finance-insights keeps its own `logsetup`** and is not a consumer. It is
  deliberately rich-free, with `RotatingFileHandler` plus a second `llm_audit`
  logger tree: a different design, not a parameterisation.
* **`load_env` no longer carries dialogue-lens' `DEFAULTS` dict.** Those values
  (`WORK_TZ`, `WORK_START`, …) are that app's domain config; pass them in.
* **`merge_keep_nonempty` returns a new dict**; dental-parser mutated the
  `existing` dict and reassigned. Assign the result.
* **`load_or_default` raises on corrupt JSON** where dental-parser's
  `except: pass` returned empty. A consumer that really wants the old behaviour
  must catch `json.JSONDecodeError` explicitly.
* **`sanitize_name` → `safe_filename`**, and the copy inlined in
  `find_clinic_directory` should call the same function. Output is unchanged for
  existing directory names.

</details>

## Tests

```bash
uv sync --all-extras
uv run pytest -q
```

105 tests, no network, no real `logs/` directory (everything goes to `tmp_path`). The rich-absent
branch is covered by monkeypatching `builtins.__import__`, so the stdlib fallback is tested with
rich installed. CI runs them on Python 3.12 and 3.13.

## License

[MIT](LICENSE)
