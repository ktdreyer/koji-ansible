#!/usr/bin/python
import sys
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils import common_koji


ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
---
module: koji_cg

short_description: Create and manage Koji content generators
description:
   - This module can grant or revoke access to a `content generator
     <https://docs.pagure.org/koji/content_generators/>`_ for a user account.
   - Your Koji Hub must be version 1.19 or newer in order to use the new
     `listCGs <https://pagure.io/koji/pull-request/1160>`_ RPC.


options:
   name:
     description:
       - The name of the Koji content generator.
       - 'Example: "debian".'
     required: true
   user:
     description:
       - The name of the Koji user account.
       - This user account must already exist in Koji's database. For example,
         you may run an authenticated "koji hello" command to create the
         account database entry.
       - 'Example: "cguser".'
     required: true
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: Grant a user access to a content generator.
  hosts: localhost
  tasks:
    - name: Grant access to the rcm/debbuild account
      koji_cg:
        name: debian
        user: rcm/debbuild
        state: present
'''

RETURN = ''' # '''


class UnknownCGsError(Exception):
    """ We cannot know what CGs are present """
    pass


def list_cgs(session):
    """ Return the result of listCGs, or raise UnknownCGsError """
    koji_profile = sys.modules[session.__module__]
    try:
        return session.listCGs()
    except koji_profile.GenericError as e:
        if str(e) == 'Invalid method: listCGs':
            # Kojihub before version 1.20 will raise this error.
            raise UnknownCGsError
        raise


def ensure_cg(session, user, name, state, cgs, check_mode):
    """
    Ensure that a content generator and user is present or absent.

    :param session: koji ClientSession
    :param str user: koji user name
    :param str name: content generator name
    :param str state: "present" or "absent"
    :param dict cgs: existing content generators and users
    :param bool check_mode: if True, show what would happen, but don't do it.
    :returns: result
    """
    result = {'changed': False}
    if state == 'present':
        if name not in cgs or user not in cgs[name]['users']:
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.grantCGAccess(user, name, create=True)
            result['changed'] = True
    elif state == 'absent':
        if name in cgs and user in cgs[name]['users']:
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.revokeCGAccess(user, name)
            result['changed'] = True
    return result


def ensure_unknown_cg(session, user, name, state):
    """
    Ensure that a content generator and user is present or absent.

    This method is for older versions of Koji where we do not have the listCGs
    RPC. This method does not support check_mode.

    :param session: koji ClientSession
    :param str user: koji user name
    :param str name: content generator name
    :param str state: "present" or "absent"
    :returns: result
    """
    result = {'changed': False}
    koji_profile = sys.modules[session.__module__]
    common_koji.ensure_logged_in(session)
    if state == 'present':
        # The "grant" method will at least raise an error if the permission
        # was already granted, so we can set the "changed" result based on
        # that.
        try:
            session.grantCGAccess(user, name, create=True)
            result['changed'] = True
        except koji_profile.GenericError as e:
            if 'User already has access to content generator' not in str(e):
                raise
    elif state == 'absent':
        # There's no indication whether this changed anything, so we're going
        # to be pessimistic and say we're always changing it.
        session.revokeCGAccess(user, name)
        result['changed'] = True
    return result


def run_module():
    module_args = dict(
        koji=dict(),
        name=dict(required=True),
        user=dict(required=True),
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
    user = params['user']
    state = params['state']

    session = common_koji.get_session(profile)

    try:
        cgs = list_cgs(session)
        result = ensure_cg(session, user, name, state, cgs, check_mode)
    except UnknownCGsError:
        if check_mode:
            msg = 'check mode does not work without listCGs'
            result = {'changed': False, 'msg': msg}
        else:
            result = ensure_unknown_cg(session, user, name, state)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
