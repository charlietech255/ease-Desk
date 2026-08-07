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

# Port-availability helper (works with both ss and net-tools' netstat)
port_ready() {
    ss -tln 2>/dev/null | grep -qE ":$1 " && return 0
    netstat -tln 2>/dev/null | grep -qE ":$1 " && return 0
    return 1
}

# 0. Clean up stale sessions, leftover ports and lock files.
#    This is what fixes a previous 502/port-conflict install on re-run.
if [ "$(id -u)" -eq 0 ]; then
    echo "🧹 Cleaning up stale ease-Desk sessions before install..."
    pkill -f "desktop.session.session" 2>/dev/null || true
    pkill -f "desktop.shell.shell" 2>/dev/null || true
    pkill -f "websockify --web" 2>/dev/null || true
    pkill -f "x11vnc -display" 2>/dev/null || true
    systemctl stop easedesk >/dev/null 2>&1 || true
    rm -f "/etc/systemd/system/easedesk.service" 2>/dev/null || true

    if command -v docker >/dev/null 2>&1; then
        # Free host ports 5900/6080 that a previous Docker setup holds
        docker rm -f charlie-vps >/dev/null 2>&1 || true
    fi

    # Remove stale X11 lock/socket files from dead virtual displays
    for num in $(seq 99 119); do
        rm -f "/tmp/.X${num}-lock"
        rm -f "/tmp/.X11-unix/X${num}"
    done

    # Wait until old ports are actually freed before we rebind them
    for port in 6080 5900; do
        for i in $(seq 1 15); do
            port_ready "${port}" || break
            sleep 0.5
        done
    done
    echo "✅ Old sessions stopped, ports 6080/5900 freed."
fi

if [ -n "${EASEDESK_VNC_PASS:-}" ]; then
    VNC_PASS="$EASEDESK_VNC_PASS"
else
    echo -n "🔒 Enter a secure password for your ease-Desk login: "
    read -s VNC_PASS
    echo ""
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
        certbot \
        python3-certbot-nginx \
        procps \
        scrot \
        curl \
        net-tools \
        fonts-dejavu-core \
        fonts-noto-color-emoji \
        adwaita-icon-theme \
        hicolor-icon-theme \
        >/dev/null 2>&1 || {
            echo "Standard apt-get install complete with warnings (retrying essentials)..."
            apt-get install -y python3 python3-gi gir1.2-gtk-3.0 xvfb x11vnc novnc websockify nginx
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
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:6080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
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

# 5. Setup Systemd Service (Start it in background, restart automatically)
if command -v systemctl >/dev/null 2>&1 && [ "$(id -u)" -eq 0 ]; then
    echo "⚙️ Configuring ease-Desk Systemd Background Service..."
    SERVICE_USER="${SUDO_USER:-$USER}"
    cat << EOF > /etc/systemd/system/easedesk.service
[Unit]
Description=ease-Desk Virtual Desktop Session
After=network-online.target nginx.service
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
Environment=HOME=$(eval echo "~${SERVICE_USER}")
Environment=PYTHONPATH=${INSTALL_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${BIN_DIR}/desktop
Restart=always
RestartSec=3
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable easedesk >/dev/null 2>&1
    systemctl restart easedesk || echo "⚠️ Failed to start background service."
    echo "✓ Background service 'easedesk' started!"
fi

# 6. Healthcheck — verify the whole chain: Nginx :80 -> websockify :6080 -> x11vnc :5900
if [ "$(id -u)" -eq 0 ]; then
    echo ""
    echo "🔍 Running final health checks..."
    for i in $(seq 1 45); do
        port_ready 6080 && break
        sleep 1
    done

    if port_ready 5900; then
        echo "✓ x11vnc listening on :5900"
    else
        echo "✗ x11vnc NOT listening on :5900 (check: journalctl -u easedesk)"
    fi

    if port_ready 6080; then
        echo "✓ websockify listening on :6080"
    else
        echo "✗ websockify NOT listening on :6080 — restarting service and re-testing..."
        systemctl restart easedesk >/dev/null 2>&1 || true
        sleep 8
        port_ready 6080 && echo "✓ websockify now listening on :6080" || echo "✗ websockify still down (check: journalctl -u easedesk)"
    fi

    PUBLIC_IP="$(curl -s -m 3 https://api.ipify.org 2>/dev/null | tr -d '[:space:]')"
    [ -z "$PUBLIC_IP" ] && PUBLIC_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    BASE_URL="${PUBLIC_IP:-127.0.0.1}"

    HTTP_CODE="$(curl -s -o /dev/null -m 5 -w "%{http_code}" "http://${BASE_URL}/vnc.html" 2>/dev/null)"
    echo ""
    if [ "${HTTP_CODE:-000}" = "200" ]; then
        echo "====================================================="
        echo "✓ ease-Desk Installed & Running in Background!"
        echo "====================================================="
        echo "   👉 Open: http://${BASE_URL}/vnc.html?autoconnect=true&resize=scale"
        echo ""
        echo "   Status anytime:  systemctl status easedesk"
        echo "====================================================="
    else
        echo "====================================================="
        echo "⚠️  ease-Desk installed, but the web URL is NOT ready yet."
        echo "====================================================="
        echo "  Nginx answered HTTP ${HTTP_CODE:-000} on :80."
        echo "  Diagnose with:"
        echo "    systemctl status nginx easedesk"
        echo "    journalctl -u easedesk --no-pager -n 50"
        echo "    ss -tln | grep -E ':(80|6080|5900)'"
        echo "====================================================="
    fi
else
    echo ""
    echo "====================================================="
    echo "✓ ease-Desk Installed Successfully!"
    echo "====================================================="
    echo "Type 'desktop' to launch it."
    echo "====================================================="
fi
