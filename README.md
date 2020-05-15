# AnsibleSpawner

[![Build Status](https://travis-ci.com/manics/jupyterhub-ansiblespawner.svg?branch=master)](https://travis-ci.com/manics/jupyterhub-ansiblespawner)

Spawn [JupyterHub](https://github.com/jupyterhub/jupyterhub) single user notebook servers using [Ansible](https://www.ansible.com/).


## Prerequisites

Python 3.6 or above and JupyterHub 1.0.0 or above are required.


## Installation


## Configuration


## Development

Pytest is used to run automated tests that require [Docker](https://www.docker.com/) and [Podman](https://podman.io/).
These platforms were chosen because they are self-contained and can be installed in Travis, whereas testing with public cloud platforms requires secure access credentials.

If you only have one of these you can limit tests by specifying a marker.
For example, to disable the Docker tests:

    pytest -vs -m "not docker"
