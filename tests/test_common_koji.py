from ansible.module_utils.common_koji import get_profile_name
import pytest


def test_get_profile_name():
    assert get_profile_name('fakekoji') == 'fakekoji'


def test_get_profile_name_from_env(monkeypatch):
    monkeypatch.setenv('KOJI_PROFILE', 'fakekoji')
    assert get_profile_name(None) == 'fakekoji'


def test_get_profile_name_error():
    with pytest.raises(ValueError) as e:
        get_profile_name(None)
    assert 'KOJI_PROFILE environment variable' in str(e)


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
