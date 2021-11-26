import pytest
from koji_target import ensure_target
from koji_target import delete_target


class GenericError(Exception):
    def __str__(self):
        return str(self.args[0])


class FakeKojiSession(object):

    def __init__(self):
        self.targets = {}
        self.next_id = 0

    def getBuildTarget(self, info):
        if isinstance(info, int):
            name = self._find_target_name(info)
        else:
            name = info
        if name not in self.targets:
            return None
        return self.targets[name]

    def createBuildTarget(self, name, build_tag, dest_tag):
        if name in self.targets:
            raise GenericError("'%s' already exists" % name)
        self.next_id += 1
        this_id = self.next_id
        target = {
            'build_tag_name': build_tag,
            'dest_tag_name': dest_tag,
            'id': this_id,
            'name': name,
        }
        self.targets[name] = target

    def editBuildTarget(self, buildTargetInfo, name, build_tag, dest_tag):
        if isinstance(buildTargetInfo, int):
            current_name = self._find_target_name(buildTargetInfo)
        else:
            current_name = buildTargetInfo
        # This fake can only edit build_tag_name and dest_tag_name.
        if name is not None and name != current_name:
            raise NotImplementedError('cannot rename targets')
        self.targets[current_name]['build_tag_name'] = build_tag
        self.targets[current_name]['dest_tag_name'] = dest_tag

    def deleteBuildTarget(self, buildTargetInfo):
        if isinstance(buildTargetInfo, int):
            name = self._find_target_name(buildTargetInfo)
        else:
            name = buildTargetInfo
        if name not in self.targets:
            raise GenericError('invalid build target: %s' % buildTargetInfo)
        del self.targets[name]

    def _find_target_name(self, target_id):
        for target in self.targets.values():
            if target['id'] == target_id:
                return target['name']

    def ensure_logged_in(self, session):
        return self._session

    def logged_in(self, session):
        return True


@pytest.fixture
def session():
    return FakeKojiSession()


@pytest.fixture
def name():
    return 'epel8-candidate'


@pytest.fixture
def build_tag():
    return 'epel8-build'


@pytest.fixture
def dest_tag():
    return 'epel8-testing-candidate'


def epel8_target():
    return {'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate',
            'id': 1,
            'name': 'epel8-candidate'}


def test_create(session, name, build_tag, dest_tag):
    check_mode = False
    result = ensure_target(session, name, check_mode, build_tag, dest_tag)
    assert result['stdout_lines'] == ['created target 1']
    assert result['changed'] is True
    expected = {
        'before': {},
        'after': {
            'name': 'epel8-candidate',
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate',
        },
        'before_header': 'Not present',
        'after_header': "New target 'epel8-candidate'",
    }
    assert result['diff'] == expected
    assert session.targets == {'epel8-candidate': epel8_target()}


def test_create_check_mode(session, name, build_tag, dest_tag):
    check_mode = True
    result = ensure_target(session, name, check_mode, build_tag, dest_tag)
    expected = 'would create target epel8-candidate'
    assert result['stdout_lines'] == [expected]
    assert result['changed'] is True
    expected = {
        'before': {},
        'after': {
            'name': 'epel8-candidate',
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate',
        },
        'before_header': 'Not present',
        'after_header': "New target 'epel8-candidate'",
    }
    assert result['diff'] == expected
    assert session.targets == {}


def test_update_build_tag(session, name, dest_tag):
    check_mode = False
    session.targets = {'epel8-candidate': epel8_target()}
    # Assign a new build_tag to this target.
    build_tag = 'epel8-other-build'
    result = ensure_target(session, name, check_mode, build_tag, dest_tag)
    assert result['changed'] is True
    assert result['stdout_lines'] == ['build_tag_name: epel8-other-build']
    expected = {
        'before': {
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate',
            'name': 'epel8-candidate',
        },
        'after': {
            'name': 'epel8-candidate',
            'build_tag_name': 'epel8-other-build',
            'dest_tag_name': 'epel8-testing-candidate'
        },
        'before_header': "Original target 'epel8-candidate'",
        'after_header': "Modified target 'epel8-candidate'",
    }
    assert result['diff'] == expected
    new_target = epel8_target()
    new_target['build_tag_name'] = 'epel8-other-build'
    assert session.targets == {'epel8-candidate': new_target}


def test_update_dest_tag(session, name, build_tag):
    check_mode = False
    session.targets = {'epel8-candidate': epel8_target()}
    # Assign a new dest_tag to this target.
    dest_tag = 'epel8-other-dest'
    result = ensure_target(session, name, check_mode, build_tag, dest_tag)
    assert result['changed'] is True
    assert result['stdout_lines'] == ['dest_tag_name: epel8-other-dest']
    expected = {
        'before': {
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate',
            'name': 'epel8-candidate'
        },
        'after': {
            'name': 'epel8-candidate',
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-other-dest'
        },
        'before_header': "Not present",
        'after_header': "New target 'epel8-candidate'",
    }
    expected = {
        'before': {
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate',
            'name': 'epel8-candidate'
        },
        'after': {
            'name': 'epel8-candidate',
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-other-dest'
        },
        'before_header': "Original target 'epel8-candidate'",
        'after_header': "Modified target 'epel8-candidate'",
    }
    assert result['diff'] == expected
    new_target = epel8_target()
    new_target['dest_tag_name'] = 'epel8-other-dest'
    assert session.targets == {'epel8-candidate': new_target}


def test_update_check_mode(session, name, build_tag):
    check_mode = True
    session.targets = {'epel8-candidate': epel8_target()}
    # Assign a new dest_tag to this target.
    dest_tag = 'epel8-other-dest'
    result = ensure_target(session, name, check_mode, build_tag, dest_tag)
    assert result['changed'] is True
    assert result['stdout_lines'] == ['dest_tag_name: epel8-other-dest']
    expected = {
        'before': {
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate',
            'name': 'epel8-candidate'
        },
        'after': {
            'name': 'epel8-candidate',
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-other-dest',
        },
        'before_header': "Original target 'epel8-candidate'",
        'after_header': "Modified target 'epel8-candidate'",
    }
    assert result['diff'] == expected
    assert session.targets == {'epel8-candidate': epel8_target()}


@pytest.mark.parametrize('check_mode', (False, True))
def test_ensure_unchanged(session, name, build_tag, dest_tag, check_mode):
    # Test that there are no changes.
    session.targets = {'epel8-candidate': epel8_target()}
    result = ensure_target(session, name, check_mode, build_tag, dest_tag)
    assert result['changed'] is False
    expected = {
        'before': {
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate',
            'name': 'epel8-candidate',
        },
        'after': {
            'name': 'epel8-candidate',
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate'
        },
        'before_header': "Original target 'epel8-candidate'",
        'after_header': "Modified target 'epel8-candidate'",
    }
    assert result['diff'] == expected
    assert session.targets == {'epel8-candidate': epel8_target()}


def test_delete(session, name):
    check_mode = False
    session.targets = {'epel8-candidate': epel8_target()}
    result = delete_target(session, name, check_mode)
    assert result['changed'] is True
    assert result['stdout'] == 'deleted target 1'
    expected = {
        'before': {
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate',
            'id': 1, 'name': 'epel8-candidate'
        },
        'after': {},
        'before_header': "target 'epel8-candidate'",
        'after_header': 'Not present',
    }
    assert result['diff'] == expected
    assert session.targets == {}


def test_delete_check_mode(session, name):
    check_mode = True
    session.targets = {'epel8-candidate': epel8_target()}
    result = delete_target(session, name, check_mode)
    assert result['changed'] is True
    assert result['stdout'] == 'deleted target 1'
    expected = {
        'before': {
            'build_tag_name': 'epel8-build',
            'dest_tag_name': 'epel8-testing-candidate',
            'id': 1,
            'name': 'epel8-candidate'
        },
        'after': {},
        'before_header': "target 'epel8-candidate'",
        'after_header': 'Not present',
    }
    assert result['diff'] == expected
    assert session.targets == {'epel8-candidate': epel8_target()}


@pytest.mark.parametrize('check_mode', (False, True))
def test_delete_unchanged(session, name, check_mode):
    # Test that there are no changes.
    result = delete_target(session, name, check_mode)
    assert result['changed'] is False
    assert session.targets == {}
