"""ease-Desk Task Manager & System Activity Monitor.

Displays live CPU, Memory, Disk usage gauges, and real-time process list
with search filtering, column sorting, and End Task capabilities.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GLib, Gtk

from shared.utilities import sysinfo
from shared.utilities.icons import get_icon_pixbuf


def list_processes() -> list[dict]:
    """Retrieve list of active processes using ps for fast and robust cross-distro inspection."""
    procs = []
    try:
        # ps -eo pid,user,%cpu,%mem,rss,stat,comm --sort=-%cpu
        cmd = ["ps", "-eo", "pid,user,%cpu,%mem,rss,stat,comm", "--no-headers"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        for line in res.stdout.strip().splitlines():
            parts = line.split(None, 6)
            if len(parts) >= 7:
                try:
                    pid = int(parts[0])
                    user = parts[1]
                    cpu = float(parts[2])
                    mem = float(parts[3])
                    rss_kb = int(parts[4])
                    stat = parts[5]
                    comm = parts[6]

                    rss_mb = f"{rss_kb / 1024.0:.1f} MB"
                    procs.append({
                        "pid": pid,
                        "user": user,
                        "cpu": cpu,
                        "mem": mem,
                        "rss": rss_mb,
                        "stat": stat,
                        "name": comm,
                    })
                except ValueError:
                    continue
    except Exception:
        pass
    return procs


def _ensure_gtk_initialized() -> None:
    try:
        if hasattr(Gtk, "get_initialized") and Gtk.get_initialized():
            return
    except Exception:
        pass
    try:
        Gtk.init_check()
    except Exception:
        pass
    try:
        Gtk.init()
    except Exception:
        pass


class TaskManagerWindow(Gtk.Window):
    """Full-featured Task Manager window for ease-Desk."""

    def __init__(self):
        _ensure_gtk_initialized()
        super().__init__(title="Task Manager — ease-Desk")
        
        geometry = Gdk.Geometry()
        geometry.min_width = 400
        geometry.min_height = 300
        self.set_geometry_hints(None, geometry, Gdk.WindowHints.MIN_SIZE)
        
        self.set_default_size(820, 560)
        self.set_position(Gtk.WindowPosition.CENTER)

        icon_pb = get_icon_pixbuf("task_manager", size=48)
        self.set_icon(icon_pb)

        self.filter_text = ""
        self.timer_id: Optional[int] = None
        self.refresh_interval = 2  # seconds

        self._load_css()
        self._build_ui()
        self._refresh_data()
        self.timer_id = GLib.timeout_add_seconds(self.refresh_interval, self._refresh_data)
        self.connect("delete-event", self._on_close)


    def _load_css(self) -> None:
        provider = Gtk.CssProvider()
        css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme.css")
        if os.path.exists(css_path):
            provider.load_from_path(css_path)
            screen = Gdk.Screen.get_default()
            if screen is not None:
                Gtk.StyleContext.add_provider_for_screen(
                    screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )

    def _build_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)

        # Header Bar
        header = Gtk.HeaderBar()
        header.set_show_close_button(False)
        header.set_title("Task Manager")
        header.set_subtitle("Processes and System Resources")
        main_box.pack_start(header, False, False, 0)

        # Refresh button
        ref_btn = Gtk.Button(label="Refresh")
        ref_btn.connect("clicked", lambda *_: self._refresh_data())
        header.pack_start(ref_btn)

        # End Task button
        self.kill_btn = Gtk.Button(label="End Task")
        self.kill_btn.get_style_context().add_class("destructive-action")
        self.kill_btn.connect("clicked", self._on_end_task_clicked)
        header.pack_end(self.kill_btn)

        # 1. System Performance Overview Cards
        perf_grid = Gtk.Grid(column_spacing=14, row_spacing=8, hexpand=True)

        # CPU Card
        self.cpu_frame, self.cpu_bar, self.cpu_val = self._create_meter_card("CPU Usage")
        # Memory Card
        self.mem_frame, self.mem_bar, self.mem_val = self._create_meter_card("Memory Usage")
        # Disk Card
        self.disk_frame, self.disk_bar, self.disk_val = self._create_meter_card("Disk Space")

        perf_grid.attach(self.cpu_frame, 0, 0, 1, 1)
        perf_grid.attach(self.mem_frame, 1, 0, 1, 1)
        perf_grid.attach(self.disk_frame, 2, 0, 1, 1)
        main_box.pack_start(perf_grid, False, False, 0)

        # 2. Search / Filter Toolbar
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        search_lbl = Gtk.Label(label="Filter Processes:")
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search by process name or PID…")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_changed)

        self.proc_count_lbl = Gtk.Label(label="0 processes")
        self.proc_count_lbl.get_style_context().add_class("dim-label")

        search_box.pack_start(search_lbl, False, False, 0)
        search_box.pack_start(self.search_entry, True, True, 0)
        search_box.pack_start(self.proc_count_lbl, False, False, 0)
        main_box.pack_start(search_box, False, False, 0)

        # 3. Process Table (TreeView)
        # Model: PID (0), Name (1), User (2), CPU% (3), CPU_str (4), Mem% (5), Mem_str (6), RSS (7), Status (8)
        self.store = Gtk.ListStore(int, str, str, float, str, float, str, str, str)
        self.tree_filter = self.store.filter_new()
        self.tree_filter.set_visible_func(self._filter_func)

        self.tree_sort = Gtk.TreeModelSort(model=self.tree_filter)
        self.tree_view = Gtk.TreeView(model=self.tree_sort)
        self.tree_view.set_rules_hint(True)
        # Enable row striping for better readability (using theme styles)
        self.tree_view.set_has_tooltip(True)

        self._add_columns()

        self.tree_view.get_selection().connect("changed", self._on_selection_changed)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(150)
        scrolled.set_min_content_width(200)
        scrolled.add(self.tree_view)
        main_box.pack_start(scrolled, True, True, 0)

        self.add(main_box)

    def _create_meter_card(self, title: str) -> tuple[Gtk.Frame, Gtk.ProgressBar, Gtk.Label]:
        frame = Gtk.Frame()
        frame.get_style_context().add_class("tm-card")
        frame.set_hexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        t_lbl = Gtk.Label(label=title, xalign=0)
        t_lbl.get_style_context().add_class("tm-card-title")

        val_lbl = Gtk.Label(label="0%", xalign=0)
        val_lbl.get_style_context().add_class("tm-card-val")

        bar = Gtk.ProgressBar()
        bar.set_fraction(0.0)
        bar.get_style_context().add_class("tm-progress")

        box.pack_start(t_lbl, False, False, 0)
        box.pack_start(val_lbl, False, False, 0)
        box.pack_start(bar, False, False, 4)
        frame.add(box)
        return frame, bar, val_lbl

    def _add_columns(self) -> None:
        cols = [
            ("PID", 0, 70),
            ("Process Name", 1, 220),
            ("User", 2, 90),
            ("CPU %", 4, 85),
            ("RAM %", 6, 85),
            ("Memory", 7, 95),
            ("Status", 8, 75),
        ]

        for title, col_id, width in cols:
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=col_id)
            column.set_resizable(True)
            column.set_min_width(width)

            # Sort mapping
            if title == "PID":
                column.set_sort_column_id(0)
            elif title == "Process Name":
                column.set_sort_column_id(1)
            elif title == "User":
                column.set_sort_column_id(2)
            elif title == "CPU %":
                column.set_sort_column_id(3)
            elif title == "RAM %":
                column.set_sort_column_id(5)

            self.tree_view.append_column(column)

        # Default sort by CPU % descending
        self.tree_sort.set_sort_column_id(3, Gtk.SortType.DESCENDING)

    def _filter_func(self, model, tree_iter, data) -> bool:
        if not self.filter_text:
            return True
        pid = str(model.get_value(tree_iter, 0))
        name = str(model.get_value(tree_iter, 1)).lower()
        user = str(model.get_value(tree_iter, 2)).lower()
        query = self.filter_text.lower()
        return query in name or query in pid or query in user

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self.filter_text = entry.get_text().strip()
        self.tree_filter.refilter()


    def _update_bar_color(self, bar: Gtk.ProgressBar, pct: float) -> None:
        ctx = bar.get_style_context()
        ctx.remove_class("warning")
        ctx.remove_class("critical")
        if pct >= 90:
            ctx.add_class("critical")
        elif pct >= 75:
            ctx.add_class("warning")
            
    def _refresh_data(self) -> bool:
        # 1. Update Hardware Meters
        info = sysinfo.summary()
        ram_pct = info.get("mem_percent", 0.0) / 100.0
        disk_pct = info.get("disk_percent", 0.0) / 100.0
        cpu_load = info.get("cpu_percent", 0.0) / 100.0

        self.cpu_bar.set_fraction(min(1.0, max(0.0, cpu_load)))
        self.cpu_val.set_text(f"{cpu_load * 100:.1f}% ({info.get('cpu', 1)} Cores)")

        self.mem_bar.set_fraction(min(1.0, max(0.0, ram_pct)))
        self.mem_val.set_text(f"{ram_pct * 100:.1f}% ({info.get('mem_used', '')} / {info.get('mem_total', '')})")

        self.disk_bar.set_fraction(min(1.0, max(0.0, disk_pct)))
        self.disk_val.set_text(f"{disk_pct * 100:.1f}% ({info.get('disk_used', '')} / {info.get('disk_total', '')})")

        # 2. Update Process Table
        procs = list_processes()
        self.proc_count_lbl.set_text(f"{len(procs)} processes")

        self.store.clear()
        for p in procs:
            self.store.append([
                p["pid"],
                p["name"],
                p["user"],
                p["cpu"],
                f"{p['cpu']:.1f}%",
                p["mem"],
                f"{p['mem']:.1f}%",
                p["rss"],
                p["stat"],
            ])

        return True

    def _on_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        model, tree_iter = selection.get_selected()
        if tree_iter:
            pid = model.get_value(tree_iter, 0)
            self.kill_btn.set_sensitive(pid != 1)
        else:
            self.kill_btn.set_sensitive(False)

    def _on_end_task_clicked(self, btn: Gtk.Button) -> None:
        selection = self.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if not tree_iter:
            return

        pid = model.get_value(tree_iter, 0)
        name = model.get_value(tree_iter, 1)

        if pid == 1:
            return

        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"End Process '{name}' (PID: {pid})?",
        )
        dialog.format_secondary_text("Ending a process may cause unsaved data loss.")
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            try:
                os.kill(pid, signal.SIGTERM)
                GLib.timeout_add(300, self._refresh_data)
            except OSError as exc:
                err_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.CLOSE,
                    text=f"Failed to end process: {exc}",
                )
                err_dialog.run()
                err_dialog.destroy()

    def _on_close(self, *args) -> bool:
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = None
        return False
