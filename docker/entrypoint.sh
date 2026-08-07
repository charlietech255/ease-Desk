#!/usr/bin/env bash
# ==============================================================================
# ease-Desk Container Entrypoint
# ==============================================================================
set -e

# Generate host SSH keys if missing
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    ssh-keygen -A
fi

echo "====================================================="
echo "   ease-Desk — Docker VPS Environment                "
echo "====================================================="
echo "Web Desktop: http://localhost:6080/vnc.html"
echo "VNC Server:  localhost:5900"
echo "SSH Server:  localhost:2222 (User: charlie | Pass: charlie)"
echo "====================================================="

# Start SSH daemon
/usr/sbin/sshd

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

if [ "${AUTOSTART_DESKTOP:-1}" = "1" ] || [ "${AUTOSTART_DESKTOP:-1}" = "true" ]; then
    echo "Starting ease-Desk graphical environment..."
    export HOME=/home/charlie
    exec su - charlie -c "/opt/ease-desk/scripts/desktop"
else
    # Keep container alive with logs
    tail -f /dev/null
fi
