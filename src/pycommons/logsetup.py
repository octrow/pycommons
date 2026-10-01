"""One `setup_logging` for the whole fleet — per-run log file + optional console.

Extracted from four near-identical copies (tiktok-lazy-follower `logsetup.py`,
get_cool_event `logsetup.py` — byte-for-byte the same but for the logger name —
dialogue-lens `log.py`, and jobs `scrape_jobs.py`).

The shape all four share: a **per-package logger tree** (`logging.getLogger("tlf")`,
`"gce"`, `"dialogue_lens"`) at DEBUG with `propagate = False`, a file handler at
DEBUG that gets *everything*, and a console handler at INFO so a long step never
looks stuck. Module code only ever does `logging.getLogger("<pkg>.<area>")`.

`rich` is optional: without it installed (or with ``rich=False``) the console sink
is a plain `StreamHandler` with the same compact `[HH:MM:SS] message` layout, so
stdlib-only consumers can use this module too.

Production extras, all stdlib and all on by default: the persistent file rotates
at a size cap, uncaught exceptions (main thread and worker threads) and
`warnings.warn` land in the log file, and values of secret-looking env vars plus
``Bearer`` tokens are masked before any handler writes them.
"""

from __future__ import annotations

import copy
import fnmatch
import logging
import os
import re
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable

__all__ = [
    "FILE_FORMAT", "PERSISTENT_BACKUPS", "PERSISTENT_MAX_BYTES", "RUN_STAMP",
    "run_log_path", "setup_logging",
]

FILE_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
FILE_DATEFMT = "%H:%M:%S"
# The persistent file spans many days, so its lines carry the date; a per-run
# file's date is already in its filename.
PERSISTENT_DATEFMT = "%Y-%m-%d %H:%M:%S"
CONSOLE_FORMAT = "[%(asctime)s] %(message)s"
CONSOLE_DATEFMT = "%H:%M:%S"
RUN_STAMP = "%Y-%m-%d-%H-%M-%S"
# The persistent file rotates at this size, keeping this many old copies
# (<name>.log.1 … .N) — ~60 MiB worst case instead of unbounded growth.
PERSISTENT_MAX_BYTES = 10 * 1024 * 1024
PERSISTENT_BACKUPS = 5

# Env vars whose *values* get masked in log output, and the floor below which a
# value is too short to mask without shredding ordinary words ("abc", "1").
SECRET_ENV_PATTERNS = ("*TOKEN*", "*SECRET*", "*KEY*", "*PASSWORD*", "*HASH*")
SECRET_MIN_LEN = 8
REDACTED = "***"
_BEARER = r"(?<=\bBearer )[A-Za-z0-9._~+/=-]+"

# logger name -> per-run log path, so a second call is a no-op (dialogue-lens'
# `_configured` guard, which exists because a dev reloader can re-import the CLI).
_runs: dict[str, Path] = {}
# logger name -> the (attached logger, our handler) pairs, so a reconfigure can
# take its old file handler back off loggers it does not own.
_attached: dict[str, list[tuple[logging.Logger, logging.Handler]]] = {}
# The package logger the uncaught-exception hooks report through (last setup wins).
_hook_logger: list[str] = []


def setup_logging(
    logger_name: str,
    logs_dir: str | Path = "logs",
    *,
    console_level: int | None = logging.INFO,
    file_level: int = logging.DEBUG,
    rich: bool = True,
    console: object | None = None,
    persistent_file: bool | str = False,
    attach: Iterable[str | logging.Logger] = (),
    run_prefix: str = "",
    reconfigure: bool = False,
    persistent_max_bytes: int = PERSISTENT_MAX_BYTES,
    persistent_backups: int = PERSISTENT_BACKUPS,
    catch_uncaught: bool = True,
    capture_warnings: bool = True,
    redact: bool = True,
) -> Path:
    """Wire handlers onto the ``logger_name`` tree; return the per-run log path.

    Call once, from the process entrypoint.

    * ``logger_name`` — the package logger (``"tlf"``, ``"gce"``,
      ``"dialogue_lens"``). Set to ``""`` to configure the **root** logger
      instead (the jobs / finance-insights shape); the root logger keeps its
      ``propagate`` default.
    * ``logs_dir`` — created if missing. The per-run file is
      ``<logs_dir>/<run_prefix><timestamp>.log``.
    * ``console_level`` — ``None`` installs **no** console handler (dialogue-lens
      logs to files only).
    * ``rich`` — use `rich.logging.RichHandler` when rich is importable; falls
      back to a plain `StreamHandler` silently. ``console`` is the optional
      `rich.console.Console` to share with the app's progress output.
    * ``persistent_file`` — also append to a long-lived file: ``True`` means
      ``<logger_name>.log``, or pass the filename. Off by default because
      per-run files are the common case. It rotates at ``persistent_max_bytes``
      keeping ``persistent_backups`` old copies.
    * ``attach`` — extra loggers to hand the file handler to directly, for
      libraries that set ``propagate = False`` on their own loggers (jobspy
      does). Accepts `Logger` objects, exact names, or `fnmatch` patterns
      (``"JobSpy:*"``) matched against already-created loggers.
    * ``reconfigure`` — force a rewire (and a fresh run file) even if this
      logger was already set up in this process.
    * ``catch_uncaught`` — log uncaught exceptions (``sys.excepthook``, at
      CRITICAL) and uncaught thread exceptions (``threading.excepthook``, at
      ERROR) with their traceback, then chain to the previous hook.
    * ``capture_warnings`` — route `warnings.warn` into the log file.
    * ``redact`` — mask values of env vars named like ``*TOKEN*`` / ``*SECRET*`` /
      ``*KEY*`` / ``*PASSWORD*`` / ``*HASH*`` (8+ chars) and ``Bearer <token>``.

    Idempotent by default: a repeat call returns the same path and touches
    nothing. A rewire *replaces* our handlers rather than stacking them.
    """
    if not reconfigure and logger_name in _runs:
        return _runs[logger_name]

    directory = Path(logs_dir)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / f"{run_prefix}{time.strftime(RUN_STAMP)}.log"

    logger = logging.getLogger(logger_name)
    logger.setLevel(min(file_level, console_level if console_level is not None else file_level))
    for old in logger.handlers:
        old.close()  # reconfigure must not leak the previous run's file descriptors
    logger.handlers.clear()
    for target, old in _attached.pop(logger_name, ()):
        target.removeHandler(old)  # else attached loggers write to a closed file
    if logger_name:
        # A package tree must not double-log through the root logger's handlers;
        # the root logger has no parent to propagate to.
        logger.propagate = False

    file_fmt = logging.Formatter(FILE_FORMAT, FILE_DATEFMT)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    if persistent_file:
        name = persistent_file if isinstance(persistent_file, str) else f"{logger_name or 'run'}.log"
        persistent = RotatingFileHandler(
            directory / name, maxBytes=persistent_max_bytes,
            backupCount=persistent_backups, encoding="utf-8",
        )
        persistent.setLevel(file_level)
        persistent.setFormatter(logging.Formatter(FILE_FORMAT, PERSISTENT_DATEFMT))
        logger.addHandler(persistent)

    if console_level is not None:
        handler = _console_handler(rich=rich, console=console)
        handler.setLevel(console_level)
        logger.addHandler(handler)

    if redact:
        redactor = _redact_filter()
        for handler in logger.handlers:
            handler.addFilter(redactor)

    targets = _resolve_attach(attach)
    if capture_warnings:
        logging.captureWarnings(True)
        if logger_name:  # a root setup already sees py.warnings via propagation
            targets.append(logging.getLogger("py.warnings"))
    for target in targets:
        target.addHandler(file_handler)
    _attached[logger_name] = [(target, file_handler) for target in targets]

    if catch_uncaught:
        _install_excepthooks(logger_name)

    _runs[logger_name] = log_path
    logger.debug("logging to %s", log_path)
    return log_path


def run_log_path(logger_name: str) -> Path | None:
    """Per-run log path from the last `setup_logging` for this logger, if any."""
    return _runs.get(logger_name)


def _install_excepthooks(logger_name: str) -> None:
    """Log uncaught exceptions via ``logger_name``, then chain; wraps only once."""
    _hook_logger[:] = [logger_name]
    if not getattr(sys.excepthook, "_pycommons", False):
        prev_sys = sys.excepthook

        def sys_hook(exc_type, exc, tb):
            if not issubclass(exc_type, KeyboardInterrupt):  # Ctrl-C is not a crash
                logging.getLogger(_hook_logger[0]).critical(
                    "uncaught exception", exc_info=(exc_type, exc, tb))
            prev_sys(exc_type, exc, tb)

        sys_hook._pycommons = True  # type: ignore[attr-defined]
        sys.excepthook = sys_hook
    if not getattr(threading.excepthook, "_pycommons", False):
        prev_thread = threading.excepthook

        def thread_hook(args):
            if args.exc_type is not SystemExit:  # the default hook ignores it too
                name = args.thread.name if args.thread else "?"
                logging.getLogger(_hook_logger[0]).error(
                    "uncaught exception in thread %s", name,
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
            prev_thread(args)

        thread_hook._pycommons = True  # type: ignore[attr-defined]
        threading.excepthook = thread_hook


class _RedactFilter(logging.Filter):
    """Mask secrets in a *copy* of the record (3.12+ filters may return one)."""

    def __init__(self, pattern: re.Pattern[str]) -> None:
        super().__init__()
        self._pattern = pattern

    def filter(self, record: logging.LogRecord) -> logging.LogRecord:
        msg = record.getMessage()
        exc_text = record.exc_text
        if record.exc_info and not exc_text:
            exc_text = logging.Formatter().formatException(record.exc_info)
        if not self._pattern.search(msg) and not (exc_text and self._pattern.search(exc_text)):
            return record
        out = copy.copy(record)
        out.msg, out.args = self._pattern.sub(REDACTED, msg), None
        if exc_text:
            out.exc_text = self._pattern.sub(REDACTED, exc_text)
        return out


def _redact_filter() -> _RedactFilter:
    """Compile the secret pattern once per setup from the current environment."""
    secrets = {
        value for name, value in os.environ.items()
        if len(value) >= SECRET_MIN_LEN
        and any(fnmatch.fnmatch(name.upper(), pat) for pat in SECRET_ENV_PATTERNS)
    }
    # Longest first, so a secret that contains another is masked whole.
    alts = [re.escape(v) for v in sorted(secrets, key=len, reverse=True)]
    return _RedactFilter(re.compile("|".join([*alts, _BEARER])))


def _console_handler(*, rich: bool, console: object | None) -> logging.Handler:
    """RichHandler when rich is available and wanted, else a plain StreamHandler."""
    if rich:
        try:
            from rich.logging import RichHandler
        except ImportError:
            pass
        else:
            # Compact [HH:MM:SS] time (so you can gauge speed), no date/level/path.
            return RichHandler(
                console=console, show_time=True, show_level=False, show_path=False,
                log_time_format=f"[{CONSOLE_DATEFMT}]", omit_repeated_times=False,
                markup=False, rich_tracebacks=True,
            )
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, CONSOLE_DATEFMT))
    return handler


def _resolve_attach(attach: Iterable[str | logging.Logger]) -> list[logging.Logger]:
    """Expand names/patterns into Logger objects (patterns hit existing loggers only)."""
    out: list[logging.Logger] = []
    for item in attach:
        if isinstance(item, logging.Logger):
            out.append(item)
        elif any(ch in item for ch in "*?["):
            existing = list(logging.root.manager.loggerDict.items())
            out += [
                obj for name, obj in existing
                if isinstance(obj, logging.Logger) and fnmatch.fnmatch(name, item)
            ]
        else:
            out.append(logging.getLogger(item))
    return out
