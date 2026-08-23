import re

with open("desktop/shell/game_changer.py", "r") as f:
    content = f.read()

spotlight_pattern = r'class SpotlightWindow\(Gtk\.Window\):\s*""".*?_CSS = b"""(.*?)"""'
spotlight_repl = r'''class SpotlightWindow(Gtk.Window):
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
    """'''

dashboard_pattern = r'class DashboardPanel\(Gtk\.Revealer\):\s*""".*?_CSS = b"""(.*?)"""'
dashboard_repl = r'''class DashboardPanel(Gtk.Revealer):
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
    """'''

content = re.sub(spotlight_pattern, spotlight_repl, content, flags=re.DOTALL)
content = re.sub(dashboard_pattern, dashboard_repl, content, flags=re.DOTALL)

with open("desktop/shell/game_changer.py", "w") as f:
    f.write(content)
