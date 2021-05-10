from collections import defaultdict
from koji import USER_STATUS
import pytest
from koji_user import ensure_user


class GenericError(Exception):
    def __str__(self):
        return str(self.args[0])


class FakeKojiSession(object):
    def __init__(self):
        self.users = {}
        self.permissions = defaultdict(list)

    def getUser(self, userInfo=None, strict=False, krb_princs=True):
        if isinstance(userInfo, int):
            for user in self.users.values():
                if user['id'] == userInfo:
                    return user
            if strict:
                raise GenericError('No such user: %s' % userInfo)
            return None
        if userInfo not in self.users:
            if strict:
                raise GenericError('No such user: %s' % userInfo)
            return None
        return self.users[userInfo]

    def createUser(self, username, status=None, krb_principal=None):
        if username in self.users:
            raise GenericError('user already exists: %s' % username)
        id_ = len(self.users) + 1
        if krb_principal:
            krb_principals = [krb_principal]
        else:
            krb_principals = []
        self.users[username] = {'id': id_,
                                'krb_principals': krb_principals,
                                'name': username,
                                'status': USER_STATUS['NORMAL'],
                                'usertype': 0}
        return id_

    def editUser(self, userInfo, name=None, krb_principal_mappings=None):
        user = self.getUser(userInfo, strict=True)
        if name is not None and name != user['name']:
            raise NotImplementedError('cannot rename users')
        if not krb_principal_mappings:
            return
        current = user['krb_principals']
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
        user['krb_principals'].remove(krb_principal)

    def _setKrbPrincipal(self, username, krb_principal):
        user = self.getUser(username, strict=True)
        if krb_principal not in user['krb_principals']:
            user['krb_principals'].append(krb_principal)

    def enableUser(self, username):
        user = self.getUser(username, strict=True)
        user['status'] = USER_STATUS['NORMAL']

    def disableUser(self, username):
        user = self.getUser(username, strict=True)
        user['status'] = USER_STATUS['BLOCKED']

    def getUserPerms(self, userID):
        user = self.getUser(userID, strict=True)
        username = user['name']
        return self.permissions[username]

    def grantPermission(self, userinfo, permission, create=False):
        user = self.getUser(userinfo, strict=True)
        username = user['name']
        if not create:
            raise NotImplementedError('must force permission creation')
        if permission in self.permissions[username]:
            GenericError('User already has permission')
        self.permissions[username].append(permission)

    def revokePermission(self, userinfo, permission):
        user = self.getUser(userinfo, strict=True)
        username = user['name']
        if permission not in self.permissions[username]:
            GenericError('User does not have permission')
        self.permissions[username].remove(permission)

    def ensure_logged_in(self, session):
        return session

    def logged_in(self, session):
        return True


@pytest.fixture
def session():
    return FakeKojiSession()


class TestEnsureUser(object):
    @pytest.fixture
    def kwargs(self, session):
        return {
            'session': session,
            'name': 'kdreyer',
            'check_mode': False,
            'state': 'enabled',
            'permissions': [],
            'krb_principals': ['kdreyer@EXAMPLE.COM'],
        }

    @pytest.fixture
    def kdreyer(self):
        return {'id': 1,
                'krb_principals': ['kdreyer@EXAMPLE.COM'],
                'name': 'kdreyer',
                'status': USER_STATUS['NORMAL'],
                'usertype': 0}

    def test_create(self, kwargs, kdreyer):
        session = kwargs['session']
        result = ensure_user(**kwargs)
        assert result == {'changed': True,
                          'stdout_lines': ['created kdreyer user']}
        assert session.users['kdreyer'] == kdreyer

    def test_unchanged(self, kwargs, kdreyer):
        session = kwargs['session']
        session.users['kdreyer'] = kdreyer
        result = ensure_user(**kwargs)
        assert result == {'changed': False, 'stdout_lines': []}
        assert session.users['kdreyer'] == kdreyer

    def test_disable_user(self, kwargs, kdreyer):
        session = kwargs['session']
        session.users['kdreyer'] = kdreyer
        kwargs['state'] = 'disabled'
        result = ensure_user(**kwargs)
        assert result == {'changed': True,
                          'stdout_lines': ['disabled kdreyer user']}
        assert session.users['kdreyer']['status'] == USER_STATUS['BLOCKED']

    def test_enable_user(self, kwargs, kdreyer):
        session = kwargs['session']
        session.users['kdreyer'] = kdreyer
        session.users['kdreyer']['status'] = USER_STATUS['BLOCKED'],
        result = ensure_user(**kwargs)
        assert result == {'changed': True,
                          'stdout_lines': ['enabled kdreyer user']}
        assert session.users['kdreyer']['status'] == USER_STATUS['NORMAL']

    def test_add_permission(self, kwargs, kdreyer):
        session = kwargs['session']
        session.users['kdreyer'] = kdreyer
        kwargs['permissions'] = ['admin']
        result = ensure_user(**kwargs)
        assert result == {'changed': True,
                          'stdout_lines': ['grant admin']}
        assert session.permissions['kdreyer'] == ['admin']

    def test_add_and_remove_permissions(self, kwargs, kdreyer):
        session = kwargs['session']
        session.users['kdreyer'] = kdreyer
        session.permissions['kdreyer'] = ['admin']
        kwargs['permissions'] = ['ceph']
        result = ensure_user(**kwargs)
        assert result == {'changed': True,
                          'stdout_lines': ['grant ceph', 'revoke admin']}
        assert session.permissions['kdreyer'] == ['ceph']

    def test_remove_all_permissions(self, kwargs, kdreyer):
        session = kwargs['session']
        session.users['kdreyer'] = kdreyer
        session.permissions['kdreyer'] = ['admin']
        result = ensure_user(**kwargs)
        assert result == {'changed': True,
                          'stdout_lines': ['revoke admin']}
        assert session.permissions['kdreyer'] == []

    def test_add_krb_principal(self, kwargs, kdreyer):
        session = kwargs['session']
        session.users['kdreyer'] = kdreyer
        kwargs['krb_principals'] = ['kdreyer@EXAMPLE.COM',
                                    'kdreyer@FOO.EXAMPLE.COM']
        result = ensure_user(**kwargs)
        expected_line = 'add kdreyer@FOO.EXAMPLE.COM krb principal'
        assert result == {'changed': True, 'stdout_lines': [expected_line]}
        result_princs = session.users['kdreyer']['krb_principals']
        expected_princs = ['kdreyer@EXAMPLE.COM', 'kdreyer@FOO.EXAMPLE.COM']
        assert set(result_princs) == set(expected_princs)

    def test_remove_krb_principal(self, kwargs, kdreyer):
        session = kwargs['session']
        session.users['kdreyer'] = kdreyer
        kwargs['krb_principals'] = []
        result = ensure_user(**kwargs)
        expected_line = 'remove kdreyer@EXAMPLE.COM krb principal'
        assert result == {'changed': True, 'stdout_lines': [expected_line]}
        result_princs = session.users['kdreyer']['krb_principals']
        assert set(result_princs) == set()
