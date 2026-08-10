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
