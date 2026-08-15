"""ease-Desk Session Manager — Wayland/Sway Headless Lifecycle."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import signal


class SessionManager:
    """Manages the full lifecycle of a headless Wayland/Sway graphical session."""

    def __init__(self, display=None, resolution="1920x1080", enable_vnc=True):
        self.resolution = resolution
        self.enable_vnc = enable_vnc
        self.root_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.spawned_processes = []
        self._sway_proc = None

    def _check_bin(self, name: str) -> bool:
        return shutil.which(name) is not None

    def start(self) -> int:
        print("\nStarting ease-Desk (Wayland/Headless)...")

        # ── Python path ────────────────────────────────────────────────────────
        os.environ["PYTHONPATH"] = (
            self.root_dir + os.pathsep + os.environ.get("PYTHONPATH", "")
        )

        # ── Wayland / wlroots environment ──────────────────────────────────────
        # Use headless backend with pure-software pixman renderer.
        # This works on any VPS/container with no GPU or DRM access.
        os.environ["WLR_BACKENDS"] = "headless"
        os.environ["WLR_RENDERER"] = "pixman"
        os.environ["WLR_NO_HARDWARE_CURSORS"] = "1"
        os.environ["WLR_LIBINPUT_NO_DEVICES"] = "1"
        os.environ["LIBSEAT_BACKEND"] = "noop"

        # ── XDG runtime dir ────────────────────────────────────────────────────
        runtime_dir = f"/tmp/ease-desk-runtime-{os.geteuid()}"
        os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
        os.environ["XDG_RUNTIME_DIR"] = runtime_dir

        # Sway places its Wayland socket here; we need WAYLAND_DISPLAY for child
        # processes (wayvnc, the shell) to find it.
        os.environ.setdefault("WAYLAND_DISPLAY", "wayland-1")

        # ── wayvnc password credentials file ──────────────────────────────────
        # wayvnc expects a credentials file, not a VNC passwd binary blob.
        # Format: username=<user>\npassword=<pass>
        vnc_pass_file = os.path.join(runtime_dir, "wayvnc-credentials")
        vnc_home = os.environ.get("HOME", "/root")
        vnc_passwd_bin = os.path.join(vnc_home, ".vnc", "passwd")

        # Try to read the password from the binary .vnc/passwd via x11vnc if available,
        # otherwise fall back to env variable or a default.
        vnc_password = os.environ.get("EASEDESK_VNC_PASS", "")
        if not vnc_password:
            # Check if password was written as plain text by install.sh
            plain_pass_file = os.path.join(vnc_home, ".vnc", "plainpass")
            if os.path.isfile(plain_pass_file):
                try:
                    with open(plain_pass_file) as f:
                        vnc_password = f.read().strip()
                except OSError:
                    pass

        if not vnc_password:
            vnc_password = "easedesk"  # safe fallback

        # Write wayvnc credentials file (plain text, read only by owner)
        try:
            with open(vnc_pass_file, "w") as cf:
                cf.write(f"username=easedesk\npassword={vnc_password}\n")
            os.chmod(vnc_pass_file, 0o600)
        except OSError:
            vnc_pass_file = None

        # ── Startup script executed by sway's exec directive ───────────────────
        startup_script = os.path.join(self.root_dir, "scripts", "wayland_init.sh")
        wayvnc_args = "127.0.0.1 5900"
        if vnc_pass_file:
            wayvnc_args = f"--config={vnc_pass_file} 127.0.0.1 5900"

        xwayland_line = ""
        if not self._check_bin("Xwayland"):
            xwayland_line = "# Xwayland not installed — skipping"

        with open(startup_script, "w") as f:
            f.write(
                f"""#!/bin/bash
# ease-Desk Wayland Startup Script
export PYTHONPATH="{self.root_dir}:$PYTHONPATH"
export WAYLAND_DISPLAY="{os.environ.get('WAYLAND_DISPLAY', 'wayland-1')}"
export XDG_RUNTIME_DIR="{runtime_dir}"

# Give sway a moment to initialise the compositor
sleep 1

# Set background colour
swaymsg "output * bg #050505 solid_color" >/dev/null 2>&1 || true

# Start VNC server (wayvnc)
wayvnc {wayvnc_args} &

# Start noVNC web bridge (websockify)
websockify --web /usr/share/novnc 6080 127.0.0.1:5900 &

# Start the Desktop Shell
exec python3 -m desktop.shell.shell
"""
            )
        os.chmod(startup_script, 0o755)

        # ── Sway config ────────────────────────────────────────────────────────
        sway_config = os.path.join(self.root_dir, "scripts", "sway_config")
        xwayland_directive = "disable" if not self._check_bin("Xwayland") else "enable"
        with open(sway_config, "w") as f:
            f.write(
                f"""# Sway config for ease-Desk Headless Mode
output HEADLESS-1 resolution {self.resolution} position 0,0
default_border none
default_floating_border none
xwayland {xwayland_directive}

# Force all windows to float
for_window [class=".*"] floating enable
for_window [app_id=".*"] floating enable

exec {startup_script}
"""
            )

        # ── Launch sway ────────────────────────────────────────────────────────
        if not self._check_bin("sway"):
            print("ERROR: 'sway' is not installed. Run: apt-get install -y sway", file=sys.stderr)
            return 1

        cmd = ["sway", "-c", sway_config]
        self._sway_proc = subprocess.Popen(cmd)

        print("\n" + "=" * 64)
        print("  🚀 ease-Desk Server is Running! (Wayland/Sway Headless)")
        print("=" * 64)
        print("  Local access (SSH tunnel):")
        print("  👉 http://localhost:6080/vnc.html")
        print("=" * 64)
        print("(Press Ctrl+C to shutdown)\n")

        def _handle_signal(sig, frame):
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGHUP, _handle_signal)

        try:
            returncode = self._sway_proc.wait()
        except KeyboardInterrupt:
            self.stop()
            returncode = 0

        return returncode

    def stop(self):
        print("Stopping ease-Desk...")
        for proc_name in ["wayvnc", "websockify", "desktop.shell.shell"]:
            subprocess.run(["pkill", "-f", proc_name], check=False)
        if self._sway_proc and self._sway_proc.poll() is None:
            self._sway_proc.terminate()
            try:
                self._sway_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._sway_proc.kill()


if __name__ == "__main__":
    sys.exit(SessionManager().start())
