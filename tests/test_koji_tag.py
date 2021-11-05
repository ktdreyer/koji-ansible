import pytest
import koji_tag
from collections import defaultdict


class GenericError(Exception):
    def __str__(self):
        return str(self.args[0])


class ParameterError(Exception):
    def __str__(self):
        return str(self.args[0])


class FakeKojiSession(object):
    def __init__(self):
        self.tag_repos = defaultdict(list)
        self.tags = {}
        self.inheritance = {}

    def getTag(self, tagInfo, strict=False, event=None):
        if isinstance(tagInfo, int):
            for tag in self.tags.values():
                if tag['id'] == tagInfo:
                    return tag
            if strict:
                raise GenericError('Invalid tagInfo: %s' % tagInfo)
            return None
        return self.tags.get(tagInfo)

    def getTagExternalRepos(self, tag_info=None, repo_info=None, event=None):
        if isinstance(tag_info, int):
            raise NotImplementedError('specify a tag by name')
        if isinstance(repo_info, int):
            raise NotImplementedError('specify a repo by name')
        if event is not None:
            raise NotImplementedError('cannot specify event')
        if tag_info:
            repos = self.tag_repos[tag_info]
        else:
            repos = []
            for tag in self.tag_repos:
                repos.append(self.tag_repos[tag])
        if repo_info:
            repos = [repo for repo in repos
                     if repo['external_repo_name'] == repo_info]
        return sorted(repos, key=lambda r: r['priority'])

    def addExternalRepoToTag(self, tag_info, repo_info, priority,
                             merge_mode='koji'):
        if isinstance(tag_info, int):
            raise NotImplementedError('specify a tag by name')
        if isinstance(repo_info, int):
            raise NotImplementedError('specify a repo by name')
        existing = self.getTagExternalRepos(tag_info, repo_info)
        if existing:
            # TODO: discover the exact error here:
            raise RuntimeError('%s repo already exists for %s'
                               % (repo_info, tag_info))
        repo = {
            # 'tag_id': tag_id,
            'tag_name': tag_info,
            # 'external_repo_id': external_repo_id,
            'external_repo_name': repo_info,
            # 'url': url,
            'merge_mode': merge_mode,
            'priority': priority,
        }
        self.tag_repos[tag_info].append(repo)

    def getInheritanceData(self, tag, event=None):
        if tag not in self.inheritance:
            return []
        return self.inheritance[tag]

    def removeExternalRepoFromTag(self, tag_info, repo_info):
        if isinstance(tag_info, int):
            raise NotImplementedError('specify a tag by name')
        if isinstance(repo_info, int):
            raise NotImplementedError('specify a repo by name')
        repos = self.tag_repos[tag_info]
        found = None
        for i, repo in enumerate(repos):
            if repo['external_repo_name'] == repo_info:
                found = i
        if found is None:
            raise GenericError('external repo not associated with tag')
        del repos[found]

    def setInheritanceData(self, tag, data, clear=False):
        if not clear:
            raise NotImplementedError()
        self.inheritance[tag] = data

    def listPackages(self, tagID, with_owners=True):
        tag = self.getTag(tagID)
        return tag['packages']

    def packageListAdd(self, taginfo, pkginfo, owner):
        tag = self.getTag(taginfo)
        package = {'package_id': '0',
                   'package_name': pkginfo,
                   'owner_name': owner,
                   'blocked': False}
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

    def packageListBlock(self, taginfo, pkginfo, force=False):
        tag = self.getTag(taginfo)
        for package in tag['packages']:
            if package['package_name'] == pkginfo:
                package['blocked'] = True

    def packageListUnblock(self, taginfo, pkginfo, force=False):
        tag = self.getTag(taginfo)
        for package in tag['packages']:
            if package['package_name'] == pkginfo:
                package['blocked'] = False

    def ensure_logged_in(self, session):
        return session

    def logged_in(self, session):
        return True


@pytest.fixture
def session():
    return FakeKojiSession()


class TestValidateRepos(object):

    def test_simple(self):
        repos = [{'repo': 'epel-7', 'priority': 10}]
        koji_tag.validate_repos(repos)

    def test_empty(self):
        repos = []
        koji_tag.validate_repos(repos)

    def test_duplicate_name(self):
        repos = [
            {'repo': 'epel-7', 'priority': 10},
            {'repo': 'epel-7', 'priority': 20},
        ]
        with pytest.raises(koji_tag.DuplicateNameError):
            koji_tag.validate_repos(repos)

    def test_duplicate_priority(self):
        repos = [
            {'repo': 'centos', 'priority': 10},
            {'repo': 'epel-7', 'priority': 10},
        ]
        with pytest.raises(koji_tag.DuplicatePriorityError):
            koji_tag.validate_repos(repos)


class TestAddExternalRepos(object):

    def test_simple(self, session):
        tag_name = 'my-centos-7'
        repos_to_add = [{'repo_info': 'centos-7-cr', 'priority': 10}]
        koji_tag.add_external_repos(session, tag_name, repos_to_add)

    def test_merge_mode(self, session):
        tag_name = 'my-centos-7'
        repos_to_add = [{'repo_info': 'centos-7-cr',
                         'priority': 10},
                        {'repo_info': 'epel-7',
                         'priority': 20,
                         'merge_mode': 'simple'}]
        koji_tag.add_external_repos(session, tag_name, repos_to_add)


class TestRemoveExternalRepos(object):

    def test_simple(self, session):
        tag_name = 'my-centos-7'
        session.addExternalRepoToTag(tag_name, 'centos-7-cr', 10)
        session.addExternalRepoToTag(tag_name, 'epel-7', 20)
        repos_to_remove = ['centos-7-cr', 'epel-7']
        koji_tag.remove_external_repos(session, tag_name, repos_to_remove)


class TestEnsureExternalRepos(object):

    @pytest.fixture
    def tag_name(self):
        return 'my-centos-7'

    def test_from_no_repos(self, session, tag_name):
        check_mode = False
        repos = [{'repo': 'centos-7-cr',
                  'priority': 10},
                 {'repo': 'epel-7',
                  'priority': 20},
                 ]
        koji_tag.ensure_external_repos(session, tag_name, check_mode, repos)
        result_repos = session.getTagExternalRepos('my-centos-7')
        expected_repos = [
            {'tag_name': 'my-centos-7',
             'external_repo_name': 'centos-7-cr',
             'merge_mode': 'koji',
             'priority': 10},
            {'tag_name': 'my-centos-7',
             'external_repo_name': 'epel-7',
             'merge_mode': 'koji',
             'priority': 20},
        ]
        assert result_repos == expected_repos

    def test_no_changes(self, session, tag_name):
        session.addExternalRepoToTag(tag_name, 'centos-7-cr', 10)
        check_mode = False
        repos = [{'repo': 'centos-7-cr', 'priority': 10}]
        koji_tag.ensure_external_repos(session, tag_name, check_mode, repos)
        result_repos = session.getTagExternalRepos('my-centos-7')
        expected_repos = [
            {'tag_name': 'my-centos-7',
             'external_repo_name': 'centos-7-cr',
             'merge_mode': 'koji',
             'priority': 10},
        ]
        assert result_repos == expected_repos

    def test_add_one_repo(self, session, tag_name):
        session.addExternalRepoToTag(tag_name, 'centos-7-cr', 10)
        check_mode = False
        repos = [{'repo': 'centos-7-cr',
                  'priority': 10},
                 {'repo': 'epel-7',
                  'priority': 20},
                 ]
        koji_tag.ensure_external_repos(session, tag_name, check_mode, repos)
        result_repos = session.getTagExternalRepos('my-centos-7')
        expected_repos = [
            {'tag_name': 'my-centos-7',
             'external_repo_name': 'centos-7-cr',
             'merge_mode': 'koji',
             'priority': 10},
            {'tag_name': 'my-centos-7',
             'external_repo_name': 'epel-7',
             'merge_mode': 'koji',
             'priority': 20},
        ]
        assert result_repos == expected_repos

    def test_edit_priority(self, session, tag_name):
        session.addExternalRepoToTag(tag_name, 'centos-7-cr', 10)
        check_mode = False
        repos = [{'repo': 'centos-7-cr', 'priority': 20}]
        koji_tag.ensure_external_repos(session, tag_name, check_mode, repos)
        result_repos = session.getTagExternalRepos('my-centos-7')
        expected_repos = [
            {'tag_name': 'my-centos-7',
             'external_repo_name': 'centos-7-cr',
             'merge_mode': 'koji',
             'priority': 20},
        ]
        assert result_repos == expected_repos

    def test_edit_merge_mode(self, session, tag_name):
        session.addExternalRepoToTag(tag_name, 'centos-7-cr', 10)
        session.addExternalRepoToTag(tag_name, 'epel-7', 20)
        session.addExternalRepoToTag(tag_name, 'private-el-7', 30)
        check_mode = False
        repos = [{'repo': 'centos-7-cr',
                  'priority': 10},
                 {'repo': 'epel-7',
                  'priority': 20,
                  'merge_mode': 'koji'},
                 {'repo': 'private-el-7',
                  'priority': 30,
                  'merge_mode': 'bare'},
                 ]
        koji_tag.ensure_external_repos(session, tag_name, check_mode, repos)
        result_repos = session.getTagExternalRepos(tag_name)
        expected_repos = [
            {'tag_name': 'my-centos-7',
             'external_repo_name': 'centos-7-cr',
             'merge_mode': 'koji',
             'priority': 10},
            {'tag_name': 'my-centos-7',
             'external_repo_name': 'epel-7',
             'merge_mode': 'koji',
             'priority': 20},
            {'tag_name': 'my-centos-7',
             'external_repo_name': 'private-el-7',
             'merge_mode': 'bare',
             'priority': 30},
        ]
        assert result_repos == expected_repos

    def test_remove_one_repo(self, session, tag_name):
        session.addExternalRepoToTag(tag_name, 'centos-7-cr', 10)
        session.addExternalRepoToTag(tag_name, 'epel-7', 20)
        check_mode = False
        repos = [{'repo': 'centos-7-cr', 'priority': 10}]
        koji_tag.ensure_external_repos(session, tag_name, check_mode, repos)
        result_repos = session.getTagExternalRepos('my-centos-7')
        expected_repos = [
            {'tag_name': 'my-centos-7',
             'external_repo_name': 'centos-7-cr',
             'merge_mode': 'koji',
             'priority': 10},
        ]
        assert result_repos == expected_repos


class TestEnsureInheritance(object):

    @pytest.fixture
    def session(self, session):
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

    def test_priority_string(self, session):
        tag_name = 'my-centos-7-child'
        tag_id = 2
        check_mode = False
        inheritance = [
            {'parent': 'my-centos-7-parent',
             'priority': '10'},
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
                     'priority': 10}]
        assert result == expected


class TestEnsurePackageBlocks(object):
    @pytest.mark.parametrize('check_mode', (False, True))
    def test_block_package(self, session, check_mode):
        tag_id = 1
        session.tags = {'ceph-5.0-rhel-8': {'id': tag_id, 'packages': []}}
        session.packageListAdd('ceph-5.0-rhel-8', 'ceph', 'kdreyer')
        blocked_packages = ['ceph']
        result = koji_tag.ensure_blocked_packages(session,
                                                  tag_id,
                                                  check_mode,
                                                  blocked_packages)
        assert result == ['blocked pkg ceph']
        pkgs = session.listPackages(tagID='ceph-5.0-rhel-8')
        assert len(pkgs) == 1
        assert pkgs[0]['blocked'] is not check_mode

    @pytest.mark.parametrize('check_mode', (False, True))
    def test_unblock_package(self, session, check_mode):
        tag_id = 1
        session.tags = {'ceph-5.0-rhel-8': {'id': tag_id, 'packages': []}}
        session.packageListAdd('ceph-5.0-rhel-8', 'ceph', 'kdreyer')
        session.packageListBlock('ceph-5.0-rhel-8', 'ceph')
        blocked_packages = []
        result = koji_tag.ensure_blocked_packages(session,
                                                  tag_id,
                                                  check_mode,
                                                  blocked_packages)
        assert result == ['unblocked pkg ceph']
        pkgs = session.listPackages(tagID='ceph-5.0-rhel-8')
        assert len(pkgs) == 1
        assert pkgs[0]['blocked'] is check_mode


class TestEnsurePackageBlocksOldHub(TestEnsurePackageBlocks):
    @pytest.fixture
    def session(self, session, monkeypatch):
        def oldListPackages(tagID, with_owners=None):
            if with_owners is not None:
                raise ParameterError(
                    "unexpected keyword argument 'with_owners'")
            tag = session.getTag(tagID)
            return tag['packages']
        monkeypatch.setattr(session, 'listPackages', oldListPackages)
        return session
