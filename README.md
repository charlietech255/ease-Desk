# ease-Desk

A fast, lightweight graphical environment designed specifically for Linux VPS and server administration.

![ease-Desk](screenshots/desktop-file-manager.png)

---

## Overview

I designed ease-Desk to solve a common problem: full desktop environments like GNOME, KDE, or XFCE are too heavy for remote servers. They consume hundreds of megabytes of RAM, require heavy system services, and take too long to start.

ease-Desk is built for VPS administrators and developers who work primarily through SSH terminals, but sometimes need a simple and responsive graphical interface to:

- Browse and navigate server directories (such as /var/www, /etc, /home, and /var/log)
- Create folders, rename, copy, move, and delete files
- View and edit text configuration files directly (.conf, .json, .yaml, .php, .py, .sh, .log)
- Check live server resource metrics (CPU cores, RAM usage, disk space, and OS information)
- Launch on-demand with a single command (`desktop`) over SSH X11 Forwarding, Termux on Android, or remote VNC.

When closed, it exits completely and leaves zero idle processes running on your server.

---

## Screenshots

| Clean Desktop | File Manager Open |
|---|---|
| ![Empty Desktop](screenshots/desktop-empty.png) | ![File Manager](screenshots/desktop-file-manager.png) |

---

## Resource Usage Comparison

| Metric | Standard Desktops (GNOME / XFCE) | ease-Desk |
|---|---|---|
| RAM Usage | 450 MB - 1.2 GB | ~45 MB - 65 MB |
| Idle CPU | 2% - 8% | < 0.1% |
| Startup Time | 4 - 10 seconds | < 400 milliseconds |
| Background Services | D-Bus, systemd daemons, indexers | None (runs on-demand) |
| Connection Method | Heavy RDP / VNC streams | Native X11 Forwarding / Termux / VNC |

---

## Project Structure

```text
├── desktop/                 # Desktop shell, session manager, and window management
│   ├── session/             # Display server (Xvfb/X11), WM launcher, and cleanup
│   └── shell/               # Desktop background, top bar, clock, and server monitor
│
├── file_manager/            # VPS file manager application
│   ├── core/                # Filesystem operations (copy, move, delete, permissions)
│   ├── gui.py               # GTK3 icon view, path bar, and navigation controls
│   ├── viewer.py            # Text and config file viewer / editor
│   └── types.py             # MIME types, file extensions, and size formatting
│
├── shared/                  # Shared styling and system utilities
│   ├── styles/              # Dark slate theme and CSS definitions
│   └── utilities/           # System info probes, animation helpers, security checks
│
├── docker/                  # Docker VPS testing environment
│   ├── Dockerfile           # Debian 12 container with SSH server and sample files
│   └── entrypoint.sh        # Container startup script
│
├── scripts/                 # Executable scripts
│   ├── desktop              # Main CLI entry point
│   ├── install.sh           # Automated installer for Debian / Ubuntu
│   ├── uninstall.sh         # Uninstaller script
│   └── capture_screenshots.py # Headless screenshot capture tool
│
└── tests/                   # Unit and integration test suites
```

---

## Installation

### Automatic Installation (Debian / Ubuntu / Kali / Mint)

```bash
git clone https://github.com/charlietech255/ease-Desk.git
cd ease-Desk
sudo ./scripts/install.sh
```

The install script installs the required lightweight GTK3 / Openbox packages and links the executable to `/usr/local/bin/desktop`.

### Manual Dependencies

If you prefer installing dependencies manually:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 openbox xvfb x11vnc
```

---

## How to Use

### 1. SSH with X11 Forwarding (Recommended)

From your computer (Linux, macOS, or Windows with WSLg / VcXsrv):

```bash
# Connect to your server with X11 forwarding enabled
ssh -X user@your-server-ip

# Start the desktop
desktop
```

ease-Desk automatically detects the active display and renders directly on your local screen.

### 2. Android via Termux

1. Open Termux on Android with Termux:X11 running.
2. Connect to your VPS:
   ```bash
   ssh -X user@your-server-ip
   ```
3. Run `desktop`. The desktop will open inside Termux:X11.

### 3. Headless VPS with Web Browser or VNC

If your server has no active X11 display:

```bash
desktop --resolution 1280x800
```

Open your browser and navigate to:
`http://your-server-ip:6080/vnc.html`

Or connect with any standard VNC client to `your-server-ip:5900`.

---

## Command-Line Options

```text
usage: desktop [-h] [--resolution WxH] [--vnc-port PORT] [--novnc-port PORT]
               [--no-vnc] [--no-novnc] [--native]

ease-Desk Session Manager for VPS

options:
  -h, --help            show this help message and exit
  --resolution WxH      virtual display resolution (default: 1280x800x24)
  --vnc-port PORT       VNC server port (default: 5900)
  --novnc-port PORT     noVNC web client port (default: 6080)
  --no-vnc              disable VNC server
  --no-novnc            disable noVNC web server
  --native              force native X11 display (ignore Xvfb)
```

---

## Docker Test Environment

To test ease-Desk in an isolated VPS container:

```bash
# Start the container
docker-compose up -d

# Connect via SSH (password: charlie)
ssh -X -p 2222 charlie@localhost

# Launch ease-Desk
desktop
```

---

## Security Safeguards

- Critical system directories (`/`, `/bin`, `/boot`, `/etc`, `/usr`, `/lib`, `/sys`, `/proc`) cannot be deleted.
- All file paths are validated using absolute paths to prevent directory traversal attacks.
- Subprocesses are isolated in process groups and cleanly terminated upon exit.

---

## Running Tests

Run the test suites with:

```bash
python3 -m unittest discover -s tests
python3 -m unittest discover -s file_manager/tests
```

---

## License

MIT License. Developed by Charlie for simple, efficient VPS administration.
