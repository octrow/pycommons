## Purpose

Opens a SQLite database the way every consumer needs it — parent directories
created, rows addressable by column name, schema applied — and offers a
transactional session form that commits only when a stage finishes cleanly.

## Requirements

### Requirement: Opening a database applies its schema every time
`open_sqlite_db` SHALL create any missing parent directories of the database
path, connect, and execute `schema_sql` through `executescript` on **every**
open. `schema_sql` MUST therefore be idempotent — `CREATE TABLE IF NOT EXISTS`
— which is the property that makes "open the database" and "migrate the
database" a single operation. An empty `schema_sql` SHALL be skipped. Additive
column migrations remain the consumer's responsibility, because they are that
schema's history rather than a generic concern.

#### Scenario: Parent directories are created and the schema applied
- **WHEN** `open_sqlite_db` is called with a path whose parent directory does not exist
- **THEN** the directory is created and the tables declared in `schema_sql` exist

#### Scenario: Reopening preserves existing rows
- **WHEN** a database holding rows is reopened with the same `schema_sql`
- **THEN** the schema statements run again without error and the rows are still present

#### Scenario: The schema argument is optional
- **WHEN** `open_sqlite_db` is called without `schema_sql`
- **THEN** a usable connection to the database is returned and no statements are executed

#### Scenario: A bare filename needs no parent directory
- **WHEN** `open_sqlite_db` is called with a filename carrying no directory component
- **THEN** the database opens in the current working directory without error

### Requirement: Rows are always addressable by column name
Every connection returned by this capability SHALL have
`row_factory = sqlite3.Row` set before it reaches the caller, because positional
row access is how a schema change turns into a silent wrong-column bug.

#### Scenario: Columns are readable by name
- **WHEN** a row is fetched from a connection returned by `open_sqlite_db`
- **THEN** its values are accessible by column name

### Requirement: A session commits only on a clean exit
`sqlite_session` SHALL open the database as `open_sqlite_db` does, yield the
connection, commit when the block exits without an exception, and close the
connection in all cases. When the block raises, the exception SHALL propagate
with the transaction uncommitted, so closing discards it and a half-finished
stage never lands partial rows. There is deliberately no rollback-and-continue
behaviour: the caller is meant to see the exception.

#### Scenario: Work is committed when the block finishes
- **WHEN** rows are inserted inside a `sqlite_session` block that exits normally
- **THEN** those rows are present when the database is reopened

#### Scenario: Work is discarded when the block raises
- **WHEN** rows are inserted inside a `sqlite_session` block that then raises
- **THEN** the exception propagates
- **AND** those rows are absent when the database is reopened

#### Scenario: The connection is closed either way
- **WHEN** a `sqlite_session` block exits, with or without an exception
- **THEN** the connection is closed

### Requirement: Ownership of the connection follows the entry point
`open_sqlite_db` SHALL leave closing to the caller, so a long-lived process can
hold the connection. `sqlite_session` SHALL own the connection's lifetime.

#### Scenario: A directly opened connection stays open
- **WHEN** `open_sqlite_db` returns a connection
- **THEN** that connection is usable until the caller closes it
