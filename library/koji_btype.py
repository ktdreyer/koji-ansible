#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils import common_koji


ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
---
module: koji_btype

short_description: Create and manage Koji build types
description:
   - Every build in Koji has a "type". This module allows you to define
     entirely new build types in Koji. These are typically in support of
     `content generators <https://docs.pagure.org/koji/content_generators/>`_.
   - Koji only supports adding new build types, not deleting them.

options:
   name:
     description:
       - The name of the Koji build type to create. Example: "debian".
     required: true
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: create a debian btype in koji
  hosts: localhost
  tasks:
    - name: Create a koji debian btype
      koji_btype:
        name: debian
        state: present
'''

RETURN = ''' # '''


def run_module():
    module_args = dict(
        koji=dict(type='str', required=False),
        name=dict(type='str', required=True),
        state=dict(type='str', required=False, default='present'),
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

    result = {'changed': False}

    if state == 'present':
        btype_data = session.listBTypes()
        btypes = [data['name'] for data in btype_data]
        if name not in btypes:
            result['changed'] = True
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.addBType(name)
    elif state == 'absent':
        module.fail_json(msg="Cannot remove Koji build types.",
                         changed=False, rc=1)
    else:
        module.fail_json(msg="State must be 'present' or 'absent'.",
                         changed=False, rc=1)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
