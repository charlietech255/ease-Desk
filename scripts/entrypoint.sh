#!/usr/bin/env bash
set -e

# Setup KasmVNC password
if [ -n "$EASEDESK_VNC_PASS" ]; then
    mkdir -p /home/easedesk/.vnc
    echo -e "${EASEDESK_VNC_PASS}\n${EASEDESK_VNC_PASS}" | kasmvncpasswd -u easedesk -rw /home/easedesk/.kasmpasswd
    chmod 600 /home/easedesk/.kasmpasswd
fi

# Setup Nginx SSL certificate if missing
if [ ! -f /etc/nginx/ssl/easedesk.crt ]; then
    sudo mkdir -p /etc/nginx/ssl
    sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/easedesk.key \
        -out /etc/nginx/ssl/easedesk.crt \
        -subj "/C=US/ST=State/L=City/O=ease-Desk/CN=localhost"
fi

# Configure Nginx for KasmVNC
sudo bash -c 'cat <<EOF > /etc/nginx/sites-available/default
map \$http_upgrade \$connection_upgrade {
 default upgrade;
 ""  close;
}

server {
 listen 8444 ssl default_server;
 server_name _;

 ssl_certificate /etc/nginx/ssl/easedesk.crt;
 ssl_certificate_key /etc/nginx/ssl/easedesk.key;
 ssl_protocols TLSv1.2 TLSv1.3;

 location = / {
  root /opt/ease-desk/shared/web;
  try_files /login.html =404;
 }

 location ~* ^/(login\.html|logout\.html|session-guard\.js|desktop\.html)$ {
  root /opt/ease-desk/shared/web;
 }

 location /kasmvnc/ {
  rewrite ^/kasmvnc(/.*)$ \$1 break;
  proxy_pass http://127.0.0.1:8445;
  proxy_http_version 1.1;
  proxy_set_header Upgrade \$http_upgrade;
  proxy_set_header Connection \$connection_upgrade;
  proxy_set_header Host \$host;
  proxy_read_timeout 86400s;
  proxy_send_timeout 86400s;
  proxy_set_header Authorization "Basic \$cookie_easedesk_auth";
  proxy_hide_header WWW-Authenticate;
 }

 location = /auth_check {
  proxy_pass http://127.0.0.1:8445/;
  proxy_hide_header WWW-Authenticate;
 }

 location = /logout {
  root /opt/ease-desk/shared/web;
  rewrite ^/logout$ /logout.html break;
 }

 location ~* ^/(websockify|assets|core|vendor|app|images|sounds)(/.*)?$ {
  proxy_pass http://127.0.0.1:8445;
  proxy_http_version 1.1;
  proxy_set_header Upgrade \$http_upgrade;
  proxy_set_header Connection \$connection_upgrade;
  proxy_set_header Host \$host;
  proxy_read_timeout 86400s;
  proxy_send_timeout 86400s;
  proxy_set_header Authorization "Basic \$cookie_easedesk_auth";
  proxy_hide_header WWW-Authenticate;
 }
}
EOF'

# Start Nginx
sudo systemctl restart nginx || sudo nginx

# Clean up stale locks
sudo rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 || true

# Export environment variables for the desktop session
export USER=easedesk
export HOME=/home/easedesk
export DISPLAY=:99
export PYTHONPATH=/opt/ease-desk

# Start the ease-Desk session orchestrator
echo "Starting ease-Desk session..."
exec /opt/ease-desk/scripts/desktop
