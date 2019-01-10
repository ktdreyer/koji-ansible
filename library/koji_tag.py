#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native
from ansible.errors import AnsibleError
from collections import defaultdict
import common_koji

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
---
module: koji_tag

short_description: Create and manage Koji tags
description:
   - Create and manage Koji tags
options:
   inheritance:
     description:
       - The name of the Koji tag to create and manage.
     required: true
   inheritance:
     description:
       - How to set inheritance. what happens when it's unset.
   packages:
     description:
       - dict of package owners and the a lists of packages each owner
         maintains.
   arches:
     description:
       - space-separated string of arches this Koji tag supports.
   perm:
     description:
       - permission (string or int) for this Koji tag.
   locked:
     description:
       - whether to lock this tag or not.
     choices: [true, false]
     default: false
   locked:
     description:
       - whether to lock this tag or not.
     choices: [true, false]
     default: false
   maven_support:
     description:
       - whether Maven repos should be generated for the tag.
     choices: [true, false]
     default: false
   maven_include_all:
     description:
       - include every build in this tag (including multiple versions of the
         same package) in the Maven repo.
     choices: [true, false]
     default: false
   extra:
     description:
       - set any extra parameters on this tag.
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: create a main koji tag and candidate tag
  hosts: localhost
  tasks:
    - name: Create a main product koji tag
      koji_tag:
        koji: kojidev
        name: ceph-3.1-rhel-7
        arches: x86_64
        state: present
        packages:
          kdreyer:
            - ansible
            - ceph
            - ceph-ansible

    - name: Create a candidate koji tag
      koji_tag:
        koji: kojidev
        name: ceph-3.1-rhel-7-candidate
        state: present
        inheritance:
        - parent: ceph-3.1-rhel-7
          priority: 0
'''

RETURN = ''' # '''

perm_cache = {}


def get_perm_id(session, name):
    global perm_cache
    if not perm_cache:
        perm_cache = dict([
            (perm['name'], perm['id']) for perm in session.getAllPerms()
        ])
    return perm_cache[name]


def ensure_tag(session, name, check_mode, inheritance, packages, **kwargs):
    """
    Ensure that this tag exists in Koji.

    :param session: Koji client session
    :param name: Koji tag name
    :param check_mode: don't make any changes
    :param inheritance: Koji tag inheritance settings. These will be translated
                        for Koji's setInheritanceData RPC.
    :param packages: dict of packages to add ("whitelist") for this tag.
                     If this is an empty dict, we don't touch the package list
                     for this tag.
    :param **kwargs: Pass remaining kwargs directly into Koji's createTag and
                     editTag2 RPCs.
    """
    taginfo = session.getTag(name)
    # fixme: we're clobbering 'stdout' here every time we make a change. maybe
    # use 'stdout_lines' instead or something.
    result = {'changed': False, 'stdout_lines': []}
    if not taginfo:
        if check_mode:
            result['stdout_lines'].append('would create tag %s' % name)
            result['changed'] = True
            return result
        common_koji.ensure_logged_in(session)
        if 'perm' in kwargs and kwargs['perm']:
            kwargs['perm'] = get_perm_id(session, kwargs['perm'])
        id_ = session.createTag(name, parent=None, **kwargs)
        result['stdout_lines'].append('created tag id %d' % id_)
        result['changed'] = True
        taginfo = {'id': id_}  # populate for inheritance management below
    else:
        # The tag name already exists. Ensure all the parameters are set.
        edits = {}
        for key, value in kwargs.items():
            if taginfo[key] != value:
                edits[key] = value
        # Find out which "extra" items we must explicitly remove
        # ("remove_extra" argument to editTag2).
        if 'extra' in kwargs:
            for key in taginfo['extra']:
                if key not in kwargs['extra']:
                    if 'remove_extra' not in edits:
                        edits['remove_extra'] = []
                    edits['remove_extra'].append(key)
        if edits:
            result['stdout_lines'].append(str(edits))
            result['changed'] = True
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.editTag2(name, **edits)
    # Ensure inheritance rules are all set.
    rules = []
    for rule in inheritance:
        parent_name = rule['parent']
        parent_taginfo = session.getTag(parent_name)
        if not parent_taginfo:
            raise ValueError("parent tag '%s' not found" % parent_name)
        parent_id = parent_taginfo['id']
        new_rule = {
            'child_id': taginfo['id'],
            'intransitive': False,
            'maxdepth': None,
            'name': parent_name,
            'noconfig': False,
            'parent_id': parent_id,
            'pkg_filter': '',
            'priority': rule['priority']}
        rules.append(new_rule)
    current_inheritance = session.getInheritanceData(name)
    if current_inheritance != rules:
        result['stdout_lines'].append('inheritance is %s' % inheritance)
        result['changed'] = True
        if not check_mode:
            common_koji.ensure_logged_in(session)
            session.setInheritanceData(name, rules, clear=True)
    # Ensure package list.
    if packages:
        # Note: this in particular could really benefit from koji's
        # multicalls...
        common_koji.ensure_logged_in(session)
        current_pkgs = session.listPackages(tagID=taginfo['id'])
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
                        session.packageListAdd(name, package, owner)
                    result['stdout_lines'].append('added pkg %s' % package)
                    result['changed'] = True
                else:
                    # The package is already in this tag.
                    # Verify ownership.
                    if package not in current_owned.get(owner, []):
                        if not check_mode:
                            session.packageListSetOwner(name, package, owner)
                        result['stdout_lines'].append('set %s owner %s' %
                                                      (package, owner))
                        result['changed'] = True
        # Delete any packages not in Ansible.
        all_names = [name for names in packages.values() for name in names]
        delete_names = set(current_names) - set(all_names)
        for package in delete_names:
            result['stdout_lines'].append('remove pkg %s' % package)
            result['changed'] = True
            if not check_mode:
                session.packageListRemove(name, package, owner)
    return result


def delete_tag(session, name, check_mode):
    """ Ensure that this tag is deleted from Koji. """
    taginfo = session.getTag(name)
    result = dict(
        stdout='',
        changed=False,
    )
    if taginfo:
        result['stdout'] = 'deleted tag %d' % taginfo['id']
        result['changed'] = True
        if not check_mode:
            common_koji.ensure_logged_in(session)
            session.deleteTag(name)
    return result


def run_module():
    module_args = dict(
        koji=dict(type='str', required=False),
        name=dict(type='str', required=True),
        state=dict(type='str', required=False, default='present'),
        inheritance=dict(type='list', required=False, default=[]),
        packages=dict(type='dict', required=False, default={}),
        arches=dict(type='str', required=False, default=None),
        perm=dict(type='str', required=False, default=None),
        locked=dict(type='bool', required=False, default=False),
        maven_support=dict(type='bool', required=False, default=False),
        maven_include_all=dict(type='bool', required=False, default=False),
        extra=dict(type='dict', required=False, default={}),
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

    if state == 'present':
        try:
            result = ensure_tag(session, name,
                                check_mode,
                                inheritance=params['inheritance'],
                                packages=params['packages'],
                                arches=params['arches'],
                                perm=params['perm'] or None,
                                locked=params['locked'],
                                maven_support=params['maven_support'],
                                maven_include_all=params['maven_include_all'],
                                extra=params['extra'])
        except Exception as e:
            raise AnsibleError(
                    "koji_tag ensure_tag '%s' failed:\n%s\nparameters:\n%s"
                    % (name, to_native(e), params))
    elif state == 'absent':
        try:
            result = delete_tag(session, name)
        except Exception as e:
            raise AnsibleError(
                    "koji_tag delete_tag '%s' failed:\n%s"
                    % (name, to_native(e)))
    else:
        module.fail_json(msg="State must be 'present' or 'absent'.",
                         changed=False, rc=1)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
