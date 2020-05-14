#!/bin/sh
set -eu

# If in vagrant:
if [ -d /home/vagrant -a -z "${VIRTUAL_ENV:-}" ]; then
    . ~/venv/bin/activate
    cd /jupyterhub-ansiblespawner
fi

python3 -mpip install -r dev-requirements.txt
# Need to use -e for pytest-cov to work
python3 -mpip install -e .
python3 -mpip freeze

cd examples/podman
ansible-galaxy collection install -p collections -r requirements.yml
cd ..
