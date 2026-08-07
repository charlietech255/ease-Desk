"""Core filesystem operations for Charlie File Manager.

This module contains no GTK code on purpose: it is the "core" that can later
be reimplemented in Rust (or exposed over a remote protocol) without touching
the UI layer.  Every operation is permission-aware and traversal-safe.
"""

from __future__ import annotations

import datetime
import os
import shutil
import stat
from dataclasses import dataclass

from shared.utilities.secure import SecurityError, assert_destructible, safe_child

MAX_TEXT_BYTES = 1024 * 1024  # refuse to slurp files larger than 1 MiB
COPY_SUFFIX = " (copy)"


class FileOpError(Exception):
    """User-facing error for a failed file operation."""


class PermissionDeniedError(FileOpError):
    """A filesystem permission denied the operation."""


@dataclass
class Entry:
    name: str
    path: str
    is_dir: bool
    size: int
    mtime: float
    mode: int
    uid: int
    gid: int
    is_link: bool = False
    link_target: str | None = None


def _translate(action: str, path: str, exc: BaseException) -> FileOpError:
    if isinstance(exc, PermissionError):
        return PermissionDeniedError(f"Permission denied: cannot {action} '{path}'")
    if isinstance(exc, SecurityError):
        return FileOpError(f"Unsafe operation rejected: {exc}")
    if isinstance(exc, FileOpError):
        return exc
    return FileOpError(f"Could not {action} '{path}': {exc}")


def human_size(num: float) -> str:
    if num < 0:
        num = 0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def list_dir(directory: str) -> list[Entry]:
    directory = os.path.realpath(directory)
    if not os.path.isdir(directory):
        raise FileOpError(f"Not a directory: {directory}")
    try:
        names = os.listdir(directory)
    except PermissionError as exc:
        raise PermissionDeniedError(f"Permission denied: cannot read directory '{directory}'") from exc
    except OSError as exc:
        raise _translate("list", directory, exc) from exc

    entries: list[Entry] = []
    for name in sorted(names, key=lambda n: n.lower()):
        path = os.path.join(directory, name)
        try:
            st = os.stat(path)
        except OSError:
            # Broken symlink or vanished entry: still list it with metadata.
            try:
                link = os.readlink(path)
            except OSError:
                continue
            entries.append(Entry(name, path, False, 0, 0.0, 0, 0, 0, True, link))
            continue
        is_link = os.path.islink(path)
        link_target = os.readlink(path) if is_link else None
        entries.append(
            Entry(
                name=name,
                path=path,
                is_dir=stat.S_ISDIR(st.st_mode),
                size=st.st_size,
                mtime=st.st_mtime,
                mode=st.st_mode,
                uid=st.st_uid,
                gid=st.st_gid,
                is_link=is_link,
                link_target=link_target,
            )
        )
    return entries


def make_directory(parent: str, name: str) -> str:
    target = safe_child(parent, name)
    try:
        os.mkdir(target)
    except FileExistsError as exc:
        raise FileOpError(f"A file named '{name}' already exists") from exc
    except OSError as exc:
        raise _translate("create", target, exc) from exc
    return target


def rename(path: str, new_name: str) -> str:
    parent = os.path.dirname(os.path.realpath(path))
    target = safe_child(parent, new_name)
    if os.path.realpath(path) == target:
        return target
    if os.path.exists(target):
        raise FileOpError(f"A file named '{new_name}' already exists")
    try:
        os.rename(path, target)
    except OSError as exc:
        raise _translate("rename", path, exc) from exc
    return target


def delete(path: str, recursive: bool = True) -> None:
    assert_destructible(path)
    try:
        if os.path.islink(path):
            os.unlink(path)
        elif os.path.isdir(path):
            if recursive:
                shutil.rmtree(path)
            else:
                os.rmdir(path)
        else:
            os.remove(path)
    except OSError as exc:
        raise _translate("delete", path, exc) from exc


def _unique_target(dest_dir: str, name: str) -> str:
    target = safe_child(dest_dir, name)
    if not os.path.exists(target):
        return target
    root, ext = os.path.splitext(name)
    i = 1
    while True:
        candidate = safe_child(dest_dir, f"{root}{COPY_SUFFIX} {i}{ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1


def copy(path: str, dest_dir: str, new_name: str | None = None) -> str:
    name = new_name or os.path.basename(path.rstrip(os.sep)) or "item"
    target = _unique_target(dest_dir, name)
    try:
        if os.path.isdir(path):
            shutil.copytree(path, target, symlinks=True)
        else:
            shutil.copy2(path, target)
    except OSError as exc:
        raise _translate("copy", path, exc) from exc
    return target


def move(path: str, dest_dir: str, new_name: str | None = None) -> str:
    name = new_name or os.path.basename(path.rstrip(os.sep)) or "item"
    target = _unique_target(dest_dir, name)
    try:
        shutil.move(path, target)
    except OSError as exc:
        raise _translate("move", path, exc) from exc
    return target


def read_text(path: str, max_bytes: int = MAX_TEXT_BYTES) -> tuple[str, bool]:
    """Read a text file.  Returns (content, truncated_flag).

    Refuses binary files (NUL byte in the first chunk).
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            data = f.read(min(size, max_bytes))
    except OSError as exc:
        raise _translate("read", path, exc) from exc
    if b"\x00" in data[:4096]:
        raise FileOpError(f"'{path}' appears to be a binary file")
    try:
        return (data.decode("utf-8", errors="replace"), size > max_bytes)
    except UnicodeDecodeError:
        return (data.decode("latin-1", errors="replace"), size > max_bytes)


def _mode_string(mode: int) -> str:
    perms = stat.filemode(mode)
    return perms[1:] if perms.startswith("?") else perms


def _uid_name(uid: int) -> str:
    import pwd

    try:
        return pwd.getpwuid(uid).pw_name
    except (KeyError, ImportError):
        return str(uid)


def _gid_name(gid: int) -> str:
    import grp

    try:
        return grp.getgrgid(gid).gr_name
    except (KeyError, ImportError):
        return str(gid)


def properties(path: str) -> dict:
    """Return a human-readable property dict for the Properties dialog."""
    real = os.path.realpath(path)
    try:
        st = os.stat(real)
    except OSError as exc:
        raise _translate("inspect", path, exc) from exc
    is_dir = stat.S_ISDIR(st.st_mode)
    mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "name": os.path.basename(real) or real,
        "path": real,
        "type": "Folder" if is_dir else "File",
        "size": human_size(st.st_size),
        "size_bytes": st.st_size,
        "permissions": _mode_string(st.st_mode),
        "mode": oct(st.st_mode & 0o7777),
        "owner": _uid_name(st.st_uid),
        "group": _gid_name(st.st_gid),
        "modified": mtime,
        "is_link": os.path.islink(path),
        "link_target": os.readlink(path) if os.path.islink(path) else None,
    }


def is_text_like(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return False
    return b"\x00" not in head
