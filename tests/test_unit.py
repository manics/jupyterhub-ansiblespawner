"""Unit tests for AnsibleSpawner class"""
from collections import namedtuple
import os
import pytest
from tempfile import gettempdir, TemporaryDirectory
import yaml

from ansiblespawner import AnsibleSpawner, AnsibleException


resources_dir = os.path.abspath(os.path.dirname(__file__))


@pytest.mark.asyncio
async def test_ansible_async(event_loop):
    a = AnsibleSpawner()
    with open(os.path.join(resources_dir, "unit_inventory.yml")) as f:
        inventory = yaml.safe_load(f)

    r = await a.ansible_async(
        event_loop,
        inventory=inventory,
        playbook=os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "unit_playbook.yml"
        ),
    )
    assert r.status == "successful"


@pytest.mark.parametrize(
    "inventory_dict,private_data_dir,event_handler",
    [(True, True, True), (False, False, False)],
)
@pytest.mark.asyncio
async def test_run_ansible(
    event_loop, tmp_path, inventory_dict, private_data_dir, event_handler
):
    a = AnsibleSpawner()

    inventory_file = os.path.join(resources_dir, "unit_inventory.yml")
    if inventory_dict:
        with open(inventory_file) as f:
            inventory = yaml.safe_load(f)
    else:
        with open(inventory_file) as f:
            content = f.read()
        inventory = inventory_file, content

    kwargs = {}
    if private_data_dir:
        private_data_tmp_path = tmp_path
        kwargs["private_data_dir"] = str(private_data_tmp_path)

    event_handler_events = []

    def event_handler_func(e):
        event_handler_events.append(e)
        return True

    if event_handler:
        kwargs["event_handler"] = event_handler_func

    r = await a.run_ansible(
        event_loop,
        inventory=inventory,
        playbook=os.path.join(resources_dir, "unit_playbook.yml"),
        **kwargs,
    )

    assert r["stats"] == {
        "skipped": {},
        "ok": {"localhost": 2},
        "dark": {},
        "failures": {},
        "processed": {"localhost": 1},
        "changed": {},
    }

    runner_on_ok = [e for e in r["events"] if e["event"] == "runner_on_ok"]
    assert len(runner_on_ok) == 2
    assert runner_on_ok[0]["event_data"]["task_action"] == "set_fact"
    assert runner_on_ok[1]["event_data"]["task_action"] == "set_fact"
    assert runner_on_ok[0]["event_data"]["res"]["ansible_facts"] == {
        "ansiblespawner_output": {"ip": "127.0.0.127", "port": 12345}
    }
    assert runner_on_ok[1]["event_data"]["res"]["ansible_facts"] == {
        "ansiblespawner_output": {"inventory_var": "abc"}
    }

    if private_data_dir:
        assert r["tmpdir"] is None
        items1 = sorted(p.name for p in private_data_tmp_path.iterdir())
        assert items1 == ["artifacts", "inventory"]
        items2 = sorted(
            p.name for p in (private_data_tmp_path / "artifacts").glob("**/*")
        )
        # May want to change this to >= N instead
        assert len(items2) == 16
    else:
        assert r["tmpdir"].name.startswith(
            os.path.join(gettempdir(), "ansiblespawner-")
        )
        r["tmpdir"].cleanup()

    if event_handler:
        assert [e["event"] for e in event_handler_events] == [
            "playbook_on_start",
            "playbook_on_play_start",
            "playbook_on_task_start",
            "runner_on_start",
            "runner_on_ok",
            "playbook_on_task_start",
            "runner_on_start",
            "runner_on_ok",
            "playbook_on_stats",
        ]
    else:
        assert len(event_handler_events) == 0


@pytest.mark.parametrize(
    "playbook", ["non_existent.yml", "unit_empty_playbook.yml"],
)
@pytest.mark.asyncio
async def test_run_ansible_exception(event_loop, playbook):
    a = AnsibleSpawner()

    with open(os.path.join(resources_dir, "unit_inventory.yml")) as f:
        inventory = yaml.safe_load(f)

    with pytest.raises(AnsibleException) as exc:
        _ = await a.run_ansible(
            event_loop,
            inventory=inventory,
            playbook=os.path.join(resources_dir, playbook),
        )
    exc_string = str(exc.value)
    if playbook == "non_existent.yml":
        assert exc_string.startswith("AnsibleException: Non-zero exit code ")
        assert exc.value.rc > 0
        assert exc.value.status == "failed"
        assert exc.value.stats is None
        assert len(exc.value.events) > 0
    else:
        assert exc_string.startswith("AnsibleException: No successful tasks ")
        assert exc.value.rc == 0
        assert exc.value.status == "successful"
        assert exc.value.stats == {
            "skipped": {},
            "ok": {},
            "dark": {},
            "failures": {},
            "processed": {},
            "changed": {},
        }
        assert [e["event"] for e in exc.value.events] == [
            "playbook_on_start",
            "playbook_on_play_start",
            "playbook_on_stats",
        ]


@pytest.mark.parametrize("inventory_callable", [True, False])
@pytest.mark.asyncio
async def test_get_inventory(monkeypatch, tmp_path, inventory_callable):
    a = AnsibleSpawner()
    user = {"user": {"escaped_name": "user", "name": "user"}}

    async def _get_extravars():
        return {"user": {"escaped_name": "user", "name": "user"}}

    monkeypatch.setattr(a, "_get_extravars", _get_extravars)
    inventory_input = "x: {{ user.name }}"
    expected = "x: user"
    if inventory_callable:

        def inventory_function(**kwargs):
            assert kwargs == user
            return "inventory.yml", expected

        a.inventory = inventory_function
    else:
        inventory_file = tmp_path / "inventory.yml.j2"
        inventory_file.write_text(inventory_input)
        a.inventory = str(inventory_file)
    i = await a._get_inventory()
    assert i == ("inventory.yml", expected)


@pytest.mark.parametrize("playbook_vars", [None, {"a": 1}, lambda: {"a": 1}])
@pytest.mark.asyncio
async def test_get_extravars(monkeypatch, playbook_vars):
    a = AnsibleSpawner()
    a.cmd = ["command"]
    a.playbook_vars = playbook_vars

    User = namedtuple("User", ["escaped_name", "name"])
    a.user = User("user", "user")
    monkeypatch.setattr(a, "get_env", lambda: {"ENV": "var"})

    expected = {
        "command": ["command"],
        "serverinfo": {},
        "user": {"escaped_name": "user", "name": "user"},
        "spawner_environment": {"ENV": "var"},
    }
    if playbook_vars:
        expected["a"] = 1

    vars = await a._get_extravars()
    assert vars == expected


@pytest.mark.parametrize("keep_temp_dirs", [True, False])
def test_cleanup_tmpdir(keep_temp_dirs):
    a = AnsibleSpawner()
    a.keep_temp_dirs = keep_temp_dirs
    tmpdir = TemporaryDirectory()

    a._cleanup_tmpdir(tmpdir)
    assert os.path.isdir(tmpdir.name) == keep_temp_dirs
    tmpdir.cleanup()
