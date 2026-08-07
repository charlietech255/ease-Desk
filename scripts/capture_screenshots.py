"""Automated screenshot capture tool for ease-Desk prototype.

Spawns a virtual X11 server (Xvfb), runs the ease-Desk components,
and takes exact pixel-perfect screenshots of:
1. screenshots/desktop-empty.png
2. screenshots/desktop-file-manager.png
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(ROOT_DIR, "screenshots")
SAMPLE_DIR = os.path.join(ROOT_DIR, "sample_vps")


def create_sample_fs() -> str:
    """Create a realistic sample VPS directory if /var/www is not writable locally."""
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


def capture_display(display_num: str, output_path: str) -> bool:
    """Capture root window using GDK/Cairo or scrot."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Method 1: PyGObject GdkPixbuf capture
    try:
        env = dict(os.environ)
        env["DISPLAY"] = display_num
        py_code = (
            f"import gi; gi.require_version('Gdk', '3.0'); from gi.repository import Gdk, GdkPixbuf; "
            f"screen = Gdk.Screen.get_default(); root = screen.get_root_window(); "
            f"w, h = root.get_width(), root.get_height(); "
            f"pix = Gdk.pixbuf_get_from_window(root, 0, 0, w, h); "
            f"pix.savev('{output_path}', 'png', [], [])"
        )
        proc = subprocess.run([sys.executable, "-c", py_code], env=env, timeout=10)
        if proc.returncode == 0 and os.path.exists(output_path):
            return True
    except Exception:
        pass

    # Method 2: Scrot fallback
    if shutil.which("scrot"):
        env = dict(os.environ)
        env["DISPLAY"] = display_num
        proc = subprocess.run(["scrot", output_path], env=env, timeout=10)
        if proc.returncode == 0 and os.path.exists(output_path):
            return True

    return False


def main() -> int:
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    sample_path = create_sample_fs()

    display_num = ":108"
    print(f"Starting Xvfb on {display_num} (1280x800x24)...")
    xvfb = subprocess.Popen(
        [
            "Xvfb",
            display_num,
            "-screen",
            "0",
            "1280x800x24",
            "-ac",
            "+extension",
            "GLX",
            "+render",
            "-noreset",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid,
    )
    time.sleep(0.6)

    env = dict(os.environ)
    env["DISPLAY"] = display_num
    env["PYTHONPATH"] = ROOT_DIR + os.pathsep + env.get("PYTHONPATH", "")

    wm = None
    if shutil.which("openbox"):
        wm = subprocess.Popen(
            ["openbox"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        time.sleep(0.3)

    try:
        # 1. Capture Empty Desktop
        print("Launching ease-Desk Shell...")
        shell = subprocess.Popen(
            [sys.executable, "-m", "desktop.shell.shell"],
            env=env,
            cwd=ROOT_DIR,
        )
        time.sleep(1.5)  # allow GTK fade-in and layout to render

        empty_out = os.path.join(SCREENSHOTS_DIR, "desktop-empty.png")
        print(f"Capturing {empty_out}...")
        if capture_display(display_num, empty_out):
            print("✓ Successfully captured desktop-empty.png")
        else:
            print("✗ Failed to capture desktop-empty.png")

        # 2. Capture Desktop with This PC (Partitions & Storage) Open
        print("Launching This PC (Partitions overview)...")
        thispc = subprocess.Popen(
            [sys.executable, "-m", "file_manager.app", "thispc://"],
            env=env,
            cwd=ROOT_DIR,
        )
        time.sleep(1.8)

        thispc_out = os.path.join(SCREENSHOTS_DIR, "desktop-this-pc.png")
        print(f"Capturing {thispc_out}...")
        if capture_display(display_num, thispc_out):
            print("✓ Successfully captured desktop-this-pc.png")
        else:
            print("✗ Failed to capture desktop-this-pc.png")

        # 3. Capture Desktop with File Manager Open
        print(f"Launching File Manager in {sample_path}...")
        fm = subprocess.Popen(
            [sys.executable, "-m", "file_manager.app", sample_path],
            env=env,
            cwd=ROOT_DIR,
        )
        time.sleep(1.8)

        fm_out = os.path.join(SCREENSHOTS_DIR, "desktop-file-manager.png")
        print(f"Capturing {fm_out}...")
        if capture_display(display_num, fm_out):
            print("✓ Successfully captured desktop-file-manager.png")
        else:
            print("✗ Failed to capture desktop-file-manager.png")

        # Terminate applications
        fm.terminate()
        thispc.terminate()
        shell.terminate()
        time.sleep(0.5)

    finally:
        if wm:
            try:
                os.killpg(os.getpgid(wm.pid), signal.SIGTERM)
            except Exception:
                pass
        try:
            os.killpg(os.getpgid(xvfb.pid), signal.SIGTERM)
        except Exception:
            pass

    print("\nScreenshot capture process complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
