from textwrap import dedent
from ansible.module_utils.common_koji import get_profile_name
from ansible.module_utils.common_koji import get_session
from ansible.module_utils.common_koji import describe_inheritance_rule
import pytest


def test_get_profile_name():
    assert get_profile_name('fakekoji') == 'fakekoji'


def test_get_profile_name_from_env(monkeypatch):
    monkeypatch.setenv('KOJI_PROFILE', 'fakekoji')
    assert get_profile_name(None) == 'fakekoji'


def test_get_profile_name_error():
    with pytest.raises(ValueError) as e:
        get_profile_name(None)
    assert 'KOJI_PROFILE environment variable' in str(e.value)


class TestSession(object):
    conf = dedent("""\
    [testkoji]
    server = https://testkoji.example.com/kojihub
    authtype = ssl
    topdir = /mnt/koji
    weburl = https://testkoji.example.com/koji
    topurl = https://testkoji.example.com/kojifiles

    # client certificate
    cert = ~/.koji/pki/testuser.cert
    # certificate of the CA that issued the client certificate
    ca = ~/.koji/pki/koji-ca.crt
    serverca = ~/.koji/pki/koji-ca.crt
    """)

    @pytest.fixture(autouse=True)
    def fake_config(self, monkeypatch, tmpdir):
        monkeypatch.setenv('HOME', str(tmpdir))
        dot_koji = tmpdir.mkdir('.koji')
        conf_file = dot_koji.mkdir('config.d').join('testkoji.conf')
        try:
            conf = unicode(self.conf)  # Python 2
        except NameError:
            conf = self.conf
        conf_file.write_text(conf, 'utf-8')
        pki = dot_koji.mkdir('pki')
        pki.join('testuser.cert').ensure(file=True)
        pki.join('koji-ca.crt').ensure(file=True)

    def test_anonymous(self):
        profile = 'testkoji'
        session = get_session(profile)
        assert session.logged_in is False


class TestDescribeInheritance(object):

    def test_simple(self):
        rule = {
            'child_id': 1234,
            'intransitive': False,
            'maxdepth': None,
            'name': 'rhel-8-build-base',
            'noconfig': False,
            'parent_id': 5678,
            'pkg_filter': '',
            'priority': 50,
        }
        result = describe_inheritance_rule(rule)
        assert result == ('  50   .... rhel-8-build-base',)

    def test_maxdepth(self):
        rule = {
            'child_id': 1234,
            'intransitive': False,
            'maxdepth': 1,
            'name': 'rhel-8-build-base',
            'noconfig': False,
            'parent_id': 5678,
            'pkg_filter': '',
            'priority': 50,
        }
        result = describe_inheritance_rule(rule)
        assert result == ('  50   M... rhel-8-build-base',
                          '    maxdepth: 1',)

    def test_pkg_filter(self):
        rule = {
            'child_id': 1234,
            'intransitive': False,
            'maxdepth': None,
            'name': 'rhel-8-build-base',
            'noconfig': False,
            'parent_id': 5678,
            'pkg_filter': '^prefix-',
            'priority': 50,
        }
        result = describe_inheritance_rule(rule)
        assert result == ('  50   .F.. rhel-8-build-base',
                          '    package filter: ^prefix-',)

    def test_intransitive(self):
        rule = {
            'child_id': 1234,
            'intransitive': True,
            'maxdepth': None,
            'name': 'rhel-8-build-base',
            'noconfig': False,
            'parent_id': 5678,
            'pkg_filter': '',
            'priority': 50,
        }
        result = describe_inheritance_rule(rule)
        assert result == ('  50   ..I. rhel-8-build-base',)

    def test_noconfig(self):
        rule = {
            'child_id': 1234,
            'intransitive': False,
            'maxdepth': None,
            'name': 'rhel-8-build-base',
            'noconfig': True,
            'parent_id': 5678,
            'pkg_filter': '',
            'priority': 50,
        }
        result = describe_inheritance_rule(rule)
        assert result == ('  50   ...N rhel-8-build-base',)


"""
Live tests, need to figure out how to mock these out:

def test_get_session():
    profile = 'kojidev'
    session = get_session(profile)
    assert session.logged_in is False

def test_ensure_logged_in():
    profile = 'kojidev'
    session = get_session(profile)
    ensure_logged_in(session)
    assert session.logged_in is True
"""
