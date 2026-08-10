"""ease-Desk Session Manager — manages the desktop lifecycle.

Handles display server detection/creation, window manager integration,
desktop shell execution, and clean resource teardown on exit.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time


class SessionManager:
    """Manages the full lifecycle of an ease-Desk graphical session."""

    def __init__(
        self,
        display: str | None = None,
        resolution: str = "1920x1080x24",
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
        self.kasmvnc_port: int = 8444  # computed at launch time: 8443 + display_num
        self.spawned_processes: list[subprocess.Popen] = []

    # ------------------------------------------------------------- Discovery
    def verify_dependencies(self) -> None:
        """Verify that necessary system binaries exist."""
        # Python modules are verified on import.
        # openbox is strongly recommended.
        if not shutil.which("openbox"):
            print("Warning: openbox not found in PATH. Running in raw window mode.")

    def _find_free_display(self) -> str:
        """Find the next available X11 display number.
        
        For KasmVNC: websocket port = 8443 + display_num.
        Starting from :1 means port 8444, :2 means 8445, etc.
        """
        is_kasm = os.path.exists("/usr/bin/kasmvncserver")
        start = 1 if is_kasm else 99
        end = 20 if is_kasm else 120
        for num in range(start, end):
            lock = f"/tmp/.X{num}-lock"
            sock = f"/tmp/.X11-unix/X{num}"
            kasm_port = 8443 + num
            # Check display slot is free AND the corresponding port is free
            if not os.path.exists(lock) and not os.path.exists(sock):
                if is_kasm:
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(0.2)
                        if s.connect_ex(("127.0.0.1", kasm_port)) != 0:
                            s.close()
                            return f":{num}"
                        s.close()
                    except Exception:
                        return f":{num}"
                else:
                    return f":{num}"
        return ":1" if is_kasm else ":99"

    # ----------------------------------------------------------- Lifecycle
    def start(self) -> int:
        """Start the ease-Desk session."""
        self.verify_dependencies()

        print("\nStarting ease-Desk...")

        # 1. Setup Display Server
        existing_display = os.environ.get("DISPLAY")
        if self.requested_display:
            # Explicitly requested display — trust it
            self.display_str = self.requested_display
            self.is_virtual_display = False
        elif existing_display and existing_display.strip() and self._display_is_alive(existing_display.strip()):
            # Existing DISPLAY is set AND verified to be reachable
            self.display_str = existing_display.strip()
            self.is_virtual_display = False
        else:
            # Headless / VPS / no real display — start Xvfb virtual display
            self.display_str = self._find_free_display()
            self.is_virtual_display = True
            self._start_virtual_display()

        # Export DISPLAY and XAUTHORITY for all child processes
        os.environ["DISPLAY"] = self.display_str
        os.environ["XAUTHORITY"] = os.path.expanduser("~/.Xauthority")
        os.environ["PYTHONPATH"] = (
            self.root_dir + os.pathsep + os.environ.get("PYTHONPATH", "")
        )

        # 2. Start Window Manager (Openbox or minimal fallback)
        self._start_window_manager()
        print("✓ Display server initialized")

        # 3. Start Desktop Shell
        shell_proc = self._start_desktop_shell()
        print("✓ Desktop shell initialized")
        print("✓ File Manager service ready")

        if self.is_virtual_display:
            ips = self._get_ip_addresses()
            primary_ip = ips[0] if ips else "localhost"
            is_kasm = shutil.which("vncserver") and os.path.exists("/usr/bin/kasmvncserver")
            if is_kasm:
                print("\n" + "=" * 64)
                print("         🚀 ease-Desk Server is Running! (KasmVNC)       ")
                print("=" * 64)
                print("  Open this link in your browser (Phone / PC / Tablet):")
                print(f"  👉 http://{primary_ip}:8444/")
                print("")
                print("  Local access (SSH tunnel):")
                print(f"  👉 http://localhost:8444/")
                print("-" * 64)
            else:
                url_params = "?autoconnect=true&resize=scale"
                print("\n" + "=" * 64)
                print("         🌐 ease-Desk Server is Running!         ")
                print("=" * 64)
                print("  Open this link in your browser (Phone / PC / Tablet):")
                print(f"  👉 http://{primary_ip}/vnc.html{url_params}")
                print(f"     (requires Nginx reverse proxy on port 80)")
                print("")
                print("  Or using SSH Tunnel (Secure):")
                print(f"  👉 http://localhost:{self.novnc_port}/vnc.html{url_params}")
                print("-" * 64)
                print("  💡 Tip: Mobile screens auto-scale in both portrait & landscape!")
                if self.enable_vnc:
                    print(f"  🖥️  Native VNC Client (SSH Tunnel): localhost:{self.vnc_port}")
            
            print(f"  🖥️  Display ID:       {self.display_str}")
            print("=" * 64)
            print("(Press Ctrl+C in this terminal to shutdown ease-Desk)\n")
        else:
            print("\n" + "=" * 64)
            print(f"  🖥️  ease-Desk started directly on {self.display_str}")
            print("=" * 64)
            print("(Press Ctrl+C or click 'Exit Desktop' to shutdown)\n")

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

    def _display_is_alive(self, display: str) -> bool:
        """Return True if the given DISPLAY string has a live X server."""
        # 1. Try xdpyinfo if available
        if shutil.which("xdpyinfo"):
            try:
                result = subprocess.run(
                    ["xdpyinfo", "-display", display],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                return result.returncode == 0
            except Exception:
                pass

        # 2. Check X11 UNIX socket /tmp/.X11-unix/X<num>
        try:
            disp_num = display.lstrip(":").split(".")[0]
            sock_path = f"/tmp/.X11-unix/X{disp_num}"
            if os.path.exists(sock_path):
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(1.0)
                try:
                    s.connect(sock_path)
                    s.close()
                    return True
                except Exception:
                    pass
        except Exception:
            pass

        return False

    def _get_ip_addresses(self) -> list[str]:
        """Detect local network and external IP addresses."""
        ips: list[str] = []
        
        # Try to get public IP first
        try:
            from urllib.request import urlopen
            # 1-second timeout so it doesn't block startup
            with urlopen("https://api.ipify.org", timeout=1.0) as response:
                public_ip = response.read().decode('utf-8').strip()
                if public_ip:
                    ips.append(public_ip)
        except Exception:
            pass

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            sock_ip = s.getsockname()[0]
            s.close()
            if sock_ip and sock_ip != "127.0.0.1" and sock_ip not in ips:
                ips.append(sock_ip)
        except Exception:
            pass

        try:
            res = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=1)
            for part in res.stdout.strip().split():
                if part and part not in ips and not part.startswith("127.") and not part.startswith("172.17."):
                    ips.append(part)
        except Exception:
            pass

        return ips

    # -------------------------------------------------------- Subprocesses
    def _start_virtual_display(self) -> None:
        """Launch KasmVNC or Xvfb virtual display server and optional VNC/noVNC."""
        num = self.display_str.lstrip(":")
        lock_file = f"/tmp/.X{num}-lock"
        sock_file = f"/tmp/.X11-unix/X{num}"
        for f in (lock_file, sock_file):
            if os.path.exists(f):
                try:
                    os.unlink(f)
                except OSError:
                    pass

        # Option A: KasmVNC
        if shutil.which("vncserver") and os.path.exists("/usr/bin/kasmvncserver"):
            print("Launching KasmVNC virtual display...")

            # ── Start PulseAudio (virtual sink for browser audio via KasmVNC) ───
            if shutil.which("pulseaudio"):
                pulse_env = os.environ.copy()
                pulse_env.setdefault("DBUS_SESSION_BUS_ADDRESS", "")
                try:
                    subprocess.run(
                        ["pulseaudio", "--start", "--exit-idle-time=-1"],
                        env=pulse_env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                    )
                    print("  PulseAudio started (audio will stream via KasmVNC).", flush=True)
                    os.environ["PULSE_SERVER"] = os.environ.get("PULSE_SERVER", "unix:/run/user/0/pulse/native")
                except Exception as pa_err:
                    print(f"  PulseAudio start warning: {pa_err}", flush=True)

            vnc_dir = os.path.expanduser("~/.vnc")
            os.makedirs(vnc_dir, exist_ok=True)

            # KasmVNC natural websocket port = 8443 + display_number
            # e.g. :1 -> 8444, :2 -> 8445.  We pick the display that maps to a free port.
            display_num = int(num)
            self.kasmvnc_port = 8443 + display_num

            # Write minimal kasmvnc.yaml — only disable SSL, let KasmVNC use its natural port
            # Bind to 127.0.0.1 so external access MUST go through Nginx
            kasm_yaml = os.path.join(vnc_dir, "kasmvnc.yaml")
            with open(kasm_yaml, "w") as f:
                f.write("network:\n  protocol: http\n  interface: 127.0.0.1\n  ssl:\n    require_ssl: false\n")
            
            xstartup_path = os.path.join(vnc_dir, "xstartup")
            xstartup_content = (
                "#!/bin/bash\n"
                "# ease-Desk xstartup for KasmVNC — do not remove\n"
                "unset SESSION_MANAGER\n"
                "unset DBUS_SESSION_BUS_ADDRESS\n\n"
                "# Start a lightweight window manager so KasmVNC has a valid desktop\n"
                "if command -v openbox >/dev/null 2>&1; then\n"
                "    picom -b --backend xrender & \n"
                "    exec openbox-session\n"
                "elif command -v fluxbox >/dev/null 2>&1; then\n"
                "    exec fluxbox\n"
                "else\n"
                "    exec xterm\n"
                "fi\n"
            )
            with open(xstartup_path, "w") as f:
                f.write(xstartup_content)
            os.chmod(xstartup_path, 0o755)
            
            # Verify ~/.kasmpasswd exists in native KasmVNC format.
            # If it doesn't exist (e.g., after a fresh install where only vncpasswd was used),
            # create it with a temporary password so KasmVNC won't hang on an interactive prompt.
            kasm_pass = os.path.expanduser("~/.kasmpasswd")
            if not os.path.exists(kasm_pass) or os.path.islink(kasm_pass):
                # Remove invalid symlink if present
                if os.path.islink(kasm_pass):
                    os.unlink(kasm_pass)
                kasmvncpasswd_bin = shutil.which("kasmvncpasswd")
                if kasmvncpasswd_bin:
                    import getpass
                    import pwd as _pwd
                    user = getpass.getuser()
                    # Create a temporary credential so KasmVNC starts without interactive prompt
                    subprocess.run(
                        [kasmvncpasswd_bin, "-u", user, "-rw", kasm_pass],
                        input="easedesk\neasedesk\n",
                        text=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            
            # Touch .de-was-selected so KasmVNC's perl script doesn't try to prompt for a DE
            # (which causes it to crash since stdin is redirected to DEVNULL)
            de_selected = os.path.expanduser("~/.vnc/.de-was-selected")
            with open(de_selected, "a"):
                pass
            
            import sys
            cmd = ["/usr/bin/kasmvncserver", self.display_str, "-geometry", self.resolution.rsplit('x', 1)[0]]
            proc = subprocess.Popen(
                cmd,
                stdout=sys.stdout,
                stderr=sys.stderr,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.spawned_processes.append(proc)
            
            # Wait up to 60s for KasmVNC to fully initialize.
            # Checking only the socket is not enough — Xauthority may not be written yet.
            # We poll xdpyinfo until it can actually connect to the display.
            print("  Waiting for KasmVNC display to become ready...", flush=True)
            deadline = time.time() + 60
            ready = False
            xdpyinfo_bin = shutil.which("xdpyinfo")
            xauth_env = {**os.environ, "XAUTHORITY": os.path.expanduser("~/.Xauthority")}
            while time.time() < deadline:
                if os.path.exists(sock_file):
                    if xdpyinfo_bin:
                        try:
                            r = subprocess.run(
                                [xdpyinfo_bin, "-display", self.display_str],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                timeout=2,
                                env=xauth_env,
                            )
                            if r.returncode == 0:
                                ready = True
                                break
                        except Exception:
                            pass
                    else:
                        # No xdpyinfo — wait a few extra seconds after socket appears
                        time.sleep(4)
                        ready = True
                        break
                time.sleep(1)
            
            if not ready:
                print("  Warning: KasmVNC display did not respond in 60s, proceeding anyway.", flush=True)
            return

        # Option B: Fallback to Xvfb
        if not shutil.which("Xvfb"):
            raise RuntimeError(
                "Neither KasmVNC nor Xvfb found. Please install one of them to use virtual display mode."
            )
        print("Launching Xvfb virtual display (Fallback)...")
        cmd = ["Xvfb", self.display_str, "-screen", "0", self.resolution]
        xvfb = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=None,
            start_new_session=True,
        )
        self.spawned_processes.append(xvfb)

        # Wait up to 5 seconds for X11 socket to become ready
        for _ in range(50):
            if os.path.exists(sock_file):
                break
            time.sleep(0.1)
        time.sleep(0.2)

        if self.enable_vnc and shutil.which("x11vnc"):
            pwd_file = os.path.expanduser("~/.vnc/passwd")
            auth_args = ["-rfbauth", pwd_file] if (os.path.exists(pwd_file) and os.path.getsize(pwd_file) > 0) else ["-nopw"]

            vnc_cmd = [
                "x11vnc",
                "-display",
                self.display_str,
                "-rfbport",
                str(self.vnc_port),
                "-forever",
                "-shared",
                "-quiet",
                "-bg",
            ] + auth_args
            subprocess.run(
                vnc_cmd,
                stdout=subprocess.DEVNULL,
                stderr=None,
            )

            # Optional noVNC HTML5 WebSocket proxy
            novnc_proxy = shutil.which("novnc_proxy") or shutil.which("websockify")
            if novnc_proxy:
                web_dirs = [
                    "/usr/share/novnc",
                    "/usr/share/novnc-core",
                    "/opt/novnc",
                    "/usr/local/share/novnc",
                ]
                web_dir = next((d for d in web_dirs if os.path.exists(d)), None)
                
                if shutil.which("websockify"):
                    web_arg = ["--web", web_dir] if web_dir else []
                    ws_cmd = (
                        ["websockify"]
                        + web_arg
                        + [
                            f"127.0.0.1:{self.novnc_port}",
                            f"127.0.0.1:{self.vnc_port}",
                        ]
                    )
                else:
                    ws_cmd = [
                        "novnc_proxy",
                        "--vnc",
                        f"127.0.0.1:{self.vnc_port}",
                        "--listen",
                        f"127.0.0.1:{self.novnc_port}",
                    ]
                novnc = subprocess.Popen(
                    ws_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=None,
                    start_new_session=True,
                )
                self.spawned_processes.append(novnc)

    def _start_window_manager(self) -> None:
        """Launch lightweight Openbox window manager on current DISPLAY."""
        if not shutil.which("openbox"):
            return
            
        # Deploy ease-Desk custom Openbox theme and config
        try:
            panel_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            theme_src = os.path.join(panel_dir, "shared", "openbox_theme")
            if os.path.exists(theme_src):
                theme_dest = os.path.expanduser("~/.themes/ease-Desk")
                ob_dest = os.path.expanduser("~/.config/openbox")
                
                os.makedirs(os.path.join(theme_dest, "openbox-3"), exist_ok=True)
                os.makedirs(ob_dest, exist_ok=True)
                
                shutil.copy2(os.path.join(theme_src, "ease-Desk", "openbox-3", "themerc"), 
                            os.path.join(theme_dest, "openbox-3", "themerc"))
                shutil.copy2(os.path.join(theme_src, "rc.xml"), 
                            os.path.join(ob_dest, "rc.xml"))
        except Exception as e:
            print(f"Warning: Failed to deploy Openbox theme: {e}")

        wm = subprocess.Popen(
            ["openbox"],
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.spawned_processes.append(wm)
        
        if shutil.which("picom"):
            picom = subprocess.Popen(
                ["picom", "--backend", "xrender"],
                env=os.environ.copy(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.spawned_processes.append(picom)
            
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

        # Explicitly kill KasmVNC to prevent ghost sessions
        if shutil.which("kasmvncserver"):
            subprocess.run(
                ["kasmvncserver", "-kill", self.display_str],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
        # Clean up any rogue processes
        subprocess.run(["pkill", "-f", "openbox|picom|Xvfb|websockify|novnc_proxy|Xvnc"], stderr=subprocess.DEVNULL)

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

        # Cleanup KasmVNC or x11vnc
        if self.is_virtual_display:
            if shutil.which("vncserver") and os.path.exists("/usr/bin/kasmvncserver"):
                try:
                    subprocess.run(["vncserver", "-kill", self.display_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            else:
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
    parser.add_argument("--resolution", default="1920x1080x24", help="Virtual screen resolution")
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
