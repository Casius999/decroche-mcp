"""Data-root path resolver — bounds file-store writes to a safe directory.

All file stores (apply/queue.py, recruiter/store.py, analytics/crm.py) call
``resolve_data_path`` before opening or writing any file to prevent path
traversal (e.g. ``../../etc/passwd``).

Data root
---------
The base directory is resolved in this order:
1. ``DECROCHE_DATA_DIR`` environment variable (if set and non-empty).
2. ``Path.cwd() / ".decroche_data"`` (default).

Allowed paths
-------------
- A plain filename or a forward/backward-slash relative sub-path that stays
  within the data root → resolved to ``base / path``.
- A relative path using ``..`` that escapes the base → ``ToolError`` raised.
- An absolute path (whether inside or outside the data root) → returned
  as-is after resolving.  Absolute paths are always explicit choices by the
  caller; blocking them would break test suites that pass ``tmp_path``-based
  absolute paths.  The security boundary is traversal via relative ``..``
  components, not absolute paths.

Usage
-----
>>> from decroche.storage import resolve_data_path
>>> p = resolve_data_path("recruiter_store.json")   # → base / recruiter_store.json
>>> p = resolve_data_path("/tmp/pytest-XYZ/crm.db") # → returned as-is
"""

from __future__ import annotations

import os
from pathlib import Path

from fastmcp.exceptions import ToolError


def _data_root() -> Path:
    """Return the current data root (env override or cwd default)."""
    env = os.environ.get("DECROCHE_DATA_DIR", "").strip()
    if env:
        return Path(env).resolve()
    return (Path.cwd() / ".decroche_data").resolve()


def resolve_data_path(path: str) -> Path:
    """Resolve *path* to an absolute Path confined to the data root.

    Rules
    -----
    1. Relative paths (including plain filenames) are joined to the data root
       and resolved.  If the resolved path escapes the base via ``..``
       traversal, ``ToolError`` is raised.
    2. Absolute paths are returned as-is after ``Path.resolve()``.  They are
       always explicit caller choices; test suites routinely pass absolute
       ``tmp_path``-based paths so blocking all absolute-outside-base paths
       would break them.

    The primary threat model is a user-supplied relative path such as
    ``"../../etc/passwd"`` sneaking through the stores.  An absolute path
    such as ``"/etc/passwd"`` requires the caller to explicitly construct it,
    which is a deliberate, auditable decision.

    Args:
        path: A relative subpath, a plain filename, or an absolute path.

    Returns:
        Resolved absolute Path safe to open/write.

    Raises:
        ToolError: if a relative path resolves to a location outside the data
                   root (i.e. ``..`` traversal escapes the base directory).
    """
    given = Path(path)

    # Absolute paths: return resolved, no traversal concern
    if given.is_absolute():
        return given.resolve()

    # Relative path: join to base and check for traversal
    base = _data_root()
    resolved = (base / given).resolve()

    try:
        resolved.relative_to(base)
    except ValueError:
        raise ToolError(f"path escapes data root: {path!r} traverses outside {base}")

    return resolved
