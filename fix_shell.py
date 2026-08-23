with open("desktop/shell/shell.py", "r") as f:
    content = f.read()

# Fix running_tasks_topbar_box
content = content.replace('target_box = self.running_tasks_topbar_box', 'target_box = getattr(self, "running_tasks_topbar_box", None)\n  if target_box is None:\n   return')

# Fix clock_date_label
content = content.replace('self.clock_date_label.set_text(time.strftime("%a, %b %d"))', 'if hasattr(self, "clock_date_label"):\n   self.clock_date_label.set_text(time.strftime("%a, %b %d"))')

# Fix server_label
content = content.replace('self.server_label.set_text(f"Server: {info[\'hostname\']}")', 'if hasattr(self, "server_label"):\n   self.server_label.set_text(f"Server: {info[\'hostname\']}")')

# Fix pinned indicators/buttons updates
content = content.replace('for app_id, ind in self.pinned_indicators.items():', 'if hasattr(self, "pinned_indicators"):\n   for app_id, ind in self.pinned_indicators.items():')

# Also fix running_tasks_topbar_box in _sync_running_tasks
content = content.replace('for child in self.running_tasks_topbar_box.get_children():', 'if hasattr(self, "running_tasks_topbar_box"):\n   for child in self.running_tasks_topbar_box.get_children():')

with open("desktop/shell/shell.py", "w") as f:
    f.write(content)
