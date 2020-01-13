import koji_cg


class GenericError(Exception):
    def __str__(self):
        return str(self.args[0])


class FakeKojiSession(object):
    def __init__(self):
        self.cgs = {}

    def grantCGAccess(self, user, name, create):
        if create is not True:
            raise NotImplementedError  # We don't implement this in our fake.
        if name not in self.cgs:
            # Initialize this CG.
            self.cgs[name] = {'users': []}
        if user in self.cgs[name]['users']:
            msg = 'User already has access to content generator %s' % name
            raise GenericError(msg)
        self.cgs[name]['users'].append(user)

    def listCGs(self):
        return self.cgs

    def revokeCGAccess(self, user, name):
        if name in self.cgs:
            if user in self.cgs[name]['users']:
                self.cgs[name]['users'].remove(user)
                # If there are no more users, we won't print a record in
                # listCGs. Just delete it here.
                if not self.cgs[name]['users']:
                    del self.cgs[name]
        # Koji Hub gives no indication whether this changed anything, so we
        # return nothing here.

    def ensure_logged_in(self, session):
        return session

    def logged_in(self, session):
        return True


class FakeOldKojiSession(FakeKojiSession):
    def listCGs(self):
        raise GenericError('Invalid method: listCGs')


class TestEnsureUnknownCG(object):

    def test_state_present(self):
        session = FakeOldKojiSession()
        result = koji_cg.ensure_unknown_cg(session,
                                           'rcm/debbuild',
                                           'debian',
                                           'present')
        assert result['changed'] is True
        assert session.cgs == {'debian': {'users': ['rcm/debbuild']}}

    def test_state_present_unchanged(self):
        session = FakeOldKojiSession()
        session.cgs = {'debian': {'users': ['rcm/debbuild']}}
        result = koji_cg.ensure_unknown_cg(session,
                                           'rcm/debbuild',
                                           'debian',
                                           'present')
        assert result['changed'] is False
        assert session.cgs == {'debian': {'users': ['rcm/debbuild']}}

    def test_state_absent(self):
        session = FakeOldKojiSession()
        session.cgs = {'debian': {'users': ['rcm/debbuild']}}
        result = koji_cg.ensure_unknown_cg(session,
                                           'rcm/debbuild',
                                           'debian',
                                           'absent')
        assert result['changed'] is True
        assert session.cgs == {}


class TestEnsureCG(object):

    def test_state_present(self):
        current_cgs = {}
        session = FakeKojiSession()
        result = koji_cg.ensure_cg(session,
                                   'rcm/debbuild',
                                   'debian',
                                   'present',
                                   current_cgs,
                                   False)
        assert result['changed'] is True
        # Verify the new CG that we added.
        assert session.cgs == {'debian': {'users': ['rcm/debbuild']}}

    def test_state_present_unchanged(self):
        current_cgs = {'debian': {'users': ['rcm/debbuild']}}
        session = FakeKojiSession()
        session.cgs = current_cgs.copy()
        result = koji_cg.ensure_cg(session,
                                   'rcm/debbuild',
                                   'debian',
                                   'present',
                                   current_cgs,
                                   False)
        assert result['changed'] is False
        # Verify the new CGs match the old ones.
        assert session.cgs == current_cgs

    def test_state_absent(self):
        current_cgs = {'debian': {'users': ['rcm/debbuild']}}
        session = FakeKojiSession()
        session.cgs = current_cgs.copy()
        result = koji_cg.ensure_cg(session,
                                   'rcm/debbuild',
                                   'debian',
                                   'absent',
                                   current_cgs,
                                   False)
        assert result['changed'] is True
        # Verify that the CG we deleted is gone.
        assert session.cgs == {}

    def test_state_absent_unchanged(self):
        current_cgs = {}
        session = FakeKojiSession()
        result = koji_cg.ensure_cg(session,
                                   'rcm/debbuild',
                                   'debian',
                                   'absent',
                                   current_cgs,
                                   False)
        assert result['changed'] is False
        # Verify the new CGs match the old ones.
        assert session.cgs == current_cgs
