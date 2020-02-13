import pytest
import koji_btype
from utils import exit_json
from utils import fail_json
from utils import set_module_args
from utils import AnsibleExitJson
from utils import AnsibleFailJson


class FakeKojiSession(object):
    def __init__(self):
        self.btypes = [{'id': 1, 'name': 'rpm'},
                       {'id': 2, 'name': 'maven'},
                       {'id': 3, 'name': 'win'},
                       {'id': 4, 'name': 'image'}]

    def listBTypes(self, query=None, queryOpts=None):
        if query or queryOpts:
            raise NotImplementedError()
        return self.btypes

    def addBType(self, name):
        btypes_count = len(self.btypes)
        next_id = btypes_count + 1
        new_btype = {'id': next_id, 'name': name}
        self.btypes.append(new_btype)
        # Koji Hub gives no indication whether this changed anything, so we
        # return nothing here.

    def ensure_logged_in(self, session):
        return session

    def logged_in(self, session):
        return True


@pytest.fixture(autouse=True)
def fake_exits(monkeypatch):
    monkeypatch.setattr(koji_btype.AnsibleModule,
                        'exit_json', exit_json)
    monkeypatch.setattr(koji_btype.AnsibleModule,
                        'fail_json', fail_json)


def test_simple(monkeypatch):
    session = FakeKojiSession()
    monkeypatch.setattr(koji_btype.common_koji,
                        'get_session',
                        lambda x: session)
    set_module_args({'name': 'debian'})
    with pytest.raises(AnsibleExitJson) as exit:
        koji_btype.main()
    result = exit.value.args[0]
    assert result['changed'] is True


def test_absent(monkeypatch):
    session = FakeKojiSession()
    monkeypatch.setattr(koji_btype.common_koji,
                        'get_session',
                        lambda x: session)
    set_module_args({
        'name': 'debian',
        'state': 'absent',
    })
    with pytest.raises(AnsibleFailJson) as exit:
        koji_btype.main()
    result = exit.value.args[0]
    assert result['msg'] == 'Cannot remove Koji build types.'
