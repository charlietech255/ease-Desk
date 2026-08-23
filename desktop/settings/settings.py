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
from shared.config import preferences


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
        self._add_page("Personalization", "preferences-desktop-wallpaper", self._build_personalization())
        self._add_page("Services", "task_manager", self._build_services())
        self._add_page("Firewall", "webroot", self._build_firewall())
        self._add_page("Users", "folder", self._build_users())
        self._add_page("ease-Desk", "settings", self._build_easedesk_control())

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

        # --- Network Info ---
        net_lbl = Gtk.Label(label="Network IPs:")
        net_lbl.get_style_context().add_class("info-key")
        net_lbl.set_halign(Gtk.Align.START)
        net_lbl.set_margin_top(12)
        box.pack_start(net_lbl, False, False, 0)
        
        try:
            ips = subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.strip()
            if not ips: ips = "No IP found"
        except:
            ips = "Unknown"
            
        ip_val = Gtk.Label(label=ips)
        ip_val.get_style_context().add_class("info-val")
        ip_val.set_halign(Gtk.Align.START)
        ip_val.set_selectable(True)
        box.pack_start(ip_val, False, False, 0)

        # --- System Updater ---
        update_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        update_box.set_margin_top(20)
        update_btn = Gtk.Button(label="Run System Update (apt)")
        update_btn.connect("clicked", lambda x: subprocess.Popen(["lxterminal", "-e", "sudo apt update && sudo apt upgrade -y && echo 'Done!' && sleep 3"]))
        update_box.pack_start(update_btn, False, False, 0)
        box.pack_start(update_box, False, False, 0)

        return box

    # ---------------------------------------------------------------------- Personalization
    def _build_personalization(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        
        lbl = Gtk.Label(label="Personalization")
        lbl.get_style_context().add_class("page-title")
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        # Wallpaper
        wp_lbl = Gtk.Label(label="Wallpaper")
        wp_lbl.set_halign(Gtk.Align.START)
        wp_lbl.get_style_context().add_class("info-key")
        box.pack_start(wp_lbl, False, False, 0)
        
        wp_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.wp_entry = Gtk.Entry()
        self.wp_entry.set_text(preferences.get("Personalization", "wallpaper_path", ""))
        self.wp_entry.set_hexpand(True)
        wp_hbox.pack_start(self.wp_entry, True, True, 0)
        
        wp_btn = Gtk.Button(label="Browse...")
        wp_btn.connect("clicked", self._on_browse_wallpaper)
        wp_hbox.pack_start(wp_btn, False, False, 0)
        
        box.pack_start(wp_hbox, False, False, 0)
        
        # Wallpaper Mode
        mode_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        mode_lbl = Gtk.Label(label="Mode:")
        mode_lbl.get_style_context().add_class("info-key")
        mode_hbox.pack_start(mode_lbl, False, False, 0)
        
        self.mode_combo = Gtk.ComboBoxText()
        for mode in ["fill", "fit", "stretch", "center", "solid"]:
            self.mode_combo.append(mode, mode)
        self.mode_combo.set_active_id(preferences.get("Personalization", "wallpaper_mode", "fill"))
        self.mode_combo.connect("changed", self._on_wallpaper_mode_changed)
        mode_hbox.pack_start(self.mode_combo, False, False, 0)
        box.pack_start(mode_hbox, False, False, 0)
        
        # Solid Color
        color_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        color_lbl = Gtk.Label(label="Solid Color:")
        color_lbl.get_style_context().add_class("info-key")
        color_hbox.pack_start(color_lbl, False, False, 0)
        
        self.color_btn = Gtk.ColorButton()
        rgba = Gdk.RGBA()
        rgba.parse(preferences.get("Personalization", "solid_color", "#0b0e14"))
        self.color_btn.set_rgba(rgba)
        self.color_btn.connect("color-set", self._on_color_set)
        color_hbox.pack_start(self.color_btn, False, False, 0)
        box.pack_start(color_hbox, False, False, 0)
        
        # Apply button
        apply_btn = Gtk.Button(label="Apply Wallpaper")
        apply_btn.connect("clicked", self._on_apply_wallpaper)
        apply_btn.set_halign(Gtk.Align.START)
        box.pack_start(apply_btn, False, False, 0)

        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 10)

        # Theme Mode
        theme_lbl = Gtk.Label(label="Theme Mode")
        theme_lbl.set_halign(Gtk.Align.START)
        theme_lbl.get_style_context().add_class("info-key")
        box.pack_start(theme_lbl, False, False, 0)
        
        self.theme_combo = Gtk.ComboBoxText()
        self.theme_combo.append("dark", "Dark Mode")
        self.theme_combo.append("light", "Light Mode")
        self.theme_combo.set_active_id(preferences.get("Personalization", "theme_mode", "dark"))
        self.theme_combo.connect("changed", lambda c: preferences.set("Personalization", "theme_mode", c.get_active_id() or "dark"))
        self.theme_combo.set_halign(Gtk.Align.START)
        box.pack_start(self.theme_combo, False, False, 0)
        
        # Dock Position
        dock_lbl = Gtk.Label(label="Dock Position")
        dock_lbl.set_halign(Gtk.Align.START)
        dock_lbl.get_style_context().add_class("info-key")
        box.pack_start(dock_lbl, False, False, 0)
        
        self.dock_combo = Gtk.ComboBoxText()
        self.dock_combo.append("left", "Left")
        self.dock_combo.append("bottom", "Bottom")
        self.dock_combo.set_active_id(preferences.get("Personalization", "dock_position", "left"))
        self.dock_combo.connect("changed", lambda c: preferences.set("Personalization", "dock_position", c.get_active_id() or "left"))
        self.dock_combo.set_halign(Gtk.Align.START)
        box.pack_start(self.dock_combo, False, False, 0)

        # Note about restart
        note_lbl = Gtk.Label(label="Note: Some changes may require restarting ease-Desk to take full effect.")
        note_lbl.get_style_context().add_class("info-val")
        note_lbl.set_halign(Gtk.Align.START)
        box.pack_start(note_lbl, False, False, 20)

        return box

    def _on_browse_wallpaper(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Select Wallpaper",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,
            Gtk.ResponseType.OK,
        )
        filter_img = Gtk.FileFilter()
        filter_img.set_name("Images")
        filter_img.add_mime_type("image/png")
        filter_img.add_mime_type("image/jpeg")
        filter_img.add_mime_type("image/svg+xml")
        dialog.add_filter(filter_img)

        if dialog.run() == Gtk.ResponseType.OK:
            self.wp_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def _on_wallpaper_mode_changed(self, combo):
        preferences.set("Personalization", "wallpaper_mode", combo.get_active_text() or "fill")

    def _on_color_set(self, btn):
        rgba = btn.get_rgba()
        color_hex = f"#{int(rgba.red * 255):02x}{int(rgba.green * 255):02x}{int(rgba.blue * 255):02x}"
        preferences.set("Personalization", "solid_color", color_hex)

    def _on_apply_wallpaper(self, btn):
        preferences.set("Personalization", "wallpaper_path", self.wp_entry.get_text().strip())

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

        # --- Quick Log Viewer ---
        log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        log_box.set_margin_top(16)
        log_btn = Gtk.Button(label="View Recent System Logs (journalctl)")
        log_btn.connect("clicked", lambda x: subprocess.Popen(["lxterminal", "-e", "sudo journalctl -xe -n 50 | less"]))
        log_box.pack_start(log_btn, False, False, 0)
        box.pack_start(log_box, False, False, 0)

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

    # ---------------------------------------------------------------------- ease-Desk Control
    def _build_easedesk_control(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        
        lbl = Gtk.Label(label="ease-Desk System Control")
        lbl.get_style_context().add_class("page-title")
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        desc = Gtk.Label(label="Manage your desktop environment installation, configuration, and state.")
        desc.set_halign(Gtk.Align.START)
        desc.get_style_context().add_class("info-val")
        box.pack_start(desc, False, False, 0)

        # Actions Box
        action_grid = Gtk.Grid()
        action_grid.set_column_spacing(16)
        action_grid.set_row_spacing(16)
        action_grid.set_margin_top(20)

        # Change Password
        pw_btn = Gtk.Button(label="Change VNC Password")
        pw_btn.connect("clicked", lambda x: subprocess.Popen(["lxterminal", "-e", "sudo /bin/bash -c 'echo \"Enter new password:\"; read -s p1; echo \"Confirm:\"; read -s p2; if [ \"$p1\" = \"$p2\" ]; then printf \"%s\\n%s\\n\" \"$p1\" \"$p1\" | kasmvncpasswd -u $USER -rw ~/.kasmpasswd; echo \"Done! Restart ease-Desk to apply.\"; else echo \"Mismatch!\"; fi; sleep 3'"]))
        
        pw_desc = Gtk.Label(label="Update your remote desktop connection password.")
        pw_desc.get_style_context().add_class("info-key")
        pw_desc.set_halign(Gtk.Align.START)
        
        action_grid.attach(pw_btn, 0, 0, 1, 1)
        action_grid.attach(pw_desc, 1, 0, 1, 1)

        # Restart
        res_btn = Gtk.Button(label="Restart ease-Desk")
        res_btn.connect("clicked", lambda x: subprocess.Popen(["lxterminal", "-e", "sudo systemctl restart easedesk"]))
        
        res_desc = Gtk.Label(label="Restart the display server and UI safely.")
        res_desc.get_style_context().add_class("info-key")
        res_desc.set_halign(Gtk.Align.START)
        
        action_grid.attach(res_btn, 0, 1, 1, 1)
        action_grid.attach(res_desc, 1, 1, 1, 1)

        # Uninstall
        uni_btn = Gtk.Button(label="Uninstall System")
        uni_btn.get_style_context().add_class("btn-danger")
        uni_btn.connect("clicked", lambda x: subprocess.Popen(["lxterminal", "-e", "sudo /opt/ease-desk/scripts/uninstall.sh"]))
        
        uni_desc = Gtk.Label(label="Completely remove ease-Desk and all settings from this VPS.")
        uni_desc.get_style_context().add_class("info-key")
        uni_desc.set_halign(Gtk.Align.START)
        
        action_grid.attach(uni_btn, 0, 2, 1, 1)
        action_grid.attach(uni_desc, 1, 2, 1, 1)

        box.pack_start(action_grid, False, False, 0)
        return box
