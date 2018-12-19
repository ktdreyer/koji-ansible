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
module: koji_cg

short_description: Create and manage Koji content generators
'''


def run_module():
    module_args = dict(
        koji=dict(type='str', required=False),
        name=dict(type='str', required=True),
        user=dict(type='str', required=True),
        state=dict(type='str', required=True),
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
    user = params['user']
    state = params['state']

    session = common_koji.get_session(profile)

    result = {'changed': False}

    # There are no "get" methods for content generator information, so we must
    # send the changes to Koji every time.
    # in-progress "listCGs" pull request:
    # https://pagure.io/koji/pull-request/1160

    common_koji.ensure_logged_in(session)

    if state == 'present':
        # The "grant" method will at least raise an error if the permission was
        # already granted, so we can set the "changed" result based on that.
        try:
            session.grantCGAccess(user, name, create=True)
            result['changed'] = True
        except common_koji.koji.GenericError as e:
            if 'User already has access to content generator' not in str(e):
                raise AnsibleError(to_native(e))
    elif state == 'absent':
        # There's no indication whether this changed anything, so we're going
        # to be pessimistic and say we're always changing it.
        session.revokeCGAccess(user, name)
        result['changed'] = True
    else:
        module.fail_json(msg="State must be 'present' or 'absent'.",
                         changed=False, rc=1)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
