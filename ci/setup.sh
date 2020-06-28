#!/bin/sh
set -eu

# If in vagrant:
if [ -d /home/vagrant -a -z "${VIRTUAL_ENV:-}" ]; then
    if [ ! -d ./venv ]; then
        python3 -mvenv ~/venv
    fi
    . ./venv/bin/activate
    cd jupyterhub-ansiblespawner
fi

python3 -mpip install -r dev-requirements.txt
# Need to use -e for pytest-cov to work
python3 -mpip install -e .
python3 -mpip freeze

cd examples/podman
ansible-galaxy collection install -p collections -r requirements.yml
cd ../..

PYTEST_COMMAND="pytest --cov=ansiblespawner tests -vs --cov-report=term-missing"
echo "Running $PYTEST_COMMAND"
$PYTEST_COMMAND
