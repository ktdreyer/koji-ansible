import koji_tag
import unittest
from collections import namedtuple
from mock import Mock, call


class TestPackageListing(unittest.TestCase):

    def setUp(self):
        self.pkgs = []
        self.tag_name = 'mytag'
        self.tag_id = 42
        self.next_id = 100
        self.change_types = ['add', 'remove', 'block', 'unblock']
        self.rpc_mocks = {name: Mock() for name in self.change_types}
        self.expected_calls = {name: [] for name in self.change_types}
        self.expected_output = []
        self.expect_changed = False
        self.session = Mock()
        self.session.packageListAdd = self.rpc_mocks['add']
        self.session.packageListRemove = self.rpc_mocks['remove']
        self.session.packageListBlock = self.rpc_mocks['block']
        self.session.packageListUnblock = self.rpc_mocks['unblock']
        self.session.packageListSetOwner = Mock()

    def prepare_package(self, package_name, blocked=False, extra_arches=None, owner_name='someuser', owner_id=55):
        package_id = self.next_id
        self.next_id += 1
        pkg = {
            'package_name': package_name,
            'blocked': blocked,
            'extra_arches': extra_arches,
            'owner_name': owner_name,
            'owner_id': owner_id,
            'package_id': package_id,
            'tag_id': self.tag_id,
            'tag_name': self.tag_name,
        }
        self.pkgs.append(pkg)

    def assert_changed(self):
        self.assertTrue(self.result['changed'])

    def expect_add(self, package_name, owner_name='someuser'):
        self.expected_calls['add'].append(call(self.tag_name, package_name, owner_name))
        self.expected_output.append('added pkg ' + package_name)

    def expect_remove(self, package_name):
        self.expected_calls['remove'].append(call(self.tag_name, package_name))
        self.expected_output.append('remove pkg ' + package_name)

    def expect_block(self, package_name):
        self.expected_calls['block'].append(call(self.tag_name, package_name))
        self.expected_output.append('blocked package ' + package_name)

    def expect_unblock(self, package_name):
        self.expected_calls['unblock'].append(call(self.tag_name, package_name))
        self.expected_output.append('unblocked package ' + package_name)

    def perform_test(self, packages, check_mode=False):
        self.session.listPackages = Mock(return_value=self.pkgs)

        self.result = koji_tag.ensure_packages(self.session, self.tag_name, self.tag_id, check_mode=check_mode, packages=packages)

        for change in self.change_types:
            self.rpc_mocks[change].assert_has_calls(self.expected_calls[change], any_order=True)
            if self.expected_calls[change]:
                self.expect_changed = True

        for line in self.expected_output:
            self.assertIn(line, self.result['stdout_lines'])
        self.assertEqual(len(self.expected_output), len(self.result['stdout_lines']))

        self.assertEquals(self.expect_changed, self.result['changed'])


    def test_empty_no_change(self):
        self.perform_test({})

    def test_add(self):
        self.expect_add('foo')
        self.perform_test({'someuser': ['foo']})

    def test_no_change(self):
        self.prepare_package('foo')
        self.perform_test({'someuser': ['foo']})

    def test_add_two(self):
        self.prepare_package('foo')
        self.expect_add('bar')
        self.expect_add('xyzzy', owner_name='otheruser')
        self.perform_test({'someuser': ['foo', 'bar'], 'otheruser': ['xyzzy']})

    def test_change_owner(self):
        self.prepare_package('foo')
        self.expect_changed = True
        self.expected_output = ['set foo owner otheruser']
        self.perform_test({'otheruser': ['foo']})
        self.session.packageListSetOwner.assert_called_once_with(self.tag_name, 'foo', 'otheruser')

    def test_remove(self):
        self.prepare_package('foo')
        self.prepare_package('bar')
        self.expect_remove('bar')
        self.perform_test({'someuser': ['foo']})

    def test_block(self):
        self.prepare_package('foo')
        self.expect_block('foo')
        self.perform_test({'someuser': [{'foo': {'blocked': True}}]})

    def test_blocked_no_change(self):
        self.prepare_package('foo', blocked=True)
        self.perform_test({'someuser': [{'foo': {'blocked': True}}]})

    def test_block_missing(self):
        self.expect_add('foo')
        self.expect_block('foo')
        self.perform_test({'someuser': [{'foo': {'blocked': True}}]})

    def test_add_explicitly_not_blocked(self):
        self.expect_add('foo')
        self.perform_test({'someuser': [{'foo': {'blocked': False}}]})

    def test_unblock(self):
        self.prepare_package('foo', blocked=True)
        self.expect_unblock('foo')
        self.perform_test({'someuser': ['foo']})

    def test_unblock_explicit(self):
        self.prepare_package('foo', blocked=True)
        self.expect_unblock('foo')
        self.perform_test({'someuser': [{'foo': {'blocked': False}}]})
