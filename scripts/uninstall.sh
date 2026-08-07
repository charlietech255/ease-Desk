#!/usr/bin/env bash
# ==============================================================================
# ease-Desk Uninstallation Script
# ==============================================================================
set -e

INSTALL_DIR="/opt/ease-desk"
BIN_LINK="/usr/local/bin/desktop"

echo "=== Uninstalling ease-Desk ==="

if [ "$(id -u)" -ne 0 ]; then
    echo "This script requires root privileges. Please run with sudo: sudo $0"
    exit 1
fi

if [ -L "${BIN_LINK}" ] || [ -f "${BIN_LINK}" ]; then
    echo "Removing ${BIN_LINK}..."
    rm -f "${BIN_LINK}"
fi

if [ -d "${INSTALL_DIR}" ]; then
    echo "Removing ${INSTALL_DIR}..."
    rm -rf "${INSTALL_DIR}"
fi

echo "=== Uninstallation complete ==="
