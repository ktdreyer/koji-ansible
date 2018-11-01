#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
import common_koji


ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
---
module: koji_tag

short_description: Create and manage Koji tags
'''


def ensure_tag(session, name, inheritance, **kwargs):
    """
    Ensure that this tag exists in Koji.

    :param session: Koji client session
    :param name: Koji tag name
    :param inheritance: Koji tag inheritance settings. These will be translated
                        for Koji's setInheritanceData RPC.
    :param **kwargs: Pass remaining kwargs directly into Koji's createTag and
                     editTag2 RPCs.
    """
    taginfo = session.getTag(name)
    # fixme: we're clobbering 'stdout' here every time we make a change. maybe
    # use 'stdout_lines' instead or something.
    result = {'changed': False}
    if not taginfo:
        common_koji.ensure_logged_in(session)
        id_ = session.createTag(name, parent=None, **kwargs)
        result['stdout'] = 'created tag id %d' % id_
        result['changed'] = True
        taginfo['id'] = id_  # populate for inheritance management below
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
            common_koji.ensure_logged_in(session)
            session.editTag2(name, **edits)
            result['stdout'] = str(edits)
            result['changed'] = True
    # Ensure inheritance rules are all set.
    rules = []
    for rule in inheritance:
        parent_name = rule['parent']
        parent_taginfo = session.getTag(parent_name)
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
        common_koji.ensure_logged_in(session)
        session.setInheritanceData(name, rules, clear=True)
        result['stdout'] = 'inheritance is %s' % inheritance
        result['changed'] = True
    return result


def delete_tag(session, name):
    """ Ensure that this tag is deleted from Koji. """
    taginfo = session.getTag(name)
    result = dict(
        stdout='',
        changed=False,
    )
    if taginfo:
        common_koji.ensure_logged_in(session)
        session.deleteTag(name)
        result['stdout'] = 'deleted tag %d' % taginfo['id']
        result['changed'] = True
    return result


def run_module():
    module_args = dict(
        koji=dict(type='str', required=False, default='koji'),
        name=dict(type='str', required=True),
        state=dict(type='str', required=True),
        inheritance=dict(type='list', required=False, default=[]),
        arches=dict(type='str', required=False, default=None),
        perm=dict(type='list', required=False, default=None),
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

    params = module.params
    profile = params['koji']
    name = params['name']
    state = params['state']

    session = common_koji.get_session(profile)

    if state == 'present':
        result = ensure_tag(session, name,
                            inheritance=params['inheritance'],
                            arches=params['arches'],
                            perm=params['perm'],
                            locked=params['locked'],
                            maven_support=params['maven_support'],
                            maven_include_all=params['maven_include_all'],
                            extra=params['extra'])
    elif state == 'absent':
        result = delete_tag(session, name)
    else:
        module.fail_json(msg="State must be 'present' or 'absent'.",
                         changed=False, rc=1)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
