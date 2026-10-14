"""Dependency-free `.env` reader — taken as-is from dialogue-lens.

Source: `dialogue_lens/sources/common.py::load_env`. Deliberately *not*
python-dotenv: the merge/worklog stage has to run under a bare `python3` with no
site-packages at all, and the file format in play is only ever `KEY=VALUE`.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["load_env"]


def load_env(
    path: str | Path,
    defaults: dict[str, str] | None = None,
    *,
    override_os_environ: bool = False,
) -> dict[str, str]:
    """Parse a simple ``KEY=VALUE`` .env; return ``defaults`` merged with it.

    Blank lines, ``#`` comments and lines without ``=`` are ignored. A missing
    file is **not** an error — you get ``defaults`` back, which is what makes
    the config path optional for every caller.

    Values are returned, never exported: nothing touches `os.environ` unless
    ``override_os_environ=True``, in which case the parsed pairs are also set
    there (for libraries that only read the process environment).
    """
    env: dict[str, str] = dict(defaults or {})
    p = Path(path)
    if not p.exists():
        return env
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    if override_os_environ:
        os.environ.update(env)
    return env
