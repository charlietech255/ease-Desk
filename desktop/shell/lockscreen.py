"""ease-Desk — Secure Screen Locker."""

from __future__ import annotations

import datetime
import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

from shared.config import preferences

class LockScreen(Gtk.Window):
    _CSS = b"""
        .lock-bg {
            background-color: rgba(11, 14, 20, 0.85);
            backdrop-filter: blur(20px);
        }
        .lock-clock {
            color: white;
            font-size: 72px;
            font-weight: 200;
            font-family: "Inter", "Ubuntu", sans-serif;
            text-shadow: 0 4px 24px rgba(0, 0, 0, 0.5);
        }
        .lock-date {
            color: rgba(255, 255, 255, 0.8);
            font-size: 24px;
            font-weight: 400;
            margin-bottom: 48px;
        }
        .lock-entry {
            background: rgba(255, 255, 255, 0.1);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 18px;
            caret-color: white;
        }
        .lock-entry:focus {
            border-color: rgba(255, 255, 255, 0.5);
            background: rgba(255, 255, 255, 0.15);
        }
        .lock-error {
            color: #ff6b6b;
            font-size: 14px;
            margin-top: 12px;
        }
    """

    def __init__(self, parent_shell):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.shell = parent_shell
        self.set_decorated(False)
        self.set_title("ease-Desk Locker")
        
        # Determine LayerShell usage (Wayland)
        try:
            is_wayland = "wayland" in os.environ.get("WAYLAND_DISPLAY", "") or "wayland" in os.environ.get("XDG_SESSION_TYPE", "").lower()
            self.use_layer_shell = is_wayland and GtkLayerShell.is_supported()
        except:
            self.use_layer_shell = False

        if self.use_layer_shell:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_exclusive_zone(self, -1)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
                GtkLayerShell.set_anchor(self, edge, True)
        else:
            self.fullscreen()
            self.set_keep_above(True)

        self.get_style_context().add_class("lock-bg")

        # Load CSS
        provider = Gtk.CssProvider()
        provider.load_from_data(self._CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Build UI
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_valign(Gtk.Align.CENTER)
        vbox.set_halign(Gtk.Align.CENTER)
        self.add(vbox)

        self.clock_lbl = Gtk.Label()
        self.clock_lbl.get_style_context().add_class("lock-clock")
        vbox.pack_start(self.clock_lbl, False, False, 0)

        self.date_lbl = Gtk.Label()
        self.date_lbl.get_style_context().add_class("lock-date")
        vbox.pack_start(self.date_lbl, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.set_visibility(False)
        self.entry.set_placeholder_text("Enter Password...")
        self.entry.set_size_request(300, -1)
        self.entry.get_style_context().add_class("lock-entry")
        self.entry.connect("activate", self._on_submit)
        vbox.pack_start(self.entry, False, False, 0)

        self.error_lbl = Gtk.Label(label="")
        self.error_lbl.get_style_context().add_class("lock-error")
        vbox.pack_start(self.error_lbl, False, False, 0)

        # Trap focus and delete
        self.connect("delete-event", lambda *_: True)
        self.connect("key-press-event", self._on_key_press)
        self.entry.connect("focus-out-event", lambda *_: self.entry.grab_focus())

        self._update_clock()
        GLib.timeout_add_seconds(1, self._update_clock)

    def _update_clock(self):
        now = datetime.datetime.now()
        fmt = "%H:%M" if preferences.get("Personalization", "clock_format", "24h") == "24h" else "%I:%M %p"
        self.clock_lbl.set_text(now.strftime(fmt))
        self.date_lbl.set_text(now.strftime("%A, %B %d"))
        return True

    def _on_key_press(self, widget, event):
        # Block Alt-Tab, Super, etc if possible
        if event.keyval in (Gdk.KEY_Escape, Gdk.KEY_Super_L, Gdk.KEY_Super_R):
            return True
        return False

    def _on_submit(self, entry):
        pwd = entry.get_text()
        entry.set_text("")
        
        # Verify against ~/.vnc/plainpass
        expected = ""
        pass_file = os.path.expanduser("~/.vnc/plainpass")
        if os.path.exists(pass_file):
            try:
                with open(pass_file, "r") as f:
                    expected = f.read().strip()
            except Exception:
                pass
                
        if expected == "":
            # If no password file exists, unlock automatically (fallback)
            self.unlock()
            return
            
        if pwd == expected:
            self.unlock()
        else:
            self.error_lbl.set_text("Incorrect password.")
            
    def lock(self):
        self.error_lbl.set_text("")
        self.entry.set_text("")
        self.show_all()
        self.present()
        self.entry.grab_focus()
        
    def unlock(self):
        self.hide()
