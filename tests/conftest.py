import sys
from os.path import abspath, dirname, join


def pytest_sessionstart(session):
    """
    This pytest hook gets executed after the Session object has been created
    and before any collection starts.
    The main purpose of this hook is to prepend the absolute path of the
    ``library`` directory so that imports in the test files can work correctly.
    """
    working_directory = dirname(abspath((__file__)))
    library_path = join(dirname(working_directory), 'library')
    if library_path not in sys.path:
        sys.path.insert(0, library_path)
