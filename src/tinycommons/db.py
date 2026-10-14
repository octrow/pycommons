"""The ten-line sqlite open that three repos wrote independently.

Sources: tiktok-lazy-follower `tlf/db.py::connect` (contextmanager,
commit-on-success) and get_cool_event `gce/db.py::connect` (flat, returns the
connection). Both do the same four things — mkdir the parent, connect, set
`row_factory = sqlite3.Row`, `executescript(SCHEMA)` — so both shapes live here
and the schema stays with the consumer, where it belongs.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

__all__ = ["open_sqlite_db", "sqlite_session"]


def open_sqlite_db(path: str | Path = "cache.db", schema_sql: str = "") -> sqlite3.Connection:
    """Open (creating parents) a sqlite db with `Row` rows; apply ``schema_sql``.

    ``schema_sql`` runs through `executescript` on **every** open, so it must be
    idempotent — i.e. `CREATE TABLE IF NOT EXISTS`. That is the property that
    makes "open the db" and "migrate the db" the same operation, and it is why
    no consumer here has ever needed a migration tool.

    Caller closes. Use `sqlite_session` if you want that handled.
    """
    path = Path(path)
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    if schema_sql:
        conn.executescript(schema_sql)
    return conn


@contextmanager
def sqlite_session(
    path: str | Path = "cache.db", schema_sql: str = ""
) -> Iterator[sqlite3.Connection]:
    """`open_sqlite_db` + commit on clean exit, always close (the tlf shape).

    An exception propagates with the work **uncommitted** — closing without a
    commit discards the open transaction, so a half-finished stage never lands
    partial rows.
    """
    conn = open_sqlite_db(path, schema_sql)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
