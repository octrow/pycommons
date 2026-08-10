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
"""

from __future__ import annotations

import fnmatch
import logging
import time
from pathlib import Path
from typing import Iterable

__all__ = ["FILE_FORMAT", "RUN_STAMP", "run_log_path", "setup_logging"]

FILE_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
FILE_DATEFMT = "%H:%M:%S"
# The persistent file spans many days (never rotated), so its lines carry the date;
# a per-run file's date is already in its filename.
PERSISTENT_DATEFMT = "%Y-%m-%d %H:%M:%S"
CONSOLE_FORMAT = "[%(asctime)s] %(message)s"
CONSOLE_DATEFMT = "%H:%M:%S"
RUN_STAMP = "%Y-%m-%d-%H-%M-%S"

# logger name -> per-run log path, so a second call is a no-op (dialogue-lens'
# `_configured` guard, which exists because a dev reloader can re-import the CLI).
_runs: dict[str, Path] = {}


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
    * ``persistent_file`` — also append to a never-rotated file: ``True`` means
      ``<logger_name>.log``, or pass the filename. Off by default because
      per-run files are the common case.
    * ``attach`` — extra loggers to hand the file handler to directly, for
      libraries that set ``propagate = False`` on their own loggers (jobspy
      does). Accepts `Logger` objects, exact names, or `fnmatch` patterns
      (``"JobSpy:*"``) matched against already-created loggers.
    * ``reconfigure`` — force a rewire (and a fresh run file) even if this
      logger was already set up in this process.

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
    logger.handlers.clear()
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
        persistent = logging.FileHandler(directory / name, encoding="utf-8")
        persistent.setLevel(file_level)
        persistent.setFormatter(logging.Formatter(FILE_FORMAT, PERSISTENT_DATEFMT))
        logger.addHandler(persistent)

    if console_level is not None:
        handler = _console_handler(rich=rich, console=console)
        handler.setLevel(console_level)
        logger.addHandler(handler)

    for target in _resolve_attach(attach):
        target.addHandler(file_handler)

    _runs[logger_name] = log_path
    logger.debug("logging to %s", log_path)
    return log_path


def run_log_path(logger_name: str) -> Path | None:
    """Per-run log path from the last `setup_logging` for this logger, if any."""
    return _runs.get(logger_name)


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
