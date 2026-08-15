#!/usr/bin/env bash
# ==============================================================================
# ease-Desk — Complete VPS Uninstall & Cleanup Script
# Removes everything: service, nginx config, binaries, data, runtime files
# ==============================================================================
set -euo pipefail

INSTALL_DIR="/opt/ease-desk"
BIN_DIR="/usr/local/bin"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${RED}${BOLD}"
echo "================================================================"
echo "  ease-Desk — Complete Uninstall & Cleanup"
echo "================================================================"
echo -e "${NC}"

if [ "$(id -u)" -ne 0 ]; then
    echo "This script requires root. Run: sudo $0"
    exit 1
fi

echo -n "Are you sure you want to completely remove ease-Desk and all its data? (y/N): "
read -r CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

# ── 1. Stop all running processes ─────────────────────────────────────────────
echo -e "${YELLOW}[1/7] Stopping all ease-Desk processes...${NC}"
systemctl stop easedesk >/dev/null 2>&1 || true
pkill -9 -f "desktop.session.session" 2>/dev/null || true
pkill -9 -f "desktop.shell.shell"    2>/dev/null || true
pkill -9 -f "wayvnc"                 2>/dev/null || true
pkill -9 -f "websockify"             2>/dev/null || true
pkill -9 -f "sway"                   2>/dev/null || true
echo -e "${GREEN}  Done.${NC}"

# ── 2. Remove systemd service ─────────────────────────────────────────────────
echo -e "${YELLOW}[2/7] Removing systemd service...${NC}"
systemctl disable easedesk >/dev/null 2>&1 || true
rm -f /etc/systemd/system/easedesk.service
systemctl daemon-reload >/dev/null 2>&1 || true
echo -e "${GREEN}  Done.${NC}"

# ── 3. Remove Nginx configuration ─────────────────────────────────────────────
echo -e "${YELLOW}[3/7] Removing Nginx configuration...${NC}"
rm -f /etc/nginx/sites-enabled/easedesk
rm -f /etc/nginx/sites-available/easedesk
rm -rf /etc/nginx/ssl/easedesk.crt /etc/nginx/ssl/easedesk.key
systemctl restart nginx >/dev/null 2>&1 || true
echo -e "${GREEN}  Done.${NC}"

# ── 4. Remove binary symlinks ─────────────────────────────────────────────────
echo -e "${YELLOW}[4/7] Removing CLI symlinks...${NC}"
for link in desktop ease-desk easedesk; do
    rm -f "${BIN_DIR}/${link}"
done
echo -e "${GREEN}  Done.${NC}"

# ── 5. Remove user config files ───────────────────────────────────────────────
echo -e "${YELLOW}[5/7] Removing user configuration files...${NC}"
for u_home in "/root" /home/*; do
    [ -d "$u_home" ] || continue
    rm -f  "${u_home}/.kasmpasswd"
    rm -rf "${u_home}/.vnc"
    rm -f  "${u_home}/.xsession"
    rm -rf "${u_home}/.themes/ease-Desk"
    echo "  Cleaned: ${u_home}"
done
echo -e "${GREEN}  Done.${NC}"

# ── 6. Remove runtime / temp files ────────────────────────────────────────────
echo -e "${YELLOW}[6/7] Removing runtime and temp files...${NC}"
rm -rf /tmp/ease-desk-runtime-* 2>/dev/null || true
# Clean X11 lock files (in case of previous X11 fallback)
for num in $(seq 99 125); do
    rm -f "/tmp/.X${num}-lock" "/tmp/.X11-unix/X${num}" 2>/dev/null || true
done
echo -e "${GREEN}  Done.${NC}"

# ── 7. Remove installation directory ─────────────────────────────────────────
echo -e "${YELLOW}[7/7] Removing installation directory (${INSTALL_DIR})...${NC}"
rm -rf "${INSTALL_DIR}"
echo -e "${GREEN}  Done.${NC}"

echo ""
echo -e "${GREEN}${BOLD}================================================================"
echo "  ease-Desk has been completely removed from this system."
echo -e "================================================================${NC}"
echo ""
echo "To reinstall, run:"
echo "  curl -fsSL https://raw.githubusercontent.com/charlietech255/ease-Desk/main/scripts/install.sh | sudo bash"
echo ""
