"""load_env: parsing, defaults merge, missing file."""

from __future__ import annotations

import os

from pycommons import load_env

DEFAULTS = {"WORK_TZ": "Asia/Almaty", "WORK_START": "10:30"}


def test_missing_file_returns_defaults(tmp_path):
    assert load_env(tmp_path / "nope.env", DEFAULTS) == DEFAULTS


def test_missing_file_without_defaults_is_empty(tmp_path):
    assert load_env(tmp_path / "nope.env") == {}


def test_file_values_override_defaults(tmp_path):
    p = tmp_path / ".env"
    p.write_text("WORK_START=09:00\nTG_API_ID=12345\n", encoding="utf-8")

    env = load_env(p, DEFAULTS)
    assert env["WORK_START"] == "09:00"      # overridden
    assert env["WORK_TZ"] == "Asia/Almaty"   # untouched default
    assert env["TG_API_ID"] == "12345"       # new key


def test_ignores_blanks_comments_and_lines_without_equals(tmp_path):
    p = tmp_path / ".env"
    p.write_text("\n  \n# a comment\nKEY=ok\nnot a pair\n   # indented comment\n", encoding="utf-8")
    assert load_env(p) == {"KEY": "ok"}


def test_strips_whitespace_around_key_and_value(tmp_path):
    p = tmp_path / ".env"
    p.write_text("  KEY  =   value  \n", encoding="utf-8")
    assert load_env(p) == {"KEY": "value"}


def test_value_may_contain_equals_signs(tmp_path):
    p = tmp_path / ".env"
    p.write_text("URL=https://x/?a=1&b=2\n", encoding="utf-8")
    assert load_env(p) == {"URL": "https://x/?a=1&b=2"}


def test_empty_value_is_kept_as_empty_string(tmp_path):
    p = tmp_path / ".env"
    p.write_text("EMPTY=\n", encoding="utf-8")
    assert load_env(p) == {"EMPTY": ""}


def test_last_duplicate_wins(tmp_path):
    p = tmp_path / ".env"
    p.write_text("K=first\nK=second\n", encoding="utf-8")
    assert load_env(p)["K"] == "second"


def test_defaults_are_not_mutated(tmp_path):
    p = tmp_path / ".env"
    p.write_text("NEW=1\n", encoding="utf-8")
    defaults = dict(DEFAULTS)
    load_env(p, defaults)
    assert defaults == DEFAULTS


def test_does_not_touch_os_environ_by_default(tmp_path):
    p = tmp_path / ".env"
    p.write_text("PYCOMMONS_TEST_KEY=1\n", encoding="utf-8")
    load_env(p)
    assert "PYCOMMONS_TEST_KEY" not in os.environ


def test_override_os_environ_exports(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("PYCOMMONS_TEST_KEY=1\n", encoding="utf-8")
    monkeypatch.delenv("PYCOMMONS_TEST_KEY", raising=False)

    load_env(p, override_os_environ=True)
    assert os.environ["PYCOMMONS_TEST_KEY"] == "1"
    monkeypatch.delenv("PYCOMMONS_TEST_KEY", raising=False)


def test_utf8_values(tmp_path):
    p = tmp_path / ".env"
    p.write_text("CITY=Алматы\n", encoding="utf-8")
    assert load_env(p)["CITY"] == "Алматы"
