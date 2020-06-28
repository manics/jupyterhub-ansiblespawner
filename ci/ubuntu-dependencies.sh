#!/bin/sh
set -eux

# Podman https://podman.io/getting-started/installation.html
. /etc/os-release
echo "deb http://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_${VERSION_ID}/ /" > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list
wget -nv https://download.opensuse.org/repositories/devel:kubic:libcontainers:stable/xUbuntu_${VERSION_ID}/Release.key -O- | apt-key add -

# Install Docker, Podman, language dependencies
apt-get update -qq
apt-get install -qq -y --install-recommends \
    docker.io \
    podman fuse-overlayfs \
    python3 python3-pip python3-venv \
    npm

# Other system requirements
npm install -g configurable-http-proxy
usermod -aG docker vagrant

# Display info
docker info
podman info
fuse-overlayfs --version
slirp4netns --version
python3 --version
npm version
configurable-http-proxy --version

# # echo 'user.max_user_namespaces=65536' > /etc/sysctl.d/90-podman.conf
# su vagrant -c "python3 -mvenv ~/venv"
