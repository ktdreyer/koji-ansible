import pytest
import koji_tag_packages
from utils import exit_json
from utils import fail_json
from utils import set_module_args
from utils import AnsibleExitJson
from utils import AnsibleFailJson

from mock import Mock, call


class FakeKojiSession(object):

    tags = {}

    def getTag(self, tagInfo, **kw):
        if isinstance(tagInfo, int):
            for tag in self.tags.values():
                if tag['id'] == tagInfo:
                    return tag
            return None
        return self.tags.get(tagInfo)

    def listPackages(self, tagID):
        tag = self.getTag(tagID)
        return tag['packages']

    def packageListAdd(self, taginfo, pkginfo, owner):
        tag = self.getTag(taginfo)
        package = {'package_id': '0',
                   'package_name': pkginfo,
                   'owner_name': owner}
        tag['packages'].append(package)

    def packageListRemove(self, taginfo, pkginfo):
        tag = self.getTag(taginfo)
        found = None
        for idx, package in enumerate(tag['packages']):
            if package['package_name'] == pkginfo:
                found = idx
                break
        if found is not None:
            del tag['packages'][found]

    def ensure_logged_in(self, session):
        return session

    def logged_in(self, session):
        return True


@pytest.fixture
def session():
    return FakeKojiSession()


class TestKojiTagPackages(object):

    def test_remove_packages(self):
        packages = {
            "user1": ['ceph', 'curl'],
            "user2": ['coreutils'],
        }
        check_mode = False
        session = Mock()
        result = koji_tag_packages.remove_packages(
            session, "epel8", check_mode, packages)
        assert result['changed']
        calls = [
            call("epel8", "ceph"),
            call("epel8", "curl"),
            call("epel8", "coreutils"),
        ]
        session.packageListRemove.assert_has_calls(calls, any_order=True)

    def test_add_package(self):
        packages = {
            "user1": ['ceph', 'curl'],
            "user2": ['coreutils'],
        }
        current_packages = [
            {"package_name": "curl", "owner_name": "user1"},
            {"package_name": "coreutils", "owner_name": "user2"},
        ]
        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.ensure_packages(
            session, "epel8", "5", check_mode, packages)
        assert result['changed']
        session.packageListAdd.assert_called_with("epel8", "ceph", "user1")

    def test_packages_no_change(self):
        packages = {
            "user1": ['ceph', 'curl'],
            "user2": ['coreutils'],
        }
        current_packages = [
            {"package_name": "ceph", "owner_name": "user1"},
            {"package_name": "curl", "owner_name": "user1"},
            {"package_name": "coreutils", "owner_name": "user2"},
        ]
        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.ensure_packages(
            session, "epel8", "5", check_mode, packages)
        assert not result['changed']

    def test_unblock_packages(self):
        packages = [
            'ceph',
            'curl',
        ]
        current_packages = [
            {"package_name": "ceph", "blocked": True},
            {"package_name": "curl", "blocked": True},
        ]
        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.remove_package_blocks(
            session, "epel8", check_mode, packages)
        assert result == [
            'unblock pkg ceph',
            'unblock pkg curl',
        ]
        calls = [
            call("epel8", "ceph"),
            call("epel8", "curl"),
        ]
        session.packageListUnblock.assert_has_calls(calls, any_order=True)

    def test_block_packages(self):
        packages = ["ceph", "curl", "coreutils"]
        current_packages = [
            {"package_name": "ceph", "blocked": True},
            {"package_name": "coreutils", "blocked": True},
        ]

        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.ensure_blocked_packages(
            session, "epel8", "5", check_mode, packages)
        assert result == ['block pkg curl']
        session.packageListBlock.assert_called_with("epel8", "curl")

    def test_block_no_change(self):
        packages = ["ceph", "curl", "coreutils"]
        current_packages = [
            {"package_name": "ceph", "blocked": True},
            {"package_name": "coreutils", "blocked": True},
            {"package_name": "curl", "blocked": True},
        ]

        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.ensure_blocked_packages(
            session, "epel8", "5", check_mode, packages)
        assert result == []

    def test_fix_package_ownership(self):
        packages = {
            "user1": ['ceph', 'curl'],
            "user2": ['coreutils'],
        }
        current_packages = [
            {"package_name": "ceph", "owner_name": "user1"},
            {"package_name": "curl", "owner_name": "user1"},
            {"package_name": "coreutils", "owner_name": "user1"},
        ]
        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.ensure_packages(
            session, "epel8", "5", check_mode, packages)
        assert result['changed']
        session.packageListSetOwner.assert_called_with(
            "epel8", "coreutils", "user2")


class TestMain(object):

    @pytest.fixture(autouse=True)
    def fake_exits(self, monkeypatch):
        monkeypatch.setattr(koji_tag_packages.AnsibleModule,
                            'exit_json', exit_json)
        monkeypatch.setattr(koji_tag_packages.AnsibleModule,
                            'fail_json', fail_json)

    @pytest.fixture
    def session(self, monkeypatch, session):
        monkeypatch.setattr(koji_tag_packages.common_koji,
                            'get_session',
                            lambda x: session)
        return session

    def test_no_tag_failure(self, session):
        set_module_args({
            'tag': 'ceph-5.0-rhel-8',
            'packages': {'kdreyer': ['ceph']},
        })
        with pytest.raises(AnsibleFailJson) as exit:
            koji_tag_packages.main()
        result = exit.value.args[0]
        assert result['msg'] == 'tag ceph-5.0-rhel-8 does not exist'

    def test_add_package(self, session):
        session.tags = {'ceph-5.0-rhel-8': {'id': 1, 'packages': []}}
        set_module_args({
            'tag': 'ceph-5.0-rhel-8',
            'packages': {'kdreyer': ['ceph']},
        })
        with pytest.raises(AnsibleExitJson) as exit:
            koji_tag_packages.main()
        result = exit.value.args[0]
        assert result['changed'] is True
        assert result['stdout_lines'] == ['added pkg ceph']

    def test_remove_package(self, session):
        packages = [{'blocked': False,
                     'extra_arches': '',
                     'owner_id': 1,
                     'owner_name': 'kdreyer',
                     'package_id': 2,
                     'package_name': 'ceph',
                     'tag_id': 1,
                     'tag_name': 'ceph-5.0-rhel-8'}]
        session.tags = {'ceph-5.0-rhel-8': {'id': 1, 'packages': packages}}
        set_module_args({
            'tag': 'ceph-5.0-rhel-8',
            'packages': {'kdreyer': ['ceph']},
            'state': 'absent',
        })
        with pytest.raises(AnsibleExitJson) as exit:
            koji_tag_packages.main()
        result = exit.value.args[0]
        assert result['changed'] is True
        assert result['stdout_lines'] == ['remove pkg ceph']
