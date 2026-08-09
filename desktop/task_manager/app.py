"""CLI entrypoint for ease-Desk Task Manager."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from desktop.task_manager.task_manager import TaskManagerWindow


def main(argv: list[str] | None = None) -> int:
    settings = Gtk.Settings.get_default()
    if settings:
        settings.set_property("gtk-application-prefer-dark-theme", True)
        
    win = TaskManagerWindow()
 win.connect("destroy", Gtk.main_quit)
 win.show_all()
 Gtk.main()
 return 0


if __name__ == "__main__":
 sys.exit(main())
