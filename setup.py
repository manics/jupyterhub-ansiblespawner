#!/usr/bin/env python
# coding: utf-8
from setuptools import setup


setup(
    name="ansiblespawner",
    packages=["ansiblespawner"],
    description="Spawn JupyterHub single user notebook servers using Ansible",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    use_scm_version={"write_to": "ansiblespawner/_version.py"},
    setup_requires=["setuptools_scm"],
    author="Simon Li",
    author_email="jupyter@googlegroups.com",
    url="https://jupyter.org",
    license="BSD-3-Clause",
    platforms="Linux, Mac OS X",
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
    install_requires=["jupyterhub>=1.0.0", "ansible>=2.9", "ansible-runner>=1.4"],
    python_requires=">=3.6",
    entry_points={"jupyterhub.spawners": ["ansible = ansiblespawner:AnsibleSpawner"]},
)
