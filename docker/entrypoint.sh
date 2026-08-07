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
echo "   ease-Desk — VPS Simulation Environment            "
echo "====================================================="
echo "SSH Server:  Port 22 (Mapped to host port 2222)"
echo "User:        charlie"
echo "Password:    charlie"
echo "-----------------------------------------------------"
echo "Connect with:  ssh -X -p 2222 charlie@localhost"
echo "Then execute:  desktop"
echo "====================================================="

# Start SSH daemon in foreground or execute command
if [ "$#" -eq 0 ]; then
    exec /usr/sbin/sshd -D -e
else
    # Start sshd in background then run command
    /usr/sbin/sshd
    exec "$@"
fi
