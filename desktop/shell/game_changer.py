"""ease-Desk — GNOME-inspired Spotlight Search and Quick Settings Panel."""

import os
import time
import subprocess
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from shared.utilities import sysinfo
from shared.utilities.apps import launcher_applications


# ------------------------------------------------------------------ Spotlight
class SpotlightWindow(Gtk.Window):
    """GNOME Activities-style command search overlay."""

    _CSS = b"""
        .spotlight-window {
            background-color: rgba(30, 30, 32, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            box-shadow: 0 24px 64px rgba(0, 0, 0, 0.4);
        }
        .spotlight-entry {
            background: transparent;
            border: none;
            box-shadow: none;
            color: #ffffff;
            font-size: 22px;
            font-weight: 300;
            font-family: "Inter", "Ubuntu", sans-serif;
            padding: 14px 24px;
            caret-color: #007aff;
        }
        .spotlight-entry:focus {
            border: none;
            box-shadow: none;
        }
    """

    def __init__(self, parent_shell):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.shell = parent_shell
        self.applications = launcher_applications()
        self.set_decorated(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(600, 56)
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
            matches = [app for app in self.applications if app.matches(query)]
            if matches:
                self.shell._launch_application(matches[0])
                entry.set_text("")
                self.hide()
                return
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
            elif q in ("lock", "lockscreen", "lock screen"):
                self.shell._lock_screen()
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
            background-color: rgba(18, 18, 20, 0.85);
            border-left: 1px solid rgba(255, 255, 255, 0.08);
            padding: 0px 24px 24px 24px;
            box-shadow: -12px 0 32px rgba(0, 0, 0, 0.4);
        }
        .dash-header {
            color: #ffffff;
            font-size: 18px;
            font-weight: 700;
            font-family: "Inter", "Ubuntu", sans-serif;
            margin-bottom: 4px;
        }
        .dash-section-lbl {
            color: rgba(255, 255, 255, 0.5);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.0px;
            text-transform: uppercase;
            margin-top: 20px;
            margin-bottom: 8px;
        }
        .dash-stat-key {
            color: rgba(255, 255, 255, 0.7);
            font-size: 13px;
            font-weight: 500;
        }
        .dash-stat-val {
            color: #ffffff;
            font-size: 13px;
            font-weight: 600;
        }
        .dash-action-btn {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            color: #ffffff;
            font-size: 13px;
            font-weight: 500;
            padding: 8px 12px;
            transition: all 200ms ease;
        }
        .dash-action-btn:hover {
            background: rgba(255, 255, 255, 0.15);
            border-color: rgba(255, 255, 255, 0.2);
        }
        progressbar > trough {
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            min-height: 8px;
        }
        progressbar > trough > progress {
            background: linear-gradient(to right, #007aff, #00c6ff);
            border-radius: 8px;
        }
        progressbar.warning > trough > progress {
            background: linear-gradient(to right, #f9e2af, #fab387);
        }
        progressbar.critical > trough > progress {
            background: linear-gradient(to right, #f38ba8, #eba0ac);
        }
        .notif-row {
            background-color: transparent;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        .notif-title {
            color: #ffffff;
            font-size: 13px;
            font-weight: 700;
        }
        .notif-body {
            color: rgba(255, 255, 255, 0.7);
            font-size: 11px;
        }
        .transparent-bg {
            background-color: transparent;
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
            ("Wallpaper",   lambda *_: self.shell._dialog_change_wallpaper()),
            ("Screenshot",  lambda *_: self.shell._take_screenshot()),
            ("Lock Screen", lambda *_: self.shell._lock_screen()),
            ("Exit Session",lambda *_: self.shell._exit()),
        ]
        for idx, (label_txt, cb) in enumerate(actions):
            btn = Gtk.Button.new_with_label(label_txt)
            btn.get_style_context().add_class("dash-action-btn")
            btn.connect("clicked", cb)
            actions_grid.attach(btn, idx % 2, idx // 2, 1, 1)
        self.box.pack_start(actions_grid, False, False, 0)

        self.box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 12)
        
        # Notifications Header
        notif_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        notif_lbl = Gtk.Label(label="Notifications", xalign=0)
        notif_lbl.get_style_context().add_class("dash-section-lbl")
        notif_lbl.set_margin_top(0)
        notif_hdr.pack_start(notif_lbl, True, True, 0)
        
        clear_btn = Gtk.Button.new_with_label("Clear")
        clear_btn.get_style_context().add_class("dash-action-btn")
        clear_btn.connect("clicked", self._on_clear_notifications)
        notif_hdr.pack_end(clear_btn, False, False, 0)
        
        self.box.pack_start(notif_hdr, False, False, 0)
        
        # Notifications List
        self.notif_scroll = Gtk.ScrolledWindow()
        self.notif_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.notif_scroll.set_min_content_height(150)
        self.notif_list = Gtk.ListBox()
        self.notif_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.notif_list.get_style_context().add_class("transparent-bg")
        self.notif_scroll.add(self.notif_list)
        
        self.box.pack_start(self.notif_scroll, True, True, 0)
        
        if hasattr(self.shell, "notify_manager") and self.shell.notify_manager:
            self.shell.notify_manager.on_new_notification = self._add_notification_ui
            for n in self.shell.notify_manager.history:
                self._add_notification_ui(n)

        self.show_all()
        # Only poll when visible — resource efficient
        GLib.timeout_add_seconds(2, self.update_stats)

    def _on_clear_notifications(self, btn):
        if hasattr(self.shell, "notify_manager") and self.shell.notify_manager:
            self.shell.notify_manager.clear_all()
        for row in self.notif_list.get_children():
            self.notif_list.remove(row)
            row.destroy()

    def _add_notification_ui(self, notif):
        row = Gtk.ListBoxRow()
        row.get_style_context().add_class("notif-row")
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        t_lbl = Gtk.Label(label=notif.title, xalign=0)
        t_lbl.get_style_context().add_class("notif-title")
        vbox.pack_start(t_lbl, False, False, 0)
        
        b_lbl = Gtk.Label(label=notif.body, xalign=0)
        b_lbl.get_style_context().add_class("notif-body")
        b_lbl.set_line_wrap(True)
        vbox.pack_start(b_lbl, False, False, 0)
        
        row.add(vbox)
        self.notif_list.insert(row, 0)
        self.notif_list.show_all()

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
