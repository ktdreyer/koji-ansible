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
'''


def ensure_host(session, name, state, arches, krb_principal, **kwargs):
    """
    Ensure that this host is configured in Koji.

    :param session: Koji client session
    :param str name: Koji builder host name
    :param str state: "enabled" or "disabled"
    :param list arches: list of arches for this tag.
    :param str krb_principal: custom kerberos principal, or None
    :param **kwargs: Pass remaining kwargs directly into Koji's editHost RPC.
    """
    result = {'changed': False}
    host = session.getHost(name)
    if not host:
        common_koji.ensure_logged_in(session)
        id_ = session.addHost(name, arches, krb_principal)
        result['changed'] = True
        host = session.getHost(id_)
    if state == 'enabled':
        if not host['enabled']:
            common_koji.ensure_logged_in(session)
            session.enableHost(name)
            result['changed'] = True
    if state == 'disabled':
        if host['enabled']:
            common_koji.ensure_logged_in(session)
            session.disableHost(name)
            result['changed'] = True
    edits = {}
    if ' '.join(arches) != host['arches']:
        edits['arches'] = ' '.join(arches)
    for key, value in kwargs.items():
        if value is None:
            continue  # Ansible did not set this parameter.
        if key in host and kwargs[key] != host[key]:
            edits[key] = value
    if edits:
        common_koji.ensure_logged_in(session)
        session.editHost(name, **edits)
        result['changed'] = True
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

    params = module.params
    profile = params['koji']
    name = params['name']
    state = params['state']

    session = common_koji.get_session(profile)

    if state not in ('enabled', 'disabled'):
        module.fail_json(msg="State must be 'enabled' or 'disabled'.",
                         changed=False, rc=1)

    try:
        result = ensure_host(session, name, state,
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
