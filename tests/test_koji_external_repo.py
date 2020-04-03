import pytest
import koji_external_repo
from koji_external_repo import ensure_external_repo
from koji_external_repo import delete_external_repo
from utils import exit_json
from utils import fail_json
from utils import set_module_args
from utils import AnsibleExitJson
from utils import AnsibleFailJson


class GenericError(Exception):
    def __str__(self):
        return str(self.args[0])


class FakeSession(object):
    def __init__(self):
        self.repos = {}

    def getExternalRepo(self, info, strict=False, event=None):
        if isinstance(info, int):
            for repo in self.repos.values():
                if repo['id'] == info:
                    return repo
            if strict:
                raise GenericError('Invalid repo info: %s' % info)
            return None
        if info not in self.repos:
            if strict:
                raise GenericError('Invalid repo info: %s' % info)
            return None
        return self.repos[info]

    def createExternalRepo(self, name, url):
        if name in self.repos:
            raise GenericError('An external repo named "%s" already exists' %
                               name)
        id_ = len(self.repos) + 1
        self.repos[name] = {'id': id_, 'name': name, 'url': url}
        return self.repos[name]

    def editExternalRepo(self, info, name=None, url=None):
        if name is not None:
            raise NotImplementedError('cannot rename repos')
        repo = self.getExternalRepo(info, strict=True)
        name = repo['name']
        self.repos[name]['url'] = url

    def deleteExternalRepo(self, info):
        repo = self.getExternalRepo(info, strict=True)
        name = repo['name']
        del self.repos[name]

    def ensure_logged_in(self, session):
        return session

    def logged_in(self, session):
        return True


@pytest.fixture
def session():
    return FakeSession()


class TestEnsureExternalRepo(object):

    @pytest.fixture
    def kwargs(self, session):
        return {
            'session': session,
            'name': 'centos-7-cr',
            'check_mode': False,
            'url': 'http://mirror.centos.org/centos/7/cr/x86_64/',
        }

    def test_create(self, session, kwargs):
        result = ensure_external_repo(**kwargs)
        assert result['stdout_lines'] == ['created repo id 1']
        assert result['changed'] is True

    def test_change_url(self, session, kwargs):
        ensure_external_repo(**kwargs)
        new_kwargs = kwargs.copy()
        new_kwargs['url'] = 'http://new.example.com/'
        result = ensure_external_repo(**new_kwargs)
        assert result['stdout_lines'] == ['set url to http://new.example.com/']
        assert result['changed'] is True

    def test_no_change(self, session, kwargs):
        ensure_external_repo(**kwargs)
        result = ensure_external_repo(**kwargs)
        assert result['stdout_lines'] == []
        assert result['changed'] is False

    def test_create_check_mode(self, session, kwargs):
        new_kwargs = kwargs.copy()
        new_kwargs['check_mode'] = True
        result = ensure_external_repo(**new_kwargs)
        assert result['stdout_lines'] == ['would create repo centos-7-cr']
        assert result['changed'] is True


class TestDeleteExternalRepo(object):

    @pytest.fixture
    def repos(self):
        return {'centos-7-cr': {'id': 1, 'name': 'centos-7-cr',
                'url': 'http://centos.example.com/7/cr/x86_64/'}}

    def test_delete(self, session, repos):
        session.repos = repos
        result = delete_external_repo(session, 'centos-7-cr', False)
        assert session.repos == {}
        assert result['stdout'] == 'deleted external repo centos-7-cr'
        assert result['changed'] is True

    def test_delete_check_mode(self, session, repos):
        session.repos = repos
        result = delete_external_repo(session, 'centos-7-cr', True)
        assert session.repos
        assert session.repos == repos
        assert result['stdout'] == 'deleted external repo centos-7-cr'
        assert result['changed'] is True


class TestMain(object):

    @pytest.fixture(autouse=True)
    def fake_exits(self, monkeypatch):
        monkeypatch.setattr(koji_external_repo.AnsibleModule,
                            'exit_json', exit_json)
        monkeypatch.setattr(koji_external_repo.AnsibleModule,
                            'fail_json', fail_json)

    @pytest.fixture(autouse=True)
    def fake_get_session(self, monkeypatch, session):
        repos = {'centos-7-cr': {'id': 1, 'name': 'centos-7-cr',
                 'url': 'http://centos.example.com/7/cr/x86_64/'}}
        session.repos = repos
        monkeypatch.setattr(koji_external_repo.common_koji,
                            'get_session',
                            lambda x: session)

    def test_simple(self):
        set_module_args({
            'name': 'fedora-rawhide',
            'url': 'http://mirror.example.com/fedora/rawhide/x86_64/',
        })
        with pytest.raises(AnsibleExitJson) as exit:
            koji_external_repo.main()
        result = exit.value.args[0]
        assert result['changed'] is True
        assert result['stdout_lines'] == ['created repo id 2']

    def test_absent(self):
        set_module_args({
            'name': 'centos-7-cr',
            'state': 'absent',
        })
        with pytest.raises(AnsibleExitJson) as exit:
            koji_external_repo.main()
        result = exit.value.args[0]
        assert result['changed'] is True
        assert result['stdout'] == 'deleted external repo centos-7-cr'

    def test_missing_url(self):
        set_module_args({
            'name': 'fedora-rawhide',
        })
        with pytest.raises(AnsibleFailJson) as exit:
            koji_external_repo.main()
        result = exit.value.args[0]
        assert result['msg'] == 'you must set a url for this external_repo'
