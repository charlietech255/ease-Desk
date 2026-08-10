#!/usr/bin/env bash
# ==============================================================================
# ease-Desk Uninstallation Script
# ==============================================================================
set -e

INSTALL_DIR="/opt/ease-desk"
BIN_DIR="/usr/local/bin"

echo -e "\033[0;31m================================================================"
echo " ease-Desk — Complete Uninstallation"
echo -e "================================================================\033[0m"

if [ "$(id -u)" -ne 0 ]; then
    echo "This script requires root privileges. Please run with sudo: sudo $0"
    exit 1
fi

echo -n "Are you sure you want to completely remove ease-Desk and all its configurations? (y/N): "
read -r CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

echo "Stopping services..."
systemctl stop easedesk >/dev/null 2>&1 || true
pkill -9 -f "desktop.session.session" >/dev/null 2>&1 || true
pkill -9 -f "desktop.shell.shell" >/dev/null 2>&1 || true

echo "Removing systemd service..."
systemctl disable easedesk >/dev/null 2>&1 || true
rm -f /etc/systemd/system/easedesk.service
systemctl daemon-reload >/dev/null 2>&1 || true

echo "Removing Nginx configuration..."
if [ -f "/etc/nginx/sites-enabled/easedesk" ] || [ -f "/etc/nginx/sites-available/easedesk" ]; then
    rm -f /etc/nginx/sites-enabled/easedesk
    rm -f /etc/nginx/sites-available/easedesk
    systemctl restart nginx >/dev/null 2>&1 || true
fi

echo "Removing binary symlinks..."
for link in desktop ease-desk easedesk; do
    rm -f "${BIN_DIR}/${link}"
done

echo "Removing user configuration files (~/.vnc, ~/.kasmpasswd, ~/.xsession)..."
for u_home in "/root" "/home/"*; do
    [ -d "$u_home" ] || continue
    rm -f "${u_home}/.kasmpasswd"
    rm -rf "${u_home}/.vnc"
    rm -f "${u_home}/.xsession"
    # Also clean up openbox theme
    rm -rf "${u_home}/.themes/ease-Desk"
done

echo "Removing installation directory (${INSTALL_DIR})..."
rm -rf "${INSTALL_DIR}"

echo -e "\033[0;32mease-Desk has been completely uninstalled.\033[0m"
