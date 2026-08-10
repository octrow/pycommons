"""Load-merge-save for JSON files used as a poor man's database.

Extracted from dental-parser, which writes the same three steps twice
(`scraper_2gis.py` re-reads `clinics_base.json` to preserve manual edits before
overwriting it; `processor_ai.py` reads it again to enrich it).

Two bugs the originals actually had, fixed here rather than copied:

* the write was **not atomic** — a crash mid-`json.dump` truncated the only copy
  of a scrape that took an hour of browser driving to produce;
* the read swallowed *all* exceptions (`except: pass`), so a corrupt file read as
  "no data" and the next save silently replaced it with a fresh, emptier one.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = ["load_or_default", "merge_keep_nonempty", "save_atomic"]


def load_or_default(path: str | Path, default: Any = None) -> Any:
    """Read JSON from ``path``; return ``default`` if the file does not exist.

    A file that exists but is **not** valid JSON raises
    `json.JSONDecodeError` — on purpose. dental-parser's `except: pass` turned
    corruption into silent data loss on the next save; a loud failure lets you
    look at the file.
    """
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_atomic(path: str | Path, data: Any, *, indent: int | None = 2) -> Path:
    """Write ``data`` as JSON so readers see either the old file or the new one.

    Serialise to a temp file **in the destination directory** (so `os.replace`
    stays on one filesystem and is therefore atomic), fsync, then rename over
    the target. Never leaves a partial file behind: if serialisation raises, the
    temp file is removed and the original is untouched.

    ``ensure_ascii=False`` always — the data is Russian/Kazakh and escaped
    JSON is unreadable in a diff.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return p


def merge_keep_nonempty(
    old: Mapping[str, Any],
    new: Mapping[str, Any],
    *,
    always: Iterable[str] = (),
) -> dict[str, Any]:
    """Fill blanks in ``old`` from ``new``; never overwrite non-empty with empty.

    The rule dental-parser needed: a re-scrape must not wipe a field a human
    filled in by hand, and must not wipe a field this run simply failed to
    extract. So a value from ``new`` lands only when it is truthy **and** the
    ``old`` value is falsy.

    ``always`` names the fields that are refreshed whenever ``new`` has a truthy
    value regardless — the scraper's "core stats" (`rating`, `review_count`),
    which are facts about the source, not hand-curated data.

    Returns a new dict; neither input is mutated (the original merged in place).
    """
    merged = dict(old)
    always = set(always)
    for k, v in new.items():
        if not v:
            continue
        if k in always or not merged.get(k):
            merged[k] = v
    return merged
