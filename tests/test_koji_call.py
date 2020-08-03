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

    def test_positional_args(self):
        session = FakeKojiSession()
        result = koji_call.do_call(session, 'newRepo', ['f32-build'], False)
        assert result['changed'] is True
        assert result['data'] == 12345

    def test_named_args(self):
        session = FakeKojiSession()
        result = koji_call.do_call(session, 'newRepo', {'tag': 'f32-build'},
                                   False)
        assert result['changed'] is True
        assert result['data'] == 12345

    def test_logged_in(self):
        session = FakeKojiSession()
        result = koji_call.do_call(session, 'newRepo', ['f32-build'], True)
        assert result['changed'] is True
        assert result['data'] == 12345


class TestCheckMode(object):

    def test_check_mode(self):
        result = koji_call.check_mode_call('newRepo', ['f32-build'])
        assert result['changed'] is True
        assert result['stdout_lines'] == "would have called"\
                                         " newRepo(*['f32-build'])"


class TestDescribeCall(object):

    def test_positional_args(self):
        result = koji_call.describe_call('newRepo', ['f32-build'])
        assert result == "newRepo(*['f32-build'])"

    def test_named_args(self):
        result = koji_call.describe_call('newRepo', {'tag': 'f32-build'})
        assert result == "newRepo(**{'tag': 'f32-build'})"
