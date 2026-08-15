"""ease-Desk Desktop Shell — Wayland Edition (using gtk-layer-shell)."""

import os
import sys
import json
import subprocess
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, GtkLayerShell
from shared.utilities.icons import get_icon_pixbuf
from shared.utilities import sysinfo

class TopBar(Gtk.Window):
    def __init__(self):
        super().__init__()
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 0)
        GtkLayerShell.auto_exclusive_zone_enable(self)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.get_style_context().add_class("top-bar")
        bar.set_size_request(-1, 32)
        
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        right_box.set_margin_end(16)
        
        wifi_img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf("network-wireless", size=16))
        bat_img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf("battery-good", size=16))
        self.clock_time_label = Gtk.Label(label="Clock")
        
        right_box.pack_start(wifi_img, False, False, 0)
        right_box.pack_start(bat_img, False, False, 0)
        right_box.pack_start(self.clock_time_label, False, False, 0)
        
        bar.pack_end(right_box, False, False, 0)
        self.add(bar)

class LeftDock(Gtk.Window):
    def __init__(self):
        super().__init__()
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.auto_exclusive_zone_enable(self)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        
        dock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        dock.get_style_context().add_class("left-dock")
        dock.set_margin_start(16)
        dock.set_valign(Gtk.Align.CENTER)
        
        file_btn = Gtk.Button()
        file_btn.add(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("system-file-manager", size=24)))
        file_btn.get_style_context().add_class("left-dock-btn")
        file_btn.connect("clicked", lambda *_: subprocess.Popen(["python3", "-m", "file_manager.app"]))
        
        pwr_btn = Gtk.Button()
        pwr_btn.add(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("system-shutdown", size=24)))
        pwr_btn.get_style_context().add_class("left-dock-btn")
        pwr_btn.connect("clicked", lambda *_: sys.exit(0))
        
        dock.pack_start(file_btn, False, False, 0)
        dock.pack_start(pwr_btn, False, False, 0)
        self.add(dock)

class DesktopIcons(Gtk.Window):
    def __init__(self):
        super().__init__()
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BACKGROUND)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)

        self.fixed = Gtk.Fixed()
        self.fixed.set_margin_start(16)
        self.fixed.set_margin_top(16)
        
        # Add basic icons
        self._add_icon("This PC", "computer", 0, 0, lambda: subprocess.Popen(["python3", "-m", "file_manager.app"]))
        self._add_icon("Terminal", "terminal", 0, 100, lambda: subprocess.Popen(["xterm"]))
        
        self.add(self.fixed)

    def _add_icon(self, name, icon_name, x, y, callback):
        btn = Gtk.Button()
        btn.get_style_context().add_class("icon-btn")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf(icon_name, size=48))
        lbl = Gtk.Label(label=name)
        box.pack_start(img, False, False, 0)
        box.pack_start(lbl, False, False, 0)
        btn.add(box)
        btn.connect("clicked", lambda *_: callback())
        self.fixed.put(btn, x, y)

def main():
    provider = Gtk.CssProvider()
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme.css")
    if os.path.exists(css_path):
        provider.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # Launch Wayland Layer Shell components
    top = TopBar()
    dock = LeftDock()
    icons = DesktopIcons()
    
    top.show_all()
    dock.show_all()
    icons.show_all()

    Gtk.main()

if __name__ == "__main__":
    sys.exit(main())
