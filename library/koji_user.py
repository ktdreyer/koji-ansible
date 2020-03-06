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
module: koji_user

short_description: Create and manage Koji user accounts
description:
   - This module can add new users and manage existing users.
   - 'Koji only supports adding new users, not deleting them. Once they are
     defined, you can enable or disable the users with "state: enabled" or
     "state: disabled".'

options:
   name:
     description:
       - The name of the Koji user.
       - 'Example: "kdreyer".'
     required: true
   state:
     description:
       - Whether to set this user as "enabled" or "disabled". If unset, this
         defaults to "enabled".
   permissions:
     description:
       - A list of permissions for this user. If unset, Ansible will not edit
         the permissions for this user. To remove all permissions, set this to
         an empty list.
       - 'Example: [admin]'
   krb_principal:
     description:
       - Set a non-default krb principal for this user. If unset, Koji will
         use the standard krb principal scheme for user accounts.
       - Warning, Koji only allows you to set this one time, at the point at
         which you create the new account. You cannot edit the krb_principal
         for an existing account.
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: create a koji user
  hosts: localhost
  tasks:
    - name: Add new kdreyer user
      koji_user:
        name: kdreyer
        state: enabled
        permissions: [admin]
'''


def ensure_user(session, name, check_mode, state, permissions, krb_principal):
    """
    Ensure that this user is configured in Koji.

    :param session: Koji client session
    :param str name: Koji builder user name
    :param bool check_mode: don't make any changes
    :param str state: "enabled" or "disabled"
    :param list permissions: list of permissions for this user.
    :param str krb_principal: custom kerberos principal, or None. Used only at
                              account creation time.
    """
    result = {'changed': False, 'stdout_lines': []}
    if state == 'enabled':
        desired_status = common_koji.koji.USER_STATUS['NORMAL']
    else:
        desired_status = common_koji.koji.USER_STATUS['BLOCKED']
    user = session.getUser(name)
    if not user:
        result['changed'] = True
        result['stdout_lines'] = ['created %s user' % name]
        if check_mode:
            return result
        common_koji.ensure_logged_in(session)
        id_ = session.createUser(name, desired_status, krb_principal)
        user = session.getUser(id_)
    if user['status'] != desired_status:
        result['changed'] = True
        result['stdout_lines'] = ['%s %s user' % (state, name)]
        if not check_mode:
            common_koji.ensure_logged_in(session)
        if state == 'enabled':
            session.enableUser(name)
        else:
            session.disableUser(name)
    if permissions is None:
        return result
    current_perms = session.getUserPerms(user['id'])
    to_grant = set(permissions) - set(current_perms)
    to_revoke = set(current_perms) - set(permissions)
    if to_grant or to_revoke:
        result['changed'] = True
        if not check_mode:
            common_koji.ensure_logged_in(session)
    for permission in to_grant:
        result['stdout_lines'].append('grant %s' % permission)
        if not check_mode:
            session.grantPermission(name, permission, True)
    for permission in to_revoke:
        result['stdout_lines'].append('revoke %s' % permission)
        if not check_mode:
            session.revokePermission(name, permission)
    return result


def run_module():
    module_args = dict(
        koji=dict(required=False),
        name=dict(required=True),
        permissions=dict(type='list', required=True),
        krb_principal=dict(required=False, default=None),
        state=dict(choices=['enabled', 'disabled'], required=False,
                   default='enabled'),
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

    result = ensure_user(session, name, check_mode, state,
                         permissions=params['permissions'],
                         krb_principal=params['krb_principal'])

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
