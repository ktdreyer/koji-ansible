import koji_host


class FakeKojiSession(object):

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def getHost(self, name):
        return self._getHost

    def ensure_logged_in(self, session):
        return self._session

    def logged_in(self, session):
        return True


class TestEnsureHostUnchanged(object):

    def test_state_enabled(self):
        session = FakeKojiSession(_getHost={'enabled': True, 'arches': ''})
        result = koji_host.ensure_host(session, 'builder', False, 'enabled',
                                       [], None, None)
        assert result['changed'] is False

    def test_state_disabled(self):
        session = FakeKojiSession(_getHost={'enabled': False, 'arches': ''})
        result = koji_host.ensure_host(session, 'builder', False, 'disabled',
                                       [], None, None)
        assert result['changed'] is False
