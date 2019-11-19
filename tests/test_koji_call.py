import koji_call


class FakeKojiSession(object):

    def newRepo(self, tag, *a, **kw):
        # Return a fake newRepo task ID number
        return 12345

    def ensure_logged_in(self, session):
        return session

    def logged_in(self, session):
        return True


class TestNewRepo(object):

    def test_new_repo(self):
        session = FakeKojiSession()
        result = koji_call.do_call(session, 'newRepo', ['f30-build'], False)
        assert result['changed'] is True
        assert result['data'] == 12345


class TestDescribeCall(object):

    def test_describe_call(self):
        result = koji_call.describe_call('newRepo', ['f30-build'])
        assert result == "newRepo(*['f30-build'])"
