import os
import socket

local_ip = socket.gethostbyname(socket.gethostname())
ansible_path = os.getenv("ANSIBLESPAWNER_ANSIBLE_PATH")
if not ansible_path:
    ansible_path = os.path.abspath(os.path.dirname(__file__))
ansible_path = ansible_path.rstrip("/") + "/"

c.JupyterHub.spawner_class = "ansible"
c.AnsibleSpawner.inventory = ansible_path + "inventory.yml.j2"
c.AnsibleSpawner.create_playbook = ansible_path + "create.yml"

c.AnsibleSpawner.update_playbook = ansible_path + "update.yml"
c.AnsibleSpawner.poll_playbook = ansible_path + "poll.yml"

c.AnsibleSpawner.destroy_playbook = ansible_path + "destroy.yml"

c.AnsibleSpawner.playbook_vars = {
    "ansible_srcdir": ansible_path,
    # These will be substituted when this file is copied in jupyterhub-deploy.yml
    "key_name": "{{ _jupyter_ec2_key_name }}",
    "subnet_id": "{{ _jupyter_ec2_subnet }}",
}
c.AnsibleSpawner.start_timeout = 600
c.AnsibleSpawner.keep_temp_dirs = True

c.JupyterHub.authenticator_class = "dummy"
c.JupyterHub.hub_connect_ip = local_ip
