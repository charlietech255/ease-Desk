"""ease-Desk — GNOME-inspired Spotlight Search and Quick Settings Panel."""

import os
import time
import subprocess
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from shared.utilities import sysinfo


# ------------------------------------------------------------------ Spotlight
class SpotlightWindow(Gtk.Window):
    """GNOME Activities-style command search overlay."""

    _CSS = b"""
        .spotlight-window {
            background-color: rgba(255, 255, 255, 0.95);
            border: 1px solid rgba(0, 0, 0, 0.05);
            border-radius: 14px;
            box-shadow: 0 12px 48px rgba(0, 0, 0, 0.2);
        }
        .spotlight-entry {
            background: transparent;
            border: none;
            box-shadow: none;
            color: #333333;
            font-size: 22px;
            font-weight: 300;
            font-family: "Inter", "Ubuntu", sans-serif;
            padding: 14px 24px;
            caret-color: #000000;
        }
        .spotlight-entry:focus {
            border: none;
            box-shadow: none;
        }
    """

    def __init__(self, parent_shell):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.shell = parent_shell
        self.set_decorated(False)
        self.set_transient_for(parent_shell.window)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(580, 56)
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
        self.entry.set_placeholder_text("Search applications, files, or run a command...")
        self.entry.get_style_context().add_class("spotlight-entry")
        self.entry.set_has_frame(False)
        self.entry.set_size_request(-1, 56)
        self.entry.connect("activate", self._on_activate)
        self.entry.connect("key-press-event", self._on_key_press)

        vbox.pack_start(self.entry, True, True, 0)
        self.add(vbox)

        provider = Gtk.CssProvider()
        provider.load_from_data(self._CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.hide()

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def _on_activate(self, entry):
        query = entry.get_text().strip()
        if query:
            q = query.lower()
            if q in ("terminal", "term", "bash", "console"):
                self.shell._launch_path("app://terminal")
            elif q in ("browser", "web", "chrome", "firefox", "epiphany"):
                self.shell._launch_path("app://browser")
            elif q in ("task manager", "monitor", "top", "htop", "processes"):
                self.shell._launch_path("app://task_manager")
            elif q in ("files", "this pc", "file manager"):
                self.shell._launch_path("thispc://")
            elif q in ("wallpaper", "theme", "personalize"):
                self.shell._launch_path("app://wallpaper")
            elif q in ("settings", "system"):
                self.shell._launch_path("app://settings")
            elif os.path.exists(query):
                self.shell._launch_path(query)
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


# ------------------------------------------------------------------ Quick Settings Panel
class DashboardPanel(Gtk.Revealer):
    """GNOME-inspired Quick Settings side panel, triggered from the clock."""

    _CSS = b"""
        .dashboard-panel {
            background-color: rgba(255, 255, 255, 0.95);
            border-left: 1px solid rgba(0, 0, 0, 0.05);
            padding: 0px 20px 20px 20px;
            box-shadow: -8px 0 28px rgba(0, 0, 0, 0.15);
        }
        .dash-header {
            color: #333333;
            font-size: 16px;
            font-weight: 700;
            font-family: "Inter", "Ubuntu", sans-serif;
            margin-bottom: 4px;
        }
        .dash-section-lbl {
            color: #888888;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.8px;
            margin-top: 16px;
            margin-bottom: 6px;
        }
        .dash-stat-key {
            color: #555555;
            font-size: 12px;
            font-weight: 500;
        }
        .dash-stat-val {
            color: #333333;
            font-size: 12px;
            font-weight: 600;
        }
        .dash-action-btn {
            background: rgba(0, 0, 0, 0.05);
            border: 1px solid rgba(0, 0, 0, 0.1);
            border-radius: 8px;
            color: #333333;
            font-size: 12px;
            font-weight: 500;
            padding: 6px 10px;
            transition: all 130ms ease;
        }
        .dash-action-btn:hover {
            background: rgba(0, 0, 0, 0.1);
            border-color: rgba(0, 0, 0, 0.15);
        }
        progressbar > trough {
            background-color: rgba(0, 0, 0, 0.1);
            border-radius: 6px;
            min-height: 6px;
        }
        progressbar > trough > progress {
            background: linear-gradient(to right, #007aff, #00c6ff);
            border-radius: 6px;
        }
        progressbar.warning > trough > progress {
            background: linear-gradient(to right, #f9e2af, #fab387);
        }
        progressbar.critical > trough > progress {
            background: linear-gradient(to right, #f38ba8, #eba0ac);
        }
    """

    def __init__(self, parent_shell):
        super().__init__()
        self.shell = parent_shell
        self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.set_transition_duration(250)
        self.set_halign(Gtk.Align.END)
        self.set_valign(Gtk.Align.FILL)

        provider = Gtk.CssProvider()
        provider.load_from_data(self._CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.box.get_style_context().add_class("dashboard-panel")
        self.box.set_size_request(300, -1)
        self.add(self.box)

        # --- Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        header_box.set_margin_top(52)
        header_box.set_margin_bottom(12)
        header_lbl = Gtk.Label(label="Quick Settings")
        header_lbl.get_style_context().add_class("dash-header")
        header_lbl.set_halign(Gtk.Align.START)
        header_box.pack_start(header_lbl, True, True, 0)

        close_btn = Gtk.Button.new_with_label("✕")
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.get_style_context().add_class("dash-action-btn")
        close_btn.connect("clicked", lambda *_: self.toggle())
        header_box.pack_end(close_btn, False, False, 0)
        self.box.pack_start(header_box, False, False, 0)

        self.box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # --- Resource Meters
        res_lbl = Gtk.Label(label="Resources", xalign=0)
        res_lbl.get_style_context().add_class("dash-section-lbl")
        self.box.pack_start(res_lbl, False, False, 0)

        self.cpu_key_lbl = Gtk.Label(label="CPU", xalign=0)
        self.cpu_key_lbl.get_style_context().add_class("dash-stat-key")
        self.cpu_val_lbl = Gtk.Label(label="0%", xalign=1)
        self.cpu_val_lbl.get_style_context().add_class("dash-stat-val")
        cpu_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        cpu_row.pack_start(self.cpu_key_lbl, True, True, 0)
        cpu_row.pack_end(self.cpu_val_lbl, False, False, 0)
        self.box.pack_start(cpu_row, False, False, 0)

        self.cpu_bar = Gtk.ProgressBar()
        self.cpu_bar.set_fraction(0.0)
        self.box.pack_start(self.cpu_bar, False, False, 4)

        self.ram_key_lbl = Gtk.Label(label="Memory", xalign=0)
        self.ram_key_lbl.get_style_context().add_class("dash-stat-key")
        self.ram_val_lbl = Gtk.Label(label="0%", xalign=1)
        self.ram_val_lbl.get_style_context().add_class("dash-stat-val")
        ram_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        ram_row.pack_start(self.ram_key_lbl, True, True, 0)
        ram_row.pack_end(self.ram_val_lbl, False, False, 0)
        self.box.pack_start(ram_row, False, False, 0)

        self.ram_bar = Gtk.ProgressBar()
        self.ram_bar.set_fraction(0.0)
        self.box.pack_start(self.ram_bar, False, False, 4)

        # --- System Info
        info_lbl = Gtk.Label(label="System", xalign=0)
        info_lbl.get_style_context().add_class("dash-section-lbl")
        self.box.pack_start(info_lbl, False, False, 0)

        self._info_grid = Gtk.Grid(column_spacing=12, row_spacing=4)
        self.box.pack_start(self._info_grid, False, False, 0)
        self._info_rows: list[tuple[Gtk.Label, Gtk.Label]] = []
        for row_idx, key_text in enumerate(("Host", "OS", "Disk")):
            kl = Gtk.Label(label=key_text, xalign=0)
            kl.get_style_context().add_class("dash-stat-key")
            vl = Gtk.Label(label="—", xalign=1)
            vl.get_style_context().add_class("dash-stat-val")
            vl.set_selectable(True)
            self._info_grid.attach(kl, 0, row_idx, 1, 1)
            self._info_grid.attach(vl, 1, row_idx, 1, 1)
            self._info_rows.append((kl, vl))

        # --- Quick Actions
        act_lbl = Gtk.Label(label="Actions", xalign=0)
        act_lbl.get_style_context().add_class("dash-section-lbl")
        self.box.pack_start(act_lbl, False, False, 0)

        actions_grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        actions = [
            ("Wallpaper", lambda *_: self.shell._dialog_change_wallpaper()),
            ("Screenshot", lambda *_: self.shell._take_screenshot()),
            ("Add Shortcut", lambda *_: self.shell._dialog_add_shortcut()),
            ("Exit Session", lambda *_: self.shell._exit()),
        ]
        for idx, (label_txt, cb) in enumerate(actions):
            btn = Gtk.Button.new_with_label(label_txt)
            btn.get_style_context().add_class("dash-action-btn")
            btn.connect("clicked", cb)
            actions_grid.attach(btn, idx % 2, idx // 2, 1, 1)
        self.box.pack_start(actions_grid, False, False, 0)

        self.show_all()
        # Only poll when visible — resource efficient
        GLib.timeout_add_seconds(2, self.update_stats)

    def update_stats(self):
        if self.get_reveal_child():
            info = sysinfo.summary()
            cpu = info.get("cpu_percent", 0.0)
            ram = info.get("mem_percent", 0.0)

            self.cpu_val_lbl.set_text(f"{cpu:.1f}%")
            self.cpu_bar.set_fraction(min(1.0, cpu / 100.0))
            self._update_bar_color(self.cpu_bar, cpu)

            self.ram_val_lbl.set_text(f"{ram:.1f}%")
            self.ram_bar.set_fraction(min(1.0, ram / 100.0))
            self._update_bar_color(self.ram_bar, ram)

            if len(self._info_rows) >= 3:
                self._info_rows[0][1].set_text(info.get("hostname", "—"))
                self._info_rows[1][1].set_text(info.get("os", "—"))
                self._info_rows[2][1].set_text(
                    f"{info.get('disk_used', '')} / {info.get('disk_total', '')}"
                )
        return True

    def _update_bar_color(self, bar: Gtk.ProgressBar, pct: float) -> None:
        ctx = bar.get_style_context()
        ctx.remove_class("warning")
        ctx.remove_class("critical")
        if pct >= 90:
            ctx.add_class("critical")
        elif pct >= 75:
            ctx.add_class("warning")

    def toggle(self):
        self.set_reveal_child(not self.get_reveal_child())
