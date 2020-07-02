import koji_host
import pytest


class FakeKojiSession(object):

    def __init__(self):
        self.hosts = {}

    def getHost(self, hostInfo, strict=False):
        if isinstance(hostInfo, int):
            raise NotImplementedError('specify a hostname')
        return self.hosts.get(hostInfo)

    def ensure_logged_in(self, session):
        return self._session

    def logged_in(self, session):
        return True


@pytest.fixture
def session():
    return FakeKojiSession()


@pytest.fixture
def builder():
    return {
        'arches': 'x86_64',
        'capacity': 20.0,
        'comment': 'my builder host',
        'description': '',
        'enabled': True,
        'id': 1,
        'name': 'builder',
        'ready': True,
        'task_load': 0.0,
        'user_id': 2,
    }


class TestEnsureHostUnchanged(object):

    def test_state_enabled(self, session, builder):
        session.hosts['builder'] = builder
        result = koji_host.ensure_host(session, 'builder', False, 'enabled',
                                       ['x86_64'], None, None)
        assert result['changed'] is False

    def test_state_disabled(self, session, builder):
        session.hosts['builder'] = builder
        session.hosts['builder']['enabled'] = False
        result = koji_host.ensure_host(session, 'builder', False, 'disabled',
                                       ['x86_64'], None, None)
        assert result['changed'] is False
