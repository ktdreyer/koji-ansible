#!/usr/bin/python

try:
    import koji
    from koji_cli.lib import activate_session
    HAS_KOJI = True
except ImportError:
    HAS_KOJI = False


def get_session(profile):
    """
    Return an anonymous koji session for this profile name.
    :param str profile: profile name, like "koji" or "cbs"
    :returns: anonymous koji.ClientSession
    """
    # Note: this raises koji.ConfigurationError if we could not find this
    # profile name.
    # (ie. "check /etc/koji.conf.d/*.conf")
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
