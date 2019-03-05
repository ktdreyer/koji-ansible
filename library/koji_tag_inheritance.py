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
     required: true
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
    child_taginfo = session.getTag(child_tag, strict=True)
    parent_taginfo = session.getTag(parent_tag, strict=True)
    child_id = child_taginfo['id']
    parent_id = parent_taginfo['id']
    current_inheritance = session.getInheritanceData(child_id)
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


def generate_new_rule(child_id, parent_tag, parent_id, priority):
    """
    Return a full inheritance rule to add for this child tag.

    :param int child_id: Koji tag id
    :param str parent_tag: Koji tag name
    :param int parent_id: Koji tag id
    :param int priority: Priority of this parent for this child
    """
    return {
        'child_id': child_id,
        'intransitive': False,
        'maxdepth': None,
        'name': parent_tag,
        'noconfig': False,
        'parent_id': parent_id,
        'pkg_filter': '',
        'priority': priority}


def add_tag_inheritance(session, child_tag, parent_tag, priority, check_mode):
    """
    Ensure that a tag inheritance rule exists.

    :param session: Koji client session
    :param str child_tag: Koji tag name
    :param str parent_tag: Koji tag name
    :param int priority: Priority of this parent for this child
    :param bool check_mode: don't make any changes
    :return: result (dict)
    """
    result = {'changed': False}
    data = get_ids_and_inheritance(session, child_tag, parent_tag)
    child_id, parent_id, current_inheritance = data
    new_rule = generate_new_rule(child_id, parent_tag, parent_id, priority)
    new_rules = [new_rule]
    for rule in current_inheritance:
        if rule == new_rule:
            return result
        if rule['priority'] == priority:
            delete_rule = rule.copy()
            # Mark this rule for deletion
            delete_rule['delete link'] = True
            new_rules.insert(0, delete_rule)
    result['stdout'] = 'set parent %s (%d)' % (parent_tag, priority)
    result['changed'] = True
    if not check_mode:
        common_koji.ensure_logged_in(session)
        session.setInheritanceData(child_tag, new_rules)
    return result


def remove_tag_inheritance(session, child_tag, parent_tag, priority,
                           check_mode):
    """
    Ensure that a tag inheritance rule does not exist.

    :param session: Koji client session
    :param str child_tag: Koji tag name
    :param str parent_tag: Koji tag name
    :param int priority: Priority of this parent for this child
    :param bool check_mode: don't make any changes
    :return: result (dict)
    """
    result = {'changed': False}
    current_inheritance = session.getInheritanceData(child_tag)
    found_rule = {}
    for rule in current_inheritance:
        if rule['name'] == parent_tag and rule['priority'] == priority:
            found_rule = rule.copy()
            # Mark this rule for deletion
            found_rule['delete link'] = True
    if not found_rule:
        return result
    result['changed'] = True
    result['stdout'] = 'remove parent %s (%d)' % (parent_tag, priority)
    if not check_mode:
        common_koji.ensure_logged_in(session)
        session.setInheritanceData(child_tag, [found_rule])
    return result


def run_module():
    module_args = dict(
        koji=dict(type='str', required=False),
        child_tag=dict(type='str', required=True),
        parent_tag=dict(type='str', required=True),
        priority=dict(type='int', required=True),
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
        result = add_tag_inheritance(session,
                                     child_tag=params['child_tag'],
                                     parent_tag=params['parent_tag'],
                                     priority=params['priority'],
                                     check_mode=check_mode)
    elif state == 'absent':
        result = remove_tag_inheritance(session,
                                        child_tag=params['child_tag'],
                                        parent_tag=params['parent_tag'],
                                        priority=params['priority'],
                                        check_mode=check_mode)
    else:
        module.fail_json(msg="State must be 'present' or 'absent'.",
                         changed=False, rc=1)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
