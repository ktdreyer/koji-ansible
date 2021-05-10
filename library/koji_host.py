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
module: koji_host

short_description: Create and manage Koji build hosts
description:
   - This module can add new hosts and manage existing hosts.
   - 'Koji only supports adding new hosts, not deleting them. Once they are
     defined, you can enable or disable the hosts with "state: enabled" or
     "state: disabled".'

options:
   name:
     description:
       - The name of the Koji builder.
       - 'Example: "builder1.example.com".'
     required: true
   arches:
     description:
       - The list of arches this host supports.
       - 'Example: [x86_64]'
     required: true
   channels:
     description:
       - The list of channels this host should belong to.
       - If you specify a completely new channel here, Ansible will create the
         channel on the hub. For example, when you set up OSBS with Koji, you
         must add a builder host to a new "container" channel. You can simply
         specify "container" in the list here, and Ansible will create the new
         "container" channel when it adds your host to that channel.
       - 'Example: [default, createrepo]'
     required: false
   state:
     description:
       - Whether to set this host as "enabled" or "disabled". If unset, this
         defaults to "enabled".
   krb_principal:
     description:
       - Set a single non-default krb principal for this host. If unset, Koji
         will use the standard krb principal scheme for builder accounts.
       - Mutually exclusive with I(krb_principals).
   krb_principals:
     description:
       - Set a list of non-default krb principals for this host. If unset,
         Koji will use the standard krb principal scheme for builder accounts.
         Your Koji Hub must be v1.19 or later to use this option.
       - Mutually exclusive with I(krb_principal).
   capacity:
     description:
       - Total task weight for this host. This is a float value. If unset,
         Koji will use the standard capacity for a host (2.0).
       - 'Example: 10.0'
   description:
     description:
       - Human-readable description for this host.
   comment:
     description:
       - Human-readable comment explaining the current state of the host. You
         may write a description here explaining how this host was set up, or
         why this host is currently offline.
requirements:
  - "python >= 2.7"
  - "koji"
'''

EXAMPLES = '''
- name: create a koji host
  hosts: localhost
  tasks:
    - name: Add new builder1 host
      koji_host:
        name: builder1.example.com
        arches: [x86_64]
        state: enabled
        channels:
          - createrepo
          - default

    - name: Add new builder host for OSBS
      koji_host:
        name: containerbuild1.example.com
        arches: [x86_64]
        state: enabled
        channels:
          # This will automatically create the "container" channel
          # if it does not already exist:
          - container
'''


def ensure_channels(session, host_id, host_name, check_mode, desired_channels):
    """
    Ensure that given host belongs to given channels (and only them).

    :param session: Koji client session
    :param int host_id: Koji host ID
    :param str host_name: Koji host name
    :param bool check_mode: don't make any changes
    :param list desired_channels: channels that the host should belong to
    """
    result = {'changed': False, 'stdout_lines': []}
    common_koji.ensure_logged_in(session)
    current_channels = session.listChannels(host_id)
    current_channels = [channel['name'] for channel in current_channels]
    for channel in current_channels:
        if channel not in desired_channels:
            if not check_mode:
                session.removeHostFromChannel(host_name, channel)
            result['stdout_lines'].append('removed host from channel %s' % channel)
            result['changed'] = True
    for channel in desired_channels:
        if channel not in current_channels:
            if not check_mode:
                session.addHostToChannel(host_name, channel, create=True)
            result['stdout_lines'].append('added host to channel %s' % channel)
            result['changed'] = True
    return result


def ensure_host(session, name, check_mode, state, arches, krb_principals,
                channels, **kwargs):
    """
    Ensure that this host is configured in Koji.

    :param session: Koji client session
    :param str name: Koji builder host name
    :param bool check_mode: don't make any changes
    :param str state: "enabled" or "disabled"
    :param list arches: list of arches for this builder.
    :param list krb_principals: custom kerberos principals, or None
    :param list chanels: list of channels this host should belong to.
    :param **kwargs: Pass remaining kwargs directly into Koji's editHost RPC.
    """
    result = {'changed': False, 'stdout_lines': []}
    host = session.getHost(name)
    if not host:
        result['changed'] = True
        result['stdout_lines'].append('created host')
        if check_mode:
            return result
        common_koji.ensure_logged_in(session)
        krb_principal = krb_principals[0] if krb_principals else None
        id_ = session.addHost(name, arches, krb_principal)
        host = session.getHost(id_)
    if state == 'enabled':
        if not host['enabled']:
            result['changed'] = True
            result['stdout_lines'].append('enabled host')
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.enableHost(name)
    elif state == 'disabled':
        if host['enabled']:
            result['changed'] = True
            result['stdout_lines'].append('disabled host')
            if not check_mode:
                common_koji.ensure_logged_in(session)
                session.disableHost(name)
    edits = {}
    if ' '.join(arches) != host['arches']:
        edits['arches'] = ' '.join(arches)
    for key, value in kwargs.items():
        if value is None:
            continue  # Ansible did not set this parameter.
        if key in host and kwargs[key] != host[key]:
            edits[key] = value
    if edits:
        result['changed'] = True
        for edit in edits.keys():
            result['stdout_lines'].append('edited host %s' % edit)
        if not check_mode:
            common_koji.ensure_logged_in(session)
            session.editHost(name, **edits)

    # Ensure host is member of desired channels.
    if channels not in (None, ''):
        channels_result = ensure_channels(session, host['id'],
                                          name, check_mode, channels)
        if channels_result['changed']:
            result['changed'] = True
        result['stdout_lines'].extend(channels_result['stdout_lines'])

    if krb_principals is not None:
        user = session.getUser(host['user_id'])
        changes = common_koji.ensure_krb_principals(
            session, user, check_mode, krb_principals)
        if changes:
            result['changed'] = True
            result['stdout_lines'].extend(changes)

    return result


def run_module():
    module_args = dict(
        koji=dict(),
        name=dict(required=True),
        arches=dict(type='list', required=True),
        channels=dict(type='list'),
        krb_principal=dict(),
        krb_principals=dict(type='list', elements='str'),
        capacity=dict(type='float'),
        description=dict(),
        comment=dict(),
        state=dict(choices=['enabled', 'disabled'], default='enabled'),
    )
    module = AnsibleModule(
        argument_spec=module_args,
        mutually_exclusive=[('krb_principal', 'krb_principals')],
        supports_check_mode=True
    )

    if not common_koji.HAS_KOJI:
        module.fail_json(msg='koji is required for this module')

    check_mode = module.check_mode
    params = module.params
    profile = params['koji']
    name = params['name']
    state = params['state']
    if params['krb_principals'] is not None:
        krb_principals = params['krb_principals']
    elif params['krb_principal'] is not None:
        krb_principals = [params['krb_principal']]
    else:
        krb_principals = None

    session = common_koji.get_session(profile)

    result = ensure_host(session, name, check_mode, state,
                         arches=params['arches'],
                         channels=params['channels'],
                         krb_principals=krb_principals,
                         capacity=params['capacity'],
                         description=params['description'],
                         comment=params['comment'])
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
