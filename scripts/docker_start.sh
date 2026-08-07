#!/usr/bin/env bash
# ==============================================================================
# ease-Desk — 1-Command Docker VPS Launcher
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo "====================================================="
echo "   Starting ease-Desk in Isolated Docker Container   "
echo "====================================================="

# Check if docker is installed
if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed on this system."
    echo "To install Docker on Ubuntu/Debian/VPS, run:"
    echo "    curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# Build and start container
docker compose up --build -d

echo ""
echo "====================================================="
echo "✓ ease-Desk Container is now running!"
echo "====================================================="
echo "🌐 Web Browser Access:  http://localhost:6080/vnc.html"
echo "🖥️  VNC Client:         localhost:5900"
echo "🔑 SSH Access:          ssh -X -p 2222 charlie@localhost"
echo "                        (Password: charlie)"
echo "====================================================="
echo "To view live logs:      docker compose logs -f"
echo "To stop container:      docker compose down"
echo "====================================================="
