import pytest
import koji_archivetype
from utils import exit_json
from utils import fail_json
from utils import set_module_args
from utils import AnsibleExitJson
from utils import AnsibleFailJson


class FakeKojiSession(object):
    def __init__(self):
        self.archivetypes = []

    def getArchiveType(self, filename=None, type_name=None, type_id=None,
                       strict=False):
        results = [t for t in self.archivetypes if t['name'] == type_name]
        if results:
            return results[0]
        return None

    def addArchiveType(self, name, description, extensions):
        archivetype = {'name': name,
                       'description': description,
                       'extensions': extensions,
                       }
        self.archivetypes.append(archivetype)
        # Koji Hub gives no indication whether this changed anything, so we
        # return nothing here.

    def ensure_logged_in(self, session):
        return session

    def logged_in(self, session):
        return True


@pytest.fixture(autouse=True)
def fake_exits(monkeypatch):
    monkeypatch.setattr(koji_archivetype.AnsibleModule,
                        'exit_json', exit_json)
    monkeypatch.setattr(koji_archivetype.AnsibleModule,
                        'fail_json', fail_json)


def test_simple(monkeypatch):
    session = FakeKojiSession()
    monkeypatch.setattr(koji_archivetype.common_koji,
                        'get_session',
                        lambda x: session)
    set_module_args({
        'name': 'deb',
        'description': 'Debian package',
        'extensions': 'deb',
    })
    with pytest.raises(AnsibleExitJson) as exit:
        koji_archivetype.main()
    result = exit.value.args[0]
    assert result['changed'] is True


def test_absent(monkeypatch):
    session = FakeKojiSession()
    monkeypatch.setattr(koji_archivetype.common_koji,
                        'get_session',
                        lambda x: session)
    set_module_args({
        'name': 'deb',
        'description': 'Debian package',
        'extensions': 'deb',
        'state': 'absent',
    })
    with pytest.raises(AnsibleFailJson) as exit:
        koji_archivetype.main()
    result = exit.value.args[0]
    assert result['msg'] == 'Cannot remove Koji archive types.'
