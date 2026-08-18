## Purpose

Configures a per-run log file and an optional console sink on one package logger
tree, so an unattended run leaves a complete DEBUG record on disk while the
operator sees INFO-level progress.

## Requirements

### Requirement: Handlers are installed only on explicit setup
The library SHALL NOT configure logging at import time. Handlers SHALL be
installed only by an explicit `setup_logging` call, and `logs_dir` SHALL NOT be
created until then, so importing a consumer's library module never leaves a
`logs/` directory behind in its test suite.

#### Scenario: Importing a module does not create a log directory
- **WHEN** a consumer imports `pycommons.logsetup` without calling `setup_logging`
- **THEN** no `logs/` directory is created and no handler is added to any logger

#### Scenario: Setup creates the directory and a run file
- **WHEN** `setup_logging(name, logs_dir)` is called and `logs_dir` does not exist
- **THEN** `logs_dir` is created and a per-run file named
  `<run_prefix><YYYY-MM-DD-HH-MM-SS>.log` exists inside it
- **AND** the returned value is that file's `Path`

### Requirement: One logger tree per package, isolated from root
`setup_logging` SHALL attach handlers to `logging.getLogger(logger_name)` and
SHALL set `propagate = False` on it, so records never reach the root logger's
handlers a second time. When `logger_name` is `""` the root logger is configured
instead and its `propagate` attribute SHALL be left untouched, because the root
logger has no parent to propagate to.

#### Scenario: A package tree does not propagate
- **WHEN** `setup_logging("tlf", logs_dir)` is called
- **THEN** `logging.getLogger("tlf").propagate` is `False`

#### Scenario: The root logger keeps its default
- **WHEN** `setup_logging("", logs_dir)` is called
- **THEN** the root logger's `propagate` attribute is unchanged

### Requirement: Two levels for two audiences
The per-run file handler SHALL be set to `file_level` (DEBUG by default) so the
file holds the complete record of the run, and the console handler to
`console_level` (INFO by default) so a long step never looks stuck. The
configured logger's own level SHALL be the minimum of the two so neither sink is
starved. `console_level=None` SHALL install no console handler at all.

#### Scenario: File receives DEBUG, console does not
- **WHEN** a DEBUG record and an INFO record are emitted after a default setup
- **THEN** the run file contains both records
- **AND** the console sink received only the INFO record

#### Scenario: Console can be disabled entirely
- **WHEN** `setup_logging(..., console_level=None)` is called
- **THEN** the logger has no console handler and only file handlers remain

### Requirement: One file per run, with an optional persistent companion
Each configured run SHALL write to its own timestamped file, because a run is the
unit of debugging and a single appended log makes "what did last night's run do"
an exercise in grep. Timestamp resolution is one second; two runs started inside
the same second SHALL share a file, which is a deliberate and accepted
limitation. `persistent_file` SHALL additionally append to a never-rotated file,
named `<logger_name>.log` when `True` or by the given string, whose lines carry
the full date because that file spans many days.

#### Scenario: A second configured run gets its own file
- **WHEN** `setup_logging(..., reconfigure=True)` is called in a later second
- **THEN** a new run file is created and the previous run's file is left intact

#### Scenario: The persistent file accumulates across runs
- **WHEN** two runs are configured with the same `persistent_file`
- **THEN** that single file contains records from both runs
- **AND** its lines are formatted with a full `%Y-%m-%d %H:%M:%S` timestamp

#### Scenario: Run prefix is applied to the run file name
- **WHEN** `setup_logging(..., run_prefix="run-")` is called
- **THEN** the run file's name begins with `run-`

### Requirement: rich is optional at runtime, not only at install time
When `rich=True` and `rich.logging.RichHandler` is importable, the console sink
SHALL be a `RichHandler`. An `ImportError` SHALL degrade silently to a
`logging.StreamHandler` carrying the equivalent compact `[HH:MM:SS] message`
layout. `rich=False` SHALL use the plain handler even when rich is installed. A
logging setup must never be the thing that breaks a deployment.

#### Scenario: RichHandler when rich is importable
- **WHEN** rich is installed and `rich=True`
- **THEN** the console handler is a `RichHandler`

#### Scenario: Silent fallback when rich is absent
- **WHEN** importing `rich.logging` raises `ImportError`
- **THEN** `setup_logging` succeeds
- **AND** the console handler is a `StreamHandler` formatted as `[HH:MM:SS] message`

#### Scenario: rich can be declined explicitly
- **WHEN** rich is installed and `rich=False`
- **THEN** the console handler is a `StreamHandler`

### Requirement: Repeat setup is a no-op unless reconfigure is requested
A second `setup_logging` for a `logger_name` already configured in this process
SHALL return the same path and add no handlers, so a development reloader
re-importing the entrypoint cannot cause every line to be logged twice.
`reconfigure=True` SHALL rewire deliberately, replacing the previously installed
handlers rather than stacking onto them. This guarantee is scoped to the current
process: the record of configured loggers is process-global and is not reset.

#### Scenario: Repeat call changes nothing
- **WHEN** `setup_logging("tlf", logs_dir)` is called a second time without `reconfigure`
- **THEN** both calls return the same path
- **AND** the logger's handler count is unchanged

#### Scenario: Reconfigure replaces rather than stacks
- **WHEN** `setup_logging("tlf", logs_dir, reconfigure=True)` follows an earlier setup
- **THEN** the logger's handler count matches a fresh setup rather than double it

### Requirement: Non-propagating third-party loggers can be attached directly
`attach` SHALL add the per-run file handler directly to the named loggers, so
libraries that set `propagate = False` on their own loggers are still captured.
It SHALL accept `Logger` objects, exact logger names, and `fnmatch` patterns.
Patterns SHALL match only loggers that already exist, so a caller relying on a
pattern MUST call `setup_logging` after the library has created them.

#### Scenario: An exact name reaches a non-propagating logger
- **WHEN** `attach=["JobSpy:Indeed"]` is passed and that logger has `propagate = False`
- **THEN** records emitted by that logger appear in the run file

#### Scenario: A pattern matches loggers created before setup
- **WHEN** `attach=["JobSpy:*"]` is passed and matching loggers already exist
- **THEN** each matching logger receives the per-run file handler

#### Scenario: A Logger object is accepted directly
- **WHEN** a `logging.Logger` instance is passed in `attach`
- **THEN** that logger receives the per-run file handler

### Requirement: The run path is retrievable after setup
`run_log_path(logger_name)` SHALL return the per-run `Path` recorded by the most
recent `setup_logging` for that logger name, and SHALL return `None` when that
logger has never been configured in this process.

#### Scenario: Path is None before any setup
- **WHEN** `run_log_path("never-configured")` is called
- **THEN** it returns `None`

#### Scenario: Path matches the value setup returned
- **WHEN** `setup_logging("tlf", logs_dir)` has returned a path
- **THEN** `run_log_path("tlf")` returns that same `Path`
