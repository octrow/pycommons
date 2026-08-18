## Purpose

Turns arbitrary text into a filesystem- and identifier-safe string, through two
separate functions because the call sites depend on two different contracts —
one preserves the input alphabet and the other deliberately destroys it.

## Requirements

### Requirement: The two functions are not one function with a flag
`safe_filename` and `slugify` SHALL remain distinct entry points. `safe_filename`
preserves Unicode letters and case; `slugify` reduces text to a lowercase ASCII
identifier. A single function with an `ascii_only` flag would hide which contract
a call site depends on, and the two are used for different purposes: one names a
directory that is later looked up again by re-deriving the same name, the other
produces something a person types on a command line.

#### Scenario: Both functions are available independently
- **WHEN** the `pycommons` package is imported
- **THEN** `safe_filename` and `slugify` are both exported

### Requirement: safe_filename preserves the input alphabet and case
`safe_filename` SHALL remove every character that is not a word character,
whitespace, or `-`; collapse each run of whitespace to `sep` (`_` by default);
and truncate to `max_len` characters (50 by default). Letters outside ASCII and
the original casing SHALL be preserved, because a directory named from a
Cyrillic clinic name is found again by re-deriving that name — mangling
non-ASCII would break the lookup, not merely the appearance.

Truncation SHALL happen **before** trailing separators are trimmed, so the
result is a prefix-stable directory key that never ends in a separator. Input
with nothing usable in it SHALL yield `""`, matching the behaviour call sites
already check for.

#### Scenario: Cyrillic text and case survive
- **WHEN** `safe_filename` is given mixed-case non-ASCII text
- **THEN** the returned name retains those characters and their case

#### Scenario: Whitespace runs collapse to the separator
- **WHEN** the input contains runs of spaces and punctuation
- **THEN** punctuation is dropped and each whitespace run becomes a single `sep`

#### Scenario: Truncation never leaves a trailing separator
- **WHEN** truncating at `max_len` would land on a separator
- **THEN** the trailing separator is trimmed from the result

#### Scenario: Re-deriving the name is stable
- **WHEN** `safe_filename` is applied to its own output
- **THEN** the result is unchanged

#### Scenario: Unusable input yields an empty string
- **WHEN** the input contains no word characters, whitespace or `-`
- **THEN** the result is `""`

### Requirement: slugify produces a lowercase ASCII identifier
`slugify` SHALL lowercase the input and replace every run of characters outside
`[a-z0-9]` with `sep` (`-` by default), then strip leading and trailing
separators, so the result matches `^[a-z0-9][a-z0-9_-]*$`. Non-ASCII characters
SHALL be **removed**, not transliterated. `max_len=0` means no truncation; a
non-zero `max_len` SHALL truncate and then trim trailing separators.

An otherwise empty result SHALL become `fallback` (`"x"` by default), because
the slug is used as both a filename stem and a dictionary key and neither may be
empty.

#### Scenario: Ordinary text becomes a hyphenated slug
- **WHEN** `slugify` is given `"Ivan P. Sidorov"`
- **THEN** the result is `"ivan-p-sidorov"`

#### Scenario: Fully non-ASCII input falls back
- **WHEN** the input contains no ASCII alphanumerics
- **THEN** the result is `fallback`

#### Scenario: Mixed-script input keeps only its ASCII part
- **WHEN** the input mixes Cyrillic and ASCII words
- **THEN** only the ASCII words appear in the result

#### Scenario: Truncation leaves no trailing separator
- **WHEN** a non-zero `max_len` would cut the slug at a separator
- **THEN** the trailing separator is trimmed

#### Scenario: Slugging a slug is a no-op
- **WHEN** `slugify` is applied to its own output
- **THEN** the result is unchanged
