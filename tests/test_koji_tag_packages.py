import koji_tag_packages

from mock import Mock, call


class TestKojiTagPackages(object):

    def test_remove_packages(self):
        packages = {
            "user1": ['foo', 'bar'],
            "user2": ['baz'],
        }
        check_mode = False
        session = Mock()
        result = koji_tag_packages.remove_packages(
            session, "tag", check_mode, packages)
        assert result['changed']
        calls = [
            call("tag", "foo", "user1"),
            call("tag", "bar", "user1"),
            call("tag", "baz", "user2"),
        ]
        session.packageListRemove.assert_has_calls(calls, any_order=True)

    def test_add_package(self):
        packages = {
            "user1": ['foo', 'bar'],
            "user2": ['baz'],
        }
        current_packages = [
            {"package_name": "foo", "owner_name": "user1"},
            {"package_name": "baz", "owner_name": "user2"},
        ]
        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.ensure_packages(
            session, "tag", "5", check_mode, packages)
        assert result['changed']
        session.packageListAdd.assert_called_with("tag", "bar", "user1")

    def test_packages_no_change(self):
        packages = {
            "user1": ['foo', 'bar'],
            "user2": ['baz'],
        }
        current_packages = [
            {"package_name": "foo", "owner_name": "user1"},
            {"package_name": "bar", "owner_name": "user1"},
            {"package_name": "baz", "owner_name": "user2"},
        ]
        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.ensure_packages(
            session, "tag", "5", check_mode, packages)
        assert not result['changed']

    def test_unblock_packages(self):
        packages = [
            'foo',
            'bar',
        ]
        current_packages = [
            {"package_name": "foo", "blocked": True},
            {"package_name": "bar", "blocked": True},
        ]
        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.remove_package_blocks(
            session, "tag", check_mode, packages)
        assert result == [
            'unblock pkg foo',
            'unblock pkg bar',
        ]
        calls = [
            call("tag", "foo"),
            call("tag", "bar"),
        ]
        session.packageListUnblock.assert_has_calls(calls, any_order=True)

    def test_block_packages(self):
        packages = ["foo", "bar", "baz"]
        current_packages = [
            {"package_name": "foo", "blocked": True},
            {"package_name": "baz", "blocked": True},
        ]

        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.ensure_blocked_packages(
            session, "tag", "5", check_mode, packages)
        assert result == ['block pkg bar']
        session.packageListBlock.assert_called_with("tag", "bar")

    def test_block_no_change(self):
        packages = ["foo", "bar", "baz"]
        current_packages = [
            {"package_name": "foo", "blocked": True},
            {"package_name": "baz", "blocked": True},
            {"package_name": "bar", "blocked": True},
        ]

        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.ensure_blocked_packages(
            session, "tag", "5", check_mode, packages)
        assert result == []

    def test_fix_package_ownership(self):
        packages = {
            "user1": ['foo', 'bar'],
            "user2": ['baz'],
        }
        current_packages = [
            {"package_name": "foo", "owner_name": "user1"},
            {"package_name": "bar", "owner_name": "user1"},
            {"package_name": "baz", "owner_name": "user1"},
        ]
        check_mode = False
        session = Mock()
        session.listPackages = Mock(return_value=current_packages)
        result = koji_tag_packages.ensure_packages(
            session, "tag", "5", check_mode, packages)
        assert result['changed']
        session.packageListSetOwner.assert_called_with("tag", "baz", "user2")
