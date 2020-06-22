import pytest
from ansible.module_utils.six import string_types
from ansible.module_utils.basic import AnsibleModule
from utils import set_module_args

"""
This test is designed to exercise the behavior of the AnsibleModule
class, particularly argument_spec's settings.
"""

STR_ARG_SPECS = [
    {'mykey': dict()},
    {'mykey': dict(type='str')},
    {'mykey': dict(type='str', default=None)},
]

LIST_ARG_SPECS = [
    {'mykey': dict(type='list')},
    {'mykey': dict(type='list', default=None)},
]

BOOL_ARG_SPECS = [
    {'mykey': dict(type='bool')},
    {'mykey': dict(type='bool', default=None)},
]

RAW_ARG_SPECS = [
    {'mykey': dict(type='raw')},
    {'mykey': dict(type='raw', default=None)},
]

ALL_ARG_SPECS = STR_ARG_SPECS + LIST_ARG_SPECS + BOOL_ARG_SPECS + RAW_ARG_SPECS


@pytest.mark.parametrize('argument_spec', STR_ARG_SPECS)
@pytest.mark.parametrize('test_input', ['mystr', 123456, ['foo', 'bar']])
def test_string(argument_spec, test_input):
    set_module_args({'mykey': test_input})
    module = AnsibleModule(argument_spec=argument_spec)
    mykey = module.params['mykey']
    assert isinstance(mykey, string_types)


@pytest.mark.parametrize('argument_spec', ALL_ARG_SPECS)
@pytest.mark.parametrize('module_args', [{'mykey': None}, {}])
def test_none(argument_spec, module_args):
    set_module_args(module_args)
    module = AnsibleModule(argument_spec=argument_spec)
    mykey = module.params['mykey']
    assert mykey is None


@pytest.mark.parametrize('argument_spec', LIST_ARG_SPECS)
@pytest.mark.parametrize('test_input', ['mystr', 123456, ['foo', 'bar']])
def test_list(argument_spec, test_input):
    set_module_args({'mykey': test_input})
    module = AnsibleModule(argument_spec=argument_spec)
    mykey = module.params['mykey']
    assert isinstance(mykey, list)


@pytest.mark.parametrize('argument_spec', BOOL_ARG_SPECS)
@pytest.mark.parametrize('test_input', [True, False])
def test_bool(argument_spec, test_input):
    set_module_args({'mykey': test_input})
    module = AnsibleModule(argument_spec=argument_spec)
    mykey = module.params['mykey']
    assert isinstance(mykey, bool)


@pytest.mark.parametrize('argument_spec', RAW_ARG_SPECS)
def test_raw(argument_spec):
    set_module_args({'mykey': {'foo': 'bar'}})
    module = AnsibleModule(argument_spec=argument_spec)
    mykey = module.params['mykey']
    assert isinstance(mykey, dict)
