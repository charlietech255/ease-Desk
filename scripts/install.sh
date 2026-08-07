#!/usr/bin/env bash
# ==============================================================================
# ease-Desk Installation Script (Debian / Ubuntu)
# ==============================================================================
set -e

INSTALL_DIR="/opt/ease-desk"
BIN_LINK="/usr/local/bin/desktop"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Installing ease-Desk ==="

# Check root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "This script requires root privileges to install system packages and global binaries."
    echo "Please run with sudo: sudo $0"
    exit 1
fi

# Update and install dependencies if apt-get is available
if command -v apt-get >/dev/null 2>&1; then
    echo "Installing system dependencies via apt..."
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
        procps \
        scrot \
        curl
fi

# Create target installation directory
echo "Deploying files to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
cp -r "${ROOT_DIR}/desktop" "${INSTALL_DIR}/"
cp -r "${ROOT_DIR}/file_manager" "${INSTALL_DIR}/"
cp -r "${ROOT_DIR}/shared" "${INSTALL_DIR}/"
cp -r "${ROOT_DIR}/scripts" "${INSTALL_DIR}/"
[ -f "${ROOT_DIR}/unnamed.png" ] && cp "${ROOT_DIR}/unnamed.png" "${INSTALL_DIR}/"

# Set permissions
chmod +x "${INSTALL_DIR}/scripts/desktop"
chmod -R a+rX "${INSTALL_DIR}"

# Create symlink
echo "Creating symlink ${BIN_LINK}..."
ln -sf "${INSTALL_DIR}/scripts/desktop" "${BIN_LINK}"
chmod +x "${BIN_LINK}"

echo ""
echo "=== Installation complete ==="
echo "You can now start ease-Desk by running:"
echo "    desktop"
