# Example AWS EC2 deployment

Provision infrastructure:

    ansible-playbook -i localhost.yml jupyterhub-provision.yml

This will create a ssh configuration file for convenience to make it easier for you to login, though it isn't needed by jupyterhub-ansiblespawner since the inventory is dynamically created.
It will also install JupyterHub.

Replace `subnet-TODO` in `jupyterhub_config.py` with the actual subnet ID.

Copy files:

    rsync -e 'ssh -F jupyterhub-ssh-config' \
        create.yml destroy.yml poll.yml update.yml inventory.yml.j2 \
        jupyterhub_config.py jupyterhub-singleuser.service.j2 jupyter-id_rsa.pem \
        jupyterhub:jupyterhub/

Run:

    ssh -F jupyterhub-ssh-config jupyterhub
    cd jupyterhub
    AWS_DEFAULT_REGION=eu-west-1 jupyterhub --debug -f jupyterhub_config.py


## Useful AWS CLI commands

Enable bash completion for AWS CLI:

    complete -C aws_completer aws

List all instance IDs and selected information:

    aws ec2 describe-instances --query 'Reservations[].Instances[].{Id:InstanceId,State:State,LaunchTime:LaunchTime}'

    aws ec2 describe-instances --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name,LaunchTime:LaunchTime,PrivateIpAddress:PrivateIpAddress}'

Delete instance(s)

    aws ec2 terminate-instances --instance-ids ...
