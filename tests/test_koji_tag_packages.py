import koji_tag_packages

from mock import Mock, call


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
            call("epel8", "ceph", "user1"),
            call("epel8", "curl", "user1"),
            call("epel8", "coreutils", "user2"),
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
