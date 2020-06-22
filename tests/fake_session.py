class GenericError(Exception):
    def __str__(self):
        return str(self.args[0])


class FakeSession(object):
    """ Fake Koji client that mimics Koji Hub behavior in memory. """

    def ensure_logged_in(self, session):
        return self._session

    def logged_in(self, session):
        return True
