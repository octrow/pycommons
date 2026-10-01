"""setup_logging: handler wiring, the rich-absent fallback, attach, idempotency."""

from __future__ import annotations

import builtins
import logging
from pathlib import Path

import pytest

from pycommons import logsetup
from pycommons.logsetup import run_log_path, setup_logging


@pytest.fixture(autouse=True)
def clean_logging():
    """Every test gets a fresh process-level state (module cache + our loggers)."""
    logsetup._runs.clear()
    yield
    for name in list(logging.root.manager.loggerDict):
        if name.startswith(("pkgtest", "JobSpy:")):
            logging.getLogger(name).handlers.clear()
    logsetup._runs.clear()


def handlers(name):
    return logging.getLogger(name).handlers


def file_handlers(name):
    return [h for h in handlers(name) if isinstance(h, logging.FileHandler)]


def test_creates_logs_dir_and_timestamped_run_file(tmp_path):
    path = setup_logging("pkgtest.a", tmp_path / "logs")

    assert path.parent == tmp_path / "logs"
    assert path.exists() and path.suffix == ".log"
    # <YYYY-MM-DD-HH-MM-SS>.log — 19 chars of stamp
    assert len(path.stem) == 19 and path.stem.count("-") == 5


def test_file_gets_debug_console_gets_info(tmp_path):
    path = setup_logging("pkgtest.b", tmp_path)
    log = logging.getLogger("pkgtest.b.area")

    log.debug("debug-line")
    log.info("info-line")
    for h in handlers("pkgtest.b"):
        h.flush()

    text = path.read_text(encoding="utf-8")
    assert "debug-line" in text and "info-line" in text
    console = [h for h in handlers("pkgtest.b") if not isinstance(h, logging.FileHandler)]
    assert len(console) == 1 and console[0].level == logging.INFO
    assert file_handlers("pkgtest.b")[0].level == logging.DEBUG


def test_package_tree_does_not_propagate(tmp_path):
    setup_logging("pkgtest.c", tmp_path)
    assert logging.getLogger("pkgtest.c").propagate is False


def test_root_logger_keeps_propagate_default(tmp_path):
    root = logging.getLogger()
    before, saved = root.propagate, root.handlers[:]
    try:
        setup_logging("", tmp_path, reconfigure=True)
        assert root.propagate is before
    finally:
        root.handlers[:] = saved
        logsetup._runs.clear()


def test_console_level_none_means_no_console(tmp_path):
    setup_logging("pkgtest.d", tmp_path, console_level=None)
    assert all(isinstance(h, logging.FileHandler) for h in handlers("pkgtest.d"))


def test_rich_handler_used_when_available(tmp_path):
    pytest.importorskip("rich")
    setup_logging("pkgtest.e", tmp_path)
    console = [h for h in handlers("pkgtest.e") if not isinstance(h, logging.FileHandler)]
    assert type(console[0]).__name__ == "RichHandler"


def test_falls_back_to_streamhandler_when_rich_missing(tmp_path, monkeypatch):
    """rich uninstalled must not break logging — the whole point of the extra."""
    real_import = builtins.__import__

    def no_rich(name, *args, **kw):
        if name.startswith("rich"):
            raise ImportError("no rich here")
        return real_import(name, *args, **kw)

    monkeypatch.setattr(builtins, "__import__", no_rich)
    setup_logging("pkgtest.f", tmp_path)

    console = [h for h in handlers("pkgtest.f") if not isinstance(h, logging.FileHandler)]
    assert len(console) == 1
    assert type(console[0]) is logging.StreamHandler


def test_rich_false_uses_streamhandler_even_with_rich_installed(tmp_path):
    setup_logging("pkgtest.g", tmp_path, rich=False)
    console = [h for h in handlers("pkgtest.g") if not isinstance(h, logging.FileHandler)]
    assert type(console[0]) is logging.StreamHandler
    assert console[0].formatter.datefmt == "%H:%M:%S"


def test_persistent_file_true_names_after_logger(tmp_path):
    setup_logging("pkgtest_h", tmp_path, persistent_file=True)
    assert (tmp_path / "pkgtest_h.log").exists()
    assert len(file_handlers("pkgtest_h")) == 2


def test_persistent_file_string_is_the_filename(tmp_path):
    setup_logging("pkgtest.i", tmp_path, persistent_file="dialogue-lens.log")
    assert (tmp_path / "dialogue-lens.log").exists()


def test_persistent_file_survives_a_second_run(tmp_path):
    setup_logging("pkgtest.j", tmp_path, persistent_file="hist.log")
    logging.getLogger("pkgtest.j").info("first")
    # (two runs inside the same second share a per-run filename — the stamp has
    # 1s resolution, as in every source copy — but the persistent file appends.)
    setup_logging("pkgtest.j", tmp_path, persistent_file="hist.log", reconfigure=True)
    logging.getLogger("pkgtest.j").info("second")
    for h in handlers("pkgtest.j"):
        h.flush()

    history = (tmp_path / "hist.log").read_text(encoding="utf-8")
    assert "first" in history and "second" in history


def test_persistent_file_lines_carry_the_date(tmp_path):
    """The persistent file spans days — a time-only stamp is ambiguous there."""
    import re

    setup_logging("pkgtest.r", tmp_path, persistent_file="hist.log")
    logging.getLogger("pkgtest.r").info("dated line")
    for h in handlers("pkgtest.r"):
        h.flush()

    line = (tmp_path / "hist.log").read_text(encoding="utf-8").splitlines()[-1]
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ", line)


def test_run_prefix_applies(tmp_path):
    path = setup_logging("pkgtest.k", tmp_path, run_prefix="run-")
    assert path.name.startswith("run-")


def test_idempotent_by_default(tmp_path):
    first = setup_logging("pkgtest.l", tmp_path)
    count = len(handlers("pkgtest.l"))
    second = setup_logging("pkgtest.l", tmp_path / "elsewhere")

    assert second == first                          # same path
    assert len(handlers("pkgtest.l")) == count      # no stacking
    assert not (tmp_path / "elsewhere").exists()    # not even touched
    assert run_log_path("pkgtest.l") == first


def test_reconfigure_replaces_handlers_rather_than_stacking(tmp_path):
    setup_logging("pkgtest.m", tmp_path)
    count = len(handlers("pkgtest.m"))
    setup_logging("pkgtest.m", tmp_path, reconfigure=True)
    assert len(handlers("pkgtest.m")) == count


def test_run_log_path_is_none_before_setup():
    assert run_log_path("pkgtest.never") is None


def test_attach_by_name_reaches_a_non_propagating_logger(tmp_path):
    """The jobs/jobspy case: a lib sets propagate=False on its own logger."""
    lib = logging.getLogger("JobSpy:Indeed")
    lib.handlers.clear()
    lib.propagate = False
    lib.setLevel(logging.INFO)

    path = setup_logging("pkgtest.n", tmp_path, attach=["JobSpy:Indeed"])
    lib.info("from the library")
    for h in lib.handlers:
        h.flush()

    assert "from the library" in path.read_text(encoding="utf-8")


def test_attach_pattern_matches_existing_loggers(tmp_path):
    for name in ("JobSpy:LinkedIn", "JobSpy:Glassdoor"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = False
        lg.setLevel(logging.INFO)

    path = setup_logging("pkgtest.o", tmp_path, attach=["JobSpy:*"])
    logging.getLogger("JobSpy:LinkedIn").info("li")
    logging.getLogger("JobSpy:Glassdoor").info("gd")
    for name in ("JobSpy:LinkedIn", "JobSpy:Glassdoor"):
        for h in logging.getLogger(name).handlers:
            h.flush()

    text = path.read_text(encoding="utf-8")
    assert "li" in text and "gd" in text


def test_attach_accepts_logger_objects(tmp_path):
    lib = logging.getLogger("JobSpy:Direct")
    lib.handlers.clear()
    setup_logging("pkgtest.p", tmp_path, attach=[lib])
    assert any(isinstance(h, logging.FileHandler) for h in lib.handlers)


def test_returns_path_object(tmp_path):
    assert isinstance(setup_logging("pkgtest.q", tmp_path), Path)


def test_reconfigure_closes_the_previous_file_handlers(tmp_path):
    setup_logging("pkgtest.close", tmp_path)
    old = file_handlers("pkgtest.close")
    setup_logging("pkgtest.close", tmp_path, reconfigure=True)
    assert all(h.stream is None for h in old)


# --- production hardening: attach cleanup, rotation, hooks, warnings, redaction ---


def test_reconfigure_detaches_the_old_file_handler_from_attached_loggers(tmp_path):
    lib = logging.getLogger("JobSpy:Reconf")
    lib.handlers.clear()
    setup_logging("pkgtest.s", tmp_path, attach=[lib])
    old = list(lib.handlers)
    setup_logging("pkgtest.s", tmp_path / "second", attach=[lib], reconfigure=True)

    assert len(lib.handlers) == 1                    # no accumulation
    assert not any(h in lib.handlers for h in old)   # the closed one is gone


def test_persistent_file_rotates_at_the_size_cap(tmp_path):
    from logging.handlers import RotatingFileHandler

    setup_logging("pkgtest.t", tmp_path, persistent_file="hist.log",
                  persistent_max_bytes=200, persistent_backups=2)
    rot = [h for h in handlers("pkgtest.t") if isinstance(h, RotatingFileHandler)]
    assert len(rot) == 1 and rot[0].maxBytes == 200 and rot[0].backupCount == 2
    for i in range(30):
        logging.getLogger("pkgtest.t").info("line %d padded out to fill the file", i)
    assert (tmp_path / "hist.log.1").exists()
    assert not (tmp_path / "hist.log.3").exists()


def test_persistent_file_has_a_default_size_cap(tmp_path):
    from logging.handlers import RotatingFileHandler

    setup_logging("pkgtest.u", tmp_path, persistent_file=True)
    rot = [h for h in handlers("pkgtest.u") if isinstance(h, RotatingFileHandler)]
    assert rot[0].maxBytes == logsetup.PERSISTENT_MAX_BYTES
    assert rot[0].backupCount == logsetup.PERSISTENT_BACKUPS


@pytest.fixture(autouse=True)
def saved_hooks():
    """setup_logging installs process-wide hooks; give them back after each test."""
    import sys
    import threading

    saved = sys.excepthook, threading.excepthook
    yield
    sys.excepthook, threading.excepthook = saved
    logging.captureWarnings(False)
    logging.getLogger("py.warnings").handlers.clear()


def test_uncaught_exception_is_logged_then_chained(tmp_path, saved_hooks, monkeypatch):
    import sys

    seen = []
    monkeypatch.setattr(sys, "excepthook", lambda *a: seen.append(a))
    path = setup_logging("pkgtest.v", tmp_path)
    setup_logging("pkgtest.v", tmp_path, reconfigure=True)   # repeat: no double wrap
    try:
        raise RuntimeError("boom-uncaught")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    for h in handlers("pkgtest.v"):
        h.flush()

    text = path.read_text(encoding="utf-8")
    assert text.count("boom-uncaught") >= 1 and "CRITICAL" in text
    assert "Traceback" in text
    assert len(seen) == 1                            # previous hook ran exactly once


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_uncaught_thread_exception_is_logged(tmp_path, saved_hooks):
    import threading

    path = setup_logging("pkgtest.w", tmp_path)
    t = threading.Thread(target=lambda: 1 / 0, name="worker-x")
    t.start()
    t.join()
    for h in handlers("pkgtest.w"):
        h.flush()

    text = path.read_text(encoding="utf-8")
    assert "worker-x" in text and "ZeroDivisionError" in text


def test_catch_uncaught_false_leaves_hooks_alone(tmp_path, saved_hooks):
    import sys
    import threading

    before = sys.excepthook, threading.excepthook
    setup_logging("pkgtest.x", tmp_path, catch_uncaught=False)
    assert (sys.excepthook, threading.excepthook) == before


def test_warnings_land_in_the_file(tmp_path):
    import warnings

    # pytest restores warnings.showwarning between tests, which leaves logging's
    # "already capturing" flag stale — reset it so this test is order-independent.
    logging.captureWarnings(False)
    path = setup_logging("pkgtest.y", tmp_path)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("always")
            warnings.warn("deprecated-thing", UserWarning)
    finally:
        logging.captureWarnings(False)
        logging.getLogger("py.warnings").handlers.clear()
    for h in handlers("pkgtest.y"):
        h.flush()
    assert "deprecated-thing" in path.read_text(encoding="utf-8")


def test_secrets_are_redacted_in_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_API_TOKEN", "s3cr3t-value-123")
    monkeypatch.setenv("SHORT_KEY", "abc")           # too short to mask safely
    path = setup_logging("pkgtest.z", tmp_path)
    log = logging.getLogger("pkgtest.z")
    log.info("token=%s", "s3cr3t-value-123")
    log.info("header Authorization: Bearer eyJhbGciOi.payload.sig")
    log.info("short abc stays")
    for h in handlers("pkgtest.z"):
        h.flush()

    text = path.read_text(encoding="utf-8")
    assert "s3cr3t-value-123" not in text and "token=***" in text
    assert "eyJhbGciOi" not in text and "Bearer ***" in text
    assert "short abc stays" in text


def test_redact_false_keeps_values(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_API_TOKEN", "s3cr3t-value-123")
    path = setup_logging("pkgtest.za", tmp_path, redact=False)
    logging.getLogger("pkgtest.za").info("token=%s", "s3cr3t-value-123")
    for h in handlers("pkgtest.za"):
        h.flush()
    assert "s3cr3t-value-123" in path.read_text(encoding="utf-8")
