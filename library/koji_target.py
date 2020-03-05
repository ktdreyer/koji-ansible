from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils import common_koji


ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
---
module: koji_target

short_description: Create and manage Koji targets
description:
   - Create, update, and delete targets within Koji.
options:
   name:
     description:
       - The name of the Koji target to create and manage.
     required: true
   build_tag:
     description:
       - The name of the "build" or "buildroot" tag. The latest builds in
         this tag will be available in the buildroot when you build an RPM or
         container for this Koji target.
       - 'Example: "f29-build"'
     required: true
   dest_tag:
     description:
       - The name of the "destination" tag. When Koji completes a build for
         this target, it will tag that build into this destination tag.
       - 'Example: "f29-updates-candidate"'
     required: true
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: create a koji target
  hosts: localhost
  tasks:

    - name: Configure CBS target
      koji_target:
        name: storage7-ceph-nautilus-el7
        build_tag: storage7-ceph-nautilus-el7-build
        dest_tag: storage7-ceph-nautilus-candidate
'''


def ensure_target(session, name, check_mode, build_tag, dest_tag):
    """
    Ensure that this target exists in Koji.

    :param session: Koji client session
    :param name: Koji target name
    :param check_mode: don't make any changes
    :param build_tag: Koji build tag name, eg. "f29-build"
    :param dest_tag: Koji destination tag name, eg "f29-updates-candidate"
    """
    targetinfo = session.getBuildTarget(name)
    result = {'changed': False, 'stdout_lines': []}
    if not targetinfo:
        result['changed'] = True
        if check_mode:
            result['stdout_lines'].append('would create target %s' % name)
            return result
        common_koji.ensure_logged_in(session)
        session.createBuildTarget(name, build_tag, dest_tag)
        targetinfo = session.getBuildTarget(name)
        result['stdout_lines'].append('created target %s' % targetinfo['id'])
    # Ensure the build and destination tags are set for this target.
    needs_edit = False
    if build_tag != targetinfo['build_tag_name']:
        needs_edit = True
        result['stdout_lines'].append('build_tag_name: %s' % build_tag)
    if dest_tag != targetinfo['dest_tag_name']:
        needs_edit = True
        result['stdout_lines'].append('dest_tag_name: %s' % dest_tag)
    if needs_edit:
        result['changed'] = True
        if check_mode:
            return result
        common_koji.ensure_logged_in(session)
        session.editBuildTarget(name, name, build_tag, dest_tag)
    return result


def delete_target(session, name, check_mode):
    """ Ensure that this tag is deleted from Koji. """
    targetinfo = session.getBuildTarget(name)
    result = dict(
        stdout='',
        changed=False,
    )
    if targetinfo:
        common_koji.ensure_logged_in(session)
        session.deleteBuildTarget(targetinfo)
        result['stdout'] = 'deleted target %d' % targetinfo['id']
        result['changed'] = True
    return result


def run_module():
    module_args = dict(
        koji=dict(type='str', required=False),
        name=dict(type='str', required=True),
        state=dict(type='str', required=False, default='present'),
        build_tag=dict(type='str', required=True),
        dest_tag=dict(type='str', required=True),
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
    build_tag = params['build_tag']
    dest_tag = params['dest_tag']

    session = common_koji.get_session(profile)

    if state == 'present':
        result = ensure_target(session, name, check_mode, build_tag, dest_tag)
    elif state == 'absent':
        result = delete_target(session, name, check_mode)
    else:
        module.fail_json(msg="State must be 'present' or 'absent'.",
                         changed=False, rc=1)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
