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

## Invariants (the reason this library exists)

**logsetup**

* **One logger tree per package, `propagate = False`.** Handlers go on
  `logging.getLogger("tlf")`; module code only ever does
  `logging.getLogger("tlf.<area>")` and logs. Nothing is configured at import
  time, so importing a library module never creates a `logs/` directory — that
  is what keeps consumers' test suites clean.
  `logger_name=""` targets the **root** logger instead (the jobs shape) and is
  the one case where `propagate` is left alone, because the root has no parent.
* **Two levels, two audiences.** The file gets DEBUG — the complete record of the
  run, which is the thing you actually need after an unattended scrape. The
  console gets INFO, so a long step never *looks* stuck. `console_level=None`
  drops the console entirely (dialogue-lens logs to files only).
* **One file per run, timestamped.** Runs are the unit of debugging; a single
  appended log makes "what did last night's run do" an exercise in grep. The
  stamp has **1-second resolution** — two runs started inside the same second
  share a file (true of every source copy). `persistent_file=` adds a
  never-rotated append-only companion when you want history too.
* **`rich` is optional at runtime, not just at install time.** The import lives
  inside `_console_handler`; an `ImportError` degrades to `StreamHandler` with
  the same compact `[HH:MM:SS] message` layout. A logging setup must not be the
  thing that breaks a deployment.
* **Idempotent by default.** A repeat call returns the same path and touches
  nothing (dialogue-lens needed this: a dev reloader re-imports the CLI, and the
  original stacked a second set of handlers → every line logged twice).
  `reconfigure=True` rewires deliberately, and *replaces* our handlers rather
  than stacking them.
* **`attach=` exists because some libraries opt out of propagation.** jobspy
  sets `propagate = False` on `JobSpy:<Site>` loggers, so the only way to capture
  them is to hand them the file handler itself. Patterns (`"JobSpy:*"`) match
  loggers that **already exist**, so call `setup_logging` after the library has
  created them (or pass exact names).

**env**

* A **missing file is not an error** — you get `defaults` back. That is what
  makes the config path optional for every caller, and it is why this is 12 lines
  instead of python-dotenv.
* Values are **returned, never exported**. `os.environ` is process-global state;
  polluting it from a parser surprises everyone. `override_os_environ=True` opts
  in.
* `KEY=VALUE`, split on the **first** `=` only (so URLs with query strings
  survive). Blank lines, `#` comments and lines without `=` are skipped. No
  quote-stripping, no interpolation, no `export ` prefix — the format in play
  never had them, and inventing support invites files that only work here.

**db**

* **`schema_sql` runs on every open**, so it must be idempotent
  (`CREATE TABLE IF NOT EXISTS`). That single property makes "open the db" and
  "migrate the db" the same call, which is why no consumer has ever needed a
  migration tool. Additive column migrations stay with the consumer (tlf does its
  own `ALTER TABLE … ADD COLUMN` inside a `try`), because they are schema
  history, not a generic concern.
* **`row_factory = sqlite3.Row` always.** Positional row access is how a schema
  change turns into a silent wrong-column bug.
* `sqlite_session` **commits only on a clean exit**; an exception propagates with
  the transaction open, and closing discards it — a half-finished stage never
  lands partial rows. There is deliberately no rollback-and-continue: the caller
  should see the exception.
* Parent directories are created. `open_sqlite_db` leaves closing to the caller;
  `sqlite_session` handles it.

**json_store**

* **`save_atomic` writes to a temp file in the destination directory, fsyncs, then
  `os.replace`s.** Same-directory means same filesystem means the rename is
  atomic: a reader sees the old file or the new one, never a truncated one. The
  original `json.dump` straight onto the target could destroy an hour of browser
  driving on a crash. On a serialisation failure the temp file is removed and the
  original is untouched — no `.name.tmp` litter.
* **`ensure_ascii=False` always.** The data is Russian/Kazakh; escaped JSON is
  unreviewable in a diff.
* **A corrupt file raises.** dental-parser's `except: pass` read corruption as
  "no data", and the next save then replaced the file with a smaller one. Losing
  data quietly is worse than failing loudly.
* **`merge_keep_nonempty` never overwrites a non-empty value.** A re-scrape must
  not wipe a field a human filled in by hand, nor one this run merely failed to
  extract. `always=` names the fields that *are* facts about the source
  (`rating`, `review_count`) and get refreshed whenever the new value is truthy.
  Returns a new dict — the original merged in place.

**text**

* **Two functions, because the three copies in the wild are two contracts.**
  `safe_filename` keeps case and keeps Cyrillic (dental-parser looks a directory
  up again by re-slugifying the clinic name, so mangling non-ASCII breaks the
  lookup, not just the looks). `slugify` deliberately destroys non-ASCII to
  produce a `^[a-z0-9][a-z0-9_-]*$` identifier you can type on a command line.
  A single function with an `ascii_only` flag would hide which contract a call
  site depends on.
* Both are **idempotent** — slugging a slug is a no-op — and both trim trailing
  separators *after* truncating, so a truncated key never ends in `_`.
* `slugify` returns `fallback` (`"x"`) rather than `""`: the result is used as a
  filename stem and a dict key, and neither may be empty. `safe_filename`
  returns `""` for unusable input, as its original did — callers there already
  check.

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

93 tests, no network, no real `logs/` directory (everything goes to `tmp_path`).
The rich-absent branch is covered by monkeypatching `builtins.__import__`, so the
stdlib fallback is tested with rich installed.
