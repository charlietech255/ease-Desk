"""CLI entrypoint for ease-Desk Terminal."""

from __future__ import annotations

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from desktop.terminal.terminal import TerminalWindow


def main(argv: list[str] | None = None) -> int:
 args = argv if argv is not None else sys.argv[1:]
 initial_dir = args[0] if args else os.path.expanduser("~")

 win = TerminalWindow(initial_dir=initial_dir)
 win.connect("destroy", Gtk.main_quit)
 win.show_all()
 Gtk.main()
 return 0


if __name__ == "__main__":
 sys.exit(main())
