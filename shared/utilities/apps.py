"""Lightweight application registry for the ease-Desk launcher."""

from __future__ import annotations

import configparser
import os
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppDefinition:
    """Launchable application metadata read from a desktop entry."""

    app_id: str
    name: str
    exec_command: tuple[str, ...]
    icon: str = "application-x-executable"
    comment: str = ""
    source: str = ""

    def matches(self, query: str) -> bool:
        query = query.casefold().strip()
        haystack = f"{self.name} {self.app_id} {self.comment}".casefold()
        return not query or query in haystack


def _desktop_dirs() -> list[Path]:
    dirs = [Path.home() / ".local/share/applications"]
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        dirs.insert(0, Path(data_home) / "applications")
    dirs.extend(Path(path) / "applications" for path in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"))
    return list(dict.fromkeys(dirs))


def _expand_exec(value: str) -> tuple[str, ...]:
    """Remove desktop-entry field codes while preserving quoted arguments."""
    tokens = shlex.split(value, posix=True)
    return tuple(token for token in tokens if not (len(token) == 2 and token.startswith("%")))


def _parse_entry(path: Path) -> AppDefinition | None:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        with path.open(encoding="utf-8") as stream:
            parser.read_file(stream)
        entry = parser["Desktop Entry"]
    except (OSError, KeyError, configparser.Error):
        return None

    if entry.get("Type", "Application") != "Application":
        return None
    if entry.get("Hidden", "false").casefold() == "true" or entry.get("NoDisplay", "false").casefold() == "true":
        return None
    command = _expand_exec(entry.get("Exec", ""))
    name = entry.get("Name", "").strip()
    if not name or not command:
        return None
    try_exec = entry.get("TryExec", "").strip()
    if try_exec and shutil.which(try_exec) is None:
        return None
    return AppDefinition(
        app_id=path.stem,
        name=name,
        exec_command=command,
        icon=entry.get("Icon", "application-x-executable"),
        comment=entry.get("Comment", ""),
        source=str(path),
    )


def discover_applications(directories: list[Path] | None = None) -> list[AppDefinition]:
    """Discover visible applications, with user entries overriding system entries."""
    found: dict[str, AppDefinition] = {}
    for directory in directories or _desktop_dirs():
        if not directory.is_dir():
            continue
        try:
            paths = sorted(directory.glob("*.desktop"))
        except OSError:
            continue
        for path in paths:
            app = _parse_entry(path)
            if app is not None:
                found[app.app_id] = app
    return sorted(found.values(), key=lambda app: app.name.casefold())


def project_applications() -> list[AppDefinition]:
    """Return ease-Desk applications available even without installed desktop files."""
    return [
        AppDefinition("ease-desk-files", "Files", ("python3", "-m", "file_manager.app"), "folder"),
        AppDefinition("ease-desk-terminal", "Terminal", ("python3", "-m", "desktop.terminal.app"), "terminal"),
        AppDefinition("ease-desk-task-manager", "Task Manager", ("python3", "-m", "desktop.task_manager.app"), "task_manager"),
        AppDefinition("ease-desk-settings", "Settings", ("python3", "-m", "desktop.settings.app"), "settings"),
    ]


def launcher_applications() -> list[AppDefinition]:
    """Return project apps first, followed by installed desktop applications."""
    apps = {app.app_id: app for app in discover_applications()}
    apps.update({app.app_id: app for app in project_applications()})
    return sorted(apps.values(), key=lambda app: app.name.casefold())
