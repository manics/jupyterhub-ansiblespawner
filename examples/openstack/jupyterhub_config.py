import os

ansible_path = os.path.abspath(os.path.dirname(__file__)) + "/"

c.JupyterHub.spawner_class = "ansible"
c.AnsibleSpawner.inventory = ansible_path + "inventory.yml.j2"
c.AnsibleSpawner.create_playbook = ansible_path + "create.yml"

c.AnsibleSpawner.update_playbook = ansible_path + "update.yml"
c.AnsibleSpawner.poll_playbook = ansible_path + "poll.yml"

c.AnsibleSpawner.destroy_playbook = ansible_path + "destroy.yml"

c.AnsibleSpawner.playbook_vars = {
    "ansible_srcdir": ansible_path,
}
c.AnsibleSpawner.start_timeout = 600
c.AnsibleSpawner.keep_temp_dirs = True

c.JupyterHub.authenticator_class = "dummy"
c.JupyterHub.hub_connect_ip = "192.168.1.1"

# On a fedore 32 host may need to open firewall:
# sudo firewall-cmd --zone=libvirt --add-port=8081/tcp
