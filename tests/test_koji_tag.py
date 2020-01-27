import pytest
import koji_tag


class GenericError(Exception):
    def __str__(self):
        return str(self.args[0])


class FakeSession(object):
    def __init__(self):
        self.repos = []
        self.tags = {}
        self.inheritance = {}

    def getTag(self, tagInfo, strict=False, event=None):
        if tagInfo not in self.tags:
            if strict:
                raise GenericError('Invalid tagInfo: %s' % tagInfo)
            return None
        return self.tags[tagInfo]

    def getTagExternalRepos(self, tag_info=None, repo_info=None):
        return self.repos

    def addExternalRepoToTag(self, tag_info, repo_info, priority,
                             merge_mode='koji'):
        pass

    def getInheritanceData(self, tag, event=None):
        if tag not in self.inheritance:
            return []
        return self.inheritance[tag]

    def removeExternalRepoFromTag(self, tag_info, repo_info):
        pass

    def setInheritanceData(self, tag, data, clear=False):
        if not clear:
            raise NotImplementedError()
        self.inheritance[tag] = data

    def ensure_logged_in(self, session):
        return session

    def logged_in(self, session):
        return True


class TestEnsureExternalRepos(object):

    def test_from_no_repos(self):
        session = FakeSession()
        tag_name = 'my-centos-7'
        check_mode = False
        repos = [{'repo': 'centos-7-cr',
                  'priority': 10},
                 {'repo': 'epel-7-cr',
                  'priority': 20},
                 ]
        koji_tag.ensure_external_repos(session, tag_name, check_mode, repos)

    def test_add_one_repo(self):
        session = FakeSession()
        session.repos = [{'external_repo_name': 'centos-7-cr',
                          'priority': 10}]
        tag_name = 'my-centos-7'
        check_mode = False
        repos = [{'repo': 'centos-7-cr',
                  'priority': 10},
                 {'repo': 'epel-7-cr',
                  'priority': 20},
                 ]
        koji_tag.ensure_external_repos(session, tag_name, check_mode, repos)


class TestEnsureInheritance(object):

    @pytest.fixture
    def session(self):
        session = FakeSession()
        session.tags = {'my-centos-7-parent': {'id': 1},
                        'my-centos-7-child': {'id': 2}}
        return session

    def test_add_simple(self, session):
        tag_name = 'my-centos-7-child'
        tag_id = 2
        check_mode = False
        inheritance = [
            {'parent': 'my-centos-7-parent',
             'priority': 0},
        ]
        koji_tag.ensure_inheritance(session, tag_name, tag_id, check_mode,
                                    inheritance)
        result = session.getInheritanceData('my-centos-7-child')
        expected = [{'child_id': 2,
                     'intransitive': False,
                     'maxdepth': None,
                     'name': 'my-centos-7-parent',
                     'noconfig': False,
                     'parent_id': 1,
                     'pkg_filter': '',
                     'priority': 0}]
        assert result == expected

    def test_parent_does_not_exist(self, session):
        tag_name = 'my-centos-7-child'
        tag_id = 2
        check_mode = False
        inheritance = [
            {'parent': 'my-nonexistant-parent',
             'priority': 0},
        ]
        with pytest.raises(ValueError):
            koji_tag.ensure_inheritance(session, tag_name, tag_id, check_mode,
                                        inheritance)

    def test_parent_does_not_exist_check_mode(self, session):
        tag_name = 'my-centos-7-child'
        tag_id = 2
        check_mode = True
        inheritance = [
            {'parent': 'my-nonexistant-parent',
             'priority': 0},
        ]
        result = koji_tag.ensure_inheritance(session, tag_name, tag_id, check_mode,
                                             inheritance)
        expected = {
            'changed': True,
            'stdout_lines': ["parent tag 'my-nonexistant-parent' not found",
                             'current inheritance:',
                             'new inheritance:',
                             '   0   .... my-nonexistant-parent']}
        assert result == expected

    def test_maxdepth_empty_string(self, session):
        tag_name = 'my-centos-7-child'
        tag_id = 2
        check_mode = False
        inheritance = [
            {'parent': 'my-centos-7-parent',
             'priority': 0,
             'maxdepth': ''},
        ]
        koji_tag.ensure_inheritance(session, tag_name, tag_id, check_mode,
                                    inheritance)
        result = session.getInheritanceData('my-centos-7-child')
        expected = [{'child_id': 2,
                     'intransitive': False,
                     'maxdepth': None,
                     'name': 'my-centos-7-parent',
                     'noconfig': False,
                     'parent_id': 1,
                     'pkg_filter': '',
                     'priority': 0}]
        assert result == expected

    def test_maxdepth_string(self, session):
        tag_name = 'my-centos-7-child'
        tag_id = 2
        check_mode = False
        inheritance = [
            {'parent': 'my-centos-7-parent',
             'priority': 0,
             'maxdepth': '30'},
        ]
        koji_tag.ensure_inheritance(session, tag_name, tag_id, check_mode,
                                    inheritance)
        result = session.getInheritanceData('my-centos-7-child')
        expected = [{'child_id': 2,
                     'intransitive': False,
                     'maxdepth': 30,
                     'name': 'my-centos-7-parent',
                     'noconfig': False,
                     'parent_id': 1,
                     'pkg_filter': '',
                     'priority': 0}]
        assert result == expected
