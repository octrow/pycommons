## Purpose

Uses a JSON file as a small database safely: reads that fail loudly rather than
silently, writes that a crash cannot truncate, and a merge rule that lets a
re-scrape enrich records without destroying data already in them.

## Requirements

### Requirement: A missing file yields the default, a corrupt one raises
`load_or_default` SHALL return the caller's `default` when the file does not
exist. A file that exists but does not parse as JSON SHALL raise
`json.JSONDecodeError` rather than returning the default, because reading
corruption as "no data" lets the next save replace the file with a smaller one —
losing data quietly is worse than failing loudly.

#### Scenario: Missing file returns the default
- **WHEN** `load_or_default` is called with a path that does not exist
- **THEN** it returns the supplied `default`

#### Scenario: An existing file is parsed
- **WHEN** `load_or_default` is called with a path holding valid JSON
- **THEN** it returns the parsed value

#### Scenario: Corrupt content raises rather than returning the default
- **WHEN** `load_or_default` is called with a path holding invalid JSON
- **THEN** `json.JSONDecodeError` is raised

### Requirement: Saving is atomic and never leaves a partial file
`save_atomic` SHALL create any missing parent directories, serialise to a
temporary file **in the destination directory**, flush and `fsync` it, then
`os.replace` it over the target. Writing the temporary file beside the target
keeps the rename within one filesystem and therefore atomic, so a concurrent
reader sees either the old file or the new one and never a truncated one.

If serialisation fails for any reason, the temporary file SHALL be removed and
the original target SHALL be left untouched, so a failed save leaves neither
data loss nor temporary-file litter. The function SHALL return the target
`Path`.

#### Scenario: A saved value round-trips and leaves no temporary file
- **WHEN** `save_atomic` writes a value and it is read back
- **THEN** the value matches
- **AND** no temporary file remains in the destination directory

#### Scenario: Parent directories are created
- **WHEN** `save_atomic` is called with a path whose parent directory does not exist
- **THEN** the directory is created and the file is written

#### Scenario: Overwriting replaces the content entirely
- **WHEN** `save_atomic` writes a smaller value over a larger existing file
- **THEN** the file holds only the new value

#### Scenario: A serialisation failure preserves the original
- **WHEN** `save_atomic` is given a value that cannot be serialised to JSON
- **THEN** the exception propagates
- **AND** the original file is unchanged and no temporary file remains

### Requirement: Saved JSON is human-reviewable
`save_atomic` SHALL always write with `ensure_ascii=False`, because the stored
data is Russian and Kazakh text and escaped JSON is unreadable in a diff.
Output SHALL be indented by `indent` (2 by default); `indent=None` SHALL produce
compact output.

#### Scenario: Non-ASCII text is written unescaped and indented
- **WHEN** `save_atomic` writes a value containing Cyrillic text
- **THEN** the file contains those characters literally rather than `\u` escapes
- **AND** the output is indented

#### Scenario: Indent None produces compact output
- **WHEN** `save_atomic` is called with `indent=None`
- **THEN** the file contains no added newlines or indentation

### Requirement: Merging fills blanks and never overwrites with nothing
`merge_keep_nonempty` SHALL take a value from `new` only when that value is
truthy **and** the corresponding value in `old` is falsy. A re-scrape must not
wipe a field a human filled in by hand, nor a field this run merely failed to
extract. Keys present only in `old` SHALL be preserved.

Names listed in `always` SHALL be refreshed whenever `new` holds a truthy value
for them regardless of `old`, because those are facts about the source rather
than hand-curated data. A falsy value in `new` SHALL be skipped even for an
`always` name.

The function SHALL return a new dictionary and SHALL NOT mutate either input.

#### Scenario: Blank fields are filled from the new record
- **WHEN** `old` holds an empty value for a key and `new` holds a truthy one
- **THEN** the result holds the value from `new`

#### Scenario: A non-empty value is never replaced
- **WHEN** `old` holds a truthy value for a key not listed in `always`
- **THEN** the result keeps the value from `old`, whether `new`'s value is truthy or falsy

#### Scenario: A falsy new value never creates a key
- **WHEN** `new` holds a falsy value for a key absent from `old`
- **THEN** that key is absent from the result

#### Scenario: Always-listed fields are refreshed
- **WHEN** a key listed in `always` has a truthy value in `new` and a different truthy value in `old`
- **THEN** the result holds the value from `new`

#### Scenario: Always-listed fields are still skipped when empty
- **WHEN** a key listed in `always` has a falsy value in `new`
- **THEN** the result keeps the value from `old`

#### Scenario: Keys only in the old record survive
- **WHEN** `old` holds a key absent from `new`
- **THEN** that key and its value are present in the result

#### Scenario: Neither input is mutated
- **WHEN** `merge_keep_nonempty` returns
- **THEN** both the `old` and `new` mappings the caller passed in are unchanged
