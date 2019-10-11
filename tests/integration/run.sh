#!/bin/bash

set -eux

# Use our local Koji Git clone:
export PYTHONPATH=$(pwd)/koji:$(pwd)/koji/cli

# Use our local koji-ansible Git clone:
export ANSIBLE_LIBRARY=$(pwd)/library
export ANSIBLE_MODULE_UTILS=$(pwd)/module_utils

# Use our local Ansible installation (from pip):
export PATH=$PATH:$HOME/.local/bin

export KOJI_PROFILE=travisci

. tests/integration/functions.sh

ansible-playbook -vvv tests/integration/koji_btype/main.yml

reset_instance

ansible-playbook -vvv tests/integration/koji_cg/main.yml

reset_instance

ansible-playbook -vvv tests/integration/koji_host/main.yml

reset_instance

ansible-playbook -vvv tests/integration/koji_tag/main.yml

reset_instance

ansible-playbook -vvv tests/integration/koji_tag_inheritance/main.yml

reset_instance

ansible-playbook -vvv tests/integration/koji_target/main.yml
