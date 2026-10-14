"""Two slug functions, because the three copies in the wild are two behaviours.

* `safe_filename` — dental-parser `scraper_insta.py::sanitize_name`, copied
  verbatim a second time inside `processor_ai.py::find_clinic_directory`. Keeps
  case and keeps Cyrillic (the clinic names *are* Cyrillic, and the directory
  name is looked up again by re-slugifying the name — so mangling non-ASCII
  would break the lookup, not just look ugly).
* `slugify` — dialogue-lens `config.py::slugify`. ASCII-only lowercase
  identifier for a filename that also has to be typed on a command line and
  matched by `^[a-z0-9][a-z0-9_-]*$`.

They are **not** one function with a flag: one preserves the input alphabet and
the other deliberately destroys it. Merging them would hide which contract a
call site depends on.
"""

from __future__ import annotations

import re

__all__ = ["safe_filename", "slugify"]

_UNSAFE = re.compile(r"[^\w\s-]", re.UNICODE)
_SPACES = re.compile(r"\s+")
_NON_ASCII_ALNUM = re.compile(r"[^a-z0-9]+")


def safe_filename(name: str, *, max_len: int = 50, sep: str = "_") -> str:
    """Filename-safe name that **keeps** Unicode letters and case.

    Drops everything that is not a word char, whitespace or ``-``; runs of
    whitespace collapse to ``sep``; truncated to ``max_len`` characters
    (dental-parser's 50 — the value its existing directories are named with).
    Returns ``""`` for input with nothing usable in it, matching the original.

    Slugs are truncated *before* being trimmed of trailing separators, so
    ``safe_filename`` of a long name is a prefix-stable directory key.
    """
    safe = _UNSAFE.sub("", name)
    safe = _SPACES.sub(sep, safe.strip())
    return safe[:max_len].strip(sep)


def slugify(text: str, *, max_len: int = 0, sep: str = "-", fallback: str = "x") -> str:
    """ASCII lowercase slug: ``"Ivan P. Sidorov" -> "ivan-p-sidorov"``.

    Every run of non-``[a-z0-9]`` becomes ``sep``, leading/trailing separators
    are stripped, and an empty result becomes ``fallback`` — dialogue-lens
    returns ``"x"`` rather than ``""`` because the slug is used as a filename
    stem and a profile key, and neither may be empty.

    Non-ASCII is *removed*, not transliterated: a fully Cyrillic name slugs to
    ``fallback``. ``max_len=0`` means no truncation (dialogue-lens' behaviour).
    """
    s = _NON_ASCII_ALNUM.sub(sep, text.strip().lower()).strip(sep)
    if max_len:
        s = s[:max_len].strip(sep)
    return s or fallback
