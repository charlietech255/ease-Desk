#!/usr/bin/env bash
set -e

# Setup wayvnc password
if [ -n "$EASEDESK_VNC_PASS" ]; then
    mkdir -p /home/easedesk/.vnc
    printf '%s' "$EASEDESK_VNC_PASS" > /home/easedesk/.vnc/plainpass
    chmod 600 /home/easedesk/.vnc/plainpass
fi

# Ensure config and log directories exist
mkdir -p /home/easedesk/.config/easedesk /home/easedesk/.cache/easedesk/logs
chown -R easedesk:easedesk /home/easedesk/.config /home/easedesk/.cache /home/easedesk/.vnc 2>/dev/null || true

# Setup Nginx SSL certificate if missing
if [ ! -f /etc/nginx/ssl/easedesk.crt ]; then
    sudo mkdir -p /etc/nginx/ssl
    sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/easedesk.key \
        -out /etc/nginx/ssl/easedesk.crt \
        -subj "/C=US/ST=State/L=City/O=ease-Desk/CN=localhost"
fi

# Configure Nginx for wayvnc/websockify
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

 location /novnc/ {
  rewrite ^/novnc(/.*)$ \$1 break;
  proxy_pass http://127.0.0.1:6080/;
  proxy_http_version 1.1;
  proxy_set_header Upgrade \$http_upgrade;
  proxy_set_header Connection \$connection_upgrade;
  proxy_set_header Host \$host;
  proxy_read_timeout 86400s;
  proxy_send_timeout 86400s;
 }

 location = /auth_check {
  proxy_pass http://127.0.0.1:6080/;
  proxy_hide_header WWW-Authenticate;
 }

 location /websockify {
  proxy_pass http://127.0.0.1:6080;
  proxy_http_version 1.1;
  proxy_set_header Upgrade \$http_upgrade;
  proxy_set_header Connection \$connection_upgrade;
  proxy_set_header Host \$host;
  proxy_read_timeout 86400s;
  proxy_send_timeout 86400s;
 }

 location = /logout {
  root /opt/ease-desk/shared/web;
  rewrite ^/logout$ /logout.html break;
 }

 location ~* ^/(assets|core|vendor|app|images|sounds)(/.*)?$ {
  proxy_pass http://127.0.0.1:6080;
  proxy_http_version 1.1;
  proxy_set_header Upgrade \$http_upgrade;
  proxy_set_header Connection \$connection_upgrade;
  proxy_set_header Host \$host;
  proxy_read_timeout 86400s;
  proxy_send_timeout 86400s;
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
