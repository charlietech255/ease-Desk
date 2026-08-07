# ==============================================================================
# Charlie Desktop — Lightweight VPS Environment Dockerfile
# ==============================================================================
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
ENV PYTHONPATH=/opt/ease-desk
ENV AUTOSTART_DESKTOP=1

# Install system dependencies, graphical stack, OpenSSH, and tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    sudo \
    locales \
    python3 \
    python3-pip \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-gdkpixbuf-2.0 \
    openbox \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    procps \
    scrot \
    curl \
    net-tools \
    fonts-dejavu-core \
    fonts-noto-color-emoji \
    adwaita-icon-theme \
    && rm -rf /var/lib/apt/lists/* \
    && ( [ -f /usr/share/novnc/vnc.html ] && ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html || true )

# Configure locales
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && locale-gen

# Configure SSH server for X11 Forwarding & remote login
RUN mkdir -p /var/run/sshd && \
    echo "X11Forwarding yes" >> /etc/ssh/sshd_config && \
    echo "X11UseLocalhost no" >> /etc/ssh/sshd_config && \
    echo "PermitUserEnvironment no" >> /etc/ssh/sshd_config && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# Create user 'charlie' with password 'charlie'
RUN useradd -m -s /bin/bash -G sudo charlie && \
    echo "charlie:charlie" | chpasswd

# Create realistic sample VPS filesystem structure
RUN mkdir -p /var/www/html \
             /var/www/assets \
             /var/www/uploads \
             /var/log \
             /etc/charlie \
             /home/charlie/Documents \
             /home/charlie/Downloads \
             /home/charlie/Projects

# Populate sample files
RUN echo '<?php\n// Charlie VPS Demo Application\necho "<h1>Welcome to Charlie VPS</h1>";\nphpinfo();\n?>' > /var/www/html/index.php && \
    echo '<!DOCTYPE html>\n<html>\n<head><title>Charlie Server</title><link rel="stylesheet" href="/assets/style.css"></head>\n<body>\n  <h1>Charlie Web Server</h1>\n  <p>Status: Online</p>\n</body>\n</html>' > /var/www/html/index.html && \
    echo 'body { font-family: sans-serif; background: #0e121c; color: #dce3f0; margin: 2rem; }\nh1 { color: #7aa2f7; }' > /var/www/assets/style.css && \
    echo 'console.log("Charlie Server Application Loaded.");' > /var/www/assets/app.js && \
    echo '{\n  "server_name": "charlie-vps",\n  "environment": "production",\n  "version": "1.0.0",\n  "port": 8080\n}' > /home/charlie/Projects/config.json && \
    echo '# ease-Desk VPS\n\nWelcome to your lightweight server administration environment.\nRun `desktop` to manage server files.' > /home/charlie/Documents/README.md && \
    echo '[database]\nhost = 127.0.0.1\nport = 5432\nname = charlie_db\nuser = charlie\n' > /etc/charlie/database.conf && \
    echo '[2026-08-07 09:00:00] INFO: Server initialized.\n[2026-08-07 09:05:00] INFO: SSH service started on port 22.\n[2026-08-07 09:10:00] INFO: ease-Desk environment ready.' > /var/log/server.log

# Fix ownership
RUN chown -R charlie:charlie /home/charlie /var/www

# Install ease-Desk into /opt/ease-desk
WORKDIR /opt/ease-desk
COPY . /opt/ease-desk

RUN chmod +x /opt/ease-desk/scripts/desktop /opt/ease-desk/scripts/*.sh && \
    ln -sf /opt/ease-desk/scripts/desktop /usr/local/bin/desktop

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22 5900 6080

ENTRYPOINT ["/entrypoint.sh"]
