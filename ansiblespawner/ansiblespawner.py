"""
JupyterHub spawner that uses Ansible to create singleuser servers
"""
import ansible_runner
import asyncio
from jinja2 import Template
from jupyterhub.spawner import Spawner
from jupyterhub.traitlets import Callable
import logging
import os
import tempfile
from traitlets import Any, Dict, Unicode, Union


logger = logging.getLogger(__name__)


class AnsibleException(Exception):
    def __init__(self, message, runner):
        super().__init__(message)
        self.rc = runner.rc
        self.status = runner.status
        self.stats = runner.stats
        self.events = list(runner.events)

    def __str__(self):
        nevents = len(self.events)
        nfailed = len(list(e for e in self.events if e["event"] == "runner_on_failed"))
        nok = len(list(e for e in self.events if e["event"] == "runner_on_ok"))
        return (
            f"AnsibleException: {self.args[0]} rc:{self.rc} "
            f"status:{self.status} stats:{self.stats} "
            f"events:[failed:{nfailed} ok:{nok} other:{nevents - nfailed - nok}]"
        )


class AnsibleSpawner(Spawner):

    inventory = Union(
        [Unicode(), Callable()],
        allow_none=True,
        config=True,
        help="""
        The Ansible inventory.
        Either the path to a Jinja2 template file or a callable that returns the
        inventory as a dictionary.

        If this is a file the template will be rendered with the JupyterHub User
        object passed as "user".

        If this is a callable JupyterHub User object will be passed as the keyword
        argument "user".

        If None Ansible will default to "localhost"
        """,
    )

    create_playbook = Unicode(
        config=True,
        help="""
        Playbook to create a singleuser server.

        Typically this will target "localhost".
        "user", "spawner_environment" and "playbook_vars" variables will be passed
        to this playbook.

        The playbook may set a fact "ansiblespawner_out" which must include the
        fields "ip" and "port".
        Other fields may be included.

        If these fields are not set the update_playbook must set them.

        The contents of "ansiblespawner_out" will be saved as state.
        """,
    )

    update_playbook = Unicode(
        allow_none=True,
        config=True,
        help="""
        Playbook to update a singleuser server after creation.

        Typically this will target the singleuser server.
        "user", "spawner_environment" and "playbook_vars" variables will be passed
        to this playbook, along with the contents of "ansiblespawner_out" from the
        create playbook in a variable named "create_out"

        If the create_playbook does not set the fields "ip" and "port" in a fact
        "ansiblespawner_out" this playbook must set them.
        Other fields may be included.
        "ansiblespawner_out" from the create and update playbooks will be shallow
        merged with update having a higher priority

        The contents of "ansiblespawner_out" will be saved as state.
        """,
    )

    poll_playbook = Unicode(
        config=True,
        help="""
        Playbook to check whether a singleuser server exists.

        Typically this will target "localhost".
        "user", "spawner_environment" and "playbook_vars" variables will be passed
        to this playbook.

        The playbook must set a fact "ansiblespawner_out" with a boolean field
        "running" to indicate whether the server is running or not.
        """,
    )

    destroy_playbook = Unicode(
        config=True,
        help="""
        Playbook to destroy a singleuser server.

        Typically this will target "localhost".
        "user", "spawner_environment" and "playbook_vars" variables will be passed
        to this playbook.
        """,
    )

    playbook_vars = Union(
        [Dict(), Callable()],
        allow_none=True,
        config=True,
        help="""
        Dictionary of parameters passed to Ansible in addition to "user"
        or a callable that returns a dictionary of parameters.
        """,
    )

    serverinfo = Any(allow_none=True)

    async def ansible_async(self, loop, **kwargs):
        """
        Wrap ansible_runner.run_async so it can be used with asyncio
        loop: The event loop
        *kwargs: Keyword arguments for ansible_runner.run_async
        """
        # https://docs.python.org/3.6/library/asyncio-task.html#example-future-with-run-until-complete

        # Ansible runs in a different thread from asyncio so must use
        # call_soon_threadsafe
        # https://docs.python.org/3.6/library/asyncio-dev.html#concurrency-and-multithreading

        future = loop.create_future()

        def finished_callback(runner):
            self.log.debug(f"finished_callback: {runner}")
            loop.call_soon_threadsafe(future.set_result, runner)

        t, r = ansible_runner.run_async(finished_callback=finished_callback, **kwargs)

        result = await future
        # Shouldn't block since future should only return when ansible has finished
        t.join()
        return result

    async def run_ansible(self, loop, inventory, **kwargs):
        ansible_kwargs = dict(quiet=True,)
        # Use temporary artifacts dir otherwise the events seem to accumulate from
        # previous runs
        tmpdir = None
        private_data_dir = kwargs.get("private_data_dir", None)
        if not private_data_dir:
            tmpdir = tempfile.TemporaryDirectory()
            private_data_dir = tmpdir.name
            ansible_kwargs["private_data_dir"] = private_data_dir

        if isinstance(inventory, dict):
            ansible_kwargs["inventory"] = inventory
        else:
            filename, content = inventory
            inventory_file = os.path.join(private_data_dir, filename)
            with open(inventory_file, "w") as f:
                f.write(content)
            ansible_kwargs["inventory"] = inventory_file

        ansible_kwargs.update(kwargs)
        self.log.debug(f"ansible_kwargs: {ansible_kwargs}")
        r = await self.ansible_async(loop, **ansible_kwargs)

        self.log.debug(f"{r.stats}")
        events = list(r.events)

        self.log.debug("".join(r.stdout))

        if r.rc != 0:
            self.log.error(f"Ansible: Non-zero exit code: {r.rc}")
            for e in events:
                if e["event"] == "runner_on_failed":
                    self.log.error(e)
            raise AnsibleException("Non-zero exit code", r)
        if len(r.stats["ok"]) == 0:
            self.log.error(f"Ansible: No successful tasks: {r.stats}")
            raise AnsibleException("No successful tasks", r)

        ansiblespawner_out = None
        for e in reversed(events):
            if e["event"] == "runner_on_ok":
                try:
                    ansiblespawner_out = e["event_data"]["res"]["ansible_facts"][
                        "ansiblespawner_out"
                    ]
                    break
                except KeyError:
                    continue

        return dict(
            ansiblespawner_out=ansiblespawner_out,
            events=events,
            rc=r.rc,
            stats=r.stats,
            status=r.status,
            # Caller should call tmpdir.cleanup() if not None
            tmpdir=tmpdir,
        )

    def _env_keep_default(self):
        """Don't inherit any env from the parent process"""
        return []

    async def _get_inventory(self):
        if callable(self.inventory):
            return self.inventory(self.user)
        with open(self.inventory) as f:
            filename = os.path.basename(self.inventory)
            if filename.endswith(".j2"):
                filename = filename[:-3]
            content = Template(f.read()).render(user=self.user)
        return filename, content

    def _get_user(self):
        """
        A JSON serialisable user object containing a subset of fields from the
        User object
        """
        # https://github.com/jupyterhub/jupyterhub/blob/1.0.0/jupyterhub/user.py#L142
        # https://github.com/jupyterhub/jupyterhub/blob/1.0.0/jupyterhub/orm.py#L147
        return dict(escaped_name=self.user.escaped_name, name=self.user.name,)

    async def _get_extravars(self):
        vars = {
            "user": self._get_user(),
            "spawner_environment": self.get_env(),
        }
        if self.playbook_vars:
            if callable(self.playbook_vars):
                vars.update(self.playbook_vars())
            else:
                vars.update(self.playbook_vars)
        return vars

    def load_state(self, state):
        super().load_state(state)
        self.serverinfo = state.get("serverinfo")

    def get_state(self):
        state = super().get_state()
        if self.serverinfo:
            state["serverinfo"] = self.serverinfo
        return state

    async def start(self):
        inv = await self._get_inventory()
        extravars = await self._get_extravars()
        self.log.debug(f"extravars: {extravars}")
        loop = asyncio.get_event_loop()

        create = await self.run_ansible(
            loop,
            inv,
            extravars=extravars,
            quiet=not self.debug,
            playbook=os.path.abspath(self.create_playbook),
        )
        self.log.debug(
            f'create_playbook ansiblespawner_out: {create["ansiblespawner_out"]}'
        )
        create["tmpdir"].cleanup()
        self.serverinfo = create["ansiblespawner_out"] or {}
        extravars["create_out"] = self.serverinfo

        if self.update_playbook:
            update = await self.run_ansible(
                loop,
                inv,
                extravars=extravars,
                quiet=not self.debug,
                playbook=os.path.abspath(self.update_playbook),
            )
            self.log.debug(
                f'update_playbook ansiblespawner_out: {update["ansiblespawner_out"]}'
            )
            update["tmpdir"].cleanup()
            self.serverinfo.update(update["ansiblespawner_out"] or {})

        ip = self.serverinfo["ip"]
        port = int(self.serverinfo["port"])

        self.log.info(f"Started server on {ip}:{port}")
        return ip, port

    async def stop(self, now=False):
        # TODO or not bother?
        #   now=False (default), shutdown the server gracefully
        #   now=True, terminate the server immediately.
        inv = await self._get_inventory()
        extravars = await self._get_extravars()
        loop = asyncio.get_event_loop()

        destroy = await self.run_ansible(
            loop,
            inv,
            extravars=extravars,
            quiet=not self.debug,
            playbook=os.path.abspath(self.destroy_playbook),
        )
        self.log.debug(
            f'destroy_playbook ansiblespawner_out: {destroy["ansiblespawner_out"]}'
        )
        destroy["tmpdir"].cleanup()

    async def poll(self):
        # None: single-user process is running.
        # Integer: not running, return exit status (0 if unknown)
        # Spawner not initialized: behave as not running (0).
        # Spawner not finished starting: behave as running (None)
        # May be called before start when state is loaded on Hub launch,
        #   if spawner not initialized via load_state or start: unknown (0)
        # If called while start is in progress (yielded): running (None)
        inv = await self._get_inventory()
        extravars = await self._get_extravars()
        loop = asyncio.get_event_loop()

        poll = await self.run_ansible(
            loop,
            inv,
            extravars=extravars,
            quiet=not self.debug,
            playbook=os.path.abspath(self.poll_playbook),
        )
        self.log.debug(
            f'poll_playbook ansiblespawner_out: {poll["ansiblespawner_out"]}'
        )
        poll["tmpdir"].cleanup()

        if poll["ansiblespawner_out"]["running"]:
            return None
        return 0
