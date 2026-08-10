"""open_sqlite_db / sqlite_session: roundtrip, Row factory, schema idempotency."""

from __future__ import annotations

import sqlite3

import pytest

from pycommons import open_sqlite_db, sqlite_session

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    tiktok_id TEXT PRIMARY KEY,
    author    TEXT
);
CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT);
"""


def tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_applies_schema_and_creates_parent_dirs(tmp_path):
    path = tmp_path / "deep" / "nested" / "cache.db"
    conn = open_sqlite_db(path, SCHEMA)
    try:
        assert path.exists()
        assert tables(conn) == {"videos", "state"}
    finally:
        conn.close()


def test_row_factory_gives_named_access(tmp_path):
    conn = open_sqlite_db(tmp_path / "c.db", SCHEMA)
    try:
        conn.execute("INSERT INTO videos VALUES ('id1', 'bob')")
        row = conn.execute("SELECT * FROM videos").fetchone()
        assert isinstance(row, sqlite3.Row)
        assert row["author"] == "bob" and row[0] == "id1"
    finally:
        conn.close()


def test_reopening_with_schema_preserves_rows(tmp_path):
    """executescript on every open must be a no-op on an existing db."""
    path = tmp_path / "c.db"
    with sqlite_session(path, SCHEMA) as conn:
        conn.execute("INSERT INTO videos VALUES ('id1', 'bob')")

    with sqlite_session(path, SCHEMA) as conn:
        assert conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0] == 1
        assert tables(conn) == {"videos", "state"}


def test_schema_optional(tmp_path):
    conn = open_sqlite_db(tmp_path / "empty.db")
    try:
        assert tables(conn) == set()
    finally:
        conn.close()


def test_bare_filename_needs_no_parent_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = open_sqlite_db("cache.db", SCHEMA)
    try:
        assert (tmp_path / "cache.db").exists()
    finally:
        conn.close()


def test_session_commits_on_clean_exit(tmp_path):
    path = tmp_path / "c.db"
    with sqlite_session(path, SCHEMA) as conn:
        conn.execute("INSERT INTO state VALUES ('k', 'v')")

    with sqlite_session(path, SCHEMA) as conn:
        assert conn.execute("SELECT v FROM state WHERE k='k'").fetchone()["v"] == "v"


def test_session_discards_work_on_exception(tmp_path):
    path = tmp_path / "c.db"
    with pytest.raises(RuntimeError):
        with sqlite_session(path, SCHEMA) as conn:
            conn.execute("INSERT INTO state VALUES ('k', 'v')")
            raise RuntimeError("stage blew up")

    with sqlite_session(path, SCHEMA) as conn:
        assert conn.execute("SELECT COUNT(*) FROM state").fetchone()[0] == 0


def test_session_closes_the_connection(tmp_path):
    with sqlite_session(tmp_path / "c.db", SCHEMA) as conn:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
