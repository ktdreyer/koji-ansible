import os
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
    if '~' in str(mykoji.config.ca):
        mykoji.config.ca = os.path.expanduser(mykoji.config.ca)
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
