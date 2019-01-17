import sys
from os.path import abspath, dirname, join


def pytest_sessionstart(session):
    """
    This pytest hook gets executed after the Session object has been created
    and before any collection starts.

    ansible-playbook will automatically load modules from the "library"
    directory. To mimic this during tests, we will prepend the absolute path
    of the ``library`` directory, so we can import modules during testing.

    ansible-playbook will also import files from the "module_utils" directory
    into the "ansible.module_utils.*" namespace, so we mimic that here as
    well for common_koji.py.
    """
    working_directory = dirname(abspath((__file__)))
    library_path = join(dirname(working_directory), 'library')
    if library_path not in sys.path:
        sys.path.insert(0, library_path)

    module_utils_path = join(dirname(working_directory), 'module_utils')

    location = join(module_utils_path, 'common_koji.py')
    module_name = "ansible.module_utils.common_koji"
    if sys.version_info[0] == 3:
        # Python 3.5+
        import importlib.util
        spec = importlib.util.spec_from_file_location(module_name, location)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    if sys.version_info[0] == 2:
        import imp
        module = imp.load_source(module_name, location)
    sys.modules[module_name] = module
    import ansible.module_utils
    ansible.module_utils.common_koji = module
