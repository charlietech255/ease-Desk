"""ease-Desk Session Manager — Wayland/labwc Lifecycle."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

class SessionManager:
    """Manages the full lifecycle of a Wayland/labwc graphical session."""

    def __init__(self, display=None, resolution="1920x1080", enable_vnc=True):
        self.resolution = resolution
        self.enable_vnc = enable_vnc
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.spawned_processes = []

    def start(self) -> int:
        print("\nStarting ease-Desk (Wayland)...")
        os.environ["PYTHONPATH"] = self.root_dir + os.pathsep + os.environ.get("PYTHONPATH", "")
        
        # 1. Start sway in headless mode
        os.environ["WLR_BACKENDS"] = "headless"
        os.environ["WLR_RENDERER_ALLOW_SOFTWARE"] = "1"
        os.environ["WLR_NO_HARDWARE_CURSORS"] = "1"
        os.environ["LIBSEAT_BACKEND"] = "noop"
        os.environ["WLR_LIBINPUT_NO_DEVICES"] = "1"
        
        runtime_dir = f"/tmp/ease-desk-runtime-{os.geteuid()}"
        os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
        os.environ["XDG_RUNTIME_DIR"] = runtime_dir
        
        # Create a startup script for sway
        startup_script = os.path.join(self.root_dir, "scripts", "wayland_init.sh")
        with open(startup_script, "w") as f:
            f.write(f"""#!/bin/bash
# ease-Desk Wayland Startup Script
export PYTHONPATH="{self.root_dir}:$PYTHONPATH"

# Set background to black to hide sway logo
swaymsg "output * bg #050505 solid_color" >/dev/null 2>&1

# Start VNC Server
wayvnc 127.0.0.1 5900 &

# Start Web Bridge (noVNC + websockify)
websockify --web /usr/share/novnc 6080 127.0.0.1:5900 &

# Start the Desktop Shell
exec python3 -m desktop.shell.shell
""")
        os.chmod(startup_script, 0o755)

        # Create sway config
        sway_config = os.path.join(self.root_dir, "scripts", "sway_config")
        with open(sway_config, "w") as f:
            f.write(f"""
# Sway config for ease-Desk Headless Mode
output HEADLESS-1 resolution 1920x1080 position 0,0
default_border none
default_floating_border none
xwayland enable

# Force all windows to float (Openbox-like behavior)
for_window [class=".*"] floating enable
for_window [app_id=".*"] floating enable

exec {startup_script}
""")

        cmd = ["sway", "-c", sway_config]
        proc = subprocess.Popen(cmd)
        
        print("\n" + "=" * 64)
        print("         🚀 ease-Desk Server is Running! (Wayland/labwc)       ")
        print("=" * 64)
        print("  Local access (SSH tunnel):")
        print(f"  👉 http://localhost:6080/vnc.html")
        print("=" * 64)
        print("(Press Ctrl+C to shutdown)\n")
        
        try:
            returncode = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            returncode = 0
            
        return returncode

    def stop(self):
        print("Stopping ease-Desk...")
        subprocess.run(["pkill", "-f", "wayvnc"], check=False)
        subprocess.run(["pkill", "-f", "websockify"], check=False)
        subprocess.run(["pkill", "-f", "desktop.shell.shell"], check=False)

if __name__ == "__main__":
    sys.exit(SessionManager().start())
