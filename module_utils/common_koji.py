# -*- coding: utf-8 -*-
import os
import copy
try:
    import koji
    from koji_cli.lib import activate_session
    HAS_KOJI = True
except ImportError:
    HAS_KOJI = False


def get_profile_name(profile):
    """
    Return a koji profile name.

    :param str profile: profile name, like "koji" or "cbs", or None. If None,
                        we will use return the "KOJI_PROFILE" environment
                        variable. If we could find no profile name, raise
                        ValueError.
    :returns: str, the profile name
    """
    if profile:
        return profile
    profile = os.getenv('KOJI_PROFILE')
    if profile:
        return profile
    raise ValueError('set a profile "koji" argument for this task, or set '
                     'the KOJI_PROFILE environment variable')


def get_session(profile):
    """
    Return an anonymous koji session for this profile name.

    :param str profile: profile name, like "koji" or "cbs". If None, we will
                        use a profile name from the "KOJI_PROFILE" environment
                        variable.
    :returns: anonymous koji.ClientSession
    """
    profile = get_profile_name(profile)
    # Note, get_profile_module() raises koji.ConfigurationError if we
    # could not find this profile's name in /etc/koji.conf.d/*.conf and
    # ~/.koji/config.d/*.conf.
    mykoji = koji.get_profile_module(profile)
    # Workaround https://pagure.io/koji/issue/1022 . Koji 1.17 will not need
    # this.
    if '~' in str(mykoji.config.cert):
        mykoji.config.cert = os.path.expanduser(mykoji.config.cert)
    # Note, Koji has a grab_session_options() method that can also create a
    # stripped-down dict of our module's (OptParse) configuration, like:
    #   opts = mykoji.grab_session_options(mykoji.config)
    # The idea is that callers then pass that opts dict into ClientSession's
    # constructor.
    # There are two reasons we don't use that here:
    # 1. The dict is only suitable for the ClientSession(..., opts), not for
    #    activate_session(..., opts). activate_session() really wants the full
    #    set of key/values in mykoji.config.
    # 2. We may call activate_session() later outside of this method, so we
    #    need to preserve all the configuration data from mykoji.config inside
    #    the ClientSession object. We might as well just store it in the
    #    ClientSession's .opts and then pass that into activate_session().
    opts = vars(mykoji.config)
    # Force an anonymous session (noauth):
    opts['noauth'] = True
    session = mykoji.ClientSession(mykoji.config.server, opts)
    # activate_session with noauth will simply ensure that we can connect with
    # a getAPIVersion RPC. Let's avoid it here because it just slows us down.
    # activate_session(session, opts)
    return session


def ensure_logged_in(session):
    """
    Authenticate this Koji session (if necessary).

    :param session: a koji.ClientSession
    :returns: None
    """
    if not session.logged_in:
        session.opts['noauth'] = False
        # Log in ("activate") this session:
        # Note: this can raise SystemExit if there is a problem, eg with
        # Kerberos:
        activate_session(session, session.opts)


# inheritance display utils


def describe_inheritance_rule(rule):
    """
    Given a dictionary representing a koji inheritance rule (i.e., one of the
    elements of getInheritanceData()'s result), return a tuple of strings to be
    appended to a module's stdout_lines array conforming to the output of
    koji's taginfo CLI command, e.g.:
       0   .... a-parent-tag
      10   M... another-parent-tag
        maxdepth: 1
     100   .F.. yet-another-parent-tag
        package filter: ^prefix-
    """
    # koji_cli/commands.py near the end of anon_handle_taginfo()
    flags = '%s%s%s%s' % (
        'M' if rule['maxdepth'] not in ('', None) else '.',
        'F' if rule['pkg_filter'] not in ('', None) else '.',
        'I' if rule['intransitive'] else '.',
        'N' if rule['noconfig'] else '.',
    )

    result = ["%4d   %s %s" % (rule['priority'], flags, rule['name'])]

    if rule['maxdepth'] not in ('', None):
        result.append("    maxdepth: %d" % rule['maxdepth'])
    if rule['pkg_filter'] not in ('', None):
        result.append("    package filter: %s" % rule['pkg_filter'])

    return tuple(result)


def describe_inheritance(rules):
    """
    Given a sequence of dictionaries representing koji inheritance rules (i.e.,
    getInheritanceData()'s result), return a tuple of strings to be appended to
    a module's stdout_lines array conforming to the output of koji's taginfo
    CLI command. See describe_inheritance_rule for sample output.
    """

    # each invocation of describe_inheritance_rule yields a tuple of strings
    # to be appended to a module's stdout_lines result, so concatenate them:
    # sum(…, tuple()) will flatten tuples of tuples into just the child tuples
    # > sum( ((1, 2), (3, 4)), tuple() ) ⇒ (1, 2) + (3, 4) + (,) ⇒ (1, 2, 3, 4)
    return sum(tuple(map(describe_inheritance_rule, rules)), tuple())


# permission utils


perm_cache = {}


def get_perms(session):
    global perm_cache
    if not perm_cache:
        perm_cache = dict([
            (perm['name'], perm['id']) for perm in session.getAllPerms()
        ])
    return perm_cache


def get_perm_id(session, name):
    perms = get_perms(session)
    return perms[name]


def get_perm_name(session, id_):
    perms = get_perms(session)
    for perm_name, perm_id in perms.items():
        if perm_id == id_:
            return perm_name


def ensure_krb_principals(session, user, check_mode, krb_principals):
    """
    Ensure that a user or host has a list of Kerberos principals.

    This method adds or removes Kerberos principals on a user or host.
    The Koji Hub must be running Koji v1.19 or greater.

    :param session: Koji client session
    :param dict user: Koji "user" (person or host) information, from the
                      getUser RPC.
    :param bool check_mode: don't make any changes
    :param list krb_principals: list of desired Kerberos principals for this
                                user or host.
    :returns: a possibly-empty list of human-readable changes
    """
    current_principals = user['krb_principals']
    to_add = set(krb_principals) - set(current_principals)
    to_remove = set(current_principals) - set(krb_principals)
    changes = []
    mappings = []  # list of dicts
    for principal in to_add:
        changes.append('add %s krb principal' % principal)
        mappings.append({'old': None, 'new': principal})
    for principal in to_remove:
        changes.append('remove %s krb principal' % principal)
        mappings.append({'old': principal, 'new': None})
    if changes and not check_mode:
        ensure_logged_in(session)
        session.editUser(user['id'], krb_principal_mappings=mappings)
    return changes


def task_diff_data(before, after, item_name, item_type,
                   keys_to_copy=[], keys_to_omit=[]):
    """
    Prepare a dict suitable for use as the value of the 'diff' key in
    the dict returned by an ansible task.

    """
    if before is None:
        # Creating a new item
        before_header = "Not present"
        after_header = "New %s '%s'" % (item_type, item_name)

        # Need to use an empty dict instead of None otherwise
        # ansible's built-in diff callback will throw errors
        # trying to call splitlines() on it
        before = {}

    elif after is None:
        # Deleting an item
        before_header = "%s '%s'" % (item_type, item_name)
        after_header = "Not present"

        # Need to use an empty dict instead of None otherwise
        # ansible's built-in diff callback will throw errors
        # trying to call splitlines() on it
        after = {}

    else:
        # Modifying an existing item
        before_header = "Original %s '%s'" % (item_type, item_name)
        after_header = "Modified %s '%s'" % (item_type, item_name)

        # Don't accidentally modify the method params
        after = copy.copy(after)
        before = copy.copy(before)

        # Avoid misleading diffs by copying some values from the
        # before dict to the after dict
        for key in keys_to_copy:
            if key in before and key not in after:
                after[key] = before[key]

        # Skip some keys if they're not useful
        for key in keys_to_omit + ['id']:
            if key in before and key not in after:
                del before[key]

    return {
        'before': before,
        'after': after,
        'before_header': before_header,
        'after_header': after_header,
    }


def clean_data(obj_list, keys_to_copy=[], keys_to_omit=[]):
    """
    Clean a list of objects with needed fields by defining
    keys_to_copy or keys_to_omit.

    :param list obj_list: a list of object
    :param keys_to_copy: the field list which will be returned
    :params keys_to_omit: the field list which will be omitted
    :returns: a list of objects with needed fields
    """
    if keys_to_copy:
        new_obj_list = []
        for obj in obj_list:
            new_obj = {}
            for key in keys_to_copy:
                if key in obj.keys():
                    new_obj.update({key: obj[key]})
            new_obj_list.append(new_obj)
        return new_obj_list
    else:
        for obj in obj_list:
            new_obj = {}
            for key in keys_to_omit:
                if key in obj.keys():
                    del new_obj[key]
        return obj_list


def combine_diff_data(item_type, item_name, result1, result2):
    """
    Combine the diff date in result1 and result2

    :param string the of the tag to combine the diff data
    :param dict result1
    :param dict result2
    """
    if not result1.get('diff'):
        result1['diff'] = {
            'before_header': "Original %s '%s'" % (item_type, item_name),
            'after_header': "Modified %s '%s'" % (item_type, item_name),
            'before': {item_type: item_name},
            'after': {item_type: item_name},
        }
    result1['diff']['before'].update(result2['diff']['before'])
    result1['diff']['after'].update(result2['diff']['after'])

    return result1['diff']
