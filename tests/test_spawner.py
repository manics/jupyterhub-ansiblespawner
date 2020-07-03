"""Tests for AnsibleSpawner class"""
# https://github.com/jupyterhub/yarnspawner/blob/0.4.0/yarnspawner/tests/test_spawner.py
import pytest

from jupyterhub.tests.utils import add_user, api_request
from jupyterhub.tests.mocking import public_url
from jupyterhub.tests.utils import async_requests
from jupyterhub.utils import url_path_join
from shutil import which
from tornado import gen

from ansiblespawner import AnsibleSpawner


def _podman_enabled():
    return bool(which("podman"))


@pytest.mark.parametrize(
    "app",
    [
        pytest.param("docker", marks=pytest.mark.docker),
        pytest.param("podman", marks=pytest.mark.podman),
    ],
    indirect=["app"],
)
@pytest.mark.asyncio
async def test_integration(app):
    # Create a user
    add_user(app.db, app, name="alice")
    alice = app.users["alice"]
    assert isinstance(alice.spawner, AnsibleSpawner)
    token = alice.new_api_token()

    # Not started, status should be 0
    status = await alice.spawner.poll()
    assert status == 0

    # Stop can be called before start, no-op
    await alice.spawner.stop()

    # Start the server, and wait for it to start
    resp = None
    while resp is None or resp.status_code == 202:
        await gen.sleep(2.0)
        resp = await api_request(app, "users", "alice", "server", method="post")

    # check progress events were emitted
    count = 0
    async for e in alice.spawner.progress():
        count += 1
        assert e["message"].startswith("playbook_on_")
    # Actual number of events obviously depends on the playbook
    assert count >= 5

    # Check that everything is running fine
    url = url_path_join(public_url(app, alice), "api/status")
    resp = await async_requests.get(url, headers={"Authorization": "token %s" % token})
    resp.raise_for_status()
    assert "kernels" in resp.json()

    # Save the app_id to use later
    # app_id = alice.spawner.app_id

    # Shutdown the server
    resp = await api_request(app, "users", "alice", "server", method="delete")
    resp.raise_for_status()

    # Check status
    status = await alice.spawner.poll()
    assert status == 0
