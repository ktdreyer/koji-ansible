#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native
from ansible.errors import AnsibleError
import common_koji


ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
---
module: koji_host

short_description: Create and manage Koji build hosts
description:
   - This module can add new hosts and manage existing hosts.
   - Koji only supports adding new hosts, not deleting them. Once they are
     defined, you can enable or disable the hosts with "state: enabled" or
     "state: disabled".

options:
   name:
     description:
       - The name of the Koji builder. Example: "builder1.example.com".
     required: true
   arches:
     description:
       - The list of arches this host supports. Example: [x86_64]
     required: true
   state:
     description:
       - Whether to set this host as "enabled" or "disabled". If unset, this
         defaults to "enabled".
   krb_principal:
     description:
       - Set a non-default krb principal for this host. If unset, Koji will
         use the standard krb principal scheme for builder accounts.
   capacity:
     description:
       - Total task weight for this host. This is a float value, example:
         10.0. If unset, Koji will use the standard capacity for a host (2.0).
   description:
     description:
       - Human-readable description for this host.
   comment:
     description:
       - Human-readable comment explaining the current state of the host. You
         may write a description here explaining how this host was set up, or
         why this host is currently offline.
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: create a koji host
  hosts: localhost
  tasks:
    - name: Add new builder1 host
      koji_host:
        name: builder1.example.com
        arches: [x86_64]
        state: enabled
'''


def ensure_host(session, name, check_mode, state, arches, krb_principal,
                **kwargs):
    """
    Ensure that this host is configured in Koji.

    :param session: Koji client session
    :param str name: Koji builder host name
    :param bool check_mode: don't make any changes
    :param str state: "enabled" or "disabled"
    :param list arches: list of arches for this builder.
    :param str krb_principal: custom kerberos principal, or None
    :param **kwargs: Pass remaining kwargs directly into Koji's editHost RPC.
    """
    result = {'changed': False}
    host = session.getHost(name)
    if not host:
        result['changed'] = True
        if check_mode:
            return result
        common_koji.ensure_logged_in(session)
        id_ = session.addHost(name, arches, krb_principal)
        host = session.getHost(id_)
    if state == 'enabled':
        if not host['enabled']:
            result['changed'] = True
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.enableHost(name)
    if state == 'disabled':
        if host['enabled']:
            result['changed'] = True
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.disableHost(name)
    edits = {}
    if ' '.join(arches) != host['arches']:
        edits['arches'] = ' '.join(arches)
    for key, value in kwargs.items():
        if value is None:
            continue  # Ansible did not set this parameter.
        if key in host and kwargs[key] != host[key]:
            edits[key] = value
    if edits:
        result['changed'] = True
        if not check_mode:
            common_koji.ensure_logged_in(session)
            session.editHost(name, **edits)
    return result


def run_module():
    module_args = dict(
        koji=dict(type='str', required=False),
        name=dict(type='str', required=True),
        arches=dict(type='list', required=True),
        krb_principal=dict(type='str', required=False, default=None),
        capacity=dict(type='float', required=False, default=None),
        description=dict(type='str', required=False, default=None),
        comment=dict(type='str', required=False, default=None),
        state=dict(type='str', required=False, default='enabled'),
    )
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    if not common_koji.HAS_KOJI:
        module.fail_json(msg='koji is required for this module')

    check_mode = module.check_mode
    params = module.params
    profile = params['koji']
    name = params['name']
    state = params['state']

    session = common_koji.get_session(profile)

    if state not in ('enabled', 'disabled'):
        module.fail_json(msg="State must be 'enabled' or 'disabled'.",
                         changed=False, rc=1)

    try:
        result = ensure_host(session, name, check_mode, state,
                             arches=params['arches'],
                             krb_principal=params['krb_principal'],
                             capacity=params['capacity'],
                             description=params['description'],
                             comment=params['comment'])
    except Exception as e:
        raise AnsibleError('koji_host ensure_host failed:\n%s' % to_native(e))

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
