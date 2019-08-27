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
module: koji_tag_inheritance

short_description: Manage a Koji tag inheritance relationship
description:
   - Fine-grained management for tag inheritance relationships.
   - The `koji_tag` module is all-or-nothing when it comes to managing tag
     inheritance. When you set inheritance with `koji_tag`, the module will
     delete any inheritance relationships that are not defined there.
   - In some cases you may want to declare *some* inheritance relationships
     within Ansible without clobbering other existing inheritance
     relationships. For example, `MBS
     <https://fedoraproject.org/wiki/Changes/ModuleBuildService>`_ will
     dynamically manage some inheritance relationships of tags.
options:
   child_tag:
     description:
       - The name of the Koji tag that will be the child.
     required: true
   parent_tag:
     description:
       - The name of the Koji tag that will be the parent of the child.
     required: true
   priority:
     description:
       - The priority of this parent for this child. Parents with smaller
         numbers will override parents with bigger numbers.
       - When defining an inheritance relationship with "state: present", you
         must specify a priority. When deleting an inheritance relationship
         with "state: absent", you should not specify a priority. Ansible will
         simply remove the parent_tag link, regardless of its priority.
     required: true
   maxdepth:
     description:
       - By default, a tag's inheritance chain is unlimited. This means that
         Koji will look back through an unlimited chain of parent and
         grandparent tags to determine the contents of the tag.
       - You may use this maxdepth parameter to limit the maximum depth of the
         inheritance. For example "0" means that only the parent tag itself
         will be available in the inheritance - parent tags of the parent tag
         won't be available.
       - To restore the default umlimited depth behavior on a tag, you can set
         ``maxdepth: null`` or ``maxdepth: `` (empty value).
       - If you do not set any ``maxdepth`` parameter at all, koji-ansible
         will overwrite an existing tag's current maxdepth setting to "null"
         (in other words, unlimited depth). This was the historical behavior
         of the module and the easiest way to implement this in the code.
         Arguably this behavior is unexpected, because Ansible should only do
         what you tell it to do. We might change this in the future so that
         Ansible only modifies ``maxdepth`` *if* you explicitly configure it.
         Please open GitHub issues to discuss your use-case.
     required: false
     default: null (unlimited depth)
   pkg_filter:
     description:
       - Regular expression selecting the packages for which builds can be
         inherited through this inheritance link.
       - Don't forget to use ``^`` and ``$`` when limiting to exact package
         names; they are not implicit.
       - The default empty string allows all packages to be inherited through
         this link.
     required: false
     default: ''
   intransitive:
     description:
       - Prevents inheritance link from being used by the child tag's children.
         In other words, the link is only used to determine parent tags for the
         child tag directly, but not to determine "grandparent" tags for the
         child tag's children.
     required: false
     default: false
   noconfig:
     description:
       - Prevents tag options ("extra") from being inherited.
     required: false
     default: false
   state:
     description:
       - Whether to add or remove this inheritance link.
     choices: [present, absent]
     default: present
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: Use devtoolset to build for Ceph Nautilus
  hosts: localhost
  tasks:
    - name: set devtoolset-7 as a parent of ceph nautilus
      koji_tag_inheritance:
        koji: kojidev
        parent_tag: sclo7-devtoolset-7-rh-release
        child_tag: storage7-ceph-nautilus-el7-build
        priority: 25

    - name: remove devtoolset-7 as a parent of my other build tag
      koji_tag_inheritance:
        parent_tag: sclo7-devtoolset-7-rh-release
        child_tag: other-storage-el7-build
        state: absent
'''

RETURN = ''' # '''


def get_ids_and_inheritance(session, child_tag, parent_tag):
    """
    Query Koji for the current state of these tags and inheritance.

    :param session: Koji client session
    :param str child_tag: Koji tag name
    :param str parent_tag: Koji tag name
    :return: 3-element tuple of child_id (int), parent_id (int),
             and current_inheritance (list)
    """
    child_taginfo = session.getTag(child_tag)
    parent_taginfo = session.getTag(parent_tag)
    child_id = child_taginfo['id'] if child_taginfo else None
    parent_id = parent_taginfo['id'] if parent_taginfo else None
    if child_id:
        current_inheritance = session.getInheritanceData(child_id)
    else:
        current_inheritance = []
    # TODO use multicall to get all of this at once:
    # (Need to update the test suite fakes to handle multicalls)
    # session.multicall = True
    # session.getTag(child_tag, strict=True)
    # session.getTag(parent_tag, strict=True)
    # session.getInheritanceData(child_tag)
    # multicall_results = session.multiCall(strict=True)
    # # flatten multicall results:
    # multicall_results = [result[0] for result in multicall_results]
    # child_id = multicall_results[0]['id']
    # parent_id = multicall_results[1]['id']
    # current_inheritance = multicall_results[2]
    return (child_id, parent_id, current_inheritance)


def generate_new_rule(child_id, parent_tag, parent_id, priority, maxdepth,
                      pkg_filter, intransitive, noconfig):
    """
    Return a full inheritance rule to add for this child tag.

    :param int child_id: Koji tag id
    :param str parent_tag: Koji tag name
    :param int parent_id: Koji tag id
    :param int priority: Priority of this parent for this child
    :param int maxdepth: Max depth of the inheritance
    :param str pkg_filter: Regular expression string of package names to include
    :param bool intransitive: Don't allow this inheritance link to be inherited
    :param bool noconfig: Prevent tag options ("extra") from being inherited
    """
    return {
        'child_id': child_id,
        'intransitive': intransitive,
        'maxdepth': maxdepth,
        'name': parent_tag,
        'noconfig': noconfig,
        'parent_id': parent_id,
        'pkg_filter': pkg_filter,
        'priority': priority}


def add_tag_inheritance(session, child_tag, parent_tag, priority, maxdepth,
                        pkg_filter, intransitive, noconfig, check_mode):
    """
    Ensure that a tag inheritance rule exists.

    :param session: Koji client session
    :param str child_tag: Koji tag name
    :param str parent_tag: Koji tag name
    :param int priority: Priority of this parent for this child
    :param int maxdepth: Max depth of the inheritance
    :param str pkg_filter: Regular expression string of package names to include
    :param bool intransitive: Don't allow this inheritance link to be inherited
    :param bool noconfig: Prevent tag options ("extra") from being inherited
    :param bool check_mode: don't make any changes
    :return: result (dict)
    """
    result = {'changed': False, 'stdout_lines': []}
    data = get_ids_and_inheritance(session, child_tag, parent_tag)
    child_id, parent_id, current_inheritance = data
    if not child_id:
        msg = 'child tag %s not found' % child_tag
        if check_mode:
            result['stdout_lines'].append(msg)
        else:
            raise ValueError(msg)
    if not parent_id:
        msg = 'parent tag %s not found' % parent_tag
        if check_mode:
            result['stdout_lines'].append(msg)
        else:
            raise ValueError(msg)

    new_rule = generate_new_rule(child_id, parent_tag, parent_id, priority,
                                 maxdepth, pkg_filter, intransitive, noconfig)
    new_rules = [new_rule]
    for rule in current_inheritance:
        if rule == new_rule:
            return result
        # if either name or priority has changed without the other, we need to
        # delete then reinsert
        if (rule['name'] == parent_tag) != (rule['priority'] == priority):
            # prefix taginfo-style inheritance strings with diff-like +/-
            result['stdout_lines'].append('dissimilar rules:')
            result['stdout_lines'].extend(
                    map(lambda r: ' -' + r,
                        common_koji.describe_inheritance_rule(rule)))
            result['stdout_lines'].extend(
                    map(lambda r: ' +' + r,
                        common_koji.describe_inheritance_rule(new_rule)))
            delete_rule = rule.copy()
            # Mark this rule for deletion
            delete_rule['delete link'] = True
            new_rules.insert(0, delete_rule)

    if len(new_rules) > 1:
        result['stdout_lines'].append('remove inheritance link:')
        result['stdout_lines'].extend(
                common_koji.describe_inheritance(new_rules[:-1]))
    result['stdout_lines'].append('add inheritance link:')
    result['stdout_lines'].extend(
            common_koji.describe_inheritance_rule(new_rule))
    result['changed'] = True
    if not check_mode:
        common_koji.ensure_logged_in(session)
        session.setInheritanceData(child_tag, new_rules)
    return result


def remove_tag_inheritance(session, child_tag, parent_tag, check_mode):
    """
    Ensure that a tag inheritance rule does not exist.

    :param session: Koji client session
    :param str child_tag: Koji tag name
    :param str parent_tag: Koji tag name
    :param bool check_mode: don't make any changes
    :return: result (dict)
    """
    result = {'changed': False, 'stdout_lines': []}
    current_inheritance = session.getInheritanceData(child_tag)
    found_rule = {}
    for rule in current_inheritance:
        if rule['name'] == parent_tag and rule['priority'] == priority:
            found_rule = rule.copy()
            # Mark this rule for deletion
            found_rule['delete link'] = True
    if not found_rule:
        return result
    result['stdout_lines'].append('remove inheritance link:')
    result['stdout_lines'].extend(
            common_koji.describe_inheritance_rule(found_rule))
    result['changed'] = True
    if not check_mode:
        common_koji.ensure_logged_in(session)
        session.setInheritanceData(child_tag, [found_rule])
    return result


def run_module():
    module_args = dict(
        koji=dict(type='str', required=False),
        child_tag=dict(type='str', required=True),
        parent_tag=dict(type='str', required=True),
        priority=dict(type='int', required=False),
        maxdepth=dict(type='int', required=False, default=None),
        pkg_filter=dict(type='str', required=False, default=''),
        intransitive=dict(type='bool', required=False, default=False),
        noconfig=dict(type='bool', required=False, default=False),
        state=dict(type='str', required=False, default='present'),
    )
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    if not common_koji.HAS_KOJI:
        module.fail_json(msg='koji is required for this module')

    check_mode = module.check_mode
    params = module.params
    state = params['state']
    profile = params['koji']

    session = common_koji.get_session(profile)

    if state == 'present':
        if 'priority' not in params:
            module.fail_json(msg='specify a "priority" integer')
        result = add_tag_inheritance(session,
                                     child_tag=params['child_tag'],
                                     parent_tag=params['parent_tag'],
                                     priority=params['priority'],
                                     maxdepth=params['maxdepth'],
                                     pkg_filter=params['pkg_filter'],
                                     intransitive=params['intransitive'],
                                     noconfig=params['noconfig'],
                                     check_mode=check_mode)
    elif state == 'absent':
        result = remove_tag_inheritance(session,
                                        child_tag=params['child_tag'],
                                        parent_tag=params['parent_tag'],
                                        check_mode=check_mode)
    else:
        module.fail_json(msg="State must be 'present' or 'absent'.",
                         changed=False, rc=1)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
