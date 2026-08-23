import re

with open("desktop/shell/shell.py", "r") as f:
    content = f.read()

# 1. Replace _build_ui logic
build_ui_pattern = r"outer\.pack_end\(self\._build_bottom_panel\(\), False, False, 0\).*?self\.overlay\.add\(outer\)"
build_ui_repl = """  # Top Bar
  self.top_bar = self._build_top_bar()
  self.top_bar.set_valign(Gtk.Align.START)
  self.top_bar.set_halign(Gtk.Align.FILL)
  self.overlay.add_overlay(self.top_bar)

  # Bottom Taskbar
  self.bottom_taskbar = self._build_bottom_taskbar()
  self.bottom_taskbar.set_valign(Gtk.Align.END)
  self.bottom_taskbar.set_halign(Gtk.Align.FILL)
  self.overlay.add_overlay(self.bottom_taskbar)

  self._build_icon_column()
  self.overlay.add(outer)"""
content = re.sub(build_ui_pattern, build_ui_repl, content, flags=re.DOTALL)

# 2. Replace _build_bottom_panel and _popup_activities with the new methods
panel_start = content.find("def _build_bottom_panel(self)")
icon_col_start = content.find("def _build_icon_column(self)")

if panel_start != -1 and icon_col_start != -1:
    new_methods = """def _build_top_bar(self):
  bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
  bar.get_style_context().add_class("top-bar")
  bar.set_size_request(-1, 32)
  
  left_lbl = Gtk.Label(label=" ease-Desk Workstation")
  left_lbl.get_style_context().add_class("topbar-clock")
  bar.pack_start(left_lbl, False, False, 8)
  
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

 def _build_bottom_taskbar(self):
  bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
  bar.get_style_context().add_class("bottom-taskbar")
  bar.set_size_request(-1, 40)
  
  left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
  left_box.set_margin_start(8)
  
  app_btn = Gtk.Button()
  app_btn.add(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("application-x-executable", size=24)))
  app_btn.get_style_context().add_class("taskbar-btn")
  left_box.pack_start(app_btn, False, False, 0)
  
  file_btn = Gtk.Button()
  file_btn.add(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("system-file-manager", size=24)))
  file_btn.get_style_context().add_class("taskbar-btn")
  file_btn.connect("clicked", lambda *_: GLib.idle_add(self._launch_path, "/opt/ease-desk/file_manager/app.py"))
  left_box.pack_start(file_btn, False, False, 0)
  
  set_btn = Gtk.Button()
  set_btn.add(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("preferences-system", size=24)))
  set_btn.get_style_context().add_class("taskbar-btn")
  set_btn.connect("clicked", lambda *_: GLib.idle_add(self._launch_path, "/opt/ease-desk/desktop/settings/app.py"))
  left_box.pack_start(set_btn, False, False, 0)
  
  bar.pack_start(left_box, False, False, 0)
  
  right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
  right_box.set_margin_end(8)
  
  pwr_btn = Gtk.Button()
  pwr_btn.add(Gtk.Image.new_from_pixbuf(get_icon_pixbuf("system-shutdown", size=20)))
  pwr_btn.get_style_context().add_class("taskbar-btn-power")
  pwr_btn.connect("clicked", lambda *_: self._exit())
  right_box.pack_end(pwr_btn, False, False, 0)
  
  bar.pack_end(right_box, False, False, 0)
  
  return bar

 """
    content = content[:panel_start] + new_methods + content[icon_col_start:]

with open("desktop/shell/shell.py", "w") as f:
    f.write(content)
