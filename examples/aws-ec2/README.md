# Example AWS EC2 deployment

## Local setup

Change into this directory.

    cd examples/aws-ec2

Install Ansible if necessary. It is used to create an EC2 instance and deploy JupyerHub:

    conda env create -n ansible --file local-environment.yml
    conda activate ansible

Edit [`ansible.cfg`](./ansible.cfg) if necessary.
The current configuration will install rules and collections to the current directory.

Install roles and collections:

    ansible-galaxy role install -r requirements.yml
    ansible-galaxy collection install -r requirements.yml

Generate a SSH key for the EC2 instance:

    ssh-keygen -P '' -t rsa -m pem -f jupyter-id_rsa.pem
    mv jupyter-id_rsa.pem.pub jupyter-id_rsa.pub

## Deploy JupyterHub with AnsibleSpawner on an EC2 instance

[Setup your AWS credentials](https://docs.ansible.com/ansible/latest/scenario_guides/guide_aws.html#authentication) if necessary.

Provision infrastructure:

    ansible-playbook -i localhost.yml jupyterhub-provision.yml

This will:
- Create an EC2 instance to run JupyterHub acessible only from your current IP address.
- Install JupyterHub withAnsibleSpawner and the playbooks from this directory on the EC2 instance.
- Create a local ssh configuration file for convenience to make it easier for you to login.

## Run JupyterHub

Log in to the EC2 instance:

    ssh -F jupyterhub-ssh-config jupyterhub

Activate the conda environment and check the AWS instance profile was setup:

    . /opt/conda/bin/activate
    aws sts get-caller-identity

Run JupyterHub:

    cd /opt/jupyterhub
    AWS_DEFAULT_REGION=eu-west-1 jupyterhub --debug -f jupyterhub_config.py

## Access JupyterHub

The playbook should print out the address of the JupyterHub server.
Login with any username and password (this uses the [DummyAuthenticator](https://github.com/jupyterhub/jupyterhub/blob/1.4.2/jupyterhub/auth.py#L1122)).

## Cleanup all resources

Login to the EC2 instance and stop JupyterHub gracefully to ensure user instances are terminated.

    ssh -F jupyterhub-ssh-config jupyterhub sudo systemctl stop jupyterhub

Delete infrastructure:

    ansible-playbook -i localhost.yml jupyterhub-destroy.yml

Check all instances were deleted:

    aws ec2 describe-instances --query 'Reservations[].Instances[].{"state": State.Name, "name": Tags[?Key==`Name`] | [0].Value}'

If they weren't delete them manually.

## Useful AWS CLI commands

Enable bash completion for AWS CLI:

    complete -C aws_completer aws

List all instance IDs and selected information:

    aws ec2 describe-instances --query 'Reservations[].Instances[].{Id:InstanceId,State:State,LaunchTime:LaunchTime}'

    aws ec2 describe-instances --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name,LaunchTime:LaunchTime,PrivateIpAddress:PrivateIpAddress}'

Delete instance(s)

    aws ec2 terminate-instances --instance-ids ...
