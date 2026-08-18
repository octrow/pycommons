## Purpose

Reads a simple `KEY=VALUE` configuration file into a dictionary without any
third-party dependency, so a stage that must run under a bare interpreter with
no site-packages can still load its configuration.

## Requirements

### Requirement: A missing file is not an error
`load_env` SHALL return the `defaults` mapping unchanged when the given path does
not exist, so the configuration file is optional for every caller. When no
`defaults` are supplied the result SHALL be an empty dictionary. The `defaults`
mapping passed in SHALL NOT be mutated.

#### Scenario: Missing file yields the defaults
- **WHEN** `load_env` is called with a path that does not exist and a `defaults` mapping
- **THEN** it returns a dictionary equal to `defaults`

#### Scenario: Missing file and no defaults yields an empty mapping
- **WHEN** `load_env` is called with a nonexistent path and no `defaults`
- **THEN** it returns an empty dictionary

#### Scenario: The caller's defaults mapping is left alone
- **WHEN** `load_env` reads a file containing keys absent from `defaults`
- **THEN** the `defaults` object the caller passed in is unchanged

### Requirement: Only KEY=VALUE lines are parsed, split on the first separator
Each line SHALL be stripped of surrounding whitespace and skipped when it is
blank, begins with `#`, or contains no `=`. A parsed line SHALL be split on the
**first** `=` only, so a value containing further `=` characters — a URL with a
query string — survives intact. Key and value SHALL each be stripped of
surrounding whitespace. When a key appears more than once the last occurrence
SHALL win. Values from the file SHALL override entries of the same name in
`defaults`.

The format SHALL NOT be extended: there is no quote-stripping, no interpolation,
and no `export ` prefix, because supporting them would invite files that only
work with this reader.

#### Scenario: Blanks, comments and separator-less lines are ignored
- **WHEN** the file contains blank lines, `#` comment lines, and a line without `=`
- **THEN** none of them contribute a key to the result

#### Scenario: A value may contain equals signs
- **WHEN** a line reads `URL=https://host/path?a=1&b=2`
- **THEN** the value is `https://host/path?a=1&b=2`

#### Scenario: Whitespace around key and value is stripped
- **WHEN** a line reads `  KEY  =  value  `
- **THEN** the result maps `KEY` to `value`

#### Scenario: An empty value is preserved as an empty string
- **WHEN** a line reads `KEY=`
- **THEN** the result maps `KEY` to `""`

#### Scenario: The last duplicate key wins
- **WHEN** the same key is assigned twice in the file
- **THEN** the result holds the value from the later line

#### Scenario: File values override defaults
- **WHEN** a key present in `defaults` is also assigned in the file
- **THEN** the result holds the file's value

#### Scenario: UTF-8 values are read correctly
- **WHEN** a value contains non-ASCII characters
- **THEN** the result holds those characters unchanged

### Requirement: Values are returned, never exported
`load_env` SHALL NOT modify `os.environ`, because the process environment is
global state and polluting it from a parser surprises every other caller. When
`override_os_environ=True` the parsed result SHALL additionally be written into
`os.environ`, for libraries that only read the process environment.

#### Scenario: os.environ is untouched by default
- **WHEN** `load_env` parses a file defining a key absent from the environment
- **THEN** that key is still absent from `os.environ`

#### Scenario: Opting in exports the parsed values
- **WHEN** `load_env` is called with `override_os_environ=True`
- **THEN** every key in the returned mapping is present in `os.environ` with the same value
