"""ease-Desk Embedded Terminal Window & Console.

Supports full interactive PTY bash shell with ANSI color rendering,
scrolling, copy/paste, font scaling, and signal handling.
"""

from __future__ import annotations

import fcntl
import os
import pty
import re
import select
import struct
import subprocess
import sys
import termios
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GLib, Gtk, Pango

# Try importing Vte if installed on the host
HAVE_VTE = False
try:
    gi.require_version("Vte", "2.91")
    from gi.repository import Vte
    HAVE_VTE = True
except (ImportError, ValueError):
    HAVE_VTE = False

from shared.utilities.icons import get_icon_pixbuf


# Standard 16 ANSI colors for dark themes
ANSI_COLORS = {
    30: "#1e222b",  # Black
    31: "#e06c75",  # Red
    32: "#98c379",  # Green
    33: "#e5c07b",  # Yellow
    34: "#61afef",  # Blue
    35: "#c678dd",  # Magenta
    36: "#56b6c2",  # Cyan
    37: "#abb2bf",  # White
    90: "#5c6370",  # Bright Black (Gray)
    91: "#ff7b86",  # Bright Red
    92: "#b5e890",  # Bright Green
    93: "#ffd47e",  # Bright Yellow
    94: "#79c0ff",  # Bright Blue
    95: "#d2a8ff",  # Bright Magenta
    96: "#7ee787",  # Bright Cyan
    97: "#ffffff",  # Bright White
}

ANSI_BG_COLORS = {
    40: "#1e222b",
    41: "#e06c75",
    42: "#98c379",
    43: "#e5c07b",
    44: "#61afef",
    45: "#c678dd",
    46: "#56b6c2",
    47: "#abb2bf",
    100: "#5c6370",
    101: "#ff7b86",
    102: "#b5e890",
    103: "#ffd47e",
    104: "#79c0ff",
    105: "#d2a8ff",
    106: "#7ee787",
    107: "#ffffff",
}


class PtyTextViewTerminal(Gtk.Box):
    """Pure Python + GTK TextView Terminal Emulator with PTY and ANSI color support."""

    def __init__(self, initial_dir: Optional[str] = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.initial_dir = initial_dir or os.path.expanduser("~")
        if not os.path.isdir(self.initial_dir):
            self.initial_dir = os.path.expanduser("~")

        self.font_size = 11
        self.master_fd: Optional[int] = None
        self.child_pid: Optional[int] = None
        self.io_watch_id: Optional[int] = None

        self._build_ui()
        self._spawn_shell()

    def _build_ui(self) -> None:
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        self.scrolled.get_style_context().add_class("terminal-scroll")

        self.text_view = Gtk.TextView()
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.CHAR)
        self.text_view.set_cursor_visible(True)
        self.text_view.set_editable(False)  # We handle key events manually
        self.text_view.set_left_margin(10)
        self.text_view.set_right_margin(10)
        self.text_view.set_top_margin(10)
        self.text_view.set_bottom_margin(10)

        # Style dark background
        css = """
        textview text {
            background-color: #0d1117;
            color: #c9d1d9;
            font-family: 'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', monospace;
            font-size: 11pt;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode("utf-8"))
        self.text_view.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.buffer = self.text_view.get_buffer()
        self._setup_tags()

        self.text_view.connect("key-press-event", self._on_key_press)
        self.scrolled.add(self.text_view)
        self.pack_start(self.scrolled, True, True, 0)

    def _setup_tags(self) -> None:
        for code, hex_col in ANSI_COLORS.items():
            self.buffer.create_tag(f"fg_{code}", foreground=hex_col)
        for code, hex_col in ANSI_BG_COLORS.items():
            self.buffer.create_tag(f"bg_{code}", background=hex_col)
        self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.buffer.create_tag("dim", weight=Pango.Weight.LIGHT)
        self.buffer.create_tag("underline", underline=Pango.Underline.SINGLE)

    def _spawn_shell(self) -> None:
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd

        shell = os.environ.get("SHELL", "/bin/bash")
        if not os.path.exists(shell):
            shell = "/bin/sh"

        env = dict(os.environ)
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        try:
            p = subprocess.Popen(
                [shell, "-l"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=self.initial_dir,
                env=env,
                preexec_fn=os.setsid,
                close_fds=True,
            )
            os.close(slave_fd)
            self.child_pid = p.pid

            # Make master_fd non-blocking
            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Watch master_fd for output
            self.io_watch_id = GLib.io_add_watch(
                master_fd,
                GLib.PRIORITY_DEFAULT,
                GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
                self._on_pty_data,
            )
        except Exception as exc:
            self._append_text(f"\n[Error launching shell: {exc}]\n")

    def _on_pty_data(self, fd: int, condition: GLib.IOCondition) -> bool:
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            self._append_text("\n[Session Terminated]\n")
            return False

        try:
            data = os.read(fd, 8192)
            if not data:
                return False
            text = data.decode("utf-8", errors="replace")
            self._parse_and_append_ansi(text)
            return True
        except (OSError, BlockingIOError):
            return True

    def _parse_and_append_ansi(self, text: str) -> None:
        """Parse standard ANSI escape sequences and insert text with matching GtkTextTags."""
        # 1. Strip OSC sequences (e.g. \x1b]0;title\x07 or \x1b]0;title\x1b\)
        clean_text = re.sub(r"\x1b\][0-9]+;[^\x07\x1b]*(\x07|\x1b\\)", "", text)

        # 2. Strip DEC private mode sequences (e.g. \x1b[?1h, \x1b[?2004h, \x1b[?25h, etc.)
        clean_text = re.sub(r"\x1b\[\?[0-9;]*[a-zA-Z]", "", clean_text)

        # 3. Strip other non-color escape codes (cursor moves, keypad modes, charset designations)
        clean_text = re.sub(r"\x1b\[[0-9;]*[A-LN-Za-ln-zHfJKsu]", "", clean_text)
        clean_text = re.sub(r"\x1b[=><\(\)][0-9A-Za-z]?", "", clean_text)

        # 4. Strip bells, backspace artifacts
        clean_text = clean_text.replace("\x07", "").replace("\x08", "")

        ansi_regex = re.compile(r"\x1b\[([0-9;]*)m")
        tokens = ansi_regex.split(clean_text)
        current_tags: list[str] = []

        for i, token in enumerate(tokens):
            if i % 2 == 1:
                # ANSI code chunk (e.g., '0;32;1')
                if not token or token == "0":
                    current_tags = []
                else:
                    codes = [int(c) for c in token.split(";") if c.isdigit()]
                    for c in codes:
                        if c == 0:
                            current_tags = []
                        elif c == 1:
                            current_tags.append("bold")
                        elif c == 2:
                            current_tags.append("dim")
                        elif c == 4:
                            current_tags.append("underline")
                        elif c in ANSI_COLORS:
                            current_tags = [t for t in current_tags if not t.startswith("fg_")]
                            current_tags.append(f"fg_{c}")
                        elif c in ANSI_BG_COLORS:
                            current_tags = [t for t in current_tags if not t.startswith("bg_")]
                            current_tags.append(f"bg_{c}")
            else:
                if token:
                    self._append_text_with_tags(token, current_tags)

        self._scroll_to_bottom()

    def _append_text(self, text: str) -> None:
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert(end_iter, text)
        self._scroll_to_bottom()

    def _append_text_with_tags(self, text: str, tag_names: list[str]) -> None:
        end_iter = self.buffer.get_end_iter()
        tags = [self.buffer.get_tag_table().lookup(tn) for tn in tag_names]
        valid_tags = [t for t in tags if t is not None]
        if valid_tags:
            self.buffer.insert_with_tags(end_iter, text, *valid_tags)
        else:
            self.buffer.insert(end_iter, text)

    def _scroll_to_bottom(self) -> None:
        adj = self.scrolled.get_vadjustment()
        if adj:
            GLib.idle_add(lambda: adj.set_value(adj.get_upper() - adj.get_page_size()))

    def _on_key_press(self, widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        if self.master_fd is None:
            return False

        keyval = event.keyval
        state = event.state

        # Ctrl+Shift+C: Copy
        if (state & Gdk.ModifierType.CONTROL_MASK) and (state & Gdk.ModifierType.SHIFT_MASK) and keyval in (Gdk.KEY_C, Gdk.KEY_c):
            self.copy_selection()
            return True

        # Ctrl+Shift+V: Paste
        if (state & Gdk.ModifierType.CONTROL_MASK) and (state & Gdk.ModifierType.SHIFT_MASK) and keyval in (Gdk.KEY_V, Gdk.KEY_v):
            self.paste_clipboard()
            return True

        # Map special keys to VT100 / ANSI escape sequences
        key_map = {
            Gdk.KEY_Return: b"\r",
            Gdk.KEY_KP_Enter: b"\r",
            Gdk.KEY_BackSpace: b"\x7f",
            Gdk.KEY_Tab: b"\t",
            Gdk.KEY_Escape: b"\x1b",
            Gdk.KEY_Up: b"\x1b[A",
            Gdk.KEY_Down: b"\x1b[B",
            Gdk.KEY_Right: b"\x1b[C",
            Gdk.KEY_Left: b"\x1b[D",
            Gdk.KEY_Home: b"\x1b[H",
            Gdk.KEY_End: b"\x1b[F",
            Gdk.KEY_Page_Up: b"\x1b[5~",
            Gdk.KEY_Page_Down: b"\x1b[6~",
            Gdk.KEY_Delete: b"\x1b[3~",
        }

        if keyval in key_map:
            os.write(self.master_fd, key_map[keyval])
            return True

        # Control key combos (Ctrl+C, Ctrl+D, Ctrl+Z, etc.)
        if state & Gdk.ModifierType.CONTROL_MASK:
            if 0x40 <= keyval <= 0x5F:
                os.write(self.master_fd, bytes([keyval - 0x40]))
                return True
            elif 0x61 <= keyval <= 0x7A:
                os.write(self.master_fd, bytes([keyval - 0x60]))
                return True

        # Normal characters
        char = chr(Gdk.keyval_to_unicode(keyval))
        if char and char != "\x00":
            os.write(self.master_fd, char.encode("utf-8"))
            return True

        return False

    def copy_selection(self) -> None:
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            text = self.buffer.get_text(start, end, True)
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)

    def paste_clipboard(self) -> None:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text()
        if text and self.master_fd:
            os.write(self.master_fd, text.encode("utf-8"))

    def clear(self) -> None:
        self.buffer.set_text("")
        if self.master_fd:
            os.write(self.master_fd, b"\x0c")  # Form Feed / Clear

    def close(self) -> None:
        if self.io_watch_id:
            GLib.source_remove(self.io_watch_id)
            self.io_watch_id = None
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        if self.child_pid:
            try:
                import signal
                os.kill(self.child_pid, signal.SIGTERM)
            except OSError:
                pass


class TerminalWindow(Gtk.Window):
    """Full-featured standalone Terminal Window for ease-Desk."""

    def __init__(self, initial_dir: Optional[str] = None):
        super().__init__(title="Terminal — ease-Desk")
        self.set_default_size(780, 480)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Set window icon
        icon_pb = get_icon_pixbuf("terminal", size=48)
        self.set_icon(icon_pb)

        self.initial_dir = initial_dir or os.path.expanduser("~")
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header Bar / Action Controls
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Terminal Console")
        header.set_subtitle(self.initial_dir)
        self.set_titlebar(header)

        # Clear Button
        clear_btn = Gtk.Button(label="Clear")
        clear_btn.connect("clicked", lambda *_: self.term.clear() if hasattr(self.term, "clear") else None)
        header.pack_start(clear_btn)

        # Paste Button
        paste_btn = Gtk.Button(label="Paste")
        paste_btn.connect("clicked", lambda *_: self.term.paste_clipboard() if hasattr(self.term, "paste_clipboard") else None)
        header.pack_start(paste_btn)

        # Create Terminal Backend
        self.term = PtyTextViewTerminal(initial_dir=self.initial_dir)
        vbox.pack_start(self.term, True, True, 0)

        self.add(vbox)
        self.connect("delete-event", self._on_close)

    def _on_close(self, *args) -> bool:
        if hasattr(self, "term") and hasattr(self.term, "close"):
            self.term.close()
        return False
