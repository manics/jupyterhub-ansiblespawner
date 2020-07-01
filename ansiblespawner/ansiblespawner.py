"""
JupyterHub spawner that uses Ansible to create singleuser servers
"""
import ansible_runner
import asyncio
from datetime import datetime
from functools import partial
from jinja2 import Template
from jupyterhub.spawner import Spawner
from jupyterhub.traitlets import Callable
import logging
import os
from re import sub as re_sub
import tempfile
from traitlets import Bool, Dict, Instance, Unicode, Union


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

    # Configuration properties

    inventory = Union(
        [Unicode(), Callable()],
        allow_none=True,
        config=True,
        help="""
        The Ansible inventory.
        Either the path to a Jinja2 template file or a callable that returns the
        inventory as a dictionary.

        If this is a file the template will be rendered with the following variables:
          - command
          - playbook_vars
          - serverinfo: Output from the create and update playbooks, may be empty
          - spawner_environment
          - user

        If this is a callable the above variables will be passed as keyword parameters.

        If None Ansible will default to "localhost"
        """,
    )

    create_playbook = Unicode(
        config=True,
        help="""
        Playbook to create a singleuser server.

        Typically this will target "localhost".
        The following variables will be passed to this playbook:
          - command
          - playbook_vars
          - spawner_environment
          - user

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
          - command
          - playbook_vars
          - serverinfo: Output from the create playbook
          - spawner_environment
          - user

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
        The following variables will be passed to this playbook:
          - command
          - playbook_vars
          - serverinfo: Output from the create and update playbooks
          - spawner_environment
          - user

        The playbook must set a fact "ansiblespawner_out" with a boolean field
        "running" to indicate whether the server is running or not.
        """,
    )

    destroy_playbook = Unicode(
        config=True,
        help="""
        Playbook to destroy a singleuser server.

        Typically this will target "localhost".
        The following variables will be passed to this playbook:
          - command
          - playbook_vars
          - serverinfo: Output from the create and update playbooks
          - spawner_environment
          - user
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

    keep_temp_dirs = Bool(
        allow_none=True,
        config=True,
        help="""
        Keep the temporary directories used for running Ansible.
        The directories will be logged at info level.
        """,
    )

    # Non-config properties

    events = Instance(
        asyncio.Queue,
        args=(),
        help="""
        Queue for Ansible events that are shown to the user
        https://asyncio.readthedocs.io/en/latest/producer_consumer.html
        """,
    )

    serverinfo = Dict(
        allow_none=True,
        help="""
        Dictionary containing persistent state about this server.
        """,
    )

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
            tmpdir = tempfile.TemporaryDirectory(
                prefix="ansiblespawner-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S-")
            )
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

        def log_event_handler(e):
            self.log.debug(e["event"] + (("\n" + e["stdout"]) if "stdout" in e else ""))
            # Needs to return True otherwise the event is discarded
            # https://github.com/ansible/ansible-runner/blob/1.4.6/ansible_runner/runner.py#L69
            return True

        if "event_handler" in ansible_kwargs:
            event_handler = ansible_kwargs["event_handler"]

            def user_event_handler(e, finished=False):
                log_event_handler(e)
                return event_handler(e)

            ansible_kwargs["event_handler"] = user_event_handler
        else:
            ansible_kwargs["event_handler"] = log_event_handler

        def status_handler(s, runner_config):
            self.log.info("Ansible status: %s", s)
            return True

        ansible_kwargs["status_handler"] = status_handler

        self.log.debug(f"ansible_kwargs: {ansible_kwargs}")
        r = await self.ansible_async(loop, **ansible_kwargs)

        self.log.debug(f"{r.stats}")
        events = list(r.events)

        if r.rc != 0:
            self.log.error(f"Ansible: Non-zero exit code: {r.rc}")
            for e in events:
                if e["event"] == "runner_on_failed":
                    self.log.error(e)
            raise AnsibleException("Non-zero exit code", r)
        if len(r.stats["ok"]) == 0:
            self.log.error(f"Ansible: No successful tasks: {r.stats}")
            raise AnsibleException("No successful tasks", r)

        ansiblespawner_out = {}
        for e in events:
            if e["event"] == "runner_on_ok":
                try:
                    ansiblespawner_out.update(
                        e["event_data"]["res"]["ansible_facts"]["ansiblespawner_out"]
                    )
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

    def _cleanup_tmpdir(self, tmpdir):
        if self.keep_temp_dirs:
            self.log.info(f"Not deleting tmpdir {tmpdir.name}")
        else:
            tmpdir.cleanup()

    def _env_keep_default(self):
        """Don't inherit any env from the parent process"""
        return []

    async def _get_inventory(self):
        args = await self._get_extravars()
        if callable(self.inventory):
            return self.inventory(**args)
        with open(self.inventory) as f:
            filename = os.path.basename(self.inventory)
            if filename.endswith(".j2"):
                filename = filename[:-3]
            content = Template(f.read()).render(**args)
        return filename, content

    def _get_command(self):
        """
        A list containing the command to run with arguments
        """
        cmd = []
        cmd.extend(self.cmd)
        cmd.extend(self.get_args())
        return cmd

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
            "command": self._get_command(),
            "serverinfo": self.serverinfo or {},
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
        if not self.port:
            self.port = 8888

        inv = await self._get_inventory()
        extravars = await self._get_extravars()
        self.log.debug(f"extravars: {extravars}")
        loop = asyncio.get_event_loop()

        # When starting we want to show progress messages.
        # Ansible async runs in a separate thread
        def event_handler(loop, queue, e):
            # Remove colour escape codes
            m = e["event"] + (
                (": " + re_sub(r"\x1b[^m]*m", "", e["stdout"])) if "stdout" in e else ""
            )
            # Optional fields: progress, html_message
            if e["event"].startswith("playbook_on_"):
                loop.call_soon_threadsafe(queue.put_nowait, {"message": m})
            return True

        create = await self.run_ansible(
            loop,
            inv,
            extravars=extravars,
            quiet=not self.debug,
            playbook=os.path.abspath(self.create_playbook),
            event_handler=partial(event_handler, loop, self.events),
        )
        self.log.debug(
            f'create_playbook ansiblespawner_out: {create["ansiblespawner_out"]}'
        )
        self._cleanup_tmpdir(create["tmpdir"])
        self.serverinfo = create["ansiblespawner_out"] or {}
        extravars["serverinfo"] = self.serverinfo
        # Create playbook may have modified the inventory
        inv = await self._get_inventory()

        if self.update_playbook:
            update = await self.run_ansible(
                loop,
                inv,
                extravars=extravars,
                quiet=not self.debug,
                playbook=os.path.abspath(self.update_playbook),
                event_handler=partial(event_handler, loop, self.events),
            )
            self.log.debug(
                f'update_playbook ansiblespawner_out: {update["ansiblespawner_out"]}'
            )
            self._cleanup_tmpdir(update["tmpdir"])
            self.serverinfo.update(update["ansiblespawner_out"] or {})

        ip = self.serverinfo["ip"]
        port = int(self.serverinfo["port"])

        self.log.info(f"Started server on {ip}:{port}")
        self.events.put_nowait(None)
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
        self._cleanup_tmpdir(destroy["tmpdir"])

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
        self._cleanup_tmpdir(poll["tmpdir"])

        if poll["ansiblespawner_out"]["running"]:
            return None
        return 0

    async def progress(self):
        """
        https://github.com/jupyterhub/jupyterhub/blob/1.1.0/jupyterhub/spawner.py#L1009-L1032
        """
        while True:
            event = await self.events.get()
            if event is None:
                break
            yield event
