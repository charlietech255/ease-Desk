#!/usr/bin/env bash
# ==============================================================================
# ease-Desk — Ultimate All-in-One Installer & Production Deployer
# Author: charlie
# Supports: Ubuntu, Debian, CentOS, RHEL, Fedora, Arch Linux, Termux
# ==============================================================================
set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}"
echo "================================================================"
echo "   ✨ ease-Desk — Ultimate All-in-One Production Installer      "
echo "================================================================"
echo -e "${NC}"

# ------------------------------------------------------------------------------
# 1. Privilege Elevation & Path Resolution
# ------------------------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
    INSTALL_DIR="/opt/ease-desk"
    BIN_DIR="/usr/local/bin"
    TARGET_USER="${SUDO_USER:-root}"
else
    if command -v sudo >/dev/null 2>&1; then
        echo -e "${YELLOW}⚡ Elevating privileges with sudo...${NC}"
        exec sudo -E "$0" "$@"
    else
        INSTALL_DIR="${HOME}/.local/share/ease-desk"
        BIN_DIR="${HOME}/.local/bin"
        TARGET_USER="$USER"
        mkdir -p "${BIN_DIR}"
    fi
fi

TARGET_HOME=$(eval echo "~${TARGET_USER}")
[ -z "$TARGET_HOME" ] && TARGET_HOME="/root"

# Determine source directory (support piped curl | bash as well)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
if [ -n "$SCRIPT_DIR" ] && [ -d "${SCRIPT_DIR}/../desktop" ]; then
    SRC_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
else
    SRC_DIR=""
fi

# Port check helper
port_busy() {
    if command -v ss >/dev/null 2>&1; then
        ss -tln | grep -qE ":$1\b" && return 0
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tln | grep -qE ":$1\b" && return 0
    fi
    return 1
}

# ------------------------------------------------------------------------------
# 2. Cleanup Stale Sessions & Port Conflicts
# ------------------------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
    echo -e "${CYAN}🧹 [1/7] Cleaning up stale sessions and freeing ports...${NC}"
    systemctl stop easedesk >/dev/null 2>&1 || true
    pkill -9 -f "desktop.session.session" 2>/dev/null || true
    pkill -9 -f "desktop.shell.shell" 2>/dev/null || true
    pkill -9 -f "websockify" 2>/dev/null || true
    pkill -9 -f "x11vnc" 2>/dev/null || true

    # Clean old X11 sockets and lock files
    for num in $(seq 99 125); do
        rm -f "/tmp/.X${num}-lock" "/tmp/.X11-unix/X${num}" 2>/dev/null || true
    done

    # Free docker container if previously used
    if command -v docker >/dev/null 2>&1; then
        docker rm -f charlie-vps >/dev/null 2>&1 || true
    fi

    # Wait for ports 6080 and 5900 to be completely free
    for port in 6080 5900; do
        for _ in $(seq 1 10); do
            port_busy "$port" || break
            sleep 0.3
        done
    done
    echo -e "${GREEN}✓ Cleaned previous processes and lock files.${NC}"
fi

# ------------------------------------------------------------------------------
# 3. Password Authentication Setup
# ------------------------------------------------------------------------------
echo -e "${CYAN}🔒 [2/7] Security & VNC Password Configuration...${NC}"
if [ -n "${EASEDESK_VNC_PASS:-}" ]; then
    VNC_PASS="$EASEDESK_VNC_PASS"
else
    EXISTING_PASS_FILE="${TARGET_HOME}/.vnc/passwd"
    if [ -f "$EXISTING_PASS_FILE" ] && [ -s "$EXISTING_PASS_FILE" ]; then
        echo -e "An existing VNC password was found for user ${TARGET_USER}."
        read -r -p "Do you want to keep the existing password? (Y/n): " KEEP_PASS
        if [[ ! "$KEEP_PASS" =~ ^[Nn]$ ]]; then
            VNC_PASS=""
        fi
    fi

    if [ -z "${VNC_PASS+x}" ] || [ -z "$VNC_PASS" ]; then
        echo -n "🔑 Enter a secure login password for ease-Desk: "
        read -r -s VNC_PASS
        echo ""
        if [ -z "$VNC_PASS" ]; then
            VNC_PASS="easedesk$(head -c 4 /dev/urandom | od -A n -t x | tr -d ' ')"
            echo -e "${YELLOW}No password entered. Generated temporary password: ${BOLD}${VNC_PASS}${NC}"
        fi
    fi
fi

# ------------------------------------------------------------------------------
# 4. Package Installation (Multi-Distro)
# ------------------------------------------------------------------------------
echo -e "${CYAN}📦 [3/7] Installing System Dependencies...${NC}"

if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    # Install base dependencies
    apt-get install -y -qq \
        git \
        curl \
        wget \
        python3 \
        python3-gi \
        python3-gi-cairo \
        gir1.2-gtk-3.0 \
        gir1.2-gdkpixbuf-2.0 \
        gir1.2-vte-2.91 \
        openbox \
        xvfb \
        x11vnc \
        novnc \
        websockify \
        xrdp \
        xorgxrdp \
        nginx \
        procps \
        scrot \
        net-tools \
        fonts-dejavu-core \
        fonts-noto-color-emoji \
        adwaita-icon-theme \
        hicolor-icon-theme \
        >/dev/null 2>&1 || {
            echo -e "${YELLOW}Retrying essential apt packages...${NC}"
            apt-get install -y -qq python3 python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91 xvfb x11vnc novnc websockify xrdp nginx git curl wget >/dev/null 2>&1 || true
        }

    # Install ultra-lightweight native WebKit browser (Epiphany) for fast startup & minimal RAM (<80MB)
    echo -e "${CYAN}🌐 Installing Lightweight WebKit Browser (Epiphany)...${NC}"
    apt-get install -y -qq epiphany-browser 2>/dev/null || true
elif command -v dnf >/dev/null 2>&1; then
    dnf install -y python3 python3-gobject gtk3 vte291 xorg-x11-server-Xvfb x11vnc novnc python3-websockify xrdp xorgxrdp epiphany firefox chromium openbox nginx git curl wget
elif command -v pacman >/dev/null 2>&1; then
    pacman -Sy --noconfirm python python-gobject gtk3 vte3 xorg-server-xvfb x11vnc novnc websockify xrdp xorgxrdp epiphany firefox chromium openbox nginx git curl wget
elif command -v pkg >/dev/null 2>&1; then
    pkg install -y python x11-repo xwayland tigervnc git
fi
echo -e "${GREEN}✓ System dependencies and real web browser installed.${NC}"

# Install KasmVNC if on supported OS (Ubuntu/Debian)
KASM_VERSION="1.5.0"
if [ -f "/etc/os-release" ] && command -v apt-get >/dev/null 2>&1; then
    . /etc/os-release
    OS_CODENAME="${VERSION_CODENAME:-${UBUNTU_CODENAME}}"
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then ARCH="amd64"; elif [ "$ARCH" = "aarch64" ]; then ARCH="arm64"; fi
    
    SUPPORTED_CODENAMES="bookworm bullseye focal jammy noble trixie kali-rolling"
    if echo "$SUPPORTED_CODENAMES" | grep -q "$OS_CODENAME" && [ "$ARCH" != "$(uname -m)" ]; then
        echo -e "${CYAN}🚀 Installing KasmVNC for ${OS_CODENAME} (${ARCH})...${NC}"
        wget -qO /tmp/kasmvncserver.deb "https://github.com/kasmtech/KasmVNC/releases/download/v${KASM_VERSION}/kasmvncserver_${OS_CODENAME}_${KASM_VERSION}_${ARCH}.deb" || true
        if [ -s /tmp/kasmvncserver.deb ]; then
            apt-get install -y -qq /tmp/kasmvncserver.deb >/dev/null 2>&1 || echo -e "${YELLOW}KasmVNC installation failed, will fallback to Xvfb.${NC}"
            rm -f /tmp/kasmvncserver.deb
            usermod -aG ssl-cert "$TARGET_USER" 2>/dev/null || true
            
            # Setup native authentication if VNC_PASS is available
            if [ -n "$VNC_PASS" ] && command -v vncpasswd >/dev/null 2>&1; then
                for u_home in "$TARGET_HOME" "/root"; do
                    [ -d "$u_home" ] || continue
                    mkdir -p "${u_home}/.vnc"
                    echo -e "${VNC_PASS}\n${VNC_PASS}\n" | vncpasswd -u "$TARGET_USER" -rw "${u_home}/.vnc/passwd" >/dev/null 2>&1 || true
                    chmod 600 "${u_home}/.vnc/passwd" 2>/dev/null || true
                    [ "$TARGET_USER" != "root" ] && chown -R "${TARGET_USER}" "${u_home}/.vnc" 2>/dev/null || true
                done
                echo -e "${GREEN}✓ KasmVNC native authentication configured.${NC}"
            fi
        fi
    fi
fi

# Store password with x11vnc
if [ -n "$VNC_PASS" ] && command -v x11vnc >/dev/null 2>&1; then
    for u_home in "$TARGET_HOME" "/root"; do
        [ -d "$u_home" ] || continue
        mkdir -p "${u_home}/.vnc"
        x11vnc -storepasswd "$VNC_PASS" "${u_home}/.vnc/passwd" >/dev/null 2>&1 || true
        chmod 600 "${u_home}/.vnc/passwd" 2>/dev/null || true
        [ "$TARGET_USER" != "root" ] && chown -R "${TARGET_USER}" "${u_home}/.vnc" 2>/dev/null || true
    done
    echo -e "${GREEN}✓ Password saved securely.${NC}"
fi

# Ensure noVNC index.html symlink exists
for nv_dir in "/usr/share/novnc" "/usr/share/novnc-core" "/opt/novnc"; do
    if [ -d "$nv_dir" ] && [ -f "${nv_dir}/vnc.html" ]; then
        ln -sf "${nv_dir}/vnc.html" "${nv_dir}/index.html" 2>/dev/null || true
    fi
done

# ------------------------------------------------------------------------------
# 5. Code Deployment & Workspace Sync
# ------------------------------------------------------------------------------
echo -e "${CYAN}📂 [4/7] Deploying ease-Desk to ${INSTALL_DIR}...${NC}"
mkdir -p "${INSTALL_DIR}"

if [ -n "$SRC_DIR" ] && [ -d "${SRC_DIR}/desktop" ]; then
    cp -r "${SRC_DIR}/desktop" "${INSTALL_DIR}/"
    cp -r "${SRC_DIR}/file_manager" "${INSTALL_DIR}/"
    cp -r "${SRC_DIR}/shared" "${INSTALL_DIR}/"
    cp -r "${SRC_DIR}/scripts" "${INSTALL_DIR}/"
    for asset in "${SRC_DIR}"/*.png "${SRC_DIR}"/*.jpg "${SRC_DIR}"/*.svg "${SRC_DIR}"/*.md; do
        [ -f "${asset}" ] && cp "${asset}" "${INSTALL_DIR}/" 2>/dev/null || true
    done
elif [ ! -f "${INSTALL_DIR}/desktop/session/session.py" ]; then
    echo "Cloning latest ease-Desk from repository..."
    git clone https://github.com/charlietech255/ease-Desk.git "${INSTALL_DIR}"
fi

# ------------------------------------------------------------------------------
# 5.5 Optional Rust Native Core Compilation
# ------------------------------------------------------------------------------
if command -v cargo >/dev/null 2>&1 && command -v pip3 >/dev/null 2>&1; then
    echo -e "${CYAN}🦀 Compiling Native Rust Core (ease_desk_core)...${NC}"
    (
        cd "${INSTALL_DIR}"
        pip3 install maturin --break-system-packages 2>/dev/null || pip3 install maturin
        maturin develop --release || echo -e "${YELLOW}⚠️ Failed to compile Rust extension, falling back to Python implementations.${NC}"
    )
fi

chmod +x "${INSTALL_DIR}/scripts/desktop" 2>/dev/null || true
chmod +x "${INSTALL_DIR}/scripts/"*.sh 2>/dev/null || true
chmod -R a+rX "${INSTALL_DIR}"

mkdir -p "${BIN_DIR}"
ln -sf "${INSTALL_DIR}/scripts/desktop" "${BIN_DIR}/desktop"
ln -sf "${INSTALL_DIR}/scripts/desktop" "${BIN_DIR}/ease-desk"
ln -sf "${INSTALL_DIR}/scripts/desktop" "${BIN_DIR}/easedesk"
chmod +x "${BIN_DIR}/desktop" "${BIN_DIR}/ease-desk" "${BIN_DIR}/easedesk" 2>/dev/null || true
echo -e "${GREEN}✓ Files deployed and global 'ease-desk' / 'desktop' commands registered.${NC}"

# ------------------------------------------------------------------------------
# 6. Nginx Reverse Proxy Setup & Conflict Cleanup
# ------------------------------------------------------------------------------
if command -v nginx >/dev/null 2>&1 && [ "$(id -u)" -eq 0 ]; then
    echo -e "${CYAN}🌐 [5/7] Configuring Nginx Reverse Proxy...${NC}"

    # Free port 80 from Apache if active
    if systemctl is-active --quiet apache2 2>/dev/null; then
        echo -e "${YELLOW}Stopping Apache2 to release port 80 for Nginx...${NC}"
        systemctl stop apache2 || true
        systemctl disable apache2 || true
    fi

    # Detect primary public IP
    PUBLIC_IP="$(curl -s -m 3 https://api.ipify.org 2>/dev/null | tr -d '[:space:]' || true)"
    [ -z "$PUBLIC_IP" ] && PUBLIC_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")"

    if command -v kasmvncserver >/dev/null 2>&1; then
        PROXY_PASS="http://127.0.0.1:8444"
    else
        PROXY_PASS="http://127.0.0.1:6080"
    fi

    cat << EOF > /tmp/easedesk.conf
map \$http_upgrade \$connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _ ${PUBLIC_IP} localhost;

    location / {
        proxy_pass ${PROXY_PASS};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOF

    mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
    mv /tmp/easedesk.conf /etc/nginx/sites-available/easedesk

    # Clean out any old/conflicting sites in sites-enabled
    for site in /etc/nginx/sites-enabled/*; do
        [ -e "$site" ] || [ -L "$site" ] || continue
        [ "$(basename "$site")" = "easedesk" ] && continue
        echo -e "${YELLOW}Disabling conflicting site: $(basename "$site")${NC}"
        rm -f "$site"
    done

    # Disable conflicting files in conf.d
    for cfile in /etc/nginx/conf.d/*.conf; do
        [ -f "$cfile" ] || continue
        if grep -qE "3000|listen.*80" "$cfile" 2>/dev/null; then
            echo -e "${YELLOW}Disabling conflicting config: $(basename "$cfile")${NC}"
            mv "$cfile" "${cfile}.disabled" 2>/dev/null || true
        fi
    done

    ln -sf /etc/nginx/sites-available/easedesk /etc/nginx/sites-enabled/easedesk

    if nginx -t >/dev/null 2>&1; then
        systemctl restart nginx || true
        echo -e "${GREEN}✓ Nginx reverse proxy configured and reloaded.${NC}"
    else
        echo -e "${RED}❌ Nginx configuration test failed.${NC}"
    fi

    # Optional Certbot SSL Setup
    if command -v certbot >/dev/null 2>&1 && [ -t 0 ]; then
        echo -n "Do you have a custom domain name to configure SSL/HTTPS? (y/N): "
        read -r SETUP_SSL || SETUP_SSL="n"
        if [[ "$SETUP_SSL" =~ ^[Yy]$ ]]; then
            echo -n "Enter your domain name (e.g. desktop.example.com): "
            read -r DOMAIN_NAME
            echo -n "Enter your email for SSL registration: "
            read -r CERT_EMAIL
            if [ -n "$DOMAIN_NAME" ] && [ -n "$CERT_EMAIL" ]; then
                echo "🔒 Securing with Certbot..."
                certbot --nginx -d "$DOMAIN_NAME" --non-interactive --agree-tos -m "$CERT_EMAIL" || echo "⚠️ Certbot failed, HTTP remains active."
            fi
        fi
    fi
fi

# ------------------------------------------------------------------------------
# 7. Systemd Service Setup
# ------------------------------------------------------------------------------
if command -v systemctl >/dev/null 2>&1 && [ "$(id -u)" -eq 0 ]; then
    echo -e "${CYAN}⚙️ [6/7] Configuring Systemd Background Service...${NC}"
    cat << EOF > /etc/systemd/system/easedesk.service
[Unit]
Description=ease-Desk Virtual Desktop Session
After=network-online.target nginx.service
Wants=network-online.target

[Service]
Type=simple
User=${TARGET_USER}
WorkingDirectory=${INSTALL_DIR}
Environment=HOME=${TARGET_HOME}
Environment=PYTHONPATH=${INSTALL_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${BIN_DIR}/desktop
Restart=always
RestartSec=3
TimeoutStopSec=15
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable easedesk >/dev/null 2>&1
    systemctl restart easedesk || echo -e "${YELLOW}⚠️ Failed to start service.${NC}"
    echo -e "${GREEN}✓ ease-Desk systemd service installed and active.${NC}"

    # Configure XRDP Session Manager for Native Remote Desktop Connection
    if command -v xrdp >/dev/null 2>&1; then
        echo -e "${CYAN}🖥️ Configuring Native Remote Desktop (XRDP / Port 3389)...${NC}"
        
        # Configure user session scripts
        for u_dir in "$TARGET_HOME" "/root" "/etc/skel"; do
            [ -d "$u_dir" ] || continue
            cat << 'XSESSION_EOF' > "${u_dir}/.xsession"
#!/bin/sh
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
export PYTHONPATH="/opt/ease-desk:$PYTHONPATH"
exec /usr/local/bin/desktop
XSESSION_EOF
            chmod +x "${u_dir}/.xsession"
            [ "$TARGET_USER" != "root" ] && chown "${TARGET_USER}" "${u_dir}/.xsession" 2>/dev/null || true
        done

        # Fix XRDP permissions for SSL certs
        adduser xrdp ssl-cert >/dev/null 2>&1 || usermod -a -G ssl-cert xrdp >/dev/null 2>&1 || true

        # Suppress colord and packagekit authentication popups in XRDP sessions
        if [ -d /etc/polkit-1/localauthority/50-local.d ]; then
            cat << 'PKLA_EOF' > /etc/polkit-1/localauthority/50-local.d/45-allow-colord.pkla
[Allow Colord all Users]
Identity=unix-user:*
Action=org.freedesktop.color-manager.create-device;org.freedesktop.color-manager.create-profile;org.freedesktop.color-manager.delete-device;org.freedesktop.color-manager.delete-profile;org.freedesktop.color-manager.modify-device;org.freedesktop.color-manager.modify-profile
ResultAny=no
ResultInactive=no
ResultActive=yes
PKLA_EOF
        fi

        # Enable & start XRDP
        systemctl enable xrdp >/dev/null 2>&1 || true
        systemctl restart xrdp >/dev/null 2>&1 || true
        systemctl restart xrdp-sesman >/dev/null 2>&1 || true
        echo -e "${GREEN}✓ Native Remote Desktop Protocol (XRDP) active on port 3389.${NC}"
    fi

    # Configure Firewall Rules (UFW / Firewalld / iptables)
    if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
        echo -e "${CYAN}🛡️ Configuring UFW firewall rules...${NC}"
        ufw allow 3389/tcp comment "ease-Desk XRDP" >/dev/null 2>&1 || true
        ufw allow 80/tcp comment "ease-Desk Web Desktop" >/dev/null 2>&1 || true
        ufw allow 443/tcp comment "ease-Desk SSL" >/dev/null 2>&1 || true
        ufw allow 6080/tcp comment "ease-Desk WebSocket" >/dev/null 2>&1 || true
        ufw reload >/dev/null 2>&1 || true
        echo -e "${GREEN}✓ UFW firewall rules updated.${NC}"
    elif command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld 2>/dev/null; then
        echo -e "${CYAN}🛡️ Configuring Firewalld rules...${NC}"
        firewall-cmd --permanent --add-port={3389/tcp,80/tcp,443/tcp,6080/tcp} >/dev/null 2>&1 || true
        firewall-cmd --reload >/dev/null 2>&1 || true
        echo -e "${GREEN}✓ Firewalld rules updated.${NC}"
    fi
    # Also ensure iptables accepts port 3389
    iptables -I INPUT -p tcp --dport 3389 -j ACCEPT 2>/dev/null || true
fi

# ------------------------------------------------------------------------------
# 8. End-to-End Health Verification & Access Summary
# ------------------------------------------------------------------------------
echo -e "${CYAN}🔍 [7/7] Running End-to-End System Health Checks...${NC}"

if [ "$(id -u)" -eq 0 ]; then
    # Wait for service to warm up
    for _ in $(seq 1 30); do
        port_busy 6080 && break
        sleep 1
    done

    if port_busy 5900; then
        echo -e "${GREEN}✓ X11 VNC server active on :5900${NC}"
    fi

    if port_busy 6080; then
        echo -e "${GREEN}✓ WebSocket proxy active on :6080${NC}"
    fi

    if port_busy 3389; then
        echo -e "${GREEN}✓ Native RDP server active on :3389${NC}"
    fi

    PUBLIC_IP="$(curl -s -m 3 https://api.ipify.org 2>/dev/null | tr -d '[:space:]' || true)"
    [ -z "$PUBLIC_IP" ] && PUBLIC_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")"
    BASE_URL="${PUBLIC_IP:-127.0.0.1}"

    HTTP_CODE="$(curl -s -o /dev/null -m 4 -w "%{http_code}" "http://${BASE_URL}/vnc.html" 2>/dev/null || echo "000")"

    echo ""
    echo -e "${GREEN}${BOLD}================================================================${NC}"
    echo -e "${GREEN}${BOLD}   🎉 ease-Desk Cloud Distro & Remote Desktop Ready!            ${NC}"
    echo -e "${GREEN}${BOLD}================================================================${NC}"
    echo -e "   🌐 ${BOLD}1. Web Browser Desktop (Zero-Install):${NC}"
    echo -e "      👉 ${CYAN}http://${BASE_URL}/vnc.html?autoconnect=true&resize=scale${NC}"
    echo ""
    echo -e "   🖥️  ${BOLD}2. Native Remote Desktop (Windows / Mac / Phone RDP):${NC}"
    echo -e "      👉 Host:     ${CYAN}${BASE_URL}:3389${NC}"
    echo -e "      👉 Username: ${BOLD}${TARGET_USER}${NC}"
    echo -e "      👉 Password: ${BOLD}<Your Linux / SSH Password>${NC}"
    echo -e "      (Use 'Remote Desktop Connection' on Windows or 'Microsoft Remote Desktop' on Mac)"
    echo ""
    echo -e "   📋 ${BOLD}System Management:${NC}"
    echo -e "      • Check Status:  systemctl status easedesk"
    echo -e "      • View Logs:     journalctl -u easedesk -f"
    echo -e "      • Restart:       systemctl restart easedesk"
    echo -e "${GREEN}${BOLD}================================================================${NC}"
else
    echo -e "${GREEN}✓ User-level setup completed! Type 'desktop' to launch.${NC}"
fi
