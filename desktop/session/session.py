"""ease-Desk Session Manager — manages the desktop lifecycle.

Handles display server detection/creation, window manager integration,
desktop shell execution, and clean resource teardown on exit.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time


class SessionManager:
    """Manages the full lifecycle of an ease-Desk graphical session."""

    def __init__(
        self,
        display: str | None = None,
        resolution: str = "1280x800x24",
        vnc_port: int = 5900,
        novnc_port: int = 6080,
        enable_vnc: bool = True,
    ) -> None:
        self.requested_display = display
        self.resolution = resolution
        self.vnc_port = vnc_port
        self.novnc_port = novnc_port
        self.enable_vnc = enable_vnc

        self.root_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.display_str: str | None = None
        self.is_virtual_display: bool = False
        self.spawned_processes: list[subprocess.Popen] = []

    # ------------------------------------------------------------- Discovery
    def verify_dependencies(self) -> None:
        """Verify that necessary system binaries exist."""
        # Python modules are verified on import.
        # openbox is strongly recommended.
        if not shutil.which("openbox"):
            print("Warning: openbox not found in PATH. Running in raw window mode.")

    def _find_free_display(self) -> str:
        """Find the next available X11 display number."""
        for num in range(99, 120):
            lock = f"/tmp/.X{num}-lock"
            sock = f"/tmp/.X11-unix/X{num}"
            if not os.path.exists(lock) and not os.path.exists(sock):
                return f":{num}"
        return ":99"

    # ----------------------------------------------------------- Lifecycle
    def start(self) -> int:
        """Start the ease-Desk session."""
        self.verify_dependencies()

        print("\nStarting ease-Desk...")

        # 1. Setup Display Server
        existing_display = os.environ.get("DISPLAY")
        if self.requested_display:
            self.display_str = self.requested_display
        elif existing_display and existing_display.strip():
            self.display_str = existing_display
            self.is_virtual_display = False
        else:
            # Headless SSH connection: start Xvfb virtual display
            self.display_str = self._find_free_display()
            self.is_virtual_display = True
            self._start_virtual_display()

        # Export DISPLAY for all child processes
        os.environ["DISPLAY"] = self.display_str
        os.environ["PYTHONPATH"] = (
            self.root_dir + os.pathsep + os.environ.get("PYTHONPATH", "")
        )

        # 2. Start Window Manager (Openbox or minimal fallback)
        self._start_window_manager()
        print("✓ Display server")

        # 3. Start Desktop Shell
        shell_proc = self._start_desktop_shell()
        print("✓ Desktop shell")
        print("✓ File Manager service")
        print(f"\nease-Desk started on {self.display_str}.")
        if self.is_virtual_display and self.enable_vnc:
            print(f"  • Native VNC Server: port {self.vnc_port}")
            print(f"  • Web Client (noVNC): http://localhost:{self.novnc_port}/vnc.html")
        print("\n(Press Ctrl+C in terminal or click 'Exit Desktop' to shutdown)\n")

        # Setup signal handlers for clean exit
        self._setup_signals(shell_proc)

        # Wait for desktop shell to exit
        try:
            returncode = shell_proc.wait()
        except KeyboardInterrupt:
            returncode = 0
        finally:
            self.stop()
        return returncode

    # -------------------------------------------------------- Subprocesses
    def _start_virtual_display(self) -> None:
        """Launch Xvfb virtual display server and optional VNC/noVNC."""
        if not shutil.which("Xvfb"):
            raise RuntimeError(
                "Xvfb not found. Please install xvfb to use virtual display mode."
            )

        cmd = ["Xvfb", self.display_str, "-screen", "0", self.resolution]
        xvfb = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.spawned_processes.append(xvfb)
        time.sleep(0.35)

        if self.enable_vnc and shutil.which("x11vnc"):
            vnc_cmd = [
                "x11vnc",
                "-display",
                self.display_str,
                "-rfbport",
                str(self.vnc_port),
                "-forever",
                "-shared",
                "-nopw",
                "-quiet",
                "-bg",
            ]
            subprocess.run(
                vnc_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Optional noVNC HTML5 WebSocket proxy
            novnc_proxy = shutil.which("novnc_proxy") or shutil.which("websockify")
            if novnc_proxy:
                web_dir = "/usr/share/novnc"
                if not os.path.exists(web_dir):
                    web_dir = "/usr/share/novnc-core"
                if shutil.which("websockify"):
                    ws_cmd = [
                        "websockify",
                        "--web",
                        web_dir,
                        str(self.novnc_port),
                        f"localhost:{self.vnc_port}",
                    ]
                else:
                    ws_cmd = [
                        "novnc_proxy",
                        "--vnc",
                        f"localhost:{self.vnc_port}",
                        "--listen",
                        str(self.novnc_port),
                    ]
                novnc = subprocess.Popen(
                    ws_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                self.spawned_processes.append(novnc)

    def _start_window_manager(self) -> None:
        """Launch lightweight Openbox window manager on current DISPLAY."""
        if not shutil.which("openbox"):
            return
        wm = subprocess.Popen(
            ["openbox"],
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.spawned_processes.append(wm)
        time.sleep(0.15)

    def _start_desktop_shell(self) -> subprocess.Popen:
        """Start the ease-Desk Shell application."""
        shell_module = "desktop.shell.shell"
        proc = subprocess.Popen(
            [sys.executable, "-m", shell_module],
            env=os.environ.copy(),
            start_new_session=True,
        )
        self.spawned_processes.append(proc)
        return proc

    # ------------------------------------------------------------- Teardown
    def _setup_signals(self, shell_proc: subprocess.Popen) -> None:
        """Attach clean signal handling."""
        def handler(sig, frame):
            try:
                shell_proc.terminate()
            except Exception:
                pass

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def stop(self) -> None:
        """Clean up all spawned processes and shutdown the graphical session."""
        print("\nStopping ease-Desk...")
        print("✓ Closing applications")

        # Kill spawned processes in reverse order
        for proc in reversed(self.spawned_processes):
            try:
                pgrp = os.getpgid(proc.pid)
                os.killpg(pgrp, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                try:
                    proc.terminate()
                except (OSError, ProcessLookupError):
                    pass

        # Cleanup x11vnc if running
        if self.is_virtual_display:
            try:
                subprocess.run(
                    ["x11vnc", "-R", "stop"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

        # Clean X11 lock files for virtual display
        if self.is_virtual_display and self.display_str:
            num = self.display_str.lstrip(":")
            lock_file = f"/tmp/.X{num}-lock"
            sock_file = f"/tmp/.X11-unix/X{num}"
            for f in (lock_file, sock_file):
                if os.path.exists(f):
                    try:
                        os.unlink(f)
                    except OSError:
                        pass

        print("✓ Cleaning graphical session")
        print("\nease-Desk stopped.\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="ease-Desk Session Manager")
    parser.add_argument("--display", help="Target X11 display (e.g. :0 or :99)")
    parser.add_argument("--resolution", default="1280x800x24", help="Virtual screen resolution")
    parser.add_argument("--vnc-port", type=int, default=5900, help="VNC port")
    parser.add_argument("--novnc-port", type=int, default=6080, help="noVNC Web port")
    parser.add_argument("--no-vnc", action="store_true", help="Disable VNC bridge")
    args = parser.parse_args()

    mgr = SessionManager(
        display=args.display,
        resolution=args.resolution,
        vnc_port=args.vnc_port,
        novnc_port=args.novnc_port,
        enable_vnc=not args.no_vnc,
    )
    return mgr.start()


if __name__ == "__main__":
    sys.exit(main())
