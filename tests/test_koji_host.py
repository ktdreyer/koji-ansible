import koji_host
import pytest
from koji import GenericError
from koji import USERTYPES, USER_STATUS
from utils import exit_json
from utils import fail_json
from utils import set_module_args
from utils import AnsibleExitJson
from utils import AnsibleFailJson


class FakeKojiSession(object):

    def __init__(self):
        self.hosts = {}
        self.host_channels = {}
        self.user_krb_principals = {}

    def addHost(self, hostname, arches, krb_principal=None, force=False):
        if hostname in self.hosts:
            raise GenericError('host already exists')
        host_id = len(self.hosts)
        # For accuracy, assume we have one human user in the "DB" already, and
        # this host will get the next "user" ID number. This should help flush
        # out any potential mistakes with regard to "id" versus "user_id" for
        # our host.
        user_id = len(self.hosts) + 1
        host = {
            'arches': ' '.join(arches),
            'capacity': 2.0,
            'comment': '',
            'description': '',
            'enabled': True,
            'id': host_id,
            'name': hostname,
            'ready': True,
            'task_load': 0.0,
            'user_id': user_id,
        }
        self.hosts[hostname] = host
        self.host_channels[hostname] = [{'id': 1, 'name': 'default'}]
        return host_id

    def getHost(self, hostInfo, strict=False):
        if isinstance(hostInfo, int):
            for host in self.hosts.values():
                if host['id'] == hostInfo:
                    return host
            if strict:
                raise GenericError('Host id %d not found' % hostInfo)
            return None
        if strict and hostInfo not in self.hosts:
            raise GenericError('Host %s not found' % hostInfo)
        return self.hosts.get(hostInfo)

    def getUser(self, userInfo=None, strict=False, krb_princs=True):
        # Find our host's user ID and username.
        user_id = None
        name = None
        if isinstance(userInfo, int):
            for host in self.hosts.values():
                if host['user_id'] == userInfo:
                    user_id = host['user_id']
                    name = host['name']
                    continue
            if not user_id:
                if strict:
                    raise GenericError('No such user: %s' % userInfo)
                return None
        elif userInfo in self.hosts:
            host = self.hosts[userInfo]
            user_id = host['user_id']
            name = host['name']
        else:
            if strict:
                raise GenericError('No such user: %s' % userInfo)
            return None
        krb_principals = self.user_krb_principals.get(user_id, [])
        return {
            'id': user_id,
            'krb_principals': krb_principals,
            'name': name,
            'status': USER_STATUS['NORMAL'],
            'usertype': USERTYPES['HOST'],
        }

    def editHost(self, hostInfo, **kw):
        host = self.getHost(hostInfo, strict=True)
        for parameter in kw:
            host[parameter] = kw[parameter]

    def enableHost(self, hostInfo, **kw):
        host = self.getHost(hostInfo, strict=True)
        host['enabled'] = True

    def disableHost(self, hostInfo, **kw):
        host = self.getHost(hostInfo, strict=True)
        host['enabled'] = False

    def listChannels(self, hostID):
        host = self.getHost(hostID, strict=True)
        hostname = host['name']
        return self.host_channels[hostname]

    def addHostToChannel(self, hostname, channel_name, create=False):
        if not create:
            raise NotImplementedError('must use create=True')
        host = self.getHost(hostname, strict=True)
        hostname = host['name']
        channels = self.host_channels[hostname]
        for channel in channels:
            if channel['name'] == channel_name:
                raise GenericError('host is already subscribed to channel')
        channel_id = len(channels) + 1
        channels.append({'id': channel_id, 'name': channel_name})

    def removeHostFromChannel(self, hostname, channel_name):
        host = self.getHost(hostname, strict=True)
        hostname = host['name']
        channels = self.host_channels[hostname]
        found = None
        for index in range(len(channels)):
            if channels[index]['name'] == channel_name:
                found = index
                break
        if found is None:
            raise GenericError('host is not subscribed to channel %s')
        del channels[found]

    def editUser(self, userInfo, name=None, krb_principal_mappings=None):
        user = self.getUser(userInfo, strict=True)
        user_id = user['id']
        if name is not None and name != user['name']:
            raise NotImplementedError('cannot rename users')
        if not krb_principal_mappings:
            return
        current = self.user_krb_principals.get(user_id, [])
        krb_to_add = set()
        krb_to_remove = set()
        for mapping in krb_principal_mappings:
            old = mapping['old']
            new = mapping['new']
            if old is None and new is None:
                raise ValueError('invalid mapping %s' % mapping)
            elif new is None:
                krb_to_remove.add(old)
            elif old is None:
                krb_to_add.add(new)
            else:
                # rename "old" to "new".
                krb_to_remove.add(old)
                krb_to_add.add(new)
        for principal in krb_to_remove:
            if principal not in current:
                raise GenericError('Cannot remove non-existent Kerberos'
                                   ' principals')
            self._removeKrbPrincipal(user['id'], krb_principal=principal)
        for principal in krb_to_add:
            if new in current:
                raise GenericError('Cannot add existing Kerberos'
                                   ' principals')
            self._setKrbPrincipal(user['id'], krb_principal=principal)

    def _removeKrbPrincipal(self, username, krb_principal):
        user = self.getUser(username, strict=True)
        user_id = user['id']
        self.user_krb_principals[user_id].remove(krb_principal)

    def _setKrbPrincipal(self, username, krb_principal):
        user = self.getUser(username, strict=True)
        user_id = user['id']
        if user_id not in self.user_krb_principals:
            self.user_krb_principals[user_id] = []
        if krb_principal not in self.user_krb_principals[user_id]:
            self.user_krb_principals[user_id].append(krb_principal)

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
        session.user_krb_principals[2] = ['compile/builder@EXAMPLE.COM']
        result = koji_host.ensure_host(session, 'builder', False, 'enabled',
                                       ['x86_64'],
                                       ['compile/builder@EXAMPLE.COM'],
                                       None)
        assert result['changed'] is False

    def test_state_disabled(self, session, builder):
        session.hosts['builder'] = builder
        session.hosts['builder']['enabled'] = False
        session.user_krb_principals[2] = ['compile/builder@EXAMPLE.COM']
        result = koji_host.ensure_host(session, 'builder', False, 'disabled',
                                       ['x86_64'],
                                       ['compile/builder@EXAMPLE.COM'],
                                       None)
        assert result['changed'] is False


class TestEnsureHostChanged(object):

    @pytest.fixture
    def session(self, session, builder):
        """ Pre-configure one builder for this session. """
        session.hosts['builder'] = builder
        session.host_channels['builder'] = [{'id': 1, 'name': 'default'}]
        return session

    def test_state_disabled(self, session):
        result = koji_host.ensure_host(session, 'builder', False, 'disabled',
                                       ['x86_64'], None, None)
        assert result['changed'] is True
        assert result['stdout_lines'] == ['disabled host']
        assert not session.hosts['builder']['enabled']

    def test_state_enabled(self, session):
        session.hosts['builder']['enabled'] = False
        result = koji_host.ensure_host(session, 'builder', False, 'enabled',
                                       ['x86_64'], None, None)
        assert result['changed'] is True
        assert result['stdout_lines'] == ['enabled host']
        assert session.hosts['builder']['enabled']

    def test_arches(self, session):
        result = koji_host.ensure_host(session, 'builder', False, 'enabled',
                                       ['i686', 'x86_64'], None, None)
        assert result['changed'] is True
        assert result['stdout_lines'] == ['edited host arches']
        assert session.hosts['builder']['arches'] == 'i686 x86_64'

    def test_comment(self, session):
        result = koji_host.ensure_host(session, 'builder', False, 'enabled',
                                       ['x86_64'], None, None,
                                       comment='my cool builder')
        assert result['changed'] is True
        assert result['stdout_lines'] == ['edited host comment']
        assert session.hosts['builder']['comment'] == 'my cool builder'

    def test_add_channel(self, session):
        new_channels = ['default', 'createrepo']
        result = koji_host.ensure_host(session, 'builder', False, 'enabled',
                                       ['x86_64'], None, new_channels)
        assert result['changed'] is True
        assert result['stdout_lines'] == ['added host to channel createrepo']
        expected_channels = [{'id': 1, 'name': 'default'},
                             {'id': 2, 'name': 'createrepo'}]
        assert session.host_channels['builder'] == expected_channels

    def test_remove_channel(self, session):
        new_channels = []
        result = koji_host.ensure_host(session, 'builder', False, 'enabled',
                                       ['x86_64'], None, new_channels)
        assert result['changed'] is True
        assert result['stdout_lines'] == ['removed host from channel default']
        assert session.host_channels['builder'] == []


class TestEnsureHostCreated(object):

    @pytest.mark.parametrize('check_mode', (True, False))
    def test_created(self, session, builder, check_mode):
        result = koji_host.ensure_host(session, 'builder', check_mode,
                                       'enabled', ['x86_64'], None, None)
        assert result['changed'] is True
        assert result['stdout_lines'] == ['created host']
        if check_mode:
            assert session.hosts == {}
        else:
            assert 'builder' in session.hosts


class TestMain(object):

    @pytest.fixture(autouse=True)
    def fake_exits(self, monkeypatch):
        monkeypatch.setattr(koji_host.AnsibleModule,
                            'exit_json', exit_json)
        monkeypatch.setattr(koji_host.AnsibleModule,
                            'fail_json', fail_json)

    @pytest.fixture(autouse=True)
    def fake_get_session(self, monkeypatch, session, builder):
        """ Pre-configure one builder for this session. """
        session.hosts['builder'] = builder
        session.host_channels['builder'] = [{'id': 1, 'name': 'default'}]
        monkeypatch.setattr(koji_host.common_koji,
                            'get_session',
                            lambda x: session)

    def test_simple(self):
        set_module_args({
            'name': 'builder2',
            'arches': ['x86_64'],
        })
        with pytest.raises(AnsibleExitJson) as exit:
            koji_host.main()
        result = exit.value.args[0]
        assert result['changed'] is True
        assert result['stdout_lines'] == ['created host']

    def test_disable(self):
        set_module_args({
            'name': 'builder',
            'arches': ['x86_64'],
            'state': 'disabled',
        })
        with pytest.raises(AnsibleExitJson) as exit:
            koji_host.main()
        result = exit.value.args[0]
        assert result['changed'] is True
        assert result['stdout_lines'] == ['disabled host']

    def test_missing_arches(self):
        set_module_args({
            'name': 'builder2',
        })
        with pytest.raises(AnsibleFailJson) as exit:
            koji_host.main()
        result = exit.value.args[0]
        assert result['msg'] == 'missing required arguments: arches'

    def test_kerberos_principal(self):
        set_module_args({
            'name': 'builder',
            'arches': ['x86_64'],
            'krb_principal': 'compile/builder.example.com@EXAMPLE.COM',
        })
        with pytest.raises(AnsibleExitJson) as exit:
            koji_host.main()
        result = exit.value.args[0]
        assert result['changed'] is True
        assert result['stdout_lines'] == [
            'add compile/builder.example.com@EXAMPLE.COM krb principal']

    def test_kerberos_principals(self):
        set_module_args({
            'name': 'builder',
            'arches': ['x86_64'],
            'krb_principals': ['compile/builder.example.com@EXAMPLE.COM'],
        })
        with pytest.raises(AnsibleExitJson) as exit:
            koji_host.main()
        result = exit.value.args[0]
        assert result['changed'] is True
        assert result['stdout_lines'] == [
            'add compile/builder.example.com@EXAMPLE.COM krb principal']
