"""CLI entrypoint for ease-Desk Media Player."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from desktop.media_player.player import MediaPlayerWindow


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    win = MediaPlayerWindow(files=args)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
