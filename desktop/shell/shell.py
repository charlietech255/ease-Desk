"""ease-Desk Shell — Next-Gen Modern Desktop Environment Shell.

Features:
- Translucent Glassmorphism Topbar & Floating Island Dock.
- Pinned Applications with Active Process Glow Indicators.
- Dynamic Running Applications Taskbar with Window/Process Focus.
- Live System Status Tray (Real-time CPU % and RAM % Gauges).
- Crisp Digital Clock & Date Widget with Interactive Calendar & Uptime Flyout.
- Signature Wallpaper Engine & Custom Theme Manager.
- High-definition Desktop Glass Cards with Grid Layout & Context Menus.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango # noqa: E402

from desktop.shell.game_changer import DashboardPanel, SpotlightWindow
from shared.utilities import animate, sysinfo, wallpaper # noqa: E402
from shared.utilities.icons import get_icon_pixbuf # noqa: E402
from shared.utilities.wallpaper import ( # noqa: E402
 CONFIG_DIR,
 CONFIG_FILE,
 DEFAULT_WALLPAPER,
 IMAGE_EXTENSIONS,
 SOLID_COLOR_PRESETS,
 WALLPAPER_MODES,
 WALLPAPER_PRESETS,
 cycle_next_wallpaper,
 get_thumbnail_pixbuf,
 get_wallpaper_config,
 hex_to_rgb,
 set_wallpaper,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ICON_PRESETS = [
 ("️", "This PC"),
 ("", "Folder"),
 ("️", "Drive / Storage"),
 ("", "Quick Launch"),
 ("", "Web (/var/www)"),
 ("", "Logs (/var/log)"),
 ("️", "Config (/etc)"),
 ("", "Terminal"),
 ("", "Backup"),
 ("", "Packages"),
]

PINNED_APPS_CONFIG = [
 {
  "id": "browser",
  "name": "Web Browser",
  "icon_key": "browser",
  "target": "app://browser",
  "tooltip": "Fast Web Browser (Google Chrome / Epiphany)",
 },
 {
  "id": "this_pc",
  "name": "This PC",
  "icon_key": "computer",
  "target": "thispc://",
  "tooltip": "Files, Storage & Drives",
 },
 {
  "id": "terminal",
  "name": "Terminal",
  "icon_key": "terminal",
  "target": "app://terminal",
  "tooltip": "Embedded Terminal Console",
 },
 {
  "id": "task_manager",
  "name": "Task Manager",
  "icon_key": "task_manager",
  "target": "app://task_manager",
  "tooltip": "Process & Resource Monitor",
 },
 {
  "id": "settings",
  "name": "System Settings",
  "icon_key": "settings",
  "target": "app://settings",
  "tooltip": "System Settings & Updates",
 },
 {
  "id": "media_player",
  "name": "Media Player",
  "icon_key": "media",
  "target": "app://media_player",
  "tooltip": "Play Music & Video",
 },
]


def _get_browser_command() -> tuple[list[str], dict[str, str]] | None:
 env = os.environ.copy()
 env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
 env["WEBKIT_FORCE_SANDBOX"] = "0"
 env["WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS"] = "1"
 if not env.get("DISPLAY"):
  env["DISPLAY"] = ":0"

 # 1. Chromium / Chrome (requires sandbox & GPU flags when run as root on VPS)
 for b in (
  "google-chrome-stable",
  "google-chrome",
  "chromium-browser",
  "chromium",
 ):
  bin_path = shutil.which(b)
  if bin_path:
   cmd = [
    bin_path,
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--password-store=basic",
    "--test-type",
    "https://google.com",
   ]
   return cmd, env

 # 2. Firefox / Firefox ESR
 for b in ("firefox-esr", "firefox"):
  bin_path = shutil.which(b)
  if bin_path:
   cmd = [bin_path, "-no-remote", "https://google.com"]
   return cmd, env

 # 3. Epiphany / WebKit / Midori / Min
 for b in ("epiphany-browser", "epiphany", "midori", "min", "x-www-browser"):
  bin_path = shutil.which(b)
  if bin_path:
   cmd = [bin_path, "https://google.com"]
   return cmd, env

 return None




class DesktopShell:
 def __init__(self) -> None:
  settings = Gtk.Settings.get_default()
  if settings:
      settings.set_property("gtk-application-prefer-dark-theme", True)

  self.children: list[int] = []
  self.tracked_processes: dict[int, dict] = {}
  self.desktop_items: list[dict] = []
  self.icon_buttons: dict[str, Gtk.Button] = {}
  self.pinned_buttons: dict[str, Gtk.Button] = {}
  self.pinned_indicators: dict[str, Gtk.Widget] = {}
  self.selected_id: str | None = None
  self.drag_widget: Gtk.Widget | None = None
  self.drag_item: dict | None = None
  self.drag_offset_x: int = 0
  self.drag_offset_y: int = 0
  self.wallpaper_path: str = DEFAULT_WALLPAPER
  self.wallpaper_mode: str = "fill"
  self.solid_color: str = "#050505"
  self.wallpaper_pixbuf: GdkPixbuf.Pixbuf | None = None
  self._cached_scaled_pixbuf: GdkPixbuf.Pixbuf | None = None
  self._cached_draw_params: tuple[int, int, str, str, str] | None = None
  self._cached_offsets: tuple[int, int] = (0, 0)
  self._cached_bg_rgb: tuple[float, float, float] = (0.031, 0.043, 0.067)
  self._config_mtime: float = 0.0
  self._cal_window: Gtk.Window | None = None
  self.spotlight: SpotlightWindow | None = None

  self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
  self.window.set_app_paintable(True)
  self.window.get_style_context().add_class("shell")
  self.window.set_title("ease-Desk")
  self.window.set_decorated(False)
  self.window.set_default_size(1280, 720)
  self.window.fullscreen()

  self.window.connect("draw", self._on_draw_background)
  self.window.connect("delete-event", self._on_delete_event)
  self.window.connect("key-press-event", self._on_key_press)

  screen = Gdk.Screen.get_default()
  if screen is not None:
   screen.connect("size-changed", self._on_screen_size_changed)

  self._load_config()
  self._load_wallpaper()
  self._load_css()
  self._build_ui()
  self._tick_clock_and_stats()
  self._refresh_info()

  self.window.show_all()
  GLib.timeout_add_seconds(1, self._tick_clock_and_stats)
  GLib.timeout_add_seconds(5, self._refresh_info)
  animate.fade_in(self.window, duration_ms=300)

 def _on_screen_size_changed(self, screen: Gdk.Screen) -> None:
  w = screen.get_width()
  h = screen.get_height()
  self.window.resize(w, h)
  # In case the resize doesn't trigger a draw correctly due to lack of WM
  self.window.queue_draw()

 # --------------------------------------------------------------- WALLPAPER
 def _load_wallpaper(self) -> None:
  wp_conf = get_wallpaper_config(CONFIG_FILE)
  self.wallpaper_path = wp_conf.get("wallpaper", DEFAULT_WALLPAPER)
  self.wallpaper_mode = wp_conf.get("wallpaper_mode", "fill")
  self.solid_color = wp_conf.get("solid_color", "#050505")

  if self.wallpaper_mode == "solid":
   self.wallpaper_pixbuf = None
  elif self.wallpaper_path and os.path.exists(self.wallpaper_path):
   try:
    self.wallpaper_pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.wallpaper_path)
   except Exception:
    self.wallpaper_pixbuf = None
  else:
   self.wallpaper_pixbuf = None

  self._cached_draw_params = None
  if os.path.exists(CONFIG_FILE):
   try:
    self._config_mtime = os.path.getmtime(CONFIG_FILE)
   except Exception:
    pass
  self.window.queue_draw()

 def _compute_scaled_wallpaper(self, w: int, h: int) -> None:
  if self.wallpaper_mode == "solid" or self.wallpaper_pixbuf is None:
   self._cached_scaled_pixbuf = None
   self._cached_offsets = (0, 0)
   self._cached_bg_rgb = hex_to_rgb(self.solid_color)
   return

  pw = max(1, self.wallpaper_pixbuf.get_width())
  ph = max(1, self.wallpaper_pixbuf.get_height())

  if self.wallpaper_mode == "fill":
   scale = max(w / pw, h / ph)
   dw = max(1, int(pw * scale))
   dh = max(1, int(ph * scale))
   dx = (w - dw) // 2
   dy = (h - dh) // 2
   self._cached_scaled_pixbuf = self.wallpaper_pixbuf.scale_simple(
    dw, dh, GdkPixbuf.InterpType.BILINEAR
   )
   self._cached_offsets = (dx, dy)
   self._cached_bg_rgb = (0.031, 0.043, 0.067)
  elif self.wallpaper_mode == "fit":
   scale = min(w / pw, h / ph)
   dw = max(1, int(pw * scale))
   dh = max(1, int(ph * scale))
   dx = (w - dw) // 2
   dy = (h - dh) // 2
   self._cached_scaled_pixbuf = self.wallpaper_pixbuf.scale_simple(
    dw, dh, GdkPixbuf.InterpType.BILINEAR
   )
   self._cached_offsets = (dx, dy)
   self._cached_bg_rgb = hex_to_rgb(self.solid_color)
  elif self.wallpaper_mode == "stretch":
   self._cached_scaled_pixbuf = self.wallpaper_pixbuf.scale_simple(
    w, h, GdkPixbuf.InterpType.BILINEAR
   )
   self._cached_offsets = (0, 0)
   self._cached_bg_rgb = (0.0, 0.0, 0.0)
  elif self.wallpaper_mode == "center":
   dx = (w - pw) // 2
   dy = (h - ph) // 2
   self._cached_scaled_pixbuf = self.wallpaper_pixbuf
   self._cached_offsets = (dx, dy)
   self._cached_bg_rgb = hex_to_rgb(self.solid_color)
  else:
   self._cached_scaled_pixbuf = None
   self._cached_offsets = (0, 0)
   self._cached_bg_rgb = (0.031, 0.043, 0.067)

 def _on_draw_background(self, widget: Gtk.Widget, cr) -> bool:
  alloc = widget.get_allocation()
  w, h = max(1, alloc.width), max(1, alloc.height)
  draw_key = (w, h, self.wallpaper_path, self.wallpaper_mode, self.solid_color)

  if self._cached_draw_params != draw_key:
   self._compute_scaled_wallpaper(w, h)
   self._cached_draw_params = draw_key

  bg_r, bg_g, bg_b = self._cached_bg_rgb
  cr.set_source_rgb(bg_r, bg_g, bg_b)
  cr.paint()

  if self._cached_scaled_pixbuf is not None:
   dx, dy = self._cached_offsets
   Gdk.cairo_set_source_pixbuf(cr, self._cached_scaled_pixbuf, dx, dy)
   cr.paint()
   # Subtle modern dark vignette for deep contrast
   if self.wallpaper_mode in ("fill", "stretch"):
    cr.set_source_rgba(0, 0, 0, 0.10)
    cr.paint()

  return False

 # --------------------------------------------------------------- CONFIG
 def _load_config(self) -> None:
  os.makedirs(CONFIG_DIR, exist_ok=True)
  default_items = [
   {
    "id": "this_pc",
    "name": "This PC",
    "icon": "️",
    "path": "thispc://",
    "icon_key": "computer",
   },
   {
    "id": "browser",
    "name": "Web Browser",
    "icon": "",
    "path": "app://browser",
    "icon_key": "browser",
   },
   {
    "id": "terminal",
    "name": "Terminal",
    "icon": "",
    "path": "app://terminal",
    "icon_key": "terminal",
   },
   {
    "id": "task_manager",
    "name": "Task Manager",
    "icon": "",
    "path": "app://task_manager",
    "icon_key": "task_manager",
   },
   {
    "id": "web_root",
    "name": "Web Root",
    "icon": "",
    "path": "/var/www",
    "icon_key": "webroot",
   },
  ]
  self.wallpaper_path = DEFAULT_WALLPAPER
  self.wallpaper_mode = "fill"
  self.solid_color = "#050505"

  if os.path.exists(CONFIG_FILE):
   try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
     data = json.load(f)
     items = data.get("items", default_items)
     for it in items:
      if it.get("id") in ("file_manager", "fm") or it.get("name") in ("File Manager", "Files"):
       it["name"] = "This PC"
       it["icon"] = "️"
       it["path"] = "thispc://"
     existing_ids = {it.get("id") for it in items}
     for default_it in default_items:
      if default_it["id"] not in existing_ids and default_it["id"] in ("browser", "terminal", "task_manager"):
       items.append(default_it)

     self.desktop_items = items
     saved_wp = data.get("wallpaper", DEFAULT_WALLPAPER)
     # Auto-upgrade previous default or missing wallpapers to new signature Horizon
     if (not os.path.exists(saved_wp)) or any(w in saved_wp for w in ("charlie-tech.png", "kali-cubes-purple.jpg", "kali-waves.png")):
      self.wallpaper_path = DEFAULT_WALLPAPER
     else:
      self.wallpaper_path = saved_wp
     self.wallpaper_mode = data.get("wallpaper_mode", "fill")
     self.solid_color = data.get("solid_color", "#050505")
     return
   except Exception:
    pass
  self.desktop_items = default_items

 def _save_config(self) -> None:
  os.makedirs(CONFIG_DIR, exist_ok=True)
  try:
   with open(CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump({
     "items": self.desktop_items,
     "wallpaper": self.wallpaper_path,
     "wallpaper_mode": self.wallpaper_mode,
     "solid_color": self.solid_color,
    }, f, indent=2)
   self._config_mtime = os.path.getmtime(CONFIG_FILE)
  except Exception:
   pass

 # ------------------------------------------------------------------ CSS
 def _load_css(self) -> None:
  provider = Gtk.CssProvider()
  css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme.css")
  provider.load_from_path(css_path)
  screen = Gdk.Screen.get_default()
  if screen is not None:
   Gtk.StyleContext.add_provider_for_screen(
    screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
   )

 # ------------------------------------------------------------------ UI
 def _build_ui(self) -> None:
  # We use an Overlay so we can float the bottom dock easily over the desktop
  self.overlay = Gtk.Overlay()
  
  outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
  
  # Main Desktop Area
  desk_event = Gtk.EventBox()
  desk_event.set_visible_window(False)
  desk_event.connect("button-press-event", self._on_desktop_click)

  self.desktop_fixed = Gtk.Fixed()
  self.desktop_fixed.set_margin_end(8)
  
  desk_event.add(self.desktop_fixed)
  outer.pack_start(desk_event, True, True, 0)
  
  # Deepin-style Unified Bottom Panel
    # Top Bar
  self.top_bar = self._build_top_bar()
  self.top_bar.set_valign(Gtk.Align.START)
  self.top_bar.set_halign(Gtk.Align.FILL)
  self.overlay.add_overlay(self.top_bar)

  # Left Dock
  self.left_dock = self._build_left_dock()
  self.left_dock.set_valign(Gtk.Align.CENTER)
  self.left_dock.set_halign(Gtk.Align.START)
  self.overlay.add_overlay(self.left_dock)

  # Bottom Center Dock
  self.bottom_dock = self._build_bottom_dock()
  self.bottom_dock.set_valign(Gtk.Align.END)
  self.bottom_dock.set_halign(Gtk.Align.CENTER)
  self.overlay.add_overlay(self.bottom_dock)

  self._build_icon_column()
  self.overlay.add(outer)
  


  # Slide-out Dashboard
  self.dashboard = DashboardPanel(self)
  self.overlay.add_overlay(self.dashboard)

  self.window.add(self.overlay)
  
  # Spotlight Window
  self.spotlight = SpotlightWindow(self)
  
  # Bottom hint (hidden or moved; let's omit for clean look or place in info panel, but omitte # ---------------------------------------------------------- UNIFIED BOTTOM PANEL
 def _build_top_bar(self) -> Gtk.Widget:
  bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
  bar.get_style_context().add_class("top-bar")
  bar.set_size_request(-1, 32)
  right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
  right_box.set_margin_end(16)
  
  wifi_img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf("network-wireless", size=16))
  wifi_img.get_style_context().add_class("topbar-icon")
  right_box.pack_start(wifi_img, False, False, 0)
  
  bat_img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf("battery-good", size=16))
  bat_img.get_style_context().add_class("topbar-icon")
  right_box.pack_start(bat_img, False, False, 0)
  
  self.clock_time_label = Gtk.Label(label="11:05 AM")
  self.clock_time_label.get_style_context().add_class("topbar-clock")
  right_box.pack_start(self.clock_time_label, False, False, 0)
  
  bar.pack_end(right_box, False, False, 0)
  return bar

 def _build_left_dock(self) -> Gtk.Widget:
  dock_event = Gtk.EventBox()
  dock_event.set_visible_window(False)
  dock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
  dock.get_style_context().add_class("left-dock")
  dock.set_margin_start(16)
  
  arrow_btn = Gtk.Button()
  arrow_btn.set_label(">")
  arrow_btn.get_style_context().add_class("left-dock-btn-arrow")
  dock.pack_start(arrow_btn, False, False, 0)
  
  set_btn = Gtk.Button()
  set_btn.add(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("preferences-system", size=24)))
  set_btn.get_style_context().add_class("left-dock-btn")
  set_btn.connect("clicked", lambda *_: GLib.idle_add(self._launch_path, "/opt/ease-desk/desktop/settings/app.py"))
  dock.pack_start(set_btn, False, False, 0)
  
  file_btn = Gtk.Button()
  file_btn.add(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("system-file-manager", size=24)))
  file_btn.get_style_context().add_class("left-dock-btn")
  file_btn.connect("clicked", lambda *_: GLib.idle_add(self._launch_path, "/opt/ease-desk/file_manager/app.py"))
  dock.pack_start(file_btn, False, False, 0)
  
  app_btn = Gtk.Button()
  app_btn.add(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("application-x-executable", size=24)))
  app_btn.get_style_context().add_class("left-dock-btn")
  dock.pack_start(app_btn, False, False, 0)
  
  pwr_btn = Gtk.Button()
  pwr_btn.add(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("system-shutdown", size=24)))
  pwr_btn.get_style_context().add_class("left-dock-btn-power")
  pwr_btn.connect("clicked", lambda *_: self._exit())
  dock.pack_start(pwr_btn, False, False, 0)
  
  dock_event.add(dock)
  return dock_event

 def _build_bottom_dock(self) -> Gtk.Widget:
  dock_event = Gtk.EventBox()
  dock_event.set_visible_window(False)
  dock = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
  dock.get_style_context().add_class("bottom-dock")
  dock.set_margin_bottom(16)
  
  file_btn = Gtk.Button()
  file_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
  file_box.pack_start(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("system-file-manager", size=28)), False, False, 0)
  lbl = Gtk.Label(label="Files")
  lbl.get_style_context().add_class("bottom-dock-label")
  file_box.pack_start(lbl, False, False, 0)
  file_btn.add(file_box)
  file_btn.get_style_context().add_class("bottom-dock-btn")
  file_btn.connect("clicked", lambda *_: GLib.idle_add(self._launch_path, "/opt/ease-desk/file_manager/app.py"))
  
  dock.pack_start(file_btn, False, False, 0)
  dock_event.add(dock)
  return dock_event

 def _build_icon_column(self) -> None:
  for child in self.desktop_fixed.get_children():
   self.desktop_fixed.remove(child)
  self.icon_buttons.clear()

  current_x = 0
  current_y = 0
  icon_width = 80
  icon_height = 90
  max_y = 600

  for item in self.desktop_items:
   btn = self._create_icon_button(item)
   self.icon_buttons[item["id"]] = btn
   
   x = item.get("x")
   y = item.get("y")
   
   if x is None or y is None:
    x = current_x
    y = current_y
    item["x"] = x
    item["y"] = y
    
    current_y += icon_height
    if current_y > max_y:
     current_y = 0
     current_x += icon_width

   self.desktop_fixed.put(btn, x, y)

  self.desktop_fixed.show_all()

 def _create_icon_button(self, item: dict) -> Gtk.Button:
  btn = Gtk.Button()
  btn.get_style_context().add_class("icon-btn")
  btn.set_relief(Gtk.ReliefStyle.NONE)

  box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
  box.set_halign(Gtk.Align.CENTER)

  item_id = item.get("id", "").lower()
  item_name = item.get("name", "").lower()
  if "pc" in item_id or "this pc" in item_name or "computer" in item_name:
   icon_key = "computer"
  elif "terminal" in item_id or "terminal" in item_name or "console" in item_name or "bash" in item_name:
   icon_key = "terminal"
  elif "task" in item_id or "task manager" in item_name or "activity" in item_name or "monitor" in item_name:
   icon_key = "task_manager"
  elif "browser" in item_id or "web" in item_id or "www" in item_name or "web root" in item_name:
   icon_key = "browser" if "browser" in item_id or "browser" in item_name else "webroot"
  elif "trash" in item_id or "trash" in item_name:
   icon_key = "trash"
  else:
   icon_key = item.get("icon_key", "folder")

  img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf(icon_key, size=48))
  box.pack_start(img, False, False, 2)

  name_lbl = Gtk.Label(label=item.get("name", "Item"))
  name_lbl.get_style_context().add_class("icon-name")
  name_lbl.set_line_wrap(True)
  name_lbl.set_max_width_chars(12)
  name_lbl.set_justify(Gtk.Justification.CENTER)
  box.pack_start(name_lbl, False, False, 0)

  btn.add(box)
  btn.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
  btn.connect("realize", lambda w: w.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2)))
  btn.connect("button-press-event", lambda w, ev, it=item: self._on_icon_click(w, ev, it))
  btn.connect("motion-notify-event", self._on_icon_motion)
  btn.connect("button-release-event", self._on_icon_release)
  return btn

 # ------------------------------------------------------------ EVENTS
 def _on_icon_click(self, widget: Gtk.Widget, event: Gdk.EventButton, item: dict) -> bool:
  item_id = item["id"]

  if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
   self._launch_path(item.get("path", os.path.expanduser("~")))
   return True

  if event.button == 1:
   self._select_icon(item_id)
   self.drag_widget = widget
   self.drag_item = item
   self.drag_offset_x = int(event.x)
   self.drag_offset_y = int(event.y)
   return True

  if event.button == 3:
   self._select_icon(item_id)
   self._show_icon_menu(event, item)
   return True

  return False

 def _on_icon_motion(self, widget: Gtk.Widget, event: Gdk.EventMotion) -> bool:
  if self.drag_widget == widget and self.drag_item:
   if not (event.get_state() & Gdk.ModifierType.BUTTON1_MASK):
    return False
    
   dx = int(event.x) - self.drag_offset_x
   dy = int(event.y) - self.drag_offset_y
   
   current_x = self.drag_item.get("x", 0)
   current_y = self.drag_item.get("y", 0)
   
   new_x = current_x + dx
   new_y = current_y + dy
   
   # Prevent dragging way out of bounds
   alloc = self.desktop_fixed.get_allocation()
   new_x = max(0, min(new_x, alloc.width - 64))
   new_y = max(0, min(new_y, alloc.height - 64))
   
   self.desktop_fixed.move(widget, new_x, new_y)
   self.drag_item["x"] = new_x
   self.drag_item["y"] = new_y
   return True
  return False

 def _on_icon_release(self, widget: Gtk.Widget, event: Gdk.EventButton) -> bool:
  if self.drag_widget == widget and self.drag_item:
   self.drag_widget = None
   self.drag_item = None
   self._save_config()
   return True
  return False

 def _on_desktop_click(self, widget: Gtk.Widget, event: Gdk.EventButton) -> bool:
  if event.button == 1:
   self._deselect_all()
   return True
  if event.button == 3:
   self._deselect_all()
   self._show_desktop_menu(event)
   return True
  return False

 def _select_icon(self, item_id: str) -> None:
  self._deselect_all()
  self.selected_id = item_id
  btn = self.icon_buttons.get(item_id)
  if btn:
   btn.get_style_context().add_class("selected")

 def _deselect_all(self) -> None:
  self.selected_id = None
  for btn in self.icon_buttons.values():
   btn.get_style_context().remove_class("selected")

 # ----------------------------------------------------- CONTEXT MENUS
 def _show_icon_menu(self, event: Gdk.EventButton, item: dict) -> None:
  menu = Gtk.Menu()

  open_mi = Gtk.MenuItem.new_with_label(f"Open '{item.get('name')}'")
  open_mi.connect("activate", lambda *_: self._launch_path(item.get("path", "~")))
  menu.append(open_mi)

  menu.append(Gtk.SeparatorMenuItem())

  ch_icon = Gtk.MenuItem.new_with_label("Change Icon / Symbol…")
  ch_icon.connect("activate", lambda *_: self._dialog_change_icon(item))
  menu.append(ch_icon)

  rename = Gtk.MenuItem.new_with_label("Rename Shortcut…")
  rename.connect("activate", lambda *_: self._dialog_rename(item))
  menu.append(rename)

  if item.get("id") not in ("file_manager", "this_pc"):
   menu.append(Gtk.SeparatorMenuItem())
   rem = Gtk.MenuItem.new_with_label("Remove Shortcut")
   rem.connect("activate", lambda *_: self._remove_shortcut(item))
   menu.append(rem)

  menu.show_all()
  menu.popup(None, None, None, None, event.button, event.time)

 def _show_desktop_menu(self, event: Gdk.EventButton) -> None:
  menu = Gtk.Menu()

  fm_mi = Gtk.MenuItem.new_with_label("️ Open This PC")
  fm_mi.connect("activate", lambda *_: self._launch_path("thispc://"))
  menu.append(fm_mi)

  br_mi = Gtk.MenuItem.new_with_label(" Open Web Browser")
  br_mi.connect("activate", lambda *_: self._launch_path("app://browser"))
  menu.append(br_mi)

  tm_mi = Gtk.MenuItem.new_with_label(" Open Terminal")
  tm_mi.connect("activate", lambda *_: self._launch_path("app://terminal"))
  menu.append(tm_mi)

  menu.append(Gtk.SeparatorMenuItem())

  add_mi = Gtk.MenuItem.new_with_label(" Add Desktop Shortcut…")
  add_mi.connect("activate", lambda *_: self._dialog_add_shortcut())
  menu.append(add_mi)

  wp_mi = Gtk.MenuItem.new_with_label(" Personalize Wallpaper & Themes…")
  wp_mi.connect("activate", lambda *_: self._dialog_change_wallpaper())
  menu.append(wp_mi)

  next_wp = Gtk.MenuItem.new_with_label(" Cycle Next Wallpaper")
  next_wp.connect("activate", lambda *_: self._cycle_wallpaper())
  menu.append(next_wp)

  menu.append(Gtk.SeparatorMenuItem())

  ref_mi = Gtk.MenuItem.new_with_label(" Refresh System Probes")
  ref_mi.connect("activate", lambda *_: self._refresh_info())
  menu.append(ref_mi)

  menu.show_all()
  menu.popup(None, None, None, None, event.button, event.time)

 def _cycle_wallpaper(self) -> None:
  cycle_next_wallpaper(CONFIG_FILE)
  self._load_wallpaper()

 # ----------------------------------------------------------- DIALOGS
 def _dialog_change_wallpaper(self) -> None:
  dialog = Gtk.Dialog(
   title="Desktop Wallpaper & Themes",
   transient_for=self.window,
   modal=True,
   destroy_with_parent=True,
  )
  dialog.add_button("Close", Gtk.ResponseType.CLOSE)
  dialog.set_default_size(580, 520)
  dialog.get_style_context().add_class("wp-dialog")

  content = dialog.get_content_area()
  main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
  main_box.set_margin_start(20)
  main_box.set_margin_end(20)
  main_box.set_margin_top(16)
  main_box.set_margin_bottom(12)

  # 1. Preset Wallpapers Section
  wp_lbl = Gtk.Label(label="SIGNATURE WALLPAPER PRESETS", xalign=0)
  wp_lbl.get_style_context().add_class("wp-section-lbl")
  main_box.pack_start(wp_lbl, False, False, 0)

  card_grid = Gtk.Grid(column_spacing=12, row_spacing=12)
  card_buttons: dict[str, Gtk.Button] = {}

  def update_active_card() -> None:
   for p_path, btn in card_buttons.items():
    if self.wallpaper_mode != "solid" and os.path.abspath(self.wallpaper_path) == os.path.abspath(p_path):
     btn.get_style_context().add_class("active")
    else:
     btn.get_style_context().remove_class("active")

  for idx, (name, path) in enumerate(WALLPAPER_PRESETS):
   if not os.path.exists(path):
    continue
   card_btn = Gtk.Button()
   card_btn.get_style_context().add_class("wp-card")
   card_btn.set_relief(Gtk.ReliefStyle.NONE)

   card_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
   card_vbox.set_size_request(150, 115)

   thumb_pixbuf = get_thumbnail_pixbuf(path, 140, 85)
   if thumb_pixbuf:
    img = Gtk.Image.new_from_pixbuf(thumb_pixbuf)
   else:
    img = Gtk.Image.new_from_icon_name("image-x-generic", Gtk.IconSize.DIALOG)
   card_vbox.pack_start(img, True, True, 0)

   title_lbl = Gtk.Label(label=name)
   title_lbl.get_style_context().add_class("wp-card-name")
   title_lbl.set_ellipsize(3)
   card_vbox.pack_start(title_lbl, False, False, 0)

   card_btn.add(card_vbox)
   card_btn.connect("clicked", lambda *_, p=path: (
    self._set_wallpaper(p, mode=self.wallpaper_mode if self.wallpaper_mode != "solid" else "fill"),
    update_active_card()
   ))

   card_buttons[path] = card_btn
   card_grid.attach(card_btn, idx % 3, idx // 3, 1, 1)

  update_active_card()
  main_box.pack_start(card_grid, False, False, 0)

  # 2. Solid Colors Section
  color_lbl = Gtk.Label(label="SOLID COLOR MINIMAL THEMES", xalign=0)
  color_lbl.get_style_context().add_class("wp-section-lbl")
  main_box.pack_start(color_lbl, False, False, 2)

  color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
  color_buttons: dict[str, Gtk.Button] = {}

  def update_active_color() -> None:
   for hex_col, btn in color_buttons.items():
    if self.wallpaper_mode == "solid" and self.solid_color.lower() == hex_col.lower():
     btn.get_style_context().add_class("active")
    else:
     btn.get_style_context().remove_class("active")

  for col_name, hex_code in SOLID_COLOR_PRESETS:
   c_btn = Gtk.Button()
   c_btn.get_style_context().add_class("color-btn")
   c_btn.set_tooltip_text(f"{col_name} ({hex_code})")
   c_btn.set_size_request(56, 36)

   c_label = Gtk.Label(label=f"<span foreground='{hex_code}'>████</span>")
   c_label.set_use_markup(True)
   c_btn.add(c_label)

   c_btn.connect("clicked", lambda *_, col=hex_code: (
    self._set_solid_color(col),
    update_active_color(),
    update_active_card()
   ))
   color_buttons[hex_code] = c_btn
   color_box.pack_start(c_btn, False, False, 0)

  update_active_color()
  main_box.pack_start(color_box, False, False, 0)

  main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

  # 3. Display Mode & Custom Wallpaper Row
  ctrl_grid = Gtk.Grid(column_spacing=12, row_spacing=8)

  ctrl_grid.attach(Gtk.Label(label="Display Mode:", xalign=0), 0, 0, 1, 1)
  mode_combo = Gtk.ComboBoxText()
  for mode_key, mode_title in WALLPAPER_MODES:
   mode_combo.append(mode_key, mode_title)
  mode_combo.set_active_id(self.wallpaper_mode)

  def on_mode_changed(combo: Gtk.ComboBoxText) -> None:
   new_mode = combo.get_active_id() or "fill"
   if new_mode == "solid":
    self._set_solid_color(self.solid_color)
   else:
    self._set_wallpaper(self.wallpaper_path, mode=new_mode)
   update_active_color()
   update_active_card()

  mode_combo.connect("changed", on_mode_changed)
  ctrl_grid.attach(mode_combo, 1, 0, 1, 1)

  custom_btn = Gtk.Button.new_with_label(" Choose Custom Image…")
  custom_btn.get_style_context().add_class("wallpaper-btn")
  custom_btn.connect("clicked", lambda *_: (
   self._dialog_browse_wallpaper(dialog),
   update_active_card(),
   update_active_color()
  ))
  ctrl_grid.attach(custom_btn, 2, 0, 1, 1)

  main_box.pack_start(ctrl_grid, False, False, 4)

  content.add(main_box)
  dialog.show_all()
  dialog.run()
  dialog.destroy()

 def _set_wallpaper(self, path: str, mode: str = "fill") -> None:
  if os.path.exists(path):
   self.wallpaper_path = path
   self.wallpaper_mode = mode
   set_wallpaper(path, mode=mode, solid_color=self.solid_color, config_path=CONFIG_FILE)
   self._load_wallpaper()

 def _set_solid_color(self, color_hex: str) -> None:
  self.solid_color = color_hex
  self.wallpaper_mode = "solid"
  set_wallpaper(self.wallpaper_path, mode="solid", solid_color=color_hex, config_path=CONFIG_FILE)
  self._load_wallpaper()

 def _dialog_browse_wallpaper(self, parent_dialog: Gtk.Dialog) -> None:
  chooser = Gtk.FileChooserDialog(
   title="Select Wallpaper Image",
   transient_for=parent_dialog,
   action=Gtk.FileChooserAction.OPEN,
  )
  chooser.add_buttons(
   "Cancel", Gtk.ResponseType.CANCEL, "Set Wallpaper", Gtk.ResponseType.OK
  )

  filter_img = Gtk.FileFilter()
  filter_img.set_name("Images (*.png, *.jpg, *.jpeg, *.webp)")
  for ext in IMAGE_EXTENSIONS:
   filter_img.add_pattern(f"*{ext}")
   filter_img.add_pattern(f"*{ext.upper()}")
  chooser.add_filter(filter_img)

  preview_img = Gtk.Image()
  chooser.set_preview_widget(preview_img)

  def update_preview(c) -> None:
   filename = c.get_preview_filename()
   if filename and wallpaper.is_image_file(filename):
    thumb = get_thumbnail_pixbuf(filename, 160, 100)
    if thumb:
     preview_img.set_from_pixbuf(thumb)
     c.set_preview_widget_active(True)
     return
   c.set_preview_widget_active(False)

  chooser.connect("update-preview", update_preview)

  if chooser.run() == Gtk.ResponseType.OK:
   selected = chooser.get_filename()
   if selected and os.path.exists(selected):
    mode = self.wallpaper_mode if self.wallpaper_mode != "solid" else "fill"
    self._set_wallpaper(selected, mode=mode)
  chooser.destroy()

 def _dialog_change_icon(self, item: dict) -> None:
  dialog = Gtk.Dialog(
   title=f"Icon for '{item.get('name')}'",
   transient_for=self.window,
   modal=True,
   destroy_with_parent=True,
  )
  dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
  dialog.add_button("Apply", Gtk.ResponseType.OK)
  dialog.set_default_size(360, 240)

  content = dialog.get_content_area()
  vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
  vbox.set_margin_start(16)
  vbox.set_margin_end(16)
  vbox.set_margin_top(14)
  vbox.set_margin_bottom(14)

  vbox.pack_start(Gtk.Label(label="Choose an icon / symbol:"), False, False, 0)

  grid = Gtk.Grid(column_spacing=8, row_spacing=8)
  grid.set_halign(Gtk.Align.CENTER)
  selected = [item.get("icon", "")]

  for i, (sym, label) in enumerate(ICON_PRESETS):
   btn = Gtk.Button.new_with_label(sym)
   btn.set_tooltip_text(label)
   btn.set_size_request(44, 44)
   btn.connect("clicked", lambda *_, s=sym: selected.__setitem__(0, s))
   grid.attach(btn, i % 5, i // 5, 1, 1)

  vbox.pack_start(grid, False, False, 0)

  vbox.pack_start(Gtk.Label(label="Or custom emoji / text:"), False, False, 0)
  custom = Gtk.Entry()
  custom.set_text(item.get("icon", ""))
  vbox.pack_start(custom, False, False, 0)
  content.add(vbox)
  dialog.show_all()

  if dialog.run() == Gtk.ResponseType.OK:
   item["icon"] = custom.get_text().strip() or selected[0]
   self._save_config()
   self._build_icon_column()
  dialog.destroy()

 def _dialog_rename(self, item: dict) -> None:
  dialog = Gtk.Dialog(
   title="Rename Shortcut",
   transient_for=self.window,
   modal=True,
   destroy_with_parent=True,
  )
  dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
  dialog.add_button("Save", Gtk.ResponseType.OK)
  dialog.set_default_size(320, 130)

  content = dialog.get_content_area()
  vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
  vbox.set_margin_start(16)
  vbox.set_margin_end(16)
  vbox.set_margin_top(14)
  vbox.set_margin_bottom(14)
  vbox.pack_start(Gtk.Label(label="New name:"), False, False, 0)
  entry = Gtk.Entry()
  entry.set_text(item.get("name", ""))
  entry.set_activates_default(True)
  vbox.pack_start(entry, False, False, 0)
  content.add(vbox)
  dialog.show_all()

  if dialog.run() == Gtk.ResponseType.OK:
   new_name = entry.get_text().strip()
   if new_name:
    item["name"] = new_name
    self._save_config()
    self._build_icon_column()
  dialog.destroy()

 def _dialog_add_shortcut(self) -> None:
  dialog = Gtk.Dialog(
   title="Add Desktop Shortcut",
   transient_for=self.window,
   modal=True,
   destroy_with_parent=True,
  )
  dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
  dialog.add_button("Add", Gtk.ResponseType.OK)
  dialog.set_default_size(380, 210)

  content = dialog.get_content_area()
  grid = Gtk.Grid(column_spacing=10, row_spacing=10)
  grid.set_margin_start(16)
  grid.set_margin_end(16)
  grid.set_margin_top(14)
  grid.set_margin_bottom(14)

  grid.attach(Gtk.Label(label="Name:"), 0, 0, 1, 1)
  name_e = Gtk.Entry()
  name_e.set_placeholder_text("e.g. Web Root")
  grid.attach(name_e, 1, 0, 1, 1)

  grid.attach(Gtk.Label(label="Path:"), 0, 1, 1, 1)
  path_e = Gtk.Entry()
  path_e.set_placeholder_text("e.g. /var/www")
  grid.attach(path_e, 1, 1, 1, 1)

  grid.attach(Gtk.Label(label="Icon:"), 0, 2, 1, 1)
  icon_e = Gtk.Entry()
  icon_e.set_text("")
  grid.attach(icon_e, 1, 2, 1, 1)

  content.add(grid)
  dialog.show_all()

  if dialog.run() == Gtk.ResponseType.OK:
   import uuid
   self.desktop_items.append({
    "id": str(uuid.uuid4())[:8],
    "name": name_e.get_text().strip() or "Shortcut",
    "icon": icon_e.get_text().strip() or "",
    "path": path_e.get_text().strip() or os.path.expanduser("~"),
   })
   self._save_config()
   self._build_icon_column()
  dialog.destroy()

 def _remove_shortcut(self, item: dict) -> None:
  self.desktop_items = [i for i in self.desktop_items if i.get("id") != item.get("id")]
  self._save_config()
  self._build_icon_column()

 # ------------------------------------------------------ STATUS PANEL
 def _build_info_panel(self) -> Gtk.Widget:
  frame = Gtk.Frame()
  frame.get_style_context().add_class("vps-frame")
  g = Gtk.Grid(column_spacing=16, row_spacing=5)
  g.set_margin_start(16)
  g.set_margin_end(16)
  g.set_margin_top(12)
  g.set_margin_bottom(12)

  title = Gtk.Label(label="Server Cloud Status")
  title.get_style_context().add_class("vps-title")
  title.set_halign(Gtk.Align.START)
  g.attach(title, 0, 0, 2, 1)

  self.vps_rows: list[tuple[Gtk.Label, Gtk.Label]] = []
  for i, key in enumerate(("Server", "OS", "CPU", "RAM", "Disk")):
   k = Gtk.Label(label=key)
   k.get_style_context().add_class("vps-key")
   k.set_halign(Gtk.Align.START)
   v = Gtk.Label()
   v.get_style_context().add_class("vps-val")
   v.set_halign(Gtk.Align.START)
   v.set_selectable(True)
   g.attach(k, 0, i + 1, 1, 1)
   g.attach(v, 1, i + 1, 1, 1)
   self.vps_rows.append((k, v))

  frame.add(g)
  return frame

 # ---------------------------------------------------------- PROCESS TRACKING & RUNNERS
 def _launch_path(self, target_path: str) -> None:
  app_id = "files"
  title = "Files"
  icon_key = "computer"
  env = os.environ.copy()
  env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
  env["WEBKIT_FORCE_SANDBOX"] = "0"
  env["WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS"] = "1"
  if not env.get("DISPLAY"):
   env["DISPLAY"] = ":0"

  if target_path in ("app://terminal", "terminal"):
   cmd = [sys.executable, "-m", "desktop.terminal.app", os.path.expanduser("~")]
   app_id = "terminal"
   title = "Terminal"
   icon_key = "terminal"
  elif target_path in ("app://task_manager", "task_manager"):
   cmd = [sys.executable, "-m", "desktop.task_manager.app"]
   app_id = "task_manager"
   title = "Task Manager"
   icon_key = "task_manager"
  elif target_path in ("app://settings", "settings"):
   cmd = [sys.executable, "-m", "desktop.settings.app"]
   app_id = "settings"
   title = "Settings"
   icon_key = "settings"
  elif target_path in ("app://wallpaper", "wallpaper"):
   self._dialog_change_wallpaper()
   return
  elif target_path in ("app://browser", "browser"):
   app_id = "browser"
   title = "Web Browser"
   icon_key = "browser"
   browser_spec = _get_browser_command()
   if browser_spec:
    cmd, browser_env = browser_spec
    env.update(browser_env)
   else:
    cmd = [
     sys.executable,
     "-m",
     "desktop.terminal.app",
     os.path.expanduser("~"),
    ]
  elif target_path in ("app://editor", "editor"):
   cmd = [sys.executable, "-m", "file_manager.app", os.path.expanduser("~")]
   app_id = "editor"
   title = "Editor"
   icon_key = "editor"
  elif target_path in ("app://media_player", "media_player"):
   cmd = [sys.executable, "-m", "desktop.media_player.app"]
   app_id = "media_player"
   title = "Media Player"
   icon_key = "media"
  else:
   cmd = [sys.executable, "-m", "file_manager.app", target_path]
   app_id = "this_pc" if target_path == "thispc://" else "files"
   title = "This PC" if target_path == "thispc://" else os.path.basename(target_path) or "Files"
   icon_key = "computer"

  try:
   p = subprocess.Popen(
    cmd,
    cwd=ROOT,
    env=env,
    start_new_session=True,
   )
   self.children.append(p.pid)
   self.tracked_processes[p.pid] = {
    "pid": p.pid,
    "app_id": app_id,
    "title": title,
    "icon_key": icon_key,
    "popen": p,
   }
   self._update_running_tasks_ui()
  except Exception as err:
   print(f"[ease-Desk] Error launching {target_path}: {err}", file=sys.stderr)

 def _poll_processes(self) -> None:
  dead_pids = []
  for pid, meta in list(self.tracked_processes.items()):
   popen = meta.get("popen")
   if popen is not None:
    if popen.poll() is not None:
     dead_pids.append(pid)
   else:
    try:
     os.kill(pid, 0)
    except OSError:
     dead_pids.append(pid)

  for pid in dead_pids:
   self.tracked_processes.pop(pid, None)

  if dead_pids:
   self._update_running_tasks_ui()

 def _update_running_tasks_ui(self) -> None:
  active_app_ids = {meta["app_id"] for meta in self.tracked_processes.values()}

  # 1. Update indicators on pinned dock icons
  for app_id, indicator in self.pinned_indicators.items():
   ctx = indicator.get_style_context()
   if app_id in active_app_ids:
    if not ctx.has_class("active"):
     ctx.add_class("active")
   else:
    if ctx.has_class("active"):
     ctx.remove_class("active")

  # 2. Prevent redundant widget rebuilds
  current_snapshot = tuple(
   sorted((pid, meta["title"], meta["icon_key"]) for pid, meta in self.tracked_processes.items())
  )
  if hasattr(self, "_last_tasks_snapshot") and self._last_tasks_snapshot == current_snapshot:
   return
  self._last_tasks_snapshot = current_snapshot

  # 3. Rebuild running tasks in the TOP BAR (GNOME window list style)
  target_box = getattr(self, "running_tasks_topbar_box", None)
  if target_box is None:
   return
  for child in target_box.get_children():
   target_box.remove(child)

  for pid, meta in list(self.tracked_processes.items()):
   task_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
   task_box.get_style_context().add_class("running-task-btn")

   btn = Gtk.Button()
   btn.set_relief(Gtk.ReliefStyle.NONE)
   btn.get_style_context().add_class("running-task-inner-btn")

   h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
   img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf(meta["icon_key"], size=16))
   h.pack_start(img, False, False, 0)

   lbl = Gtk.Label(label=meta["title"])
   lbl.set_max_width_chars(14)
   lbl.set_ellipsize(Pango.EllipsizeMode.END)
   h.pack_start(lbl, False, False, 0)

   btn.add(h)
   btn.connect("clicked", lambda *_, p=pid: self._focus_or_signal_proc(p))
   task_box.pack_start(btn, True, True, 0)

   close_btn = Gtk.Button.new_with_label("x")
   close_btn.set_relief(Gtk.ReliefStyle.NONE)
   close_btn.get_style_context().add_class("running-task-close-btn")
   close_btn.set_tooltip_text(f"Close {meta['title']}")
   close_btn.connect("clicked", lambda *_, p=pid: self._terminate_proc(p))
   task_box.pack_start(close_btn, False, False, 0)

   target_box.pack_start(task_box, False, False, 0)

  target_box.show_all()

 def _dialog_uninstall(self) -> None:
  dialog = Gtk.MessageDialog(
   transient_for=self.window,
   flags=0,
   message_type=Gtk.MessageType.WARNING,
   buttons=Gtk.ButtonsType.NONE,
   text="Uninstall ease-Desk?",
  )
  dialog.format_secondary_text(
   "This will permanently remove the ease-Desk environment from this server.\n"
   "You will need to provide your sudo password in the terminal that appears."
  )
  dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
  dialog.add_button("Uninstall", Gtk.ResponseType.OK)
  dialog.get_widget_for_response(Gtk.ResponseType.OK).get_style_context().add_class("destructive-action")

  response = dialog.run()
  dialog.destroy()

  if response == Gtk.ResponseType.OK:
   # Launch uninstaller in a standard xterm so it can prompt for sudo password
   try:
    subprocess.Popen(["xterm", "-T", "ease-Desk Uninstaller", "-e", "bash -c 'sudo /opt/ease-desk/scripts/uninstall.sh; echo \"Press Enter to close...\"; read'"])
   except OSError:
    pass

 def _on_process_died(self, pid: int, status: int) -> None:
  meta = self.tracked_processes.get(pid)
  if meta and meta.get("popen"):
   try:
    meta["popen"].terminate()
   except Exception:
    pass
  else:
   try:
    os.kill(pid, signal.SIGTERM)
   except OSError:
    pass
  self.tracked_processes.pop(pid, None)
  self._update_running_tasks_ui()

 def _terminate_proc(self, pid: int) -> None:
  meta = self.tracked_processes.get(pid)
  if meta and meta.get("popen"):
   try:
    meta["popen"].terminate()
   except Exception:
    pass
  else:
   try:
    os.kill(pid, signal.SIGTERM)
   except OSError:
    pass
  self.tracked_processes.pop(pid, None)
  self._update_running_tasks_ui()

 def _focus_or_signal_proc(self, pid: int) -> None:
  title = self.tracked_processes.get(pid, {}).get("title", "")
  if shutil.which("wmctrl") and title:
   subprocess.Popen(["wmctrl", "-a", title])
  elif shutil.which("xdotool") and title:
   subprocess.Popen(["xdotool", "search", "--name", title, "windowactivate"])

 # ---------------------------------------------------------- TICK & STATS
 def _tick_clock_and_stats(self) -> bool:
  # Clock & Date
  self.clock_time_label.set_text(time.strftime("%H:%M"))
  if hasattr(self, "clock_date_label"):
   self.clock_date_label.set_text(time.strftime("%a, %b %d"))

  self._poll_processes()
  return True

 def _refresh_info(self) -> bool:
  if os.path.exists(CONFIG_FILE):
   try:
    mtime = os.path.getmtime(CONFIG_FILE)
    if mtime > self._config_mtime:
     self._config_mtime = mtime
     self._load_wallpaper()
   except Exception:
    pass

  info = sysinfo.summary()
  if hasattr(self, "server_label"):
   self.server_label.set_text(f"Server: {info['hostname']}")
  if hasattr(self, "vps_rows") and len(self.vps_rows) >= 5:
   self.vps_rows[0][1].set_text(info["hostname"])
   self.vps_rows[1][1].set_text(info["os"])
   self.vps_rows[2][1].set_text(f"{info['cpu']} cores")
   self.vps_rows[3][1].set_text(f"{info['mem_used']} / {info['mem_total']}")
   self.vps_rows[4][1].set_text(f"{info['disk_used']} / {info['disk_total']}")
  return True

 def _on_key_press(self, window: Gtk.Window, event: Gdk.EventKey) -> bool:
  # Super key → toggle Activities Overview (GNOME convention)
  if event.keyval in (Gdk.KEY_Super_L, Gdk.KEY_Super_R):
   self._popup_activities()
   return True
  # Escape → close Activities if open
  if event.keyval == Gdk.KEY_Escape:
   if hasattr(self, "_activities_win") and self._activities_win is not None:
    self._activities_win.destroy()
    self._activities_win = None
    return True
  if event.keyval == Gdk.KEY_Delete and self.selected_id:
   item = next((i for i in self.desktop_items if i.get("id") == self.selected_id), None)
   if item and item.get("id") not in ("file_manager", "this_pc"):
    self._remove_shortcut(item)
    return True
  return False

 def _on_delete_event(self, window, event) -> bool:
  self._exit()
  return True

 def _exit(self) -> None:
  for pid in self.children:
   try:
    os.kill(pid, signal.SIGTERM)
   except OSError:
    pass
  animate.fade_out(self.window, duration_ms=250, on_done=Gtk.main_quit)


def main() -> int:
 if not os.environ.get("DISPLAY") or not os.environ["DISPLAY"].strip():
  from desktop.session.session import SessionManager
  print("No active $DISPLAY detected. Launching ease-Desk session manager...")
  return SessionManager().start()

 initialized = False
 for _ in range(25):
  try:
   res = Gtk.init_check()
   if isinstance(res, (tuple, list)) and res:
    if res[0]:
     initialized = True
     break
   elif bool(res):
    initialized = True
    break
  except Exception:
   pass
  time.sleep(0.2)

 if not initialized:
  print(f"Error: Unable to initialize GTK on display {os.environ.get('DISPLAY')}", file=sys.stderr)
  return 1

 DesktopShell()
 Gtk.main()
 return 0


if __name__ == "__main__":
 sys.exit(main())
