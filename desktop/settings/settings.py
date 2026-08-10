from __future__ import annotations

import os
import subprocess
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from shared.utilities import sysinfo
from shared.utilities.icons import get_icon_pixbuf


class SettingsWindow(Gtk.Window):
    """VPS Control Center for ease-Desk."""

    def __init__(self):
        super().__init__(title="Settings & VPS Control Center")
        
        geometry = Gdk.Geometry()
        geometry.min_width = 500
        geometry.min_height = 400
        self.set_geometry_hints(None, geometry, Gdk.WindowHints.MIN_SIZE)
        
        self.set_default_size(860, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon(get_icon_pixbuf("settings", size=48))

        self._load_css()
        self._build_ui()

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
        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(main_hbox)

        # Left Sidebar
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sidebar.get_style_context().add_class("sidebar")
        sidebar.set_size_request(200, -1)
        sidebar.set_margin_top(12)
        sidebar.set_margin_bottom(12)
        sidebar.set_margin_start(12)
        sidebar.set_margin_end(12)
        main_hbox.pack_start(sidebar, False, False, 0)

        # Title in Sidebar
        title_lbl = Gtk.Label(label="VPS Control")
        title_lbl.get_style_context().add_class("sidebar-title")
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_margin_bottom(16)
        sidebar.pack_start(title_lbl, False, False, 0)

        # Right Content Area (Stack)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.get_style_context().add_class("content-area")
        content_box.pack_start(self.stack, True, True, 0)
        main_hbox.pack_start(content_box, True, True, 0)

        # Create Pages
        self.pages = {}
        self._add_page("System Info", "computer", self._build_system_info())
        self._add_page("Services", "task_manager", self._build_services())
        self._add_page("Firewall", "webroot", self._build_firewall())
        self._add_page("Users", "folder", self._build_users())

        # Build Sidebar Navigation
        self.nav_buttons = {}
        for name in self.pages:
            btn = Gtk.Button()
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.get_style_context().add_class("nav-btn")
            
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf(self.pages[name]["icon"], size=20))
            lbl = Gtk.Label(label=name)
            box.pack_start(img, False, False, 0)
            box.pack_start(lbl, False, False, 0)
            btn.add(box)
            
            btn.connect("clicked", self._on_nav_clicked, name)
            self.nav_buttons[name] = btn
            sidebar.pack_start(btn, False, False, 0)
            
        # Select first page
        self._select_nav("System Info")

    def _add_page(self, name: str, icon: str, widget: Gtk.Widget) -> None:
        self.pages[name] = {"icon": icon, "widget": widget}
        self.stack.add_named(widget, name)

    def _on_nav_clicked(self, widget: Gtk.Button, name: str) -> None:
        self._select_nav(name)

    def _select_nav(self, name: str) -> None:
        for n, btn in self.nav_buttons.items():
            if n == name:
                btn.get_style_context().add_class("active")
            else:
                btn.get_style_context().remove_class("active")
        self.stack.set_visible_child_name(name)

    # ---------------------------------------------------------------------- System Info
    def _build_system_info(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        
        lbl = Gtk.Label(label="System Information")
        lbl.get_style_context().add_class("page-title")
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        grid = Gtk.Grid()
        grid.set_column_spacing(24)
        grid.set_row_spacing(12)
        
        info = sysinfo.summary()
        items = [
            ("Hostname", info.get("hostname", "Unknown")),
            ("Operating System", info.get("os", "Unknown")),
            ("Kernel", info.get("kernel", "Unknown")),
            ("Uptime", info.get("uptime", "Unknown")),
            ("CPU Cores", str(info.get("cpu", "Unknown"))),
            ("Memory Used", f"{info.get('mem_used', '0')} / {info.get('mem_total', '0')}"),
            ("Disk Used", f"{info.get('disk_used', '0')} / {info.get('disk_total', '0')}"),
        ]

        for i, (k, v) in enumerate(items):
            kl = Gtk.Label(label=f"{k}:")
            kl.get_style_context().add_class("info-key")
            kl.set_halign(Gtk.Align.END)
            vl = Gtk.Label(label=str(v))
            vl.get_style_context().add_class("info-val")
            vl.set_halign(Gtk.Align.START)
            vl.set_selectable(True)
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)

        box.pack_start(grid, False, False, 0)
        return box

    # ---------------------------------------------------------------------- Services
    def _build_services(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        
        lbl = Gtk.Label(label="Systemd Services")
        lbl.get_style_context().add_class("page-title")
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        # Common services to manage
        common_services = ["ssh", "apache2", "nginx", "mysql", "postgresql", "docker", "ufw"]

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(300)
        
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        
        for svc in common_services:
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            hbox.set_margin_start(10)
            hbox.set_margin_end(10)
            hbox.set_margin_top(10)
            hbox.set_margin_bottom(10)
            
            s_name = Gtk.Label(label=svc)
            s_name.set_halign(Gtk.Align.START)
            s_name.get_style_context().add_class("info-val")
            
            # check status
            status = "Inactive"
            color_class = "status-crit"
            try:
                res = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True)
                if res.stdout.strip() == "active":
                    status = "Active"
                    color_class = "status-ok"
            except Exception:
                pass
                
            s_stat = Gtk.Label(label=status)
            s_stat.get_style_context().add_class(color_class)
            
            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            restart_btn = Gtk.Button(label="Restart")
            restart_btn.connect("clicked", lambda *_, s=svc: self._run_systemctl("restart", s))
            stop_btn = Gtk.Button(label="Stop")
            stop_btn.connect("clicked", lambda *_, s=svc: self._run_systemctl("stop", s))
            start_btn = Gtk.Button(label="Start")
            start_btn.connect("clicked", lambda *_, s=svc: self._run_systemctl("start", s))
            
            btn_box.pack_start(start_btn, False, False, 0)
            btn_box.pack_start(stop_btn, False, False, 0)
            btn_box.pack_start(restart_btn, False, False, 0)
            
            hbox.pack_start(s_name, True, True, 0)
            hbox.pack_start(s_stat, False, False, 20)
            hbox.pack_start(btn_box, False, False, 0)
            row.add(hbox)
            listbox.add(row)

        scroll.add(listbox)
        box.pack_start(scroll, True, True, 0)
        return box

    def _run_systemctl(self, action: str, svc: str) -> None:
        # We spawn pkexec to ask for password if needed, or if charlie has sudo NOPASSWD, just run it
        try:
            subprocess.Popen(["sudo", "systemctl", action, svc])
        except Exception:
            pass

    # ---------------------------------------------------------------------- Firewall
    def _build_firewall(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        
        lbl = Gtk.Label(label="Firewall (UFW)")
        lbl.get_style_context().add_class("page-title")
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)
        
        status_lbl = Gtk.Label(label="Status: Check Terminal for UFW status")
        status_lbl.set_halign(Gtk.Align.START)
        box.pack_start(status_lbl, False, False, 0)
        
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.port_entry = Gtk.Entry()
        self.port_entry.set_placeholder_text("Port (e.g., 8080)")
        allow_btn = Gtk.Button(label="Allow Port")
        allow_btn.connect("clicked", self._allow_ufw_port)
        
        entry_box.pack_start(self.port_entry, False, False, 0)
        entry_box.pack_start(allow_btn, False, False, 0)
        
        box.pack_start(entry_box, False, False, 0)
        return box

    def _allow_ufw_port(self, widget) -> None:
        port = self.port_entry.get_text().strip()
        if port.isdigit():
            subprocess.Popen(["lxterminal", "-e", f"sudo ufw allow {port} && sleep 2"])
            self.port_entry.set_text("")

    # ---------------------------------------------------------------------- Users
    def _build_users(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        
        lbl = Gtk.Label(label="System Users")
        lbl.get_style_context().add_class("page-title")
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        
        try:
            with open("/etc/passwd", "r") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) > 2:
                        uid = int(parts[2])
                        if 1000 <= uid < 65000:
                            row = Gtk.ListBoxRow()
                            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                            hbox.set_margin_start(10)
                            hbox.set_margin_end(10)
                            hbox.set_margin_top(6)
                            hbox.set_margin_bottom(6)
                            
                            u_name = Gtk.Label(label=parts[0])
                            u_name.set_halign(Gtk.Align.START)
                            u_name.get_style_context().add_class("info-val")
                            
                            u_desc = Gtk.Label(label=f"UID: {uid} | Home: {parts[5]}")
                            u_desc.get_style_context().add_class("info-key")
                            
                            hbox.pack_start(u_name, True, True, 0)
                            hbox.pack_end(u_desc, False, False, 0)
                            row.add(hbox)
                            listbox.add(row)
        except Exception:
            pass
            
        box.pack_start(listbox, True, True, 0)
        return box
