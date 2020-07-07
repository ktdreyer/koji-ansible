#!/usr/bin/python
from collections import defaultdict
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils import common_koji


ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
---
module: koji_tag_packages

short_description: Manage Koji tag packages
description:
   - Fine-grained management for tag packages.
   - The `koji_tag` module is all-or-nothing when it comes to managing tag
     packages. When you set packages with `koji_tag`, the module will
     delete any packages that are not defined there.
   - In some cases you may want to declare *some* packages 
     within Ansible without clobbering other existing tag
     packages.
options:
   tag:
     description:
       - The name of the Koji tag to manage packages for.
     required: true
   packages:
     description:
       - dict of package owners and the a lists of packages each owner
         maintains.
     required: true
   state:
     description:
       - Whether to add or remove the given packages.
     choices: [present, absent]
     default: present
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: Ensure packages are present for ceph-3.1-rhel-7
  koji_tag_packages:
    koji: kojidev
    tag: ceph-3.1-rhel-7
    state: present
    packages:
      kdreyer:
        - ansible
        - ceph
        - ceph-ansible

- name: Ensure packages are absent for ceph-3.1-rhel-7
  koji_tag_packages:
    koji: kojidev
    tag: ceph-3.1-rhel-7
    state: absent 
    packages:
      kdreyer:
        - ansible
        - ceph
        - ceph-ansible
'''

RETURN = ''' # '''


def ensure_packages(session, tag_name, tag_id, check_mode, packages):
    """
    Ensure that these packages are configured on this Koji tag.

    :param session: Koji client session
    :param str tag_name: Koji tag name
    :param int tag_id: Koji tag ID
    :param bool check_mode: don't make any changes
    :param dict packages: Ensure that these owners and package names are
                          configured for this tag.
    """
    result = {'changed': False, 'stdout_lines': []}
    # Note: this in particular could really benefit from koji's
    # multicalls...
    common_koji.ensure_logged_in(session)
    current_pkgs = session.listPackages(tagID=tag_id)
    current_names = set([pkg['package_name'] for pkg in current_pkgs])
    # Create a "current_owned" dict to compare with what's in Ansible.
    current_owned = defaultdict(set)
    for pkg in current_pkgs:
        owner = pkg['owner_name']
        pkg_name = pkg['package_name']
        current_owned[owner].add(pkg_name)
    for owner, owned in packages.items():
        for package in owned:
            if package not in current_names:
                # The package was missing from the tag entirely.
                if not check_mode:
                    session.packageListAdd(tag_name, package, owner)
                result['stdout_lines'].append('added pkg %s' % package)
                result['changed'] = True
            else:
                # The package is already in this tag.
                # Verify ownership.
                if package not in current_owned.get(owner, []):
                    if not check_mode:
                        session.packageListSetOwner(tag_name, package, owner)
                    result['stdout_lines'].append('set %s owner %s' %
                                                  (package, owner))
                    result['changed'] = True
    return result


def remove_packages(session, tag_name, check_mode, packages):
    result = {'changed': False, 'stdout_lines': []}
    for owner, packages in packages.items():
        for package in packages:
            result['stdout_lines'].append('remove pkg %s' % package)
            result['changed'] = True
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.packageListRemove(tag_name, package, owner)
    return result

def run_module():
    module_args = dict(
        koji=dict(),
        tag=dict(required=True),
        state=dict(choices=['present', 'absent'], default='present'),
        packages=dict(type='dict', required=True),
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
    tag_name = params['tag']
    state = params['state']
    packages = params['packages']

    session = common_koji.get_session(profile)
    tag_info = session.getTag(tag_name)

    if state == 'present':
        # ensure packages are there
        result = ensure_packages(session, tag_name, tag_info['id'], check_mode, packages)
    elif state == 'absent':
        # delete packages
        result = remove_packages(session, tag_name, check_mode, packages)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
