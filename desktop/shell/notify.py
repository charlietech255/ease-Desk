from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, Gdk, GLib


@dataclass
class Notification:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Notification"
    body: str = ""
    timestamp: float = field(default_factory=time.time)
    app_name: str = "System"


class ToastWindow(Gtk.Window):
    """A small frosted-glass pop-up that appears for 4 seconds."""

    _CSS = b"""
        window {
            background-color: transparent;
        }
        .toast-box {
            background-color: rgba(30, 30, 32, 0.90);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            padding: 12px 16px;
        }
        .toast-title {
            color: #ffffff;
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 4px;
            font-family: "Inter", "Ubuntu", sans-serif;
        }
        .toast-body {
            color: rgba(255, 255, 255, 0.8);
            font-size: 12px;
            font-family: "Inter", "Ubuntu", sans-serif;
        }
    """

    def __init__(self, notif: Notification) -> None:
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_default_size(300, 60)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        
        # Position top right
        screen = Gdk.Screen.get_default()
        if screen:
            screen_w = screen.get_width()
            self.move(screen_w - 320, 40)
            
        provider = Gtk.CssProvider()
        provider.load_from_data(self._CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.get_style_context().add_class("toast-box")
        
        lbl_title = Gtk.Label(label=notif.title)
        lbl_title.set_halign(Gtk.Align.START)
        lbl_title.get_style_context().add_class("toast-title")
        box.pack_start(lbl_title, False, False, 0)
        
        lbl_body = Gtk.Label(label=notif.body)
        lbl_body.set_halign(Gtk.Align.START)
        lbl_body.set_line_wrap(True)
        lbl_body.get_style_context().add_class("toast-body")
        box.pack_start(lbl_body, False, False, 0)
        
        self.add(box)
        
        # Auto-destroy after 4 seconds
        GLib.timeout_add(4000, self._destroy_self)

    def _destroy_self(self) -> bool:
        self.destroy()
        return False


class NotificationManager:
    """Backend daemon to track notifications and listen to a Unix socket."""
    
    SOCKET_PATH = "/tmp/easedesk_notify.sock"

    def __init__(self):
        self.history: list[Notification] = []
        self.on_new_notification: Callable[[Notification], None] | None = None
        self._start_socket_listener()

    def add_notification(self, title: str, body: str, app_name: str = "System"):
        notif = Notification(title=title, body=body, app_name=app_name)
        self.history.append(notif)
        # Show Toast
        toast = ToastWindow(notif)
        toast.show_all()
        # Fire callback
        if self.on_new_notification:
            self.on_new_notification(notif)

    def clear_all(self):
        self.history.clear()

    def _start_socket_listener(self):
        if os.path.exists(self.SOCKET_PATH):
            try:
                os.unlink(self.SOCKET_PATH)
            except OSError:
                pass
        
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.SOCKET_PATH)
        self.sock.listen(5)
        
        t = threading.Thread(target=self._accept_loop, daemon=True)
        t.start()

    def _accept_loop(self):
        while True:
            try:
                conn, _ = self.sock.accept()
                data = conn.recv(4096).decode("utf-8").strip()
                if data:
                    try:
                        # Try parsing as JSON first
                        payload = json.loads(data)
                        title = payload.get("title", "Notification")
                        body = payload.get("body", "")
                        app = payload.get("app", "System")
                    except json.JSONDecodeError:
                        # Fallback to raw text
                        title = "Message"
                        body = data
                        app = "System"
                    
                    # Must schedule GUI updates on main thread
                    GLib.idle_add(self.add_notification, title, body, app)
                conn.close()
            except Exception:
                pass
