from koji_tag_inheritance import add_tag_inheritance
from koji_tag_inheritance import remove_tag_inheritance


class FakeKojiSession(object):

    tags = {
        'parent-tag-a': {'id': 1},
        'parent-tag-b': {'id': 2},
        'parent-tag-c': {'id': 3},
        'my-child-tag': {'id': 100},
    }

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def getInheritanceData(self, tag_id):
        if not isinstance(tag_id, int):
            taginfo = self.getTag(tag_id)
            tag_id = taginfo['id']
        return self._inheritance.get(tag_id, [])

    def getTag(self, name, **kw):
        return self.tags[name]

    def setInheritanceData(self, tag, data, clear=False):
        assert clear is False
        if tag in self._inheritance:
            # kojihub logic is kinda complicated to mock here
            pass
        else:
            self._inheritance[tag] = data

    def ensure_logged_in(self, session):
        return session

    def logged_in(self, session):
        return True


FAKE_INHERITANCE_DATA = {
    100: [
        {'child_id': 100,
         'intransitive': False,
         'maxdepth': None,
         'name': 'parent-tag-a',
         'noconfig': False,
         'parent_id': 1,
         'pkg_filter': '',
         'priority': 10},
        {'child_id': 100,
         'intransitive': False,
         'maxdepth': None,
         'name': 'parent-tag-b',
         'noconfig': False,
         'parent_id': 2,
         'pkg_filter': '',
         'priority': 20},
     ],
}


class TestEnsureInheritance(object):

    def test_add_new(self):
        session = FakeKojiSession(_inheritance={})
        result = add_tag_inheritance(session,
                                     'my-child-tag',
                                     'parent-tag-a',
                                     10,
                                     False)
        assert result['changed'] is True
        assert result['stdout_lines'] == ['set parent parent-tag-a (10)']

    def test_change_priority(self):
        session = FakeKojiSession(_inheritance=FAKE_INHERITANCE_DATA)
        result = add_tag_inheritance(session,
                                     'my-child-tag',
                                     'parent-tag-a',
                                     50,
                                     False)
        assert result['changed'] is True
        assert result['stdout_lines'] == ['set parent parent-tag-a (50)']

    def test_remove(self):
        session = FakeKojiSession(_inheritance=FAKE_INHERITANCE_DATA)
        result = remove_tag_inheritance(session,
                                        'my-child-tag',
                                        'parent-tag-a',
                                        10,
                                        False)
        assert result['changed'] is True
        assert result['stdout_lines'] == ['remove parent parent-tag-a (10)']


class TestEnsureInheritanceUnchanged(object):

    def test_ensure_unchanged(self):
        session = FakeKojiSession(_inheritance=FAKE_INHERITANCE_DATA)
        result = add_tag_inheritance(session,
                                     'my-child-tag',
                                     'parent-tag-a',
                                     10,
                                     False)
        assert result['changed'] is False

    def test_remove_unchanged(self):
        session = FakeKojiSession(_inheritance=FAKE_INHERITANCE_DATA)
        result = remove_tag_inheritance(session,
                                        'my-child-tag',
                                        'parent-tag-c',
                                        10,
                                        False)
        assert result['changed'] is False
