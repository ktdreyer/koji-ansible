#!/bin/bash

set -eux

# Use our local Koji Git clone:
export PYTHONPATH=$(pwd)/koji:$(pwd)/koji/cli

# Use our local koji-ansible Git clone:
export ANSIBLE_LIBRARY=$(pwd)/library
export ANSIBLE_MODULE_UTILS=$(pwd)/module_utils

# Use our local Ansible installation (from pip):
export PATH=$PATH:$HOME/.local/bin

export KOJI_PROFILE=ci

. tests/integration/functions.sh

playbooks=($(ls tests/integration/*/main.yml))
final_playbook=$(echo ${playbooks[-1]})

for playbook in "${playbooks[@]}"; do
  ansible-playbook -vvv $playbook
  [[ $playbook == $final_playbook ]] || reset_instance
done
