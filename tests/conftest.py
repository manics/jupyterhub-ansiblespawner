""" pytest config for ansiblespawner tests """
# https://github.com/jupyterhub/yarnspawner/blob/0.4.0/yarnspawner/tests/conftest.py
import pytest

from jupyterhub.tests.mocking import MockHub
import os
import socket
import sys
from traitlets.config import Config

from ansiblespawner import AnsibleSpawner


# make Hub connectable by default
MockHub.hub_ip = "0.0.0.0"


def pytest_configure(config):
    config.addinivalue_line("markers", "docker: Run only docker tests")
    config.addinivalue_line("markers", "podman: Run only podman tests")


def _get_host_default_ip():
    """
    IP associated with the default route
    https://stackoverflow.com/a/28950776
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        # doesn't even have to be reachable
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]


# https://docs.pytest.org/en/latest/example/parametrize.html#apply-indirect-on-particular-arguments
@pytest.fixture
async def app(request):
    """
    Mock a jupyterhub app for testing

    Takes a parameter indicating the name of the directory under examples
    """

    def abspath(f):
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "examples",
            request.param,
            f,
        )

    c = Config()
    c.JupyterHub.spawner_class = AnsibleSpawner
    c.AnsibleSpawner.inventory = abspath("inventory.yml.j2")
    c.AnsibleSpawner.create_playbook = abspath("create.yml")
    if request.param == "podman" and os.getenv("GITHUB_ACTIONS") == "true":
        # TODO: Works on Fedora and Ubuntu 20.04 Vagrant VM.
        # Doesn't work on Ubuntu 20.04 GitHub workflow.
        print("Disabling podman update_playbook")
    else:
        c.AnsibleSpawner.update_playbook = abspath("update.yml")
    c.AnsibleSpawner.poll_playbook = abspath("poll.yml")
    c.AnsibleSpawner.destroy_playbook = abspath("destroy.yml")
    c.AnsibleSpawner.playbook_vars = {
        "container_image": "docker.io/jupyter/base-notebook",
        # If you have python2 and python3 ansible-runner may get confused
        "ansible_python_interpreter": "python3",
    }
    c.AnsibleSpawner.start_timeout = 600
    c.JupyterHub.hub_connect_ip = _get_host_default_ip()

    mocked_app = MockHub.instance(config=c)

    await mocked_app.initialize([])
    await mocked_app.start()

    try:
        yield mocked_app
    finally:
        # disconnect logging during cleanup because pytest closes captured FDs
        # prematurely
        mocked_app.log.handlers = []
        MockHub.clear_instance()
        try:
            mocked_app.stop()
        except Exception as e:
            print("Error stopping Hub: %s" % e, file=sys.stderr)
