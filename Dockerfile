FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV KASM_VERSION="1.5.0"
ENV OS_CODENAME="jammy"
ENV ARCH="amd64"

# 1. Install base system dependencies
RUN apt-get update && apt-get install -y -qq --no-install-recommends \
    wget \
    curl \
    git \
    ca-certificates \
    python3 \
    python3-gi \
    gir1.2-gtk-3.0 \
    gir1.2-vte-2.91 \
    xvfb \
    openbox \
    nginx \
    procps \
    scrot \
    wmctrl \
    xdotool \
    net-tools \
    fonts-dejavu-core \
    fonts-noto-color-emoji \
    adwaita-icon-theme \
    papirus-icon-theme \
    hicolor-icon-theme \
    epiphany-browser \
    pulseaudio \
    pulseaudio-utils \
    mpv \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav \
    gstreamer1.0-gtk3 \
    gir1.2-gst-plugins-base-1.0 \
    python3-gst-1.0 \
    libgstreamer1.0-dev \
    ssl-cert \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# 2. Install KasmVNC
RUN wget -qO /tmp/kasmvncserver.deb "https://github.com/kasmtech/KasmVNC/releases/download/v${KASM_VERSION}/kasmvncserver_${OS_CODENAME}_${KASM_VERSION}_${ARCH}.deb" && \
    apt-get update && \
    apt-get install -y -qq /tmp/kasmvncserver.deb && \
    rm -f /tmp/kasmvncserver.deb && \
    rm -rf /var/lib/apt/lists/*

# Force KasmVNC remote scaling in index.html
RUN if [ -f /usr/share/kasmvnc/www/index.html ]; then \
        sed -i 's|</head>|<style>body, html, #noVNC_container { overflow: hidden !important; }</style><script>/* easedesk-force-remote-scale */ window.localStorage.setItem("kasm.scaling", "remote");</script></head>|g' /usr/share/kasmvnc/www/index.html; \
    fi

# 3. Create non-root user
RUN useradd -m -s /bin/bash -u 1000 easedesk && \
    usermod -aG ssl-cert easedesk && \
    echo "easedesk ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# 4. Copy ease-Desk codebase
COPY . /opt/ease-desk
RUN chown -R easedesk:easedesk /opt/ease-desk && \
    chmod +x /opt/ease-desk/scripts/*.sh /opt/ease-desk/scripts/desktop

USER easedesk
WORKDIR /home/easedesk

# Use the new entrypoint
ENTRYPOINT ["/opt/ease-desk/scripts/entrypoint.sh"]
