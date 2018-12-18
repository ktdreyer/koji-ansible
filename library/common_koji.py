#!/usr/bin/python

import os
from ansible.error import AnsibleError
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
                        AnsibleError.
    :returns: anonymous koji.ClientSession
    """
    if profile:
        return profile
    profile = os.getenv('KOJI_PROFILE')
    if profile:
        return profile
    raise AnsibleError('set a profile "koji" argument for this task, or set '
                       'the KOJI_PROFILE environment variable')


def get_session(profile):
    """
    Return an anonymous koji session for this profile name.

    :param str profile: profile name, like "koji" or "cbs". If None, we will
                        use a profile name from the "KOJI_PROFILE" environment
                        variable.
    :returns: anonymous koji.ClientSession
    """
    # Note: this raises koji.ConfigurationError if we could not find this
    # profile name.
    # (ie. "check /etc/koji.conf.d/*.conf")
    profile = get_profile_name(profile)
    conf = koji.read_config(profile)
    hub = conf['server']
    # TODO: support SSL auth?
    opts = {'krbservice': conf.get('krbservice')}
    session = koji.ClientSession(hub, opts)
    # KojiOptions = namedtuple('Options', ['authtype', 'debug'])
    # options = KojiOptions(authtype='')
    activate_session(session, conf)
    return session


def ensure_logged_in(session):
    """
    Authenticate (if necessary) and return this Koji session.
    :param session: a koji.ClientSession
    :returns: a koji.ClientSession
    """
    if not session.logged_in:
        # XXX hardcoding krb here
        session.krb_login()
    return session
