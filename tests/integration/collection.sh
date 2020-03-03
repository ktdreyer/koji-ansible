#!/bin/bash

# Build a collection and ensure that we can read the documentation for each
# Ansible module within it.

set -exu

./build-collection

TARBALL=$(ls _build/*.tar.gz)

ansible-galaxy collection install $TARBALL

MODULEFILES=$(ls library/*.py)

for MODULEFILE in $MODULEFILES; do
    MODULE=$(basename $MODULEFILE .py)
    # This will fail if the YAML is invalid for any module's documentation:
    ansible-doc -t module ktdreyer.koji_ansible.$MODULE
done
