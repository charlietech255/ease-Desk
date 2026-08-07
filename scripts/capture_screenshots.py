"""Automated high-fidelity screenshot capture tool for ease-Desk.

Directly captures pixel-perfect window surfaces from GTK3:
1. screenshots/desktop-empty.png (Desktop Shell)
2. screenshots/desktop-this-pc.png (This PC & Disks)
3. screenshots/desktop-file-manager.png (File Manager)
4. screenshots/desktop-terminal.png (Terminal Emulator)
5. screenshots/desktop-task-manager.png (Task Manager & Resource Monitor)
"""

from __future__ import annotations

import os
import shutil
import sys
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from desktop.shell.shell import DesktopShell
from desktop.task_manager.task_manager import TaskManagerWindow
from desktop.terminal.terminal import TerminalWindow
from file_manager.gui import FileManagerWindow
SCREENSHOTS_DIR = os.path.join(ROOT_DIR, "screenshots")
SAMPLE_DIR = os.path.join(ROOT_DIR, "sample_vps")


def create_sample_fs() -> str:
    """Create a realistic sample VPS directory."""
    target = "/var/www" if os.access("/var/www", os.W_OK) else SAMPLE_DIR
    if target == SAMPLE_DIR:
        os.makedirs(os.path.join(target, "html"), exist_ok=True)
        os.makedirs(os.path.join(target, "assets"), exist_ok=True)
        os.makedirs(os.path.join(target, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(target, "api"), exist_ok=True)
        os.makedirs(os.path.join(target, "config"), exist_ok=True)

        with open(os.path.join(target, "index.php"), "w") as f:
            f.write("<?php phpinfo(); ?>\n")
        with open(os.path.join(target, "README.md"), "w") as f:
            f.write("# Web Server Root\n")
        with open(os.path.join(target, "config.json"), "w") as f:
            f.write('{\n  "app": "charlie-vps",\n  "version": "1.0.0"\n}\n')
        with open(os.path.join(target, "assets", "style.css"), "w") as f:
            f.write("body { background: #161b29; }\n")
        with open(os.path.join(target, "assets", "app.js"), "w") as f:
            f.write("console.log('App ready');\n")
    return target


def capture_gtk_window(window: Gtk.Window, output_path: str) -> bool:
    """Pump the GTK event loop until the window is fully realized, rendered, and save pixbuf."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    window.show_all()

    # Flush iterations to process redraws and style updates
    for _ in range(60):
        Gtk.main_iteration_do(False)
    time.sleep(0.3)
    for _ in range(40):
        Gtk.main_iteration_do(False)

    gdk_win = window.get_window()
    if not gdk_win:
        return False

    w = gdk_win.get_width()
    h = gdk_win.get_height()
    pix = Gdk.pixbuf_get_from_window(gdk_win, 0, 0, w, h)
    if pix:
        pix.savev(output_path, "png", [], [])
        return os.path.exists(output_path)
    return False


def main() -> int:
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    sample_path = create_sample_fs()

    print("Starting screenshot capture process...")

    # 1. Desktop Shell
    print("Capturing desktop-empty.png...")
    shell = DesktopShell()
    empty_out = os.path.join(SCREENSHOTS_DIR, "desktop-empty.png")
    if capture_gtk_window(shell.window, empty_out):
        print(f"✓ Saved {empty_out}")
    else:
        print(f"✗ Failed {empty_out}")
    shell.window.destroy()

    # 2. This PC Window
    print("Capturing desktop-this-pc.png...")
    thispc_win = FileManagerWindow(start_path="thispc://")
    thispc_out = os.path.join(SCREENSHOTS_DIR, "desktop-this-pc.png")
    if capture_gtk_window(thispc_win, thispc_out):
        print(f"✓ Saved {thispc_out}")
    else:
        print(f"✗ Failed {thispc_out}")
    thispc_win.destroy()

    # 3. File Manager Window
    print("Capturing desktop-file-manager.png...")
    fm_win = FileManagerWindow(start_path=sample_path)
    fm_out = os.path.join(SCREENSHOTS_DIR, "desktop-file-manager.png")
    if capture_gtk_window(fm_win, fm_out):
        print(f"✓ Saved {fm_out}")
    else:
        print(f"✗ Failed {fm_out}")
    fm_win.destroy()

    # 4. Terminal Emulator Window
    print("Capturing desktop-terminal.png...")
    term_win = TerminalWindow(initial_dir=sample_path)
    if term_win.term and term_win.term.master_fd:
        try:
            os.write(term_win.term.master_fd, b"ls -la --color=auto\n")
        except OSError:
            pass
    time.sleep(0.5)
    term_out = os.path.join(SCREENSHOTS_DIR, "desktop-terminal.png")
    if capture_gtk_window(term_win, term_out):
        print(f"✓ Saved {term_out}")
    else:
        print(f"✗ Failed {term_out}")
    term_win.destroy()

    # 5. Task Manager Window
    print("Capturing desktop-task-manager.png...")
    task_win = TaskManagerWindow()
    task_out = os.path.join(SCREENSHOTS_DIR, "desktop-task-manager.png")
    if capture_gtk_window(task_win, task_out):
        print(f"✓ Saved {task_out}")
    else:
        print(f"✗ Failed {task_out}")
    task_win.destroy()

    print("\nAll screenshots updated successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
