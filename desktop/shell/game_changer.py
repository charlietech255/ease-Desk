import os
import time
import subprocess
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from shared.utilities import sysinfo

class SpotlightWindow(Gtk.Window):
    def __init__(self, parent_shell):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.shell = parent_shell
        self.set_decorated(False)
        self.set_transient_for(parent_shell.window)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(600, 60)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_app_paintable(True)
        
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        self.get_style_context().add_class("spotlight-window")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("🔍 Search apps, files, or run commands...")
        self.entry.get_style_context().add_class("spotlight-entry")
        self.entry.set_has_frame(False)
        self.entry.set_size_request(-1, 60)
        self.entry.connect("activate", self._on_activate)
        self.entry.connect("key-press-event", self._on_key_press)
        
        vbox.pack_start(self.entry, True, True, 0)
        self.add(vbox)

        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            .spotlight-window {
                background-color: rgba(13, 17, 23, 0.40);
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 16px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.6);
            }
            .spotlight-entry {
                background: transparent;
                border: none;
                box-shadow: none;
                color: #f8fafc;
                font-size: 24px;
                font-weight: 300;
                padding: 12px 24px;
                caret-color: #38bdf8;
            }
            .spotlight-entry:focus {
                border: none;
                box-shadow: none;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        # Hide it initially!
        self.hide()

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def _on_activate(self, entry):
        query = entry.get_text().strip()
        if query:
            if query.lower() in ("terminal", "term", "bash"):
                self.shell._launch_path("app://terminal")
            elif query.lower() in ("browser", "web", "chrome", "firefox"):
                self.shell._launch_path("app://browser")
            elif query.lower() in ("task manager", "top", "htop"):
                self.shell._launch_path("app://task_manager")
            else:
                subprocess.Popen(["bash", "-c", query])
        entry.set_text("")
        self.hide()

    def toggle(self):
        if self.is_visible():
            self.hide()
        else:
            self.show_all()
            self.present()
            self.entry.grab_focus()

class DashboardPanel(Gtk.Revealer):
    def __init__(self, parent_shell):
        super().__init__()
        self.shell = parent_shell
        self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.set_transition_duration(300)
        self.set_halign(Gtk.Align.END)
        self.set_valign(Gtk.Align.FILL)
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.box.get_style_context().add_class("dashboard-panel")
        self.box.set_size_request(320, -1)
        self.add(self.box)

        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            .dashboard-panel {
                background-color: rgba(10, 14, 23, 0.90);
                border-left: 1px solid rgba(255,255,255,0.1);
                padding: 20px;
                box-shadow: -10px 0 30px rgba(0,0,0,0.6);
            }
            .dash-title { color: #38bdf8; font-size: 18px; font-weight: 800; }
            .dash-bar-bg { background-color: rgba(255,255,255,0.1); border-radius: 6px; min-height: 12px; }
            .dash-bar-fg { background: linear-gradient(90deg, #38bdf8, #818cf8); border-radius: 6px; }
            .dash-label { color: #cbd5e1; font-size: 12px; font-weight: 600; margin-bottom: 4px; }
        """)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        title = Gtk.Label(label="Control Center")
        title.get_style_context().add_class("dash-title")
        title.set_halign(Gtk.Align.START)
        title.set_margin_top(48)
        self.box.pack_start(title, False, False, 0)

        self.cpu_label = Gtk.Label(label="CPU Usage: 0%")
        self.cpu_label.get_style_context().add_class("dash-label")
        self.cpu_label.set_halign(Gtk.Align.START)
        self.box.pack_start(self.cpu_label, False, False, 0)
        self.cpu_level = Gtk.LevelBar()
        self.cpu_level.set_min_value(0)
        self.cpu_level.set_max_value(100)
        self.box.pack_start(self.cpu_level, False, False, 0)

        self.ram_label = Gtk.Label(label="RAM Usage: 0%")
        self.ram_label.get_style_context().add_class("dash-label")
        self.ram_label.set_halign(Gtk.Align.START)
        self.box.pack_start(self.ram_label, False, False, 0)
        self.ram_level = Gtk.LevelBar()
        self.ram_level.set_min_value(0)
        self.ram_level.set_max_value(100)
        self.box.pack_start(self.ram_level, False, False, 0)
        
        self.show_all()
        GLib.timeout_add_seconds(2, self.update_stats)

    def update_stats(self):
        if self.get_reveal_child():
            cpu = sysinfo.cpu_percent()
            ram = sysinfo.memory_percent()
            self.cpu_label.set_text(f"CPU Usage: {cpu:.1f}%")
            self.cpu_level.set_value(cpu)
            self.ram_label.set_text(f"RAM Usage: {ram:.1f}%")
            self.ram_level.set_value(ram)
        return True

    def toggle(self):
        self.set_reveal_child(not self.get_reveal_child())
