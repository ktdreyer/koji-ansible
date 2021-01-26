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
module: koji_archivetype

short_description: Create and manage Koji archive types
description:
   - Create and manage Koji archive types
   - Your Koji Hub must be version 1.20 or newer in order to use the new
     ``addArchiveType`` RPC.

options:
   name:
     description:
       - The name of the Koji archive type to create and manage.
       - 'Examples: "dsc", "opk".'
     required: true
   description:
     description:
       - The human-readable description of this Koji archive type.  Koji uses
         this value in the UI tooling that display a build's files.
       - 'Examples: "Debian source control file", "OpenWrt package".'
     required: true
   extensions:
     description:
       - The file extensions for this Koji archive type.
       - 'For example, "dsc" means Koji will apply this archive type to files
         that end in ".dsc". "opk" will apply to files that end in ".opk",
         etc.'
     required: true
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: Add new archive types into koji
  hosts: localhost
  tasks:
    - name: Add dsc archive type
      koji_archivetype:
        name: dsc
        description: Debian source control file
        extensions: dsc
        state: present

    - name: Add opk archive type
      koji_archivetype:
        name: opk
        description: OpenWrt package
        extensions: opk
        state: present
'''

RETURN = ''' # '''


def run_module():
    module_args = dict(
        koji=dict(),
        name=dict(required=True),
        description=dict(required=True),
        extensions=dict(required=True),
        state=dict(choices=['present', 'absent'], default='present'),
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
    description = params['description']
    extensions = params['extensions']
    state = params['state']

    session = common_koji.get_session(profile)

    result = {'changed': False}

    if state == 'present':
        if not session.getArchiveType(type_name=name):
            result['changed'] = True
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.addArchiveType(name, description, extensions)
    elif state == 'absent':
        module.fail_json(msg="Cannot remove Koji archive types.",
                         changed=False, rc=1)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
