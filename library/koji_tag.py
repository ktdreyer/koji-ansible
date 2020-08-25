#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
from collections import defaultdict
from ansible.module_utils import common_koji
from ansible.module_utils.six import string_types


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
         list should have a "repo" (the external repo name) and "priority"
         (integer). You may optionally set a "merge_mode" for this external
         repo ("koji", "simple", or "bare"). For backwards compatibility, if
         you do not set a "merge_mode" and the external repository already
         exists at the given priority, then Ansible will not edit the existing
         merge mode.
   packages:
     description:
       - dict of package owners and the a lists of packages each owner
         maintains.
       - If you omit this "packages" setting, Ansible will not edit the
         existing package list for this tag. For example, if you have another
         system that already manages the package list for this tag, you may
         want to omit this setting in Ansible.
         https://github.com/project-ncl/causeway is one example of a system
         that independently manages the package lists for individual Koji
         tags.
       - If you explicitly set "packages" to an empty dict, Ansible will
         remove all the packages defined on this tag.
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
       - If a group or package defined in this field is already applicable for
         a tag due to inheritance, Koji will not allow it to be added to the
         tag, but will instead silently ignore it. Conversely, groups and
         packages that are inherited in this field are not removed if they are
         left unspecified. Therefore, this field will only have an effect if it
         includes groups and packages that are unique to this tag (i.e., not
         inherited).
       - This does not support advanced comps group operations, like
         configuring extra options on groups, or blocking packages in groups.
         If you need that level of control over comps groups, you will need
         to import a full comps XML file, outside of this Ansible module.
   arches:
     description:
       - space-separated string of arches this Koji tag supports.
       - Note, the order in which you specify architectures does matter in a
         few subtle cases. For example, the SRPM that Koji includes in the
         build is the one built on the first arch in this list. Likewise,
         rpmdiff compares RPMs built on the first arch with RPMs built on
         other arches.
   perm:
     description:
       - permission (string or int) for this Koji tag.
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


class DuplicateNameError(Exception):
    """ The user specified two external repos with the same name. """
    pass


class DuplicatePriorityError(Exception):
    """ The user specified two external repos with the same priority. """
    pass


def validate_repos(repos):
    """Ensure that each external repository has unique name and priority
    values.

    This prevents the user from accidentally specifying two or more external
    repositories with the same name or priority.

    :param list repos: list of repository dicts
    :raises: DuplicatePriorityError if two repos have the same priority.
    """
    names = set()
    priorities = set()
    for repo in repos:
        name = repo['repo']
        priority = repo['priority']
        if name in names:
            raise DuplicateNameError(name)
        if priority in priorities:
            raise DuplicatePriorityError(priority)
        names.add(name)
        priorities.add(priority)


def normalize_inheritance(inheritance):
    """
    Transform inheritance module argument input into the format returned by
    getInheritanceData(). Only includes supported fields (excluding child_id
    and parent_id), renames "parent" to "name", chooses correct defaults for
    missing fields, and performs some limited type correction for maxdepth and
    priority.

    :param inheritance: list of inheritance dicts
    """
    normalized_inheritance = []

    for rule in inheritance:
        # maxdepth: treat empty strings the same as None
        maxdepth = rule.get('maxdepth')
        if maxdepth == '':
            maxdepth = None
        if isinstance(maxdepth, string_types):
            maxdepth = int(maxdepth)

        normalized_inheritance.append(dict(
            # we don't know child_id yet
            intransitive=rule.get('intransitive', False),
            maxdepth=maxdepth,
            name=rule['parent'],
            noconfig=rule.get('noconfig', False),
            # we don't know parent_id yet
            pkg_filter=rule.get('pkg_filter', ''),
            priority=int(rule['priority']),
        ))

    return sorted(normalized_inheritance, key=lambda i: i['priority'])


def ensure_inheritance(session, tag_name, tag_id, check_mode, inheritance):
    """
    Ensure that these inheritance rules are configured on this Koji tag.

    :param session: Koji client session
    :param str tag_name: Koji tag name
    :param int tag_id: Koji tag ID
    :param bool check_mode: don't make any changes
    :param list inheritance: ensure these rules are set, and no others
    """
    result = {'changed': False, 'stdout_lines': []}

    # resolve parent tag IDs
    rules = []
    for rule in normalize_inheritance(inheritance):
        parent_name = rule['name']
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
        rules.append(dict(rule, child_id=tag_id, parent_id=parent_id))

    current_inheritance = session.getInheritanceData(tag_name)
    if current_inheritance != rules:
        result['stdout_lines'].extend(
                ('current inheritance:',)
                + common_koji.describe_inheritance(current_inheritance)
                + ('new inheritance:',)
                + common_koji.describe_inheritance(rules))
        result['changed'] = True
        if not check_mode:
            common_koji.ensure_logged_in(session)
            session.setInheritanceData(tag_name, rules, clear=True)
    return result


def remove_external_repos(session, tag_name, repos):
    """
    Remove all these external repos from this Koji tag.

    :param session: Koji client session
    :param str tag_name: Koji tag name
    :param list repos: list of repository names (str) to remove.
    """
    # TODO: refactor this loop to one single multicall.
    common_koji.ensure_logged_in(session)
    for name in repos:
        session.removeExternalRepoFromTag(tag_name, name)


def add_external_repos(session, tag_name, repos):
    """
    Add all these external repos to this Koji tag.

    :param session: Koji client session
    :param str tag_name: Koji tag name
    :param list repos: list of dicts, one for each repository to add. These
                       dicts are kwargs to the addExternalRepoToTag RPC.
    """
    # TODO: refactor this loop to one single multicall.
    common_koji.ensure_logged_in(session)
    for repo in repos:
        session.addExternalRepoToTag(tag_name, **repo)


def ensure_external_repos(session, tag_name, check_mode, repos):
    """
    Ensure that these external repos are configured on this Koji tag.

    :param session: Koji client session
    :param str tag_name: Koji tag name
    :param bool check_mode: don't make any changes
    :param list repos: ensure these external repos are set, and no others.
    """
    result = {'changed': False, 'stdout_lines': []}
    validate_repos(repos)
    current = session.getTagExternalRepos(tag_name)
    current_repos = {repo['external_repo_name']: repo for repo in current}
    desired_repos = {repo['repo']: repo for repo in repos}
    # Remove all the incorrect repos first.
    repos_to_remove = set()
    for name, repo in current_repos.items():
        if name not in desired_repos:
            msg = 'Removing %s repo from tag %s' % (name, tag_name)
            result['stdout_lines'].append(msg)
            repos_to_remove.add(name)
            continue
        priority = repo['priority']
        desired_priority = desired_repos[name]['priority']
        if priority != desired_priority:
            msg = 'Removing %s repo at priority %d from tag %s' \
                  % (name, priority, tag_name)
            result['stdout_lines'].append(msg)
            repos_to_remove.add(name)
            continue
        if 'merge_mode' in desired_repos[name]:
            merge_mode = repo['merge_mode']
            desired_merge_mode = desired_repos[name]['merge_mode']
            if merge_mode != desired_merge_mode:
                msg = 'Removing %s repo with merge mode "%s" from tag %s' \
                      % (name, merge_mode, tag_name)
                result['stdout_lines'].append(msg)
                repos_to_remove.add(name)
    # Perform the removals.
    if repos_to_remove and not check_mode:
        remove_external_repos(session, tag_name, repos_to_remove)
    # Next, find all the repos to add.
    repos_to_add = []
    for name, desired_repo in desired_repos.items():
        if name in current_repos:
            current_repo = current_repos[name]
            if desired_repo['priority'] == current_repo['priority']:
                if 'merge_mode' not in desired_repo:
                    # This repo is currently correct. Move on to the next one.
                    continue
                if desired_repo['merge_mode'] == current_repo['merge_mode']:
                    # This repo is currently correct. Move on to the next one.
                    continue
        msg = 'Adding %s repo with prio %d to tag %s' \
              % (name, desired_repo['priority'], tag_name)
        new_repo = {'repo_info': name, 'priority': desired_repo['priority']}
        if 'merge_mode' in desired_repo:
            new_repo['merge_mode'] = desired_repo['merge_mode']
            msg += ' with merge mode "%s"' % desired_repo['merge_mode']
        result['stdout_lines'].append(msg)
        repos_to_add.append(new_repo)
    # Perform the additions.
    if repos_to_add and not check_mode:
        add_external_repos(session, tag_name, repos_to_add)
    if result['stdout_lines']:
        result['changed'] = True
    return result


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
                    common_koji.ensure_logged_in(session)
                    session.packageListAdd(tag_name, package, owner)
                result['stdout_lines'].append('added pkg %s' % package)
                result['changed'] = True
            else:
                # The package is already in this tag.
                # Verify ownership.
                if package not in current_owned.get(owner, []):
                    if not check_mode:
                        common_koji.ensure_logged_in(session)
                        session.packageListSetOwner(tag_name, package, owner)
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
            common_koji.ensure_logged_in(session)
            session.packageListRemove(tag_name, package, owner)
    return result


def ensure_groups(session, tag_id, check_mode, desired_groups):
    """
    Ensure that these groups are configured on this Koji tag.

    :param session: Koji client session
    :param int tag_id: Koji tag ID
    :param bool check_mode: don't make any changes
    :param dict desired_groups: Ensure that these group names and packages are
                                configured for this tag.
    """
    result = {'changed': False, 'stdout_lines': []}
    current_groups = session.getTagGroups(tag_id)
    for group in current_groups:
        if group['tag_id'] == tag_id and group['name'] not in desired_groups:
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.groupListRemove(tag_id, group['name'])
            result['stdout_lines'].append('removed group %s' % group['name'])
            result['changed'] = True
    for group_name, desired_pkgs in desired_groups.items():
        for group in current_groups:
            if group['name'] == group_name:
                current_pkgs = {entry['package']: entry['tag_id']
                                for entry in group['packagelist']}
                break
        else:
            current_pkgs = {}
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.groupListAdd(tag_id, group_name)
            result['stdout_lines'].append('added group %s' % group_name)
            result['changed'] = True

        for package, pkg_tag_id in current_pkgs.items():
            if pkg_tag_id == tag_id and package not in desired_pkgs:
                if not check_mode:
                    common_koji.ensure_logged_in(session)
                    session.groupPackageListRemove(tag_id, group_name, package)
                result['stdout_lines'].append('removed pkg %s from group %s' % (package, group_name))
                result['changed'] = True
        for package in desired_pkgs:
            if package not in current_pkgs:
                if not check_mode:
                    common_koji.ensure_logged_in(session)
                    session.groupPackageListAdd(tag_id, group_name, package)
                result['stdout_lines'].append('added pkg %s to group %s' % (package, group_name))
                result['changed'] = True
    return result


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
            kwargs['perm'] = common_koji.get_perm_id(session, kwargs['perm'])
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
    if inheritance not in (None, ['']):
        inheritance_result = ensure_inheritance(session, name, taginfo['id'],
                                                check_mode, inheritance)
        if inheritance_result['changed']:
            result['changed'] = True
        result['stdout_lines'].extend(inheritance_result['stdout_lines'])

    # Ensure external repos.
    if external_repos not in (None, ['']):
        repos_result = ensure_external_repos(session, name, check_mode,
                                             external_repos)
        if repos_result['changed']:
            result['changed'] = True
        result['stdout_lines'].extend(repos_result['stdout_lines'])

    # Ensure package list.
    if packages not in (None, ''):
        if not isinstance(packages, dict):
            raise ValueError('packages must be a dict')
        packages_result = ensure_packages(session, name, taginfo['id'],
                                          check_mode, packages)
        if packages_result['changed']:
            result['changed'] = True
        result['stdout_lines'].extend(packages_result['stdout_lines'])

    # Ensure group list.
    if groups not in (None, ''):
        if not isinstance(groups, dict):
            raise ValueError('groups must be a dict')
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
        koji=dict(),
        name=dict(required=True),
        state=dict(choices=['present', 'absent'], default='present'),
        inheritance=dict(type='list'),
        external_repos=dict(type='list'),
        packages=dict(type='raw'),
        groups=dict(type='raw'),
        arches=dict(),
        perm=dict(),
        locked=dict(type='bool', default=False),
        maven_support=dict(type='bool', default=False),
        maven_include_all=dict(type='bool', default=False),
        extra=dict(type='dict'),
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

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
