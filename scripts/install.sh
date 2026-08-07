#!/usr/bin/env bash
# ==============================================================================
# ease-Desk — All-in-One Installer (Linux / VPS / Debian / Ubuntu / Termux)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "====================================================="
echo "   Installing ease-Desk (All-in-One Setup)          "
echo "====================================================="

# Determine installation paths based on privileges
if [ "$(id -u)" -eq 0 ]; then
    INSTALL_DIR="/opt/ease-desk"
    BIN_DIR="/usr/local/bin"
else
    # User-level installation fallback if sudo not available
    if command -v sudo >/dev/null 2>&1; then
        echo "Elevating privileges with sudo to install system dependencies & global command..."
        exec sudo "$0" "$@"
    else
        INSTALL_DIR="${HOME}/.local/share/ease-desk"
        BIN_DIR="${HOME}/.local/bin"
        mkdir -p "${BIN_DIR}"
    fi
fi

# 1. Install System Dependencies (Apt on Debian/Ubuntu, Pkg on Termux)
if command -v apt-get >/dev/null 2>&1; then
    echo "📦 Installing system packages (Xvfb, GTK3, Python-GI, VNC, noVNC)..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq \
        python3 \
        python3-gi \
        python3-gi-cairo \
        gir1.2-gtk-3.0 \
        gir1.2-gdkpixbuf-2.0 \
        openbox \
        xvfb \
        x11vnc \
        novnc \
        websockify \
        nginx \
        procps \
        scrot \
        curl \
        net-tools \
        fonts-dejavu-core \
        fonts-noto-color-emoji \
        fonts-symbola \
        adwaita-icon-theme \
        hicolor-icon-theme \
        >/dev/null 2>&1 || {
            echo "Standard apt-get install complete with warnings (retrying essentials)..."
            apt-get install -y python3 python3-gi gir1.2-gtk-3.0 xvfb x11vnc novnc websockify
        }
elif command -v pkg >/dev/null 2>&1; then
    echo "📦 Installing Termux packages..."
    pkg install -y python x11-repo xwayland tigervnc
fi

# 2. Setup noVNC index.html symlink for root URL convenience
if [ -d "/usr/share/novnc" ] && [ -f "/usr/share/novnc/vnc.html" ]; then
    ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html 2>/dev/null || true
fi

# 2.1 Setup Nginx Reverse Proxy for noVNC
if command -v nginx >/dev/null 2>&1; then
    echo "🔒 Configuring Nginx Reverse Proxy for ease-Desk..."
    cat << 'EOF' > /tmp/easedesk.conf
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:6080/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
    if [ -d "/etc/nginx/sites-available" ] && [ -d "/etc/nginx/sites-enabled" ]; then
        if [ "$(id -u)" -eq 0 ]; then
            mv /tmp/easedesk.conf /etc/nginx/sites-available/easedesk
            ln -sf /etc/nginx/sites-available/easedesk /etc/nginx/sites-enabled/
            rm -f /etc/nginx/sites-enabled/default
            systemctl restart nginx || true
        else
            echo "Skipping Nginx configuration: requires root privileges (run with sudo)"
        fi
    fi
fi

# 3. Deploy ease-Desk files
echo "📂 Deploying ease-Desk to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
cp -r "${ROOT_DIR}/desktop" "${INSTALL_DIR}/"
cp -r "${ROOT_DIR}/file_manager" "${INSTALL_DIR}/"
cp -r "${ROOT_DIR}/shared" "${INSTALL_DIR}/"
cp -r "${ROOT_DIR}/scripts" "${INSTALL_DIR}/"

# Copy assets & wallpapers
for asset in "${ROOT_DIR}"/*.png "${ROOT_DIR}"/*.jpg "${ROOT_DIR}"/*.svg; do
    [ -f "${asset}" ] && cp "${asset}" "${INSTALL_DIR}/" 2>/dev/null || true
done

# Ensure permissions
chmod +x "${INSTALL_DIR}/scripts/desktop"
chmod +x "${INSTALL_DIR}/scripts/"*.sh 2>/dev/null || true
chmod -R a+rX "${INSTALL_DIR}"

# 4. Create global command link
mkdir -p "${BIN_DIR}"
ln -sf "${INSTALL_DIR}/scripts/desktop" "${BIN_DIR}/desktop"
chmod +x "${BIN_DIR}/desktop"

echo ""
echo "====================================================="
echo "✓ ease-Desk Installed Successfully!"
echo "====================================================="
echo "Now you can simply type:"
echo ""
echo "    desktop"
echo ""
echo "• If you are on a Desktop monitor: It will open directly."
echo "• If you are on a VPS/headless: It will display a web URL"
echo "  (e.g., http://YOUR_IP/vnc.html) to open in browser (via Nginx proxy)."
echo "====================================================="
