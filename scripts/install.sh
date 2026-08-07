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

echo -n "🔒 Enter a secure password for your ease-Desk login: "
read -s VNC_PASS
echo ""

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
        certbot \
        python3-certbot-nginx \
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

# 2.1 Store VNC Password
if [ -n "$VNC_PASS" ] && command -v x11vnc >/dev/null 2>&1; then
    USER_HOME=$(eval echo "~${SUDO_USER:-$USER}")
    mkdir -p "${USER_HOME}/.vnc"
    x11vnc -storepasswd "$VNC_PASS" "${USER_HOME}/.vnc/passwd" >/dev/null 2>&1
    chown -R "${SUDO_USER:-$USER}" "${USER_HOME}/.vnc"
    echo "🔒 Password saved securely."
fi

# 2.2 Setup Nginx Reverse Proxy & SSL
if command -v nginx >/dev/null 2>&1 && [ "$(id -u)" -eq 0 ]; then
    echo "🌐 Configuring Nginx Reverse Proxy for ease-Desk..."
    
    if systemctl is-active --quiet apache2 2>/dev/null; then
        echo "⚠️ Apache2 detected. Disabling to free port 80 for Nginx..."
        systemctl stop apache2 || true
        systemctl disable apache2 || true
    fi

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
    if [ -d "/etc/nginx/sites-available" ]; then
        mv /tmp/easedesk.conf /etc/nginx/sites-available/easedesk
        ln -sf /etc/nginx/sites-available/easedesk /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default
        
        if nginx -t >/dev/null 2>&1; then
            systemctl restart nginx || true
            echo "✓ Nginx configured successfully with 0 errors."
        else
            echo "❌ Nginx configuration test failed."
        fi

        if command -v certbot >/dev/null 2>&1; then
            echo -n "Do you have a custom domain name to configure SSL/HTTPS? (y/N): "
            read -r SETUP_SSL
            if [[ "$SETUP_SSL" =~ ^[Yy]$ ]]; then
                echo -n "Enter your domain name (e.g. desktop.example.com): "
                read -r DOMAIN_NAME
                echo -n "Enter your email for SSL registration: "
                read -r CERT_EMAIL
                if [ -n "$DOMAIN_NAME" ] && [ -n "$CERT_EMAIL" ]; then
                    echo "🔒 Securing with Certbot..."
                    certbot --nginx -d "$DOMAIN_NAME" --non-interactive --agree-tos -m "$CERT_EMAIL" || echo "⚠️ Certbot failed, but HTTP is still available."
                fi
            fi
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
echo "  (e.g., http://YOUR_DOMAIN/vnc.html) to open in browser (via Nginx proxy)."
echo "====================================================="
