# AnsibleSpawner

![GitHub Workflow](https://github.com/manics/jupyterhub-ansiblespawner/workflows/Build/badge.svg?branch=master&event=push)
[![codecov](https://codecov.io/gh/manics/jupyterhub-ansiblespawner/branch/master/graph/badge.svg)](https://codecov.io/gh/manics/jupyterhub-ansiblespawner)

Spawn [JupyterHub](https://github.com/jupyterhub/jupyterhub) single user notebook servers using [Ansible](https://www.ansible.com/).

This spawner runs Ansible playbooks to start, manage and stop JupyterHub singleuser servers.
This means any Ansible module can be used to orchestrate your singleuser servers, including [Docker and many public/private clouds](https://docs.ansible.com/ansible/latest/modules/list_of_cloud_modules.html), and other infrastructure platforms supported by the community.
You can do things like create multiple storage volumes for each user, or provision additional services on other containers/VMs.


## Prerequisites

Python 3.6 or above and JupyterHub 1.0.0 or above are required.


## Installation


## Configuration

Example `jupyterhub_config.py` spawner configuration.
```
ansible_path = "/path/to/"
c.JupyterHub.spawner_class = "ansible"
c.AnsibleSpawner.inventory = ansible_path + "inventory.yml.j2"
c.AnsibleSpawner.create_playbook = ansible_path + "create.yml"
c.AnsibleSpawner.update_playbook = ansible_path + "update.yml"
c.AnsibleSpawner.poll_playbook = ansible_path + "poll.yml"
c.AnsibleSpawner.destroy_playbook = ansible_path + "destroy.yml"
c.AnsibleSpawner.playbook_vars = {
    "container_image": "docker.io/jupyter/base-notebook",
    "ansible_python_interpreter": "python3",
}
c.AnsibleSpawner.start_timeout = 600
c.JupyterHub.hub_connect_ip = "10.0.0.1"
```
See the example playbooks under [`./examples`](./examples)


## Development

Pytest is used to run automated tests that require [Docker](https://www.docker.com/) and [Podman](https://podman.io/).
These platforms were chosen because they are self-contained and can be installed in Travis, whereas testing with public cloud platforms requires secure access credentials.

If you only have one of these you can limit tests by specifying a marker.
For example, to disable the Docker tests:

    pytest -vs -m "not docker"

To view test coverage run pytest with `--cov=ansiblespawner --cov-report=html`, then open `htmlcov/index.html`.

[setuptools-scm](https://pypi.org/project/setuptools-scm/) is used to manage versions.
Just create a git tag.
