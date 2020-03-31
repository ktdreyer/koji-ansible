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
       - 'Example: "deb".'
     required: true
   description:
     description:
       - The human-readable description of this Koji archive type.  Koji uses
         this value in the UI tooling that display a build's files.
       - 'Example: "Debian packages".'
     required: true
   extensions:
     description:
       - The file extensions for this Koji archive type.
       - 'Example: "deb" means Koji will apply this archive type to files that
         end in ".deb".'
     required: true
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: Add deb archive types into koji
  hosts: localhost
  tasks:
    - name: Add deb archive type
      koji_archivetype:
        name: deb
        description: Debian packages
        extensions: deb
        state: present

    - name: Add dsc archive type
      koji_archivetype:
        name: dsc
        description: Debian source control files
        extensions: dsc
        state: present
'''

RETURN = ''' # '''


def run_module():
    module_args = dict(
        koji=dict(type='str', required=False),
        name=dict(type='str', required=True),
        description=dict(type='str', required=True),
        extensions=dict(type='str', required=True),
        state=dict(type='str', choices=[
                   'present', 'absent'], required=False, default='present'),
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
