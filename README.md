# ease-Desk

A lightweight remote desktop environment that runs in a browser and works on low-resource VPS infrastructure. Built around Wayland, Sway, and noVNC to deliver a complete virtual workspace without the bloat of traditional X11 desktop environments.

## Features
- 🌐 **Zero-Install Web Access**: Full desktop experience directly in your browser.
- 🚀 **Ultra-Lightweight**: Boot into a Wayland session taking minimal RAM on a headless VPS.
- 🛠️ **Built-in Apps**: Comes with a File Manager, Terminal, Task Manager, and Settings right out of the box.
- 🔒 **Secure**: Ships with an Nginx reverse proxy, Fail2Ban integration, and custom VNC password configurations.
- 🐳 **Docker Support**: Run the entire environment in a container with a single command.

---

## Installation

### Method 1: Native Installation (Ubuntu / Debian / CentOS / Arch)
Run the auto-installer script as root:
```bash
curl -fsSL https://raw.githubusercontent.com/charlietech255/ease-Desk/main/scripts/install.sh | sudo bash
```
> **Note**: During installation, you will be prompted to set a secure password for the VNC connection.

### Method 2: Docker Container (Any OS with Docker)
Simply run the startup script to build and launch the container:
```bash
./scripts/docker_start.sh
```
> Access via browser: `https://localhost:8444` (or port `6080` for plain HTTP).

---

## Troubleshooting & Known Issues

### 1. The browser shows "Disconnected" immediately
- **Check Logs**: Run `journalctl -u easedesk -f` to see if the `session.py` manager crashed. You can also view application logs in `~/.cache/easedesk/logs/`.
- **Wayland Support**: Ensure that your VPS supports headless Wayland (Sway requires basic DRM/render nodes unless run with `WLR_BACKENDS=headless`). The installer configures this automatically.
- **Port Conflict**: Check if port `6080` or `5900` are already in use (`netstat -tln`).

### 2. Desktop apps aren't showing in the dock or start menu
- **Reset Preferences**: Delete the user preferences file (`~/.config/easedesk/settings.ini`) and restart the service to restore default app mappings.

### 3. Nginx 502 Bad Gateway
- Wait 5-10 seconds for the backend `websockify` bridge to fully initialize before refreshing the page.

## Safe Restart / Reset
If the desktop ever freezes or behaves unexpectedly, you can safely restart the entire session without rebooting your server:

```bash
# Restart the native systemd service
sudo systemctl restart easedesk

# Or, if running via Docker
docker compose restart
```

Log files for troubleshooting can be found in `~/.cache/easedesk/logs/`.

---

## Uninstallation
To completely remove ease-Desk and all its configurations, run:
```bash
sudo ./scripts/uninstall.sh
```
