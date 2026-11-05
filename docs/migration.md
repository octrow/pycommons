# Migration notes

For the repos this was extracted from.

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
