#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils import common_koji

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
   name:
     description:
       - The name of the Koji tag to create and manage.
     required: true
   inheritance:
     description:
       - How to set inheritance. what happens when it's unset.
   external_repos:
     description:
       - list of Koji external repos to set for this tag. Each element of the
         list should have a "name" (external repo name) and "priority"
         (integer).
   packages:
     description:
       - dict of package owners and the a lists of packages each owner
         maintains.
   groups:
     description:
       - A tag's "groups" tell Koji what packages will be present in the
         tag's buildroot. For example, the "build" group defines the packages
         that Koji will put into a "build" task's buildroot. You may set other
         package groups on a tag as well, like "srpm-build" or
         "applicance-build".
       - This should be a dict of groups and packages to set for this tag.
         Each dict key will be the name of the group. Each dict value should
         be a list of package names to include in the comps for this group.
       - This does not support advanced comps group operations, like
         configuring extra options on groups, or blocking packages in groups.
         If you need that level of control over comps groups, you will need
         to import a full comps XML file, outside of this Ansible module.
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

    - name: Create a tag that uses an external repo
      koji_tag:
        koji: kojidev
        name: storage7-ceph-nautilus-el7-build
        state: present
        external_repos:
        - repo: centos7-cr
          priority: 5

    - name: Create a tag that uses comps groups
      koji_tag:
        name: foo-el7-build
        groups:
          srpm-build:
            - rpm-build
            - fedpkg
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


def describe_inheritance_rule(rule):
    return "%(priority)4d   .... %(name)s" % rule


def describe_inheritance(rules):
    return tuple(map(describe_inheritance_rule, rules))


def ensure_inheritance(session, tag_name, tag_id, check_mode, inheritance):
    """
    Ensure that these inheritance rules are configured on this Koji tag.

    :param session: Koji client session
    :param str tag_name: Koji tag name
    :param int tag_id: Koji tag ID
    :param bool check_mode: don't make any changes
    :param list inheritance: ensure these rules are set, and no others
    """
    rules = []
    result = {'changed': False, 'stdout_lines': []}
    for rule in sorted(inheritance, key=lambda i: i['priority']):
        parent_name = rule['parent']
        parent_taginfo = session.getTag(parent_name)
        if not parent_taginfo:
            msg = "parent tag '%s' not found" % parent_name
            if check_mode:
                result['stdout_lines'].append(msg)
                # spoof to allow continuation
                parent_taginfo = {'id': 0}
            else:
                raise ValueError(msg)
        parent_id = parent_taginfo['id']
        new_rule = {
            'child_id': tag_id,
            'intransitive': False,
            'maxdepth': None,
            'name': parent_name,
            'noconfig': False,
            'parent_id': parent_id,
            'pkg_filter': '',
            'priority': rule['priority']}
        rules.append(new_rule)
    current_inheritance = session.getInheritanceData(tag_name)
    if current_inheritance != rules:
        result['stdout_lines'].extend(
                ('current inheritance:',)
                + describe_inheritance(current_inheritance)
                + ('new inheritance:',)
                + describe_inheritance(rules))
        result['changed'] = True
        if not check_mode:
            common_koji.ensure_logged_in(session)
            session.setInheritanceData(tag_name, rules, clear=True)
    return result


def ensure_external_repos(session, tag_name, check_mode, repos):
    """
    Ensure that these external repos are configured on this Koji tag.

    :param session: Koji client session
    :param str tag_name: Koji tag name
    :param bool check_mode: don't make any changes
    :param list repos: ensure these external repos are set, and no others.
    """
    result = {'changed': False, 'stdout_lines': []}
    current_repo_list = session.getTagExternalRepos(tag_name)
    current = {repo['external_repo_name']: repo for repo in current_repo_list}
    current_priorities = {
        str(repo['priority']): repo for repo in current_repo_list
    }
    for repo in sorted(repos, key=lambda r: r['priority']):
        repo_name = repo['repo']
        repo_priority = repo['priority']
        if repo_name in current:
            # The repo is present for this tag.
            # Now ensure the priority is correct.
            if repo_priority == current[repo_name]['priority']:
                continue
            result['changed'] = True
            msg = 'set %s repo priority to %i' % (repo_name, repo_priority)
            result['stdout_lines'].append(msg)
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.editTagExternalRepo(tag_name, repo_name, repo_priority)
            continue
        elif str(repo_priority) in current_priorities:
            # No need to check for name equivalence here; it would already
            # have happened
            result['changed'] = True
            msg = 'set repo at priority %i to %s' % (repo_priority, repo_name)
            result['stdout_lines'].append(msg)
            if not check_mode:
                common_koji.ensure_logged_in(session)
                same_priority_repo = current_priorities.get(
                        str(repo_priority)).get('external_repo_name')
                session.removeExternalRepoFromTag(tag_name, same_priority_repo)
                session.addExternalRepoToTag(
                        tag_name, repo_name, repo_priority)
                # Prevent duplicate attempts
                del current_priorities[str(repo_priority)]
            continue
        result['changed'] = True
        msg = 'add %s external repo to %s' % (repo_name, tag_name)
        result['stdout_lines'].append(msg)
        if not check_mode:
            common_koji.ensure_logged_in(session)
            session.addExternalRepoToTag(tag_name, repo_name, repo_priority)
    # Find the repos to remove from this tag.
    repo_names = [repo['repo'] for repo in repos]
    current_names = current.keys()
    repos_to_remove = set(current_names) - set(repo_names)
    for repo_name in repos_to_remove:
        result['changed'] = True
        msg = 'removed %s repo from %s tag' % (repo_name, tag_name)
        result['stdout_lines'].append(msg)
        if not check_mode:
            common_koji.ensure_logged_in(session)
            session.removeExternalRepoFromTag(tag_name, repo_name)
    return result


def ensure_packages(session, tag_name, tag_id, check_mode, packages):
    """
    Ensure that these packages are configured on this Koji tag.

    :param session: Koji client session
    :param str tag_name: Koji tag name
    :param int tag_id: Koji tag ID
    :param bool check_mode: don't make any changes
    :param dict packages: ensure these packages are set (?)
    """
    result = {'changed': False, 'stdout_lines': []}

    # Obtain list of present packages from Koji.
    # Note: this in particular could really benefit from koji's
    # multicalls...
    common_koji.ensure_logged_in(session)
    present_pkgs = session.listPackages(tagID=tag_id)
    present_pkgs = {pkg['package_name']: pkg for pkg in present_pkgs}

    # Nolmalize list of expected packages.
    expected_pkgs = {}
    for owner, owned in packages.items():
        for package in owned:
            if isinstance(package, dict):
                package_name = package.keys()[0]
                blocked = package.values()[0].get('blocked', False)
            else:
                package_name = package
                blocked = False
            expected_pkgs[package_name] = {
                'owner_name': owner,
                'blocked': blocked,
            }

    def log_change(action, package_name):
        result['changed'] = True
        result['stdout_lines'].append('package %s was %s' % (package_name, action))

    def add_package(package_name, owner_name):
        log_change('added', package_name)
        if not check_mode:
            session.packageListAdd(tag_name, package_name, owner_name)

    def remove_package(package_name):
        log_change('removed', package_name)
        if not check_mode:
            session.packageListRemove(tag_name, package_name)

    def set_package_owner(package_name, owner_name):
        log_change('assigned to owner %s' % owner_name, package_name)
        if not check_mode:
            session.packageListSetOwner(tag_name, package_name, owner_name)

    def set_package_blocked(package_name, blocked):
        log_change('blocked' if blocked else 'unblocked', package_name)
        if not check_mode:
            if blocked:
                session.packageListBlock(tag_name, package_name)
            else:
                session.packageListUnblock(tag_name, package_name)

    present_names = set(present_pkgs.keys())
    expected_names = set(expected_pkgs.keys())

    for package_name in sorted(present_names - expected_names):
        remove_package(package_name)

    for package_name in sorted(expected_names - present_names):
        expected = expected_pkgs[package_name]
        add_package(package_name, expected['owner_name'])
        if expected['blocked']:
            set_package_blocked(package_name, True)

    for package_name in sorted(expected_names & present_names):
        present = present_pkgs[package_name]
        expected = expected_pkgs[package_name]
        if expected['owner_name'] != present['owner_name']:
            set_package_owner(package_name, expected['owner_name'])
        if expected['blocked'] != present['blocked']:
            set_package_blocked(package_name, expected['blocked'])

    return result


def ensure_groups(session, tag_id, check_mode, desired_groups):
    """
    Ensure that these groups are configured on this Koji tag.

    :param session: Koji client session
    :param int tag_id: Koji tag ID
    :param bool check_mode: don't make any changes
    :param dict desired_groups: ensure these groups are set (?)
    """
    result = {'changed': False, 'stdout_lines': []}
    common_koji.ensure_logged_in(session)
    current_groups = session.getTagGroups(tag_id, inherit=False)
    for group in current_groups:
        if group['name'] not in desired_groups:
            if not check_mode:
                session.groupListRemove(tag_id, group['name'])
            result['stdout_lines'].append('removed group %s' % group['name'])
            result['changed'] = True
    for group_name, desired_pkgs in desired_groups.items():
        for group in current_groups:
            if group['name'] == group_name:
                current_pkgs = [entry['package']
                                for entry in group['packagelist']]
                break
        else:
            current_pkgs = []
            if not check_mode:
                session.groupListAdd(tag_id, group_name)
            result['stdout_lines'].append('added group %s' % group_name)
            result['changed'] = True
        for package in current_pkgs:
            if package not in desired_pkgs:
                if not check_mode:
                    session.groupPackageListRemove(tag_id, group_name, package)
                result['stdout_lines'].append('removed pkg %s from group %s' % (package, group_name))
                result['changed'] = True
        for package in desired_pkgs:
            if package not in current_pkgs:
                if not check_mode:
                    session.groupPackageListAdd(tag_id, group_name, package)
                result['stdout_lines'].append('added pkg %s to group %s' % (package, group_name))
                result['changed'] = True
    return result


def compound_parameter_present(param_name, param, expected_type):
    if param not in (None, ''):
        if not isinstance(param, expected_type):
            raise ValueError(param_name + ' must be a '
                             + expected_type.__class__.__name__
                             + ', not a ' + param.__class__.__name__)
        return True
    return False


def ensure_tag(session, name, check_mode, inheritance, external_repos,
               packages, groups, **kwargs):
    """
    Ensure that this tag exists in Koji.

    :param session: Koji client session
    :param name: Koji tag name
    :param check_mode: don't make any changes
    :param inheritance: Koji tag inheritance settings. These will be translated
                        for Koji's setInheritanceData RPC.
    :param external_repos: Koji external repos to set for this tag.
    :param packages: dict of packages to add ("whitelist") for this tag.
                     If this is an empty dict, we don't touch the package list
                     for this tag.
    :param groups: dict of comps groups to set for this tag.
    :param **kwargs: Pass remaining kwargs directly into Koji's createTag and
                     editTag2 RPCs.
    """
    taginfo = session.getTag(name)
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
        edit_log = []
        for key, value in kwargs.items():
            if taginfo[key] != value and value is not None:
                edits[key] = value
                edit_log.append('%s: changed %s from "%s" to "%s"'
                                % (name, key, taginfo[key], value))
        # Find out which "extra" items we must explicitly remove
        # ("remove_extra" argument to editTag2).
        if 'extra' in kwargs and kwargs['extra'] is not None:
            for key in taginfo['extra']:
                if key not in kwargs['extra']:
                    if 'remove_extra' not in edits:
                        edits['remove_extra'] = []
                    edits['remove_extra'].append(key)
            if 'remove_extra' in edits:
                edit_log.append('%s: remove extra fields "%s"'
                                % (name, '", "'.join(edits['remove_extra'])))
        if edits:
            result['stdout_lines'].extend(edit_log)
            result['changed'] = True
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.editTag2(name, **edits)

    # Ensure inheritance rules are all set.
    if compound_parameter_present('inheritance', inheritance, list):
        inheritance_result = ensure_inheritance(session, name, taginfo['id'],
                                                check_mode, inheritance)
        if inheritance_result['changed']:
            result['changed'] = True
        result['stdout_lines'].extend(inheritance_result['stdout_lines'])

    # Ensure external repos.
    if compound_parameter_present('external_repos', external_repos, list):
        repos_result = ensure_external_repos(session, name, check_mode,
                                             external_repos)
        if repos_result['changed']:
            result['changed'] = True
        result['stdout_lines'].extend(repos_result['stdout_lines'])

    # Ensure package list.
    if compound_parameter_present('packages', packages, dict):
        packages_result = ensure_packages(session, name, taginfo['id'],
                                          check_mode, packages)
        if packages_result['changed']:
            result['changed'] = True
        result['stdout_lines'].extend(packages_result['stdout_lines'])

    # Ensure group list.
    if compound_parameter_present('groups', groups, dict):
        groups_result = ensure_groups(session, taginfo['id'],
                                      check_mode, groups)
        if groups_result['changed']:
            result['changed'] = True
        result['stdout_lines'].extend(groups_result['stdout_lines'])

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
        inheritance=dict(type='raw', required=False, default=None),
        external_repos=dict(type='raw', required=False, default=None),
        packages=dict(type='raw', required=False, default=None),
        groups=dict(type='raw', required=False, default=None),
        arches=dict(type='str', required=False, default=None),
        perm=dict(type='str', required=False, default=None),
        locked=dict(type='bool', required=False, default=False),
        maven_support=dict(type='bool', required=False, default=False),
        maven_include_all=dict(type='bool', required=False, default=False),
        extra=dict(type='dict', required=False, default=None),
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
        result = ensure_tag(session, name,
                            check_mode,
                            inheritance=params['inheritance'],
                            external_repos=params['external_repos'],
                            packages=params['packages'],
                            groups=params['groups'],
                            arches=params['arches'],
                            perm=params['perm'] or None,
                            locked=params['locked'],
                            maven_support=params['maven_support'],
                            maven_include_all=params['maven_include_all'],
                            extra=params['extra'])
    elif state == 'absent':
        result = delete_tag(session, name, check_mode)
    else:
        module.fail_json(msg="State must be 'present' or 'absent'.",
                         changed=False, rc=1)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
