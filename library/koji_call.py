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
module: koji_call

short_description: Make low-level Koji API calls
description:
   - Call Koji's RPC API directly.
   - Why would you use this module instead of the higher level modules like
     koji_tag, koji_target, etc? This koji_call module has two main
     uses-cases.
   - 1. You may want to do something that the higher level modules do not yet
     support. It can be easier to use this module to quickly prototype out
     your ideas for what actions you need, and then write the Python code to
     do it in a better way later. If you find that you need to use koji_call
     to achieve functionality that is not yet present in the other
     koji-ansible modules, please file a Feature Request issue in GitHub with
     your use case.
   - 2. You want to write some tests that verify Koji's data at a very low
     level. For example, you may want to write an integration test to verify
     that you've set up your Koji configuration in the way you expect.
   - 'Note that this module will always report "changed: true" every time,
     because it simply sends the RPC to the Koji Hub on every ansible run.
     This module cannot understand if your chosen RPC actually "changes"
     anything.'
options:
   name:
     description:
       - The name of the Koji RPC to send.
       - 'Example: "getTag"'
     required: true
   args:
     description:
       - The list or dict of arguments to pass into the call.
       - 'Example: ["f29-build"]'
     required: false
   login:
     description:
       - Whether to authenticate to Koji for this API call or not.
         Authentication is an extra round-trip to the Hub, so it slower and
         more load on the database. You should not authenticate if this call
         is read-only (one of the "get" API calls). If you are doing some
         create or write operation, you must authenticate. The default
         behavior is to do an anonymous (non-authenticated) call.
     choices: [true, false]
     default: false
requirements:
  - "python >= 2.7"
  - "koji"
'''

RETURNS = '''
data:
  description: Koji's representation of the call result
  returned: always
  type: various, depending on the call. Koji could return a dict, or int, or
        None.
  sample: {'...'}
'''

EXAMPLES = '''
- name: call the Koji API
  hosts: localhost
  tasks:

    - name: call the API
      koji_call:
        name: getTag
        args: [f29-build]
      register: call_result

    - debug:
        var: call_result.data
'''


def describe_call(name, args):
    """ Return a human-friendly description of this call. """
    description = '%s()' % name
    if args:
        if isinstance(args, dict):
            description = '%s(**%s)' % (name, args)
        elif isinstance(args, list):
            description = '%s(*%s)' % (name, args)
    return description


def check_mode_call(name, args):
    """
    Describe what would have happened if we executed a Koji RPC.
    """
    result = {'changed': True}
    description = describe_call(name, args)
    result['stdout_lines'] = 'would have called %s' % description
    return result


def do_call(session, name, args, login):
    """
    Execute a Koji RPC.

    :param session: Koji client session
    :param str name: Name of the RPC
    :param args: list or dict of arguments to this RPC.
    :param bool login: Whether to log in for this call or not.
    """
    result = {'changed': True}
    if login:
        common_koji.ensure_logged_in(session)
    call = getattr(session, name)
    if isinstance(args, dict):
        data = call(**args)
    else:
        data = call(*args)
    result['data'] = data
    return result


def run_module():
    module_args = dict(
        koji=dict(type='str', required=False),
        name=dict(type='str', required=True),
        args=dict(type='raw', required=False, default=[]),
        login=dict(type='bool', required=False, default=False),
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
    args = params['args']
    login = params['login']

    if args and not isinstance(args, (dict, list)):
        msg = "args must be a list or dictionary, not %s" % type(args)
        module.fail_json(msg=msg, changed=False, rc=1)

    session = common_koji.get_session(profile)

    if module.check_mode:
        result = check_mode_call(name, args)
    else:
        result = do_call(session, name, args, login)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
