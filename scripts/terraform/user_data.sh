#!/usr/bin/env bash
# Cloud-Init script to setup Docker and ease-Desk on boot

export DEBIAN_FRONTEND=noninteractive

# 1. Update and install prerequisites
apt-get update
apt-get install -y ca-certificates curl gnupg git

# 2. Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# 3. Add Docker repository
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Install Docker Compose
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. Clone ease-Desk repository
git clone https://github.com/charlietech255/ease-Desk.git /opt/ease-Desk
cd /opt/ease-Desk

# 6. Start the environment via Docker Compose
docker compose up --build -d
