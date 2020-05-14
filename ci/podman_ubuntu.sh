#!/bin/sh
set -eux
# Install Podman
# https://podman.io/getting-started/installation.html

id
env | sort

for f in /proc/sys/user/max_*; do
    echo $f
    cat $f
done

. /etc/os-release
sudo sh -c "echo 'deb http://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_${VERSION_ID}/ /' > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list"
wget -nv https://download.opensuse.org/repositories/devel:kubic:libcontainers:stable/xUbuntu_${VERSION_ID}/Release.key -O- | sudo apt-key add -
sudo apt-get update -qq
# Travis defaults to --no-install-recommends
sudo apt-get -qq -y install --install-recommends podman
# podman-rootless ?

# On ubuntu:bionic running podman as non-root defaults to using VFS instead of overlay as the fuse-overlayfs package isn't available:
# https://github.com/containers/libpod/blob/master/docs/tutorials/rootless_tutorial.md#ensure-fuse-overlayfs-is-installed
# VFS is extremely inefficient so use a custom binary built using
# https://github.com/containers/fuse-overlayfs/tree/v1.0.0#static-build

sudo curl -sSfL https://github.com/manics/fuse-overlayfs-builder/releases/download/1.0.0-0/fuse-overlayfs.ubuntu -o /usr/bin/fuse-overlayfs
sudo chmod +x /usr/bin/fuse-overlayfs

fuse-overlayfs --version
slirp4netns --version
podman info
