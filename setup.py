#!/usr/bin/env python
# coding: utf-8
from setuptools import setup
from collections import defaultdict
from pathlib import Path


def example_data_files():
    data_files = defaultdict(list)
    examples = Path("examples")
    for f in examples.glob("**/*"):
        if f.is_file() and "ci" not in f.parts and "molecule" not in f.parts:
            d = Path("etc", "ansiblespawner", *f.parts[1:-1])
            data_files[str(d)].append(str(f))
    return list(data_files.items())


setup(
    name="ansiblespawner",
    packages=["ansiblespawner"],
    description="Spawn JupyterHub single user notebook servers using Ansible",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    use_scm_version={"write_to": "ansiblespawner/_version.py"},
    setup_requires=["setuptools_scm"],
    author="Simon Li",
    url="https://github.com/manics/jupyterhub-ansiblespawner",
    license="BSD-3-Clause",
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
    install_requires=["jupyterhub>=1.0.0", "ansible>=2.9", "ansible-runner>=1.4"],
    python_requires=">=3.6",
    entry_points={"jupyterhub.spawners": ["ansible = ansiblespawner:AnsibleSpawner"]},
    data_files=example_data_files(),
)
