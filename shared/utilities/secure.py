"""Security helpers shared across Charlie Desktop components.

The goal of this module is to keep file operations safe:

* no path traversal through user-supplied names
* no arbitrary command execution from file names
* no operation on dangerous top-level paths
* permission-aware behaviour (errors are surfaced to the UI)
"""

from __future__ import annotations

import os


class SecurityError(Exception):
    """Raised when a potentially unsafe operation is requested."""


# Top-level paths that must never be deleted/renamed even by mistake.
PROTECTED_PATHS = {"/", os.path.expanduser("~")}


def ensure_within(base: str, target: str) -> str:
    """Return the realpath of `target`, guaranteeing it stays inside `base`.

    Raises SecurityError if `target` (after symlink resolution) escapes `base`.
    """
    base_real = os.path.realpath(base)
    target_real = os.path.realpath(target)
    if base_real == target_real:
        return target_real
    try:
        common = os.path.commonpath([base_real, target_real])
    except ValueError:
        common = ""
    if common != base_real:
        raise SecurityError(f"Refusing path that escapes '{base_real}': {target}")
    return target_real


def safe_child(parent: str, name: str) -> str:
    """Validate a single user-supplied component and join it under `parent`.

    A safe component may not contain a path separator, NUL byte, or traverse
    to a parent directory.  This is the front line against path traversal.
    """
    if not name or name.strip() == "":
        raise SecurityError("Empty name")
    if name in (".", ".."):
        raise SecurityError("'.' and '..' are not valid names")
    if any(sep in name for sep in (os.sep, os.altsep, "\\", "\x00") if sep):
        raise SecurityError("Path separators and NUL are not allowed in a name")
    return os.path.join(parent, name)


def assert_destructible(path: str) -> None:
    """Refuse to delete protected top-level paths."""
    real = os.path.realpath(path)
    for protected in PROTECTED_PATHS:
        if real == os.path.realpath(protected):
            raise SecurityError(f"'{path}' is protected and cannot be deleted")


def can_read(path: str) -> bool:
    return os.access(path, os.R_OK)


def can_write(path: str) -> bool:
    return os.access(path, os.W_OK)


def check_writable_parent(path: str) -> None:
    """Raise PermissionError early if the parent directory cannot accept writes."""
    parent = os.path.dirname(path) or "."
    if not os.access(parent, os.W_OK | os.X_OK):
        raise PermissionError(f"No write permission in '{parent}'")
