#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
from collections import defaultdict
import common_koji


ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
---
module: koji_target

short_description: Create and manage Koji targets
'''


def ensure_target(session, name, build_tag, dest_tag):
    """
    Ensure that this tag exists in Koji.

    :param session: Koji client session
    :param name: Koji target name
    :param build_tag: Koji build tag name, eg. "f29-build"
    :param dest_tag: Koji destination tag name, eg "f29-updates-candidate"
    """
    targetinfo = session.getBuildTarget(name)
    result = {'changed': False}
    if not targetinfo:
        common_koji.ensure_logged_in(session)
        session.createBuildTarget(name, build_tag, dest_tag)
        targetinfo = session.getBuildTarget(name)
        result['stdout'] = 'created target %s' % targetinfo['id']
        result['changed'] = True
    # Ensure the build and destination tags are set for this target.
    needs_edit = False
    if build_tag != targetinfo['build_tag_name']:
        needs_edit = True
        result['stdout'] = 'build_tag_name: %s' % build_tag
    if dest_tag != targetinfo['dest_tag_name']:
        needs_edit = True
        result['stdout'] = 'dest_tag_name: %s' % dest_tag
    if needs_edit:
        common_koji.ensure_logged_in(session)
        session.editBuildTarget(targetinfo, name, build_tag, dest_tag)
        result['changed'] = True
    return result


def delete_target(session, name):
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
        koji=dict(type='str', required=False, default='koji'),
        name=dict(type='str', required=True),
        state=dict(type='str', required=True),
        build_tag=dict(type='str', required=True),
        dest_tag=dict(type='str', required=True),
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
    build_tag = params['build_tag']
    dest_tag = params['dest_tag']

    session = common_koji.get_session(profile)

    if state == 'present':
        result = ensure_target(session, name, build_tag, dest_tag)
    elif state == 'absent':
        result = delete_target(session, name)
    else:
        module.fail_json(msg="State must be 'present' or 'absent'.",
                         changed=False, rc=1)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
