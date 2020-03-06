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
module: koji_external_repo

short_description: Create and manage Koji external repos
description:
   - Create and manage Koji external repos
options:
   name:
     description:
       - The name of the Koji external repo to create and manage.
     required: true
   url:
     description:
       - The URL to the Koji external repo.
       - Note, this uses "$arch", not the common "$basearch" you may find in a
         typical Yum repository file.
       - For idempotency, please ensure your url always ends with a "/"
         character. If you leave it out, Koji Hub will automatically add a "/"
         slash when storing this value in the database, and every subsequent
         Ansible run will appear to be "changing" the external repo's URL.
     required: true
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: create a koji tag with an external repo.
  hosts: localhost
  tasks:
    - name: Create an external repo for CentOS "CR"
      koji_external_repo:
        name: centos7-cr
        url: http://mirror.centos.org/centos/7/cr/$arch/
        state: present

    - name: Create a koji tag that uses the CentOS CR repo
      koji_tag:
        name: storage7-ceph-nautilus-el7-build
        state: present
        external_repos:
        - repo: centos7-cr
          priority: 5
'''

RETURN = ''' # '''


def ensure_external_repo(session, name, check_mode, url):
    """
    Ensure that this external repo exists in Koji.

    :param session: Koji client session
    :param name: Koji external repo name
    :param check_mode: don't make any changes
    :param url: URL to this external repo
    """
    repoinfo = session.getExternalRepo(name)
    result = {'changed': False, 'stdout_lines': []}
    if not repoinfo:
        if check_mode:
            result['stdout_lines'].append('would create repo %s' % name)
            result['changed'] = True
            return result
        common_koji.ensure_logged_in(session)
        repoinfo = session.createExternalRepo(name, url)
        result['stdout_lines'].append('created repo id %d' % repoinfo['id'])
        result['changed'] = True
        return result
    if repoinfo['url'] != url:
        result['stdout_lines'].append('set url to %s' % url)
        result['changed'] = True
        if not check_mode:
            common_koji.ensure_logged_in(session)
            session.editExternalRepo(info=repoinfo['id'], url=url)
    return result


def delete_external_repo(session, name, check_mode):
    """ Ensure that this external_repo is deleted from Koji. """
    repoinfo = session.getExternalRepo(name)
    result = dict(
        stdout='',
        changed=False,
    )
    if repoinfo:
        result['stdout'] = 'deleted external repo %s' % name
        result['changed'] = True
        if not check_mode:
            common_koji.ensure_logged_in(session)
            session.deleteExternalRepo(name)
    return result


def run_module():
    module_args = dict(
        koji=dict(),
        name=dict(required=True),
        state=dict(choices=['present', 'absent'], default='present'),
        url=dict(),
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
    url = params['url']

    session = common_koji.get_session(profile)

    if state == 'present':
        if not url:
            module.fail_json(msg='you must set a url for this external_repo')
        result = ensure_external_repo(session, name, check_mode, url)
    elif state == 'absent':
        result = delete_external_repo(session, name, check_mode)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
